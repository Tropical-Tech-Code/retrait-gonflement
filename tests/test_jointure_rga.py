import zipfile

import duckdb
import pytest

from retrait_gonflement.data.commun import ErreurDonnees
from retrait_gonflement.spatial import jointure_rga

CONFIG = {
    "perimetre": {"departements": ["31"]},
    "sources": {
        "rga_2020": {"fichier": "rga20_{departement}.zip"},
        "rga_2026": {"fichier": "rga26_{departement}.zip"},
    },
    "nettoyage": {"distance_limite_zone_m": 50},
    "estimation": {"min_ventes_fort": 2, "min_ventes_reference": 2, "min_ventes_total": 4},
}

# Carré de 1 km en Lambert 93 autour du centre de Toulouse (574317 ; 6279622)
CARRE_TOULOUSE = "POLYGON((574000 6279000, 575000 6279000, 575000 6280000, 574000 6280000, 574000 6279000))"
CARRE_47 = "POLYGON((600000 6300000, 601000 6300000, 601000 6301000, 600000 6301000, 600000 6300000))"


@pytest.fixture
def con():
    connexion = duckdb.connect()
    try:
        connexion.execute("LOAD spatial")
    except duckdb.Error:
        pytest.skip("extension DuckDB spatial non installée")
    yield connexion
    connexion.close()


def creer_polygones(con, lignes):
    con.execute(
        "CREATE TABLE rga_polygones (millesime VARCHAR, departement VARCHAR, niveau INTEGER, "
        "geom GEOMETRY, limite GEOMETRY)"
    )
    for millesime, dep, niveau, wkt in lignes:
        con.execute(
            "INSERT INTO rga_polygones VALUES (?, ?, ?, ST_GeomFromText(?), "
            "ST_Boundary(ST_GeomFromText(?)))",
            [millesime, dep, niveau, wkt, wkt],
        )


def creer_ventes(con, ventes):
    """ventes : (id, dep, x, y) en Lambert 93 ; longitude et latitude sont déduites."""
    con.execute(
        "CREATE TABLE ventes_maisons (id_mutation VARCHAR, code_commune VARCHAR, "
        "code_departement VARCHAR, annee INTEGER, longitude DOUBLE, latitude DOUBLE)"
    )
    for identifiant, dep, x, y in ventes:
        con.execute(
            "INSERT INTO ventes_maisons SELECT ?, '31555', ?, 2023, ST_X(p), ST_Y(p) FROM "
            "(SELECT ST_Transform(ST_Point(?, ?), 'EPSG:2154', 'EPSG:4326', always_xy := true) AS p)",
            [identifiant, dep, x, y],
        )


def test_point_connu_de_toulouse_en_lambert_93(con):
    # lon/lat de Toulouse : si l'ordre des axes était inversé, on sortirait de cette boîte
    x, y = con.execute(
        "SELECT ST_X(p), ST_Y(p) FROM (SELECT ST_Transform(ST_Point(1.4437, 43.6045), "
        "'EPSG:4326', 'EPSG:2154', always_xy := true) AS p)"
    ).fetchone()
    assert 568_000 < x < 581_000
    assert 6_273_000 < y < 6_286_000


def test_jointure_niveaux_et_controles(con):
    creer_polygones(con, [
        ("2020", "31", 3, CARRE_TOULOUSE),
        ("2026", "31", 2, CARRE_TOULOUSE),
        ("2020", "47", 2, CARRE_47),
    ])
    creer_ventes(con, [
        ("centre", "31", 574500, 6279500),     # dans le carré, loin des bords
        ("bord", "31", 574020, 6279500),       # dans le carré, à 20 m du bord
        ("dehors", "31", 570000, 6270000),     # loin de tout polygone
        ("pres", "31", 574500, 6280030),       # hors du carré, à 30 m
        ("autre_dep", "31", 600500, 6300500),  # dans un polygone du 47
    ])
    jointure_rga.joindre(con, CONFIG)
    lignes = {
        r[0]: r[1:]
        for r in con.execute(
            "SELECT id_mutation, rga_2020, rga_2026, proche_limite_2020, hors_dep_2020, multi_2020 "
            "FROM ventes_rga"
        ).fetchall()
    }
    assert lignes["centre"] == (3, 2, False, False, False)
    assert lignes["bord"] == (3, 2, True, False, False)
    assert lignes["dehors"] == (0, 0, False, False, False)
    assert lignes["pres"] == (0, 0, True, False, False)
    assert lignes["autre_dep"] == (0, 0, False, True, False)
    assert con.execute("SELECT count(*) FROM ventes_rga").fetchone()[0] == 5


