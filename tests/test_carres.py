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
    etiquettes = carres.etiquettes_wgs84(connexion, placement, 5)
    assert set(etiquettes) == {"31", "47"} and etiquettes["31"]["lon"] < etiquettes["47"]["lon"]


def test_contours_et_communes_differents_refuses(connexion, tmp_path):
    fichier = tmp_path / "contours.geojson"
    fichier.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"code_insee": "31001"}, "geometry": rectangle_wgs84(1, 43, 1.1, 43.1)},
    ]}), encoding="utf-8")
    with pytest.raises(ErreurDonnees, match="1 communes sans contour"):
        carres.charger_contours(connexion, fichier, {"31001": "31", "31002": "31"})
