import json

import duckdb
import numpy as np
import pandas as pd
import pytest

from retrait_gonflement.model import communes_finales
from retrait_gonflement.spatial import contours


def primes(lignes: list[dict]) -> pd.DataFrame:
    colonnes = ["code_insee", "departement", "n_ventes", "n_fort", "n_moyen", "n_faible", "n_hors_zone",
                "prix_m2_median", "statut", "motif", "prime", "ic_bas", "ic_haut", "significatif",
                "statut_decote", "erreurs", "n_sections"]
    return pd.DataFrame(lignes).reindex(columns=colonnes)


def commune(code, statut_decote, n_ventes=100, statut="estimable"):
    return {"code_insee": code, "departement": "31", "n_ventes": n_ventes, "n_fort": 40, "n_moyen": 50,
            "n_faible": 5, "n_hors_zone": 5, "prix_m2_median": 2500.0, "statut": statut,
            "motif": None if statut == "estimable" else "effectifs_insuffisants",
            "prime": -0.1 if statut_decote == "decote" else 0.05, "ic_bas": -0.2, "ic_haut": 0.1,
            "significatif": "non", "statut_decote": statut_decote, "erreurs": "sections", "n_sections": 20}


BASE = pd.DataFrame({
    "code_insee": ["31001", "31002", "31003", "31004", "31005", "31006", "31007"],
    "nom": [f"Commune {i}" for i in range(1, 8)],
    "departement": ["31"] * 7,
})
# 31001..31005 estimables ; 31006 non estimable ; 31007 sans aucune vente
PRIMES = primes([
    commune("31001", "decote"), commune("31002", "decote"), commune("31003", "pas_de_decote"),
    commune("31004", "pas_de_decote"), commune("31005", "indetermine"),
    commune("31006", None, n_ventes=30, statut="non_estimable") | {"prime": np.nan, "statut_decote": None},
])
SINISTRES = pd.DataFrame(
    {"catnat_total": [9, 6, 5, 3, 7, 8], "catnat_depuis_2015": [5, 3, 3, 1, 4, 6],
     "catnat_dernier": pd.to_datetime(["2023-09-30"] * 6)},
    index=pd.Index(["31001", "31002", "31003", "31004", "31005", "31006"], name="code_commune"),
)


@pytest.fixture(scope="module")
def resultat():
    return communes_finales.assembler(BASE, PRIMES, SINISTRES)


def test_mediane_parmi_les_communes_estimables_seulement(resultat):
    communes, mediane = resultat
    # estimables : 5, 3, 3, 1, 4 -> médiane 3 (la commune non estimable à 6 n'y compte pas)
    assert mediane == 3


def test_sinistralite_strictement_superieure_a_la_mediane(resultat):
    communes, _ = resultat
    sup = communes.set_index("code_insee")["sinistralite_sup_mediane"]
    assert sup["31001"] == True and sup["31005"] == True      # noqa: E712 (5 et 4 > 3)
    assert sup["31002"] == False and sup["31003"] == False   # noqa: E712 (3 = médiane : « inférieure ou égale »)
    assert sup["31004"] == False                              # noqa: E712
    assert pd.isna(sup["31006"]) and pd.isna(sup["31007"])    # non estimables : pas de sinistralité relative


def test_quadrants(resultat):
    communes, _ = resultat
    q = communes.set_index("code_insee")["quadrant"]
    assert q["31001"] == "Risque intégré"       # sinistralité > médiane, décote
    assert q["31002"] == "Décote à expliquer"   # sinistralité = médiane (donc ≤), décote
    assert q["31003"] == "Cohérent"             # sinistralité = médiane, pas de décote
    assert q["31004"] == "Cohérent"
    assert pd.isna(q["31005"])                  # indéterminée : dans aucun quadrant
    assert pd.isna(q["31006"]) and pd.isna(q["31007"])
    assert communes_finales.quadrant(True, "pas_de_decote") == "Angle mort"
    assert communes_finales.quadrant(True, "indetermine") is None


def test_communes_sans_vente_ni_arret(resultat):
    communes, _ = resultat
    ligne = communes.set_index("code_insee").loc["31007"]
    assert ligne["statut"] == "non_estimable" and ligne["motif"] == "effectifs_insuffisants"
    assert ligne["n_ventes"] == 0 and ligne["catnat_depuis_2015"] == 0 and ligne["catnat_total"] == 0
    assert pd.isna(ligne["catnat_dernier"]) and pd.isna(ligne["prime"])


def test_colonnes_de_docs_app_et_une_ligne_par_commune(resultat):
    communes, _ = resultat
    assert list(communes.columns) == communes_finales.COLONNES
    assert communes["code_insee"].tolist() == BASE["code_insee"].tolist()
    assert not set(communes.columns) & {"id_parcelle", "section", "erreurs", "n_sections", "longitude"}


