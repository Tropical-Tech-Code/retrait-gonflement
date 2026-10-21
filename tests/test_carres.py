import json

import duckdb
import numpy as np
import pandas as pd
import pytest

from retrait_gonflement.data.commun import ErreurDonnees
from retrait_gonflement.spatial import carres

# Deux départements voisins en mètres : « 31 » à gauche, « 47 » à droite, « 82 » en haut de « 31 »
RECTANGLES = {
    "31": (0, 0, 40_000, 30_000),
    "47": (40_000, 0, 70_000, 30_000),
    "82": (0, 30_000, 40_000, 50_000),
}
EMPRISE = (0.0, 0.0, 70_000.0, 50_000.0)


def classer(xs, ys):
    sortie = np.full(len(xs), "", dtype="<U3")
    for dep, (x0, y0, x1, y1) in RECTANGLES.items():
        sortie[(xs >= x0) & (xs < x1) & (ys >= y0) & (ys < y1)] = dep
    return sortie


def centroides(effectifs: dict[str, int], graine: int = 7) -> pd.DataFrame:
    hasard = np.random.default_rng(graine)
    lignes = []
    for dep, n in effectifs.items():
        x0, y0, x1, y1 = RECTANGLES[dep]
        for k in range(n):
            lignes.append({"code_insee": f"{dep}{k:03d}", "departement": dep,
                           "x": hasard.uniform(x0, x1), "y": hasard.uniform(y0, y1)})
    return pd.DataFrame(lignes)


@pytest.fixture(scope="module")
def zone():
    donnees = centroides({"31": 60, "47": 30, "82": 20})
    maille, placement = carres.placer_zone(donnees, EMPRISE, classer)
    return donnees, maille, placement


def test_chaque_commune_a_exactement_un_carre(zone):
    donnees, _, placement = zone
    assert len(placement) == len(donnees)
    assert sorted(placement["code_insee"]) == sorted(donnees["code_insee"])


def test_jamais_deux_communes_dans_la_meme_case(zone):
    _, _, placement = zone
    assert not placement.duplicated(["i", "j"]).any()


def test_chaque_case_est_dans_le_departement_de_sa_commune(zone):
    _, _, placement = zone
    attendu = classer(placement["x"].to_numpy(), placement["y"].to_numpy())
    assert (attendu == placement["departement"].to_numpy()).all()


def test_aucune_case_voisine_d_une_case_d_un_autre_departement(zone):
    _, _, placement = zone
    departement = {(i, j): d for i, j, d in zip(placement["i"], placement["j"], placement["departement"])}
    for (i, j), dep in departement.items():
        for voisine in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            assert departement.get(voisine, dep) == dep


def test_couloir_retire_les_cases_du_departement_au_plus_grand_code():
    # 31 et 47 se touchent en x = 40 000 : les cases perdues sont celles de 47
    cases = carres.cases_par_departement(5_000.0, EMPRISE, classer)
    assert max(i for i, _ in cases["31"]) == 7        # colonne 7 = 35 000 à 40 000 m, conservée
    assert min(i for i, _ in cases["47"]) == 9        # la colonne 8 (40 000 à 45 000) est le couloir


def test_resultat_identique_a_chaque_lancement(zone):
    donnees, maille, placement = zone
    maille2, placement2 = carres.placer_zone(donnees.sample(frac=1, random_state=3), EMPRISE, classer)
    assert maille2 == maille
    pd.testing.assert_frame_equal(placement, placement2)


def test_maille_assez_fine_pour_chaque_departement_mais_pas_beaucoup_plus(zone):
    donnees, maille, _ = zone
    besoins = donnees.groupby("departement").size().to_dict()
    cases = carres.cases_par_departement(maille, EMPRISE, classer)
    assert all(len(cases[d]) >= n for d, n in besoins.items())
    # une maille deux fois plus grande ne suffit plus (la recherche ne s'arrête pas trop tôt)
    grosses = carres.cases_par_departement(2 * maille, EMPRISE, classer)
    assert any(len(grosses.get(d, [])) < n for d, n in besoins.items())