def test_charger_polygones_depuis_une_archive(con, tmp_path):
    con.execute(
        "CREATE TABLE source AS SELECT 3.0 AS niveau, ST_GeomFromText(?) AS geom", [CARRE_TOULOUSE]
    )
    for millesime, prefixe in (("2020", "rga20"), ("2026", "rga26")):
        dossier = tmp_path / millesime
        dossier.mkdir()
        shp = tmp_path / f"{prefixe}.shp"
        con.execute(
            f"COPY source TO '{shp}' (FORMAT GDAL, DRIVER 'ESRI Shapefile', SRS 'EPSG:2154')"
        )
        with zipfile.ZipFile(dossier / f"{prefixe}_31.zip", "w") as z:
            for fichier in tmp_path.glob(f"{prefixe}.*"):
                z.write(fichier, fichier.name)
    jointure_rga.charger_polygones(con, CONFIG, tmp_path)
    assert con.execute(
        "SELECT millesime, departement, niveau, count(*) FROM rga_polygones GROUP BY ALL ORDER BY 1"
    ).fetchall() == [("2020", "31", 3, 1), ("2026", "31", 3, 1)]


def test_niveau_inattendu_refuse(con, tmp_path):
    con.execute("CREATE TABLE source AS SELECT 7.0 AS niveau, ST_GeomFromText(?) AS geom", [CARRE_TOULOUSE])
    for millesime, prefixe in (("2020", "rga20"), ("2026", "rga26")):
        (tmp_path / millesime).mkdir()
        con.execute(f"COPY source TO '{tmp_path / prefixe}.shp' (FORMAT GDAL, DRIVER 'ESRI Shapefile')")
        with zipfile.ZipFile(tmp_path / millesime / f"{prefixe}_31.zip", "w") as z:
            for fichier in tmp_path.glob(f"{prefixe}.*"):
                z.write(fichier, fichier.name)
    with pytest.raises(ErreurDonnees, match="niveaux RGA inattendus"):
        jointure_rga.charger_polygones(con, CONFIG, tmp_path)


def test_comptage_communes_mixtes(con):
    con.execute("CREATE TABLE ventes_rga (code_departement VARCHAR, code_commune VARCHAR, rga_2020 INTEGER)")
    communes = {
        "A": [3, 3, 2, 2],   # mixte, passe les seuils
        "B": [3, 3, 0, 0],   # mixte, passe les seuils : le niveau 0 compte dans la référence
        "C": [3, 3, 3, 3],   # aucune référence : pas mixte
        "D": [3, 2],         # mixte mais sous les seuils
    }
    for commune, niveaux in communes.items():
        for niveau in niveaux:
            con.execute("INSERT INTO ventes_rga VALUES ('31', ?, ?)", [commune, niveau])
    assert jointure_rga.comptage_communes(con, CONFIG) == [("31", 4, 3, 2)]


def test_transitions_et_bascules_vers_fort(con):
    con.execute(
        "CREATE TABLE ventes_rga (code_departement VARCHAR, code_commune VARCHAR, "
        "rga_2020 INTEGER, rga_2026 INTEGER)"
    )
    con.execute(
        "INSERT INTO ventes_rga VALUES ('31', 'A', 2, 3), ('31', 'A', 2, 3), ('31', 'B', 3, 3), "
        "('31', 'C', 2, 2), ('47', 'D', 0, 2)"
    )
    assert jointure_rga.transitions(con) == [
        ("31", 2, 2, 1), ("31", 2, 3, 2), ("31", 3, 3, 1), ("47", 0, 2, 1),
    ]
    # A : deux ventes basculent vers fort ; B était déjà fort en 2020
    assert jointure_rga.bascules_vers_fort(con) == [("31", 2, 1, 3), ("47", 0, 0, 1)]


def test_resume_sans_donnees_individuelles(con):
    creer_polygones(con, [("2020", "31", 3, CARRE_TOULOUSE), ("2026", "31", 2, CARRE_TOULOUSE)])
    creer_ventes(con, [("v1", "31", 574500, 6279500), ("v2", "31", 570000, 6270000)])
    jointure_rga.joindre(con, CONFIG)
    sortie = "\n".join(jointure_rga.resumer(con, CONFIG))
    assert "v1" not in sortie and "31555" not in sortie
    assert "TOTAL" in sortie
