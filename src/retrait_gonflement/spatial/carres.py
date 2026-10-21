"""Carte en carrés : un carré par commune, sur une grille régulière par zone (docs/app.md).

À partir de contours.geojson et communes.parquet, le pipeline place chaque commune dans une
case de la grille de sa zone, au plus près de son centre, département par département. Une
rangée de cases vides sépare deux départements voisins. Écrit data/processed/carres.geojson
(propriété `code_insee` seule) et complète resume_global.json (clé `carres`). La grille est
construite en Web Mercator (EPSG:3857), la projection de l'affichage : les côtés des carrés
sont alors horizontaux et verticaux à l'écran (en Lambert-93, le nord n'est le vrai nord qu'au
méridien 3° E, et les carrés du Sud-Ouest apparaissaient tournés d'un à deux degrés). Les
distances et la maille publiées sont en vrais mètres : une unité Mercator vaut cos(latitude)
mètres réels. Seuls les carrés dessinés sont reprojetés en WGS84.

    uv run python -m retrait_gonflement.spatial.carres
"""

import argparse
import json
import math
from pathlib import Path
from typing import Callable

import duckdb
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist

from retrait_gonflement.data.commun import RACINE, ErreurDonnees, charger_config
from retrait_gonflement.model.modele_global import CHEMIN_RESUME, ecrire_resume
from retrait_gonflement.spatial import contours
from retrait_gonflement.spatial.contours import LAMBERT93, WGS84

DOSSIER_PROCESSED = RACINE / "data" / "processed"
MERCATOR = "EPSG:3857"
RAYON_MERCATOR = 6_378_137.0   # rayon de la sphère de Web Mercator (m)
TAMPON_M = 100      # unités Mercator (environ 75 m réels) : referme les interstices entre contours simplifiés (50 m de tolérance)
PRECISION_M = 1.0   # la dichotomie s'arrête quand la maille est connue à 1 m près
SEUIL_ECART_M = 10_000   # écart commune - carré au-delà duquel on compte la commune
LARGEUR_ECRAN_PX = 760   # largeur de la carte pour juger la lisibilité d'un carré
ESSAIS_MAX = 12    # encadrement de la maille : au plus 2^12 fois plus petite ou plus grande

# classer(xs, ys) -> tableau de codes de département (texte), "" pour une case hors département
Classeur = Callable[[np.ndarray, np.ndarray], np.ndarray]


def echelle_mercator(y):
    """Mètres réels par unité Mercator à l'ordonnée `y` (cos de la latitude), nombre ou tableau."""
    return np.cos(2 * np.arctan(np.exp(np.asarray(y) / RAYON_MERCATOR)) - math.pi / 2)


def centres_grille(maille: float, emprise: tuple[float, float, float, float]) -> tuple[np.ndarray, np.ndarray]:
    """Coordonnées (x, y) des centres de cases, tableaux de forme (lignes, colonnes).

    La grille part du coin sud-ouest de l'emprise (xmin, ymin, xmax, ymax) ; la case (i, j)
    est la colonne i, la ligne j.
    """
    xmin, ymin, xmax, ymax = emprise
    nx, ny = math.ceil((xmax - xmin) / maille), math.ceil((ymax - ymin) / maille)
    xs = xmin + (np.arange(nx) + 0.5) * maille
    ys = ymin + (np.arange(ny) + 0.5) * maille
    return np.meshgrid(xs, ys)


def etiquettes_cases(maille: float, emprise: tuple[float, float, float, float], classer: Classeur) -> np.ndarray:
    """Département de chaque case (forme lignes × colonnes), "" si hors département.

    Les cases voisines (4 voisines) de deux départements différents : on retire celle du
    département dont le code est le plus grand, ce qui laisse un couloir d'une seule rangée.
    """
    gx, gy = centres_grille(maille, emprise)
    etiquettes = classer(gx.ravel(), gy.ravel()).reshape(gx.shape)
    retirer = np.zeros(etiquettes.shape, dtype=bool)
    for axe in (0, 1):
        a = np.take(etiquettes, range(etiquettes.shape[axe] - 1), axis=axe)
        b = np.take(etiquettes, range(1, etiquettes.shape[axe]), axis=axe)
        differents = (a != "") & (b != "") & (a != b)
        a_retire, b_retire = differents & (a > b), differents & (b > a)
        premiers = [slice(None)] * 2
        derniers = [slice(None)] * 2
        premiers[axe], derniers[axe] = slice(0, -1), slice(1, None)
        retirer[tuple(premiers)] |= a_retire
        retirer[tuple(derniers)] |= b_retire
    return np.where(retirer, "", etiquettes)