def test_une_marge_plus_grande_ne_diminue_jamais_les_cases_par_commune():
    donnees = centroides({"31": 60, "47": 30, "82": 20})
    rapports = []
    for marge in (1.0, 1.3, 1.6):
        maille, placement = carres.placer_zone(donnees, EMPRISE, classer, marge)
        cases = carres.cases_par_departement(maille, EMPRISE, classer)
        assert all(len(cases[d]) >= marge * n for d, n in donnees.groupby("departement").size().items())
        rapports.append(sum(len(c) for c in cases.values()) / len(placement))
    assert rapports == sorted(rapports)


def test_marge_plus_grande_rapproche_les_carres_des_communes():
    donnees = centroides({"31": 60, "47": 30, "82": 20})
    moyennes = [carres.placer_zone(donnees, EMPRISE, classer, m)[1]["dist"].mean() for m in (1.0, 1.6)]
    assert moyennes[1] <= moyennes[0]


def test_marge_inferieure_a_un_refusee():
    with pytest.raises(ErreurDonnees, match="marge_cases"):
        carres.placer_zone(centroides({"31": 5}), EMPRISE, classer, 0.9)


def test_statistiques_de_zone(zone):
    _, maille, placement = zone
    stats = carres.statistiques_zone(maille, EMPRISE, placement)
    assert stats["n_communes"] == len(placement)
    assert stats["distance_moyenne_km"] <= stats["distance_p95_km"] <= stats["distance_max_km"]
    assert stats["n_communes_plus_de_10_km"] == int((placement["dist"] > 10_000).sum())
    assert stats["largeur_carre_px"] == pytest.approx(760 / np.ceil(70_000 / maille), abs=0.05)


def test_commune_au_plus_pres_de_sa_case():
    # une seule commune au centre d'une case : elle y est placée
    donnees = pd.DataFrame({"code_insee": ["a"], "departement": ["31"], "x": [2_500.0], "y": [2_500.0]})
    placement = carres.affecter(donnees[["code_insee", "x", "y"]], [(0, 0), (1, 0), (0, 1)], 5_000.0, EMPRISE)
    assert (placement.loc[0, "i"], placement.loc[0, "j"]) == (0, 0)


def test_erreur_claire_si_pas_assez_de_cases():
    donnees = pd.DataFrame({"code_insee": ["a", "b"], "departement": ["31", "31"], "x": [1.0, 2.0], "y": [1.0, 2.0]})
    with pytest.raises(ErreurDonnees, match="2 communes pour 1 cases"):
        carres.affecter(donnees[["code_insee", "x", "y"]], [(0, 0)], 5_000.0, EMPRISE)


def test_maille_impossible_leve_une_erreur():
    def vide(xs, ys):
        return np.full(len(xs), "", dtype="<U3")

    with pytest.raises(ErreurDonnees):
        carres.choisir_maille(EMPRISE, vide, {"31": 5})


def test_etiquettes_a_cote_des_carres_jamais_dessus(zone):
    _, maille, placement = zone
    positions = carres.positions_etiquettes(placement, maille, EMPRISE)
    assert set(positions) == {"31", "47", "82"}
    for dep, e in positions.items():
        assert e["direction"] in carres.DIRECTIONS, dep
        recouvre = ((abs(placement["x"] - e["x"]) < e["largeur"] / 2 + maille / 2)
                    & (abs(placement["y"] - e["y"]) < e["hauteur"] / 2 + maille / 2))
        assert not recouvre.any(), dep


def test_etiquette_a_au_moins_1_5_maille_du_bord_de_son_departement(zone):
    _, maille, placement = zone
    for dep, e in carres.positions_etiquettes(placement, maille, EMPRISE).items():
        cases = placement[placement["departement"] == dep]
        distances = {
            "est": (e["x"] - e["largeur"] / 2) - (cases["x"].max() + maille / 2),
            "ouest": (cases["x"].min() - maille / 2) - (e["x"] + e["largeur"] / 2),
            "sud": (cases["y"].min() - maille / 2) - (e["y"] + e["hauteur"] / 2),
            "nord": (e["y"] - e["hauteur"] / 2) - (cases["y"].max() + maille / 2),
        }
        assert distances[e["direction"]] == pytest.approx(1.5 * maille)


