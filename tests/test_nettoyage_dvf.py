from pathlib import Path

import duckdb
import pytest

from retrait_gonflement.data import nettoyage_dvf
from retrait_gonflement.data.commun import ErreurDonnees, charger_config

FIXTURE = Path(__file__).parent / "fixtures" / "dvf_nettoyage.csv"

# percentile_exclu = 0 : les quantiles n'excluent rien, on teste les autres règles
NETTOYAGE = {
    "surface_bati_min": 20,
    "surface_bati_max": 400,
    "valeur_fonciere_min": 15000,
    "terrain_max_m2": 10000,
    "percentile_exclu": 0,
}
CONFIG = {"nettoyage": NETTOYAGE}


@pytest.fixture
def con():
    connexion = duckdb.connect()
    yield connexion
    connexion.close()


def motifs(con) -> dict[str, str | None]:
    return dict(con.execute("SELECT id_mutation, motif FROM mutations_dvf").fetchall())


def test_config_reelle_contient_le_plafond_de_terrain():
    assert charger_config()["nettoyage"]["terrain_max_m2"] == 10000


def test_motif_de_chaque_mutation(con):
    nettoyage_dvf.nettoyer(con, [str(FIXTURE)], CONFIG)
    assert motifs(con) == {
        "2023-1": None,
        "2023-2": None,
        "2023-3": "autre_local",
        "2023-4": "plusieurs_maisons",
        "2023-5": "sans_maison",
        "2023-6": "nature",
        "2023-7": "dispositions",
        "2023-8": "valeur_absente",
        "2023-9": "sans_coordonnees",
        "2023-10": "surface_bati",
        "2023-11": "surface_bati",
        "2023-12": "valeur_basse",
        "2023-13": "terrain_max",
        "2023-14": None,
        "2023-15": "sans_maison",
    }


def test_valeur_fonciere_jamais_sommee_sur_plusieurs_parcelles(con):
    nettoyage_dvf.nettoyer(con, [str(FIXTURE)], CONFIG)
    # 2023-1 : 3 lignes sur 2 parcelles, 210000 répété sur chacune
    valeur, prix = con.execute(
        "SELECT valeur_fonciere, prix_m2 FROM ventes_maisons WHERE id_mutation = '2023-1'"
    ).fetchone()
    assert valeur == 210000
    assert prix == pytest.approx(210000 / 95)


def test_terrain_somme_des_couples_parcelle_culture_distincts(con):
    nettoyage_dvf.nettoyer(con, [str(FIXTURE)], CONFIG)
    terrains = dict(con.execute("SELECT id_mutation, surface_terrain FROM ventes_maisons").fetchall())
    assert terrains["2023-1"] == 300 + 450 + 1200
    # maison + dépendance sur la même parcelle et la même culture : 600, pas 1200
    assert terrains["2023-14"] == 600


def test_variables_conservees(con):
    nettoyage_dvf.nettoyer(con, [str(FIXTURE)], CONFIG)
    colonnes = [c[0] for c in con.execute("DESCRIBE ventes_maisons").fetchall()]
    assert colonnes == [
        "id_mutation", "date_mutation", "annee", "code_commune", "code_departement",
        "id_parcelle", "valeur_fonciere", "surface_bati", "nombre_pieces",
        "surface_terrain", "prix_m2", "longitude", "latitude",
    ]
    ligne = con.execute(
        "SELECT code_commune, annee, nombre_pieces, longitude FROM ventes_maisons "
        "WHERE id_mutation = '2023-2'"
    ).fetchone()
    assert ligne == ("31001", 2023, 3, 1.46)


def test_quantiles_par_departement_et_annee(con, tmp_path):
    # 10 ventes à 1000, 2000, … 10000 €/m² : avec p = 0,1 les bornes sont 1900 et 9100
    entete = FIXTURE.read_text(encoding="utf-8").splitlines()[0]
    lignes = [
        f"2024-{k},2024-06-01,000001,Vente,{100000 * k},47001,47,47001000A{k:04d},1,Maison,100,4,"
        f"sols,,300,0.5,44.2"
        for k in range(1, 11)
    ]
    csv = tmp_path / "dvf_2024_47.csv"
    csv.write_text("\n".join([entete, *lignes]) + "\n", encoding="utf-8")
    nettoyage_dvf.nettoyer(con, [str(csv)], {"nettoyage": {**NETTOYAGE, "percentile_exclu": 0.1}})
    assert {k for k, m in motifs(con).items() if m == "prix_m2"} == {"2024-1", "2024-10"}
    assert con.execute("SELECT count(*) FROM ventes_maisons").fetchone()[0] == 8


def test_resume_comptages_sans_donnees(con):
    nettoyage_dvf.nettoyer(con, [str(FIXTURE)], CONFIG)
    sortie = "\n".join(nettoyage_dvf.resumer(con))
    lignes = [ligne.split() for ligne in sortie.splitlines() if ligne.strip().startswith("31 ")]
    # dep, année, lignes brutes, mutations, motifs E1 à E11, retenues
    assert lignes == [
        ["31", "2023", "21", "15", "1", "1", "1", "2", "1", "1", "1", "2", "1", "1", "0", "3"]
    ]
    assert "2023-1" not in sortie and "31001" not in sortie


def test_aucun_fichier():
    with pytest.raises(ErreurDonnees):
        nettoyage_dvf.nettoyer(duckdb.connect(), [], CONFIG)
