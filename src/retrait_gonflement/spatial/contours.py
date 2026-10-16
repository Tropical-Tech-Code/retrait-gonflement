"""Contours simplifiés des communes et limites des départements (docs/app.md, section 1).

Les contours viennent de data/raw/communes/ (API Géo, WGS84). La simplification se fait en
Lambert-93 (mètres) avec DuckDB spatial, puis reprojection en WGS84 (`always_xy`) et
arrondi des coordonnées. Chaque commune garde la seule propriété `code_insee`.
"""

import json
from pathlib import Path

import duckdb

from retrait_gonflement.data.commun import ErreurDonnees

LAMBERT93, WGS84 = "EPSG:2154", "EPSG:4326"


def lire_communes(dossier: Path, departements: list[str]) -> list[dict]:
    """Une entrée par commune : code, nom, département, géométrie GeoJSON (texte)."""
    communes = []
    for dep in departements:
        chemin = dossier / f"communes_{dep}.geojson"
        if not chemin.exists():
            raise ErreurDonnees(f"contours absents : {chemin.name}")
        for entite in json.loads(chemin.read_text(encoding="utf-8"))["features"]:
            communes.append({
                "code": entite["properties"]["code"],
                "nom": entite["properties"]["nom"],
                "departement": dep,
                "geometrie": json.dumps(entite["geometry"]),
            })
    return communes


def simplifier(con: duckdb.DuckDBPyConnection, communes: list[dict], tolerance_m: float) -> None:
    """Table contours_l93 (code, departement, geom) : géométries simplifiées en Lambert-93."""
    con.execute("CREATE OR REPLACE TABLE contours_l93 (code VARCHAR, departement VARCHAR, geom GEOMETRY)")
    con.executemany(
        f"INSERT INTO contours_l93 VALUES (?, ?, ST_SimplifyPreserveTopology("
        f"ST_Transform(ST_GeomFromGeoJSON(?), '{WGS84}', '{LAMBERT93}', always_xy := true), {float(tolerance_m)}))",
        [(c["code"], c["departement"], c["geometrie"]) for c in communes],
    )


def arrondir(coordonnees, decimales: int):
    """Arrondit récursivement et retire les points consécutifs identiques apparus par l'arrondi."""
    if coordonnees and isinstance(coordonnees[0], (int, float)):
        return [round(x, decimales) for x in coordonnees]
    arrondies = [arrondir(c, decimales) for c in coordonnees]
    if arrondies and isinstance(arrondies[0][0], (int, float)):
        return [p for i, p in enumerate(arrondies) if i == 0 or p != arrondies[i - 1]]
    return arrondies


def _en_wgs84(con: duckdb.DuckDBPyConnection, requete: str, decimales: int) -> list[tuple]:
    """`requete` renvoie (cle, g) avec g en Lambert-93 ; résultat : (cle, géométrie GeoJSON arrondie)."""
    lignes = con.execute(
        f"SELECT cle, ST_AsGeoJSON(ST_Transform(g, '{LAMBERT93}', '{WGS84}', always_xy := true)) "
        f"FROM ({requete}) ORDER BY cle"
    ).fetchall()
    resultat = []
    for cle, texte in lignes:
        geometrie = json.loads(texte)
        geometrie["coordinates"] = arrondir(geometrie["coordinates"], decimales)
        resultat.append((cle, geometrie))
    return resultat


def ecrire_geojson(chemin: Path, entites: list[dict]) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    collection = {"type": "FeatureCollection", "features": entites}
    chemin.write_text(json.dumps(collection, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def exporter(con: duckdb.DuckDBPyConnection, dossier: Path, tolerance_m: float, decimales: int) -> tuple[Path, Path]:
    """Écrit contours.geojson (propriété code_insee) et departements.geojson."""
    communes = _en_wgs84(con, "SELECT code AS cle, geom AS g FROM contours_l93", decimales)
    ecrire_geojson(dossier / "contours.geojson", [
        {"type": "Feature", "properties": {"code_insee": code}, "geometry": geometrie}
        for code, geometrie in communes
    ])
    departements = _en_wgs84(
        con,
        f"SELECT departement AS cle, ST_SimplifyPreserveTopology(ST_Union_Agg(geom), {float(tolerance_m)}) AS g "
        "FROM contours_l93 GROUP BY departement",
        decimales,
    )
    ecrire_geojson(dossier / "departements.geojson", [
        {"type": "Feature", "properties": {"departement": dep}, "geometry": geometrie}
        for dep, geometrie in departements
    ])
    return dossier / "contours.geojson", dossier / "departements.geojson"