def test_etiquette_premier_candidat_libre_dans_l_ordre_est_ouest_sud_nord(zone, monkeypatch):
    _, maille, placement = zone
    appels = []

    def touche(x, y, largeur, hauteur, carres_, maille_):
        appels.append((x, y))
        return len(appels) % 3 != 0          # est et ouest touchent, le 3e candidat (sud) est libre

    monkeypatch.setattr(carres, "touche_un_carre", touche)
    positions = carres.positions_etiquettes(placement, maille, EMPRISE)
    assert {e["direction"] for e in positions.values()} == {"sud"}
    assert len(appels) == 9                  # 3 départements x (est, ouest, sud) : le nord n'est pas essayé


def test_etiquette_au_centre_des_carres_si_aucun_candidat_libre(zone, monkeypatch):
    _, maille, placement = zone
    monkeypatch.setattr(carres, "touche_un_carre", lambda *args: True)
    positions = carres.positions_etiquettes(placement, maille, EMPRISE)
    assert {e["direction"] for e in positions.values()} == {"centre"}
    cases = placement[placement["departement"] == "31"]
    assert positions["31"]["x"] == pytest.approx(cases["x"].mean())


def test_emprise_contient_les_cases_et_les_etiquettes(zone):
    _, maille, placement = zone
    positions = carres.positions_etiquettes(placement, maille, EMPRISE)
    xmin, ymin, xmax, ymax = carres.emprise_avec_etiquettes(placement, maille, positions)
    assert xmin <= placement["x"].min() - maille / 2 and xmax >= placement["x"].max() + maille / 2
    for e in positions.values():
        assert xmin <= e["x"] - e["largeur"] / 2 and e["x"] + e["largeur"] / 2 <= xmax
        assert ymin <= e["y"] - e["hauteur"] / 2 and e["y"] + e["hauteur"] / 2 <= ymax


def test_wkt_carre_ferme_et_centre():
    assert carres.wkt_carre(10.0, 20.0, 4.0) == "POLYGON((8.000 18.000, 12.000 18.000, 12.000 22.000, 8.000 22.000, 8.000 18.000))"


# --- DuckDB : contours réels simplifiés, appartenance et reprojection ---

def rectangle_wgs84(lon0, lat0, lon1, lat1):
    return {"type": "Polygon", "coordinates": [[[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0]]]}


@pytest.fixture()
def connexion():
    con = duckdb.connect()
    try:
        con.execute("LOAD spatial")
    except duckdb.Error:
        pytest.skip("extension DuckDB spatial non installée")
    return con


def test_carres_issus_de_contours_simules(connexion, tmp_path):
    # 4 communes en grille 2 x 2, la moitié gauche en « 31 », la droite en « 47 » (environ 20 km de côté chacune)
    pas = 0.25
    communes = {}
    for k, (colonne, ligne) in enumerate([(0, 0), (0, 1), (1, 0), (1, 1)]):
        dep = "31" if colonne == 0 else "47"
        communes[f"{dep}{k:03d}"] = (dep, rectangle_wgs84(
            1.0 + colonne * pas, 43.0 + ligne * pas, 1.0 + (colonne + 1) * pas, 43.0 + (ligne + 1) * pas))
    fichier = tmp_path / "contours.geojson"
    fichier.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"code_insee": c}, "geometry": g} for c, (_, g) in communes.items()
    ]}), encoding="utf-8")
    carres.charger_contours(connexion, fichier, {c: d for c, (d, _) in communes.items()})
    deps = ["31", "47"]
    emprise = carres.emprise_zone(connexion, deps)
    maille, placement = carres.placer_zone(
        carres.centroides_zone(connexion, deps), emprise, carres.classeur_duckdb(connexion, deps)
    )
    assert placement["code_insee"].nunique() == 4
    entites = carres.carres_wgs84(connexion, placement, maille * 0.85, 5)
    assert sorted(e["properties"]["code_insee"] for e in entites) == sorted(communes)
    assert all(set(e["properties"]) == {"code_insee"} for e in entites)
    lon, lat = np.array(entites[0]["geometry"]["coordinates"][0]).T
    assert 0.9 < lon.min() and lon.max() < 1.6 and 42.9 < lat.min() and lat.max() < 43.6
    etiquettes = carres.etiquettes_wgs84(connexion, carres.positions_etiquettes(placement, maille, emprise), 5)
    assert set(etiquettes) == {"31", "47"}
    assert set(etiquettes["31"]) == {"lon", "lat"}
    bornes = carres.emprise_wgs84(connexion, carres.emprise_avec_etiquettes(
        placement, maille, carres.positions_etiquettes(placement, maille, emprise)), 5)
    assert bornes[0] < bornes[2] and bornes[1] < bornes[3] and 0.9 < bornes[0] < 1.6