def cases_par_departement(
    maille: float, emprise: tuple[float, float, float, float], classer: Classeur
) -> dict[str, list[tuple[int, int]]]:
    """Cases (colonne, ligne) disponibles pour chaque département, triées."""
    etiquettes = etiquettes_cases(maille, emprise, classer)
    lignes, colonnes = np.nonzero(etiquettes != "")
    cases: dict[str, list[tuple[int, int]]] = {}
    for j, i in zip(lignes, colonnes):
        cases.setdefault(str(etiquettes[j, i]), []).append((int(i), int(j)))
    return {dep: sorted(c) for dep, c in cases.items()}


def choisir_maille(
    emprise: tuple[float, float, float, float], classer: Classeur, besoins: dict[str, int]
) -> tuple[float, dict[str, list[tuple[int, int]]]]:
    """Plus grande maille (à PRECISION_M près) qui laisse au moins `besoins` cases par département.

    Encadrement par multiplication ou division par 2 depuis une maille de départ, puis
    dichotomie. Le résultat renvoyé a toujours été vérifié (la faisabilité n'est pas
    strictement monotone en la maille, mais la maille retenue est testée).
    """
    memoire: dict[float, dict[str, list[tuple[int, int]]] | None] = {}

    def essayer(maille: float):
        if maille not in memoire:
            cases = cases_par_departement(maille, emprise, classer)
            memoire[maille] = cases if all(len(cases.get(d, [])) >= n for d, n in besoins.items()) else None
        return memoire[maille]

    xmin, ymin, xmax, ymax = emprise
    depart = math.sqrt((xmax - xmin) * (ymax - ymin) / sum(besoins.values()))
    if essayer(depart):
        bon, mauvais = depart, depart * 2
        for _ in range(ESSAIS_MAX):
            if not essayer(mauvais):
                break
            bon, mauvais = mauvais, mauvais * 2
        else:
            raise ErreurDonnees("aucune maille trop grande trouvée : emprise ou besoins incohérents")
    else:
        mauvais, bon = depart, depart / 2
        for _ in range(ESSAIS_MAX):
            if essayer(bon):
                break
            mauvais, bon = bon, bon / 2
        else:
            raise ErreurDonnees("aucune maille ne laisse assez de cases : départements trop morcelés ?")
    while mauvais - bon > PRECISION_M:
        milieu = (bon + mauvais) / 2
        if essayer(milieu):
            bon = milieu
        else:
            mauvais = milieu
    return bon, memoire[bon]


def affecter(
    centroides: pd.DataFrame,
    cases: list[tuple[int, int]],
    maille: float,
    emprise: tuple[float, float, float, float],
) -> pd.DataFrame:
    """Une case par commune en minimisant la somme des distances au carré.

    `centroides` : colonnes code_insee, x, y (Web Mercator). Résultat : code_insee, i, j, x, y
    (centre de la case), trié par code_insee. Communes et cases sont triées avant l'affectation
    pour que le résultat soit identique à chaque lancement.
    """
    communes = centroides.sort_values("code_insee").reset_index(drop=True)
    cases = sorted(cases)
    if len(cases) < len(communes):
        raise ErreurDonnees(f"{len(communes)} communes pour {len(cases)} cases")
    xmin, ymin, _, _ = emprise
    cx = np.array([xmin + (i + 0.5) * maille for i, _ in cases])
    cy = np.array([ymin + (j + 0.5) * maille for _, j in cases])
    cout = cdist(communes[["x", "y"]].to_numpy(), np.column_stack([cx, cy]), metric="sqeuclidean")
    lignes, choix = linear_sum_assignment(cout)
    return pd.DataFrame({
        "code_insee": communes["code_insee"].to_numpy()[lignes],
        "i": [cases[k][0] for k in choix],
        "j": [cases[k][1] for k in choix],
        "x": cx[choix],
        "y": cy[choix],
    })