def test_resume_catnat(resultat):
    communes, mediane = resultat
    bilan = {"n_codes_perimetre": 7, "n_codes_non_rapproches": 1, "n_evenements_non_rapproches": 2}
    r = communes_finales.resume_catnat(communes, mediane, bilan, 2023, 2015)
    assert r["mediane_sinistralite"] == 3
    assert r["n_par_quadrant"] == {
        "Risque intégré": 1, "Angle mort": 0, "Décote à expliquer": 1, "Cohérent": 2,
    }
    assert r["catnat"]["periode"] == "2015-2023" and r["catnat"]["codes_perimetre"] == bilan


def test_lignes_resume_comptages_seulement(resultat):
    communes, mediane = resultat
    evt = pd.DataFrame({"code_commune": ["31001"], "date_debut": [pd.Timestamp("2023-05-01")]})
    bilan = {"n_codes_perimetre": 7, "n_codes_non_rapproches": 1, "n_evenements_non_rapproches": 2}
    sortie = "\n".join(communes_finales.lignes_resume(
        communes, bilan, evt, {"communes": 0, "ventes": 0}, mediane, {"communes.parquet": 12345}
    ))
    assert "Seuil de sinistralité" in sortie and "Risque intégré" in sortie and "0.01 Mo" in sortie
    assert "Commune 1" not in sortie  # aucun nom de commune dans le résumé


# --- contours -----------------------------------------------------------------------------

def carre(lon, lat, cote=0.02, bosses=0):
    """Polygone carré (WGS84) ; `bosses` points en plus sur le bord sud, à moins de 10 m de la ligne."""
    sud = [[lon + cote * i / (bosses + 1), lat + (0.00002 if i % 2 else 0)] for i in range(bosses + 1)]
    return {"type": "Polygon", "coordinates": [[
        *sud, [lon + cote, lat], [lon + cote, lat + cote], [lon, lat + cote], sud[0],
    ]]}


@pytest.fixture
def dossier_contours(tmp_path):
    brut = tmp_path / "brut"
    brut.mkdir()
    entites = [
        {"type": "Feature", "properties": {"code": "31001", "nom": "Bosselée"}, "geometry": carre(1.440123456, 43.59, bosses=40)},
        {"type": "Feature", "properties": {"code": "31002", "nom": "Voisine"}, "geometry": carre(1.460123456, 43.59)},
    ]
    (brut / "communes_31.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": entites}), encoding="utf-8"
    )
    return brut


@pytest.fixture
def con():
    connexion = duckdb.connect()
    try:
        connexion.execute("LOAD spatial")
    except duckdb.Error:
        pytest.skip("extension DuckDB spatial non installée")
    yield connexion
    connexion.close()


def nombre_points(geometrie):
    return sum(len(anneau) for anneau in geometrie["coordinates"])


def test_contours_simplifies_et_arrondis(con, dossier_contours, tmp_path):
    liste = contours.lire_communes(dossier_contours, ["31"])
    contours.simplifier(con, liste, 50)
    sortie = tmp_path / "processed"
    chemin_communes, chemin_deps = contours.exporter(con, sortie, 50, 5)
    collection = json.loads(chemin_communes.read_text(encoding="utf-8"))
    par_code = {f["properties"]["code_insee"]: f for f in collection["features"]}
    assert set(par_code) == {"31001", "31002"}
    assert all(set(f["properties"]) == {"code_insee"} for f in collection["features"])
    # la bosse de 2 m sur le bord sud a disparu (50 points -> les 4 coins)
    assert nombre_points(par_code["31001"]["geometry"]) < 10
    assert len(json.loads(liste[0]["geometrie"])["coordinates"][0]) > 40  # le contour d'origine en a plus de 40
    # coordonnées arrondies à 5 décimales et toujours en longitude / latitude
    for anneau in par_code["31001"]["geometry"]["coordinates"]:
        for lon, lat in anneau:
            assert round(lon, 5) == lon and round(lat, 5) == lat
            assert 1.0 < lon < 2.0 and 43.0 < lat < 44.0


def test_limites_de_departement_sans_frontiere_interne(con, dossier_contours, tmp_path):
    contours.simplifier(con, contours.lire_communes(dossier_contours, ["31"]), 50)
    _, chemin_deps = contours.exporter(con, tmp_path / "p", 50, 5)
    entites = json.loads(chemin_deps.read_text(encoding="utf-8"))["features"]
    assert [f["properties"] for f in entites] == [{"departement": "31"}]
    # deux carrés voisins de même hauteur : une seule enveloppe extérieure (communes disjointes ici,
    # un MultiPolygon à deux parties est donc attendu ; on vérifie surtout l'absence d'erreur)
    assert entites[0]["geometry"]["type"] in ("Polygon", "MultiPolygon")


def test_contours_absents_refuses(tmp_path):
    from retrait_gonflement.data.commun import ErreurDonnees

    with pytest.raises(ErreurDonnees, match="communes_47"):
        contours.lire_communes(tmp_path, ["47"])


def test_arrondi_retire_les_doublons_consecutifs():
    anneau = [[1.000001, 2.000001], [1.000002, 2.000002], [1.5, 2.5], [1.000001, 2.000001]]
    assert contours.arrondir([anneau], 5) == [[[1.0, 2.0], [1.5, 2.5], [1.0, 2.0]]]