def mercator(lon, lat):
    """(x, y) en EPSG:3857 d'après lon, lat en degrés (formule de la sphère)."""
    rayon = carres.RAYON_MERCATOR
    return rayon * np.radians(lon), rayon * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


def test_cotes_des_carres_horizontaux_et_verticaux_en_web_mercator(connexion, tmp_path):
    # loin du méridien 3° E, où la grille en Lambert-93 apparaissait tournée à l'écran
    pas = 0.2
    communes = {}
    for k, (colonne, ligne) in enumerate([(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (2, 1)]):
        dep = "31" if colonne < 2 else "47"
        communes[f"{dep}{k:03d}"] = (dep, rectangle_wgs84(
            0.0 + colonne * pas, 43.0 + ligne * pas, 0.0 + (colonne + 1) * pas, 43.0 + (ligne + 1) * pas))
    fichier = tmp_path / "contours.geojson"
    fichier.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"code_insee": c}, "geometry": g} for c, (_, g) in communes.items()
    ]}), encoding="utf-8")
    carres.charger_contours(connexion, fichier, {c: d for c, (d, _) in communes.items()})
    deps = ["31", "47"]
    emprise = carres.emprise_zone(connexion, deps)
    maille, placement = carres.placer_zone(
        carres.centroides_zone(connexion, deps), emprise, carres.classeur_duckdb(connexion, deps),
        echelle=carres.echelle_mercator,
    )
    entites = carres.carres_wgs84(connexion, placement, maille * 0.85, 7)
    assert len(entites) == 6
    for entite in entites:
        lon, lat = np.array(entite["geometry"]["coordinates"][0]).T
        x, y = mercator(lon, lat)
        a, b, c, d = np.column_stack([x, y])[:4]
        assert a[1] == pytest.approx(b[1], abs=0.5) and c[1] == pytest.approx(d[1], abs=0.5)      # côtés horizontaux
        assert b[0] == pytest.approx(c[0], abs=0.5) and d[0] == pytest.approx(a[0], abs=0.5)      # côtés verticaux
        assert b[0] - a[0] == pytest.approx(maille * 0.85, abs=0.5)                                 # carré, pas rectangle
        assert c[1] - b[1] == pytest.approx(maille * 0.85, abs=0.5)


def test_echelle_mercator_donne_des_metres_reels():
    assert float(carres.echelle_mercator(0.0)) == pytest.approx(1.0)
    _, y45 = mercator(0.0, 45.0)
    assert float(carres.echelle_mercator(y45)) == pytest.approx(np.cos(np.radians(45.0)))


def test_distances_et_maille_publiees_en_vrais_metres():
    _, y = mercator(0.0, 45.0)
    k = float(carres.echelle_mercator(y))
    donnees = pd.DataFrame({"code_insee": ["a"], "departement": ["31"], "x": [1_000.0], "y": [y]})
    emprise = (0.0, y, 8_000.0, y + 8_000.0)
    classe = lambda xs, ys: np.where(                                  # noqa: E731
        (xs >= emprise[0]) & (xs < emprise[2]) & (ys >= emprise[1]) & (ys < emprise[3]), "31", "").astype("<U3")
    maille, placement = carres.placer_zone(donnees, emprise, classe, echelle=carres.echelle_mercator)
    _, brut = carres.placer_zone(donnees, emprise, classe)
    assert placement.loc[0, "dist"] == pytest.approx(brut.loc[0, "dist"] * k, rel=1e-3)
    stats = carres.statistiques_zone(maille, emprise, placement, carres.echelle_mercator)
    k_milieu = float(carres.echelle_mercator(y + 4_000.0))           # latitude du milieu de l'emprise
    assert stats["maille_km"] == pytest.approx(maille * k_milieu / 1000, abs=0.001)


def test_contours_et_communes_differents_refuses(connexion, tmp_path):
    fichier = tmp_path / "contours.geojson"
    fichier.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"code_insee": "31001"}, "geometry": rectangle_wgs84(1, 43, 1.1, 43.1)},
    ]}), encoding="utf-8")
    with pytest.raises(ErreurDonnees, match="1 communes sans contour"):
        carres.charger_contours(connexion, fichier, {"31001": "31", "31002": "31"})