def placer_zone(
    centroides: pd.DataFrame, emprise: tuple[float, float, float, float], classer: Classeur, marge: float = 1.0,
    echelle: Callable[[np.ndarray], np.ndarray] | None = None,
) -> tuple[float, pd.DataFrame]:
    """Maille et placement de toutes les communes d'une zone.

    `centroides` : code_insee, departement, x, y. `marge` : cases exigées par département =
    marge × communes (arrondi au-dessus). `echelle(y)` : mètres réels par unité de la grille à
    l'ordonnée y (`echelle_mercator`) ; absente, la grille est déjà en mètres. Résultat : maille
    (unités de la grille), puis code_insee, departement, i, j, x, y, dist (m réels, du centre de
    la commune au centre du carré).
    """
    if marge < 1:
        raise ErreurDonnees(f"marge_cases = {marge} : il faut au moins une case par commune (1.0)")
    besoins = {dep: math.ceil(marge * n) for dep, n in centroides.groupby("departement").size().items()}
    maille, cases = choisir_maille(emprise, classer, besoins)
    morceaux = []
    for dep, communes in centroides.groupby("departement"):
        place = affecter(communes[["code_insee", "x", "y"]], cases[dep], maille, emprise)
        place["departement"] = dep
        morceaux.append(place.merge(communes[["code_insee", "x", "y"]], on="code_insee", suffixes=("", "_commune")))
    resultat = pd.concat(morceaux, ignore_index=True).sort_values("code_insee").reset_index(drop=True)
    facteur = echelle(resultat["y_commune"].to_numpy()) if echelle else 1.0
    resultat["dist"] = np.hypot(resultat["x"] - resultat["x_commune"], resultat["y"] - resultat["y_commune"]) * facteur
    return maille, resultat.drop(columns=["x_commune", "y_commune"])


# --- Étiquettes des départements : à côté des carrés, jamais dessus ---

# Même texte que l'app (textes.NOMS_DEPARTEMENTS, un test les compare) : sert à estimer la largeur du nom
NOMS_DEPARTEMENTS = {"31": "Haute-Garonne", "47": "Lot-et-Garonne", "77": "Seine-et-Marne", "82": "Tarn-et-Garonne"}
PX_PAR_CARACTERE = 7.6      # police de 11 px en capitales, graisse 600 (estimation)
MARGE_TEXTE_PX = 12         # remplissage du fond blanc, de chaque côté
HAUTEUR_TEXTE_PX = 20
SECURITE_LARGEUR = 1.2      # la zone affichée peut être un peu plus large que celle des carrés
DISTANCE_ETIQUETTE = 1.5    # mailles entre le bord des carrés du département et le texte
DIRECTIONS = ("est", "ouest", "sud", "nord")


def texte_etiquette(departement: str) -> str:
    return f"{NOMS_DEPARTEMENTS.get(departement, departement)} · {departement}".upper()


def dimensions_etiquette(departement: str, maille: float, emprise: tuple[float, float, float, float]) -> tuple[float, float]:
    """Largeur et hauteur estimées du texte, en mètres (carte de LARGEUR_ECRAN_PX px de large)."""
    xmin, _, xmax, _ = emprise
    metres_par_px = maille * math.ceil((xmax - xmin) / maille) / LARGEUR_ECRAN_PX
    largeur_px = len(texte_etiquette(departement)) * PX_PAR_CARACTERE + 2 * MARGE_TEXTE_PX
    return largeur_px * metres_par_px * SECURITE_LARGEUR, HAUTEUR_TEXTE_PX * metres_par_px


def touche_un_carre(x: float, y: float, largeur: float, hauteur: float, carres: pd.DataFrame, maille: float) -> bool:
    """Le rectangle de texte centré en (x, y) touche-t-il une case occupée ?"""
    return bool(
        ((np.abs(carres["x"] - x) < largeur / 2 + maille / 2) & (np.abs(carres["y"] - y) < hauteur / 2 + maille / 2)).any()
    )


def positions_etiquettes(placement: pd.DataFrame, maille: float, emprise: tuple[float, float, float, float]) -> dict:
    """Centre du texte de chaque département : à l'est, l'ouest, le sud puis le nord de ses carrés.

    Le premier candidat (à DISTANCE_ETIQUETTE mailles du bord) dont le rectangle de texte ne touche
    aucun carré de la zone est retenu ; sinon, centre des carrés (direction « centre »).
    """
    resultat = {}
    for dep, carres_dep in placement.groupby("departement"):
        largeur, hauteur = dimensions_etiquette(dep, maille, emprise)
        bord = maille / 2 + DISTANCE_ETIQUETTE * maille
        x0, y0 = float(carres_dep["x"].mean()), float(carres_dep["y"].mean())
        candidats = {
            "est": (carres_dep["x"].max() + bord + largeur / 2, y0),
            "ouest": (carres_dep["x"].min() - bord - largeur / 2, y0),
            "sud": (x0, carres_dep["y"].min() - bord - hauteur / 2),
            "nord": (x0, carres_dep["y"].max() + bord + hauteur / 2),
        }
        choix = next((d for d in DIRECTIONS if not touche_un_carre(*candidats[d], largeur, hauteur, placement, maille)), None)
        x, y = candidats[choix] if choix else (x0, y0)
        resultat[dep] = {"x": float(x), "y": float(y), "direction": choix or "centre",
                         "largeur": float(largeur), "hauteur": float(hauteur)}
    return resultat


def emprise_avec_etiquettes(placement: pd.DataFrame, maille: float, etiquettes: dict) -> tuple[float, float, float, float]:
    """Rectangle (Web Mercator) qui contient les cases occupées et les textes des étiquettes."""
    xs = [placement["x"].min() - maille / 2, placement["x"].max() + maille / 2]
    ys = [placement["y"].min() - maille / 2, placement["y"].max() + maille / 2]
    for e in etiquettes.values():
        xs += [e["x"] - e["largeur"] / 2, e["x"] + e["largeur"] / 2]
        ys += [e["y"] - e["hauteur"] / 2, e["y"] + e["hauteur"] / 2]
    return min(xs), min(ys), max(xs), max(ys)


def wkt_carre(x: float, y: float, cote: float) -> str:
    """Polygone (WKT) d'un carré de côté `cote` centré en (x, y)."""
    d = cote / 2
    sommets = [(x - d, y - d), (x + d, y - d), (x + d, y + d), (x - d, y + d), (x - d, y - d)]
    return "POLYGON((" + ", ".join(f"{px:.3f} {py:.3f}" for px, py in sommets) + "))"


# --- DuckDB : contours en Web Mercator, appartenance à un département, reprojection ---

def charger_contours(
    con: duckdb.DuckDBPyConnection, fichier_contours: Path, departement_de: dict[str, str]
) -> None:
    """Table contours_mercator (code, departement, geom) à partir de contours.geojson, sans simplification."""
    entites = json.loads(fichier_contours.read_text(encoding="utf-8"))["features"]
    codes = {e["properties"]["code_insee"] for e in entites}
    if codes != set(departement_de):
        raise ErreurDonnees(
            f"contours et communes différents : {len(codes - set(departement_de))} contours sans commune, "
            f"{len(set(departement_de) - codes)} communes sans contour"
        )
    liste = [
        {"code": e["properties"]["code_insee"], "departement": departement_de[e["properties"]["code_insee"]],
         "geometrie": json.dumps(e["geometry"])}
        for e in entites
    ]
    contours.simplifier(con, liste, 0.0)       # table contours_l93, tolérance nulle
    con.execute(
        f"CREATE OR REPLACE TABLE contours_mercator AS SELECT code, departement, "
        f"ST_Transform(geom, '{LAMBERT93}', '{MERCATOR}', always_xy := true) AS geom FROM contours_l93"
    )


def emprise_zone(con: duckdb.DuckDBPyConnection, departements: list[str]) -> tuple[float, float, float, float]:
    marques = ",".join("?" * len(departements))
    ligne = con.execute(
        f"SELECT min(ST_XMin(geom)), min(ST_YMin(geom)), max(ST_XMax(geom)), max(ST_YMax(geom)) "
        f"FROM contours_mercator WHERE departement IN ({marques})",
        departements,
    ).fetchone()
    return tuple(float(v) for v in ligne)


def centroides_zone(con: duckdb.DuckDBPyConnection, departements: list[str]) -> pd.DataFrame:
    marques = ",".join("?" * len(departements))
    return con.execute(
        f"SELECT code AS code_insee, departement, ST_X(ST_Centroid(geom)) AS x, ST_Y(ST_Centroid(geom)) AS y "
        f"FROM contours_mercator WHERE departement IN ({marques}) ORDER BY code",
        departements,
    ).df()


def classeur_duckdb(con: duckdb.DuckDBPyConnection, departements: list[str]) -> Classeur:
    """Département d'un point : celui dont le contour (agrandi de TAMPON_M) le contient, le plus proche d'abord."""
    marques = ",".join("?" * len(departements))
    con.execute(
        f"CREATE OR REPLACE TABLE zone_departements AS SELECT departement, ST_Union_Agg(geom) AS geom, "
        f"ST_Buffer(ST_Union_Agg(geom), {float(TAMPON_M)}) AS tampon FROM contours_mercator "
        f"WHERE departement IN ({marques}) GROUP BY departement",
        departements,
    )

    def classer(xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        points = pd.DataFrame({"id": np.arange(len(xs)), "x": xs, "y": ys})
        con.register("points_grille", points)
        try:
            trouves = con.execute(
                "SELECT p.id, d.departement, ST_Distance(d.geom, ST_Point(p.x, p.y)) AS dist "
                "FROM points_grille p JOIN zone_departements d ON ST_Contains(d.tampon, ST_Point(p.x, p.y))"
            ).df()
        finally:
            con.unregister("points_grille")
        trouves = trouves.sort_values(["id", "dist", "departement"]).drop_duplicates("id")
        sortie = np.full(len(xs), "", dtype="<U3")
        sortie[trouves["id"].to_numpy()] = trouves["departement"].to_numpy()
        return sortie

    return classer


def carres_wgs84(con: duckdb.DuckDBPyConnection, placement: pd.DataFrame, cote: float, decimales: int) -> list[dict]:
    """Entités GeoJSON (propriété code_insee) des carrés (côté `cote` en unités Mercator), reprojetés en WGS84 et arrondis."""
    con.execute("CREATE OR REPLACE TABLE carres_mercator (code VARCHAR, wkt VARCHAR)")
    con.executemany(
        "INSERT INTO carres_mercator VALUES (?, ?)",
        [(c, wkt_carre(x, y, cote)) for c, x, y in zip(placement["code_insee"], placement["x"], placement["y"])],
    )
    carres = contours._en_wgs84(
        con, "SELECT code AS cle, ST_GeomFromText(wkt) AS g FROM carres_mercator", decimales, MERCATOR
    )
    return [{"type": "Feature", "properties": {"code_insee": code}, "geometry": g} for code, g in carres]


def point_wgs84(con: duckdb.DuckDBPyConnection, x: float, y: float, decimales: int) -> tuple[float, float]:
    """(lon, lat) arrondis d'un point en Web Mercator."""
    lon, lat = con.execute(
        f"SELECT ST_X(p), ST_Y(p) FROM (SELECT ST_Transform(ST_Point(?, ?), '{MERCATOR}', '{WGS84}', "
        "always_xy := true) AS p)",
        [float(x), float(y)],
    ).fetchone()
    return round(lon, decimales), round(lat, decimales)


def etiquettes_wgs84(con: duckdb.DuckDBPyConnection, etiquettes: dict, decimales: int) -> dict[str, dict]:
    """Position (lon, lat) du centre du texte de chaque département, en WGS84."""
    return {
        dep: dict(zip(("lon", "lat"), point_wgs84(con, e["x"], e["y"], decimales)))
        for dep, e in sorted(etiquettes.items())
    }


def emprise_wgs84(con: duckdb.DuckDBPyConnection, emprise: tuple[float, float, float, float], decimales: int) -> list[float]:
    """[lon_min, lat_min, lon_max, lat_max] du rectangle, d'après ses quatre coins."""
    xmin, ymin, xmax, ymax = emprise
    coins = [point_wgs84(con, x, y, decimales) for x in (xmin, xmax) for y in (ymin, ymax)]
    lons, lats = [c[0] for c in coins], [c[1] for c in coins]
    return [min(lons), min(lats), max(lons), max(lats)]


def statistiques_zone(
    maille: float, emprise: tuple[float, float, float, float], placement: pd.DataFrame,
    echelle: Callable[[np.ndarray], np.ndarray] | None = None,
) -> dict:
    """Agrégats d'une zone : maille (km réels, à la latitude du milieu), écarts commune - carré (km) et largeur d'un carré à l'écran."""
    xmin, ymin, xmax, ymax = emprise
    colonnes = math.ceil((xmax - xmin) / maille)
    facteur = float(echelle((ymin + ymax) / 2)) if echelle else 1.0
    return {
        "maille_km": round(maille * facteur / 1000, 3),
        "n_communes": int(len(placement)),
        "distance_moyenne_km": round(float(placement["dist"].mean()) / 1000, 3),
        "distance_p95_km": round(float(placement["dist"].quantile(0.95)) / 1000, 3),
        "distance_max_km": round(float(placement["dist"].max()) / 1000, 3),
        "n_communes_plus_de_10_km": int((placement["dist"] > SEUIL_ECART_M).sum()),
        "largeur_carre_px": round(LARGEUR_ECRAN_PX / colonnes, 1),
    }


def lignes_resume(zones: dict[str, dict], marge: float) -> list[str]:
    """Agrégats seulement : maille, communes, écarts (km), largeur d'un carré pour une zone de 760 px."""
    return [
        f"{nom} (marge {marge:g}) : maille {z['maille_km']:.2f} km, {z['n_communes']} communes, "
        f"écart centre de la commune - carré : {z['distance_moyenne_km']:.2f} km en moyenne, "
        f"{z['distance_p95_km']:.2f} km au 95e centile, {z['distance_max_km']:.2f} km au maximum, "
        f"{z['n_communes_plus_de_10_km']} communes à plus de 10 km ; "
        f"carré de {z['largeur_carre_px']:.1f} px dans une zone de {LARGEUR_ECRAN_PX} px ; "
        f"étiquettes : {', '.join(f'{dep} {d}' for dep, d in z['directions_etiquettes'].items())}"
        for nom, z in zones.items()
    ]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Carrés de la carte : un par commune, une grille par zone")
    parser.add_argument("--sortie", type=Path, default=DOSSIER_PROCESSED)
    parser.add_argument("--resume", type=Path, default=CHEMIN_RESUME)
    parser.add_argument("--marge", type=float, default=None,
                        help="cases exigées = marge × communes (défaut : marge_cases de la config)")
    args = parser.parse_args(argv)

    config = charger_config()
    marge = float(args.marge if args.marge is not None else config["carte"]["marge_cases"])
    zones_config = config["carte"]["zones"]
    cote_relatif = float(config["carte"]["taille_carre"])
    decimales = int(config["carte"]["decimales_coordonnees"])
    try:
        classes = [d for deps in zones_config.values() for d in deps]
        if sorted(classes) != sorted(config["perimetre"]["departements"]):
            raise ErreurDonnees("les zones de [carte.zones] doivent couvrir exactement les départements du périmètre")
        communes = pd.read_parquet(args.sortie / "communes.parquet", columns=["code_insee", "departement"])
        con = duckdb.connect()
        con.execute("LOAD spatial")
        charger_contours(con, args.sortie / "contours.geojson", dict(zip(communes["code_insee"], communes["departement"])))

        resume_zones, placements, etiquettes = {}, [], {}
        for nom, departements in zones_config.items():
            emprise = emprise_zone(con, departements)
            maille, placement = placer_zone(
                centroides_zone(con, departements), emprise, classeur_duckdb(con, departements), marge,
                echelle_mercator,
            )
            positions = positions_etiquettes(placement, maille, emprise)
            placements.append((maille, placement))
            resume_zones[nom] = (
                {"departements": departements}
                | statistiques_zone(maille, emprise, placement, echelle_mercator)
                | {
                    "emprise": emprise_wgs84(con, emprise_avec_etiquettes(placement, maille, positions), decimales),
                    "directions_etiquettes": {dep: e["direction"] for dep, e in sorted(positions.items())},
                }
            )
            etiquettes.update(etiquettes_wgs84(con, positions, decimales))
        entites = []
        for maille, placement in placements:
            entites += carres_wgs84(con, placement, maille * cote_relatif, decimales)
        con.close()
    except (ErreurDonnees, FileNotFoundError, duckdb.Error) as e:
        raise SystemExit(f"Erreur : {e}") from e

    entites.sort(key=lambda e: e["properties"]["code_insee"])
    contours.ecrire_geojson(args.sortie / "carres.geojson", entites)
    ecrire_resume(args.resume, {"carres": {
        "marge_cases": marge, "zones": resume_zones, "etiquettes": dict(sorted(etiquettes.items())),
    }})
    print("\n".join(lignes_resume(resume_zones, marge)))


if __name__ == "__main__":
    main()
