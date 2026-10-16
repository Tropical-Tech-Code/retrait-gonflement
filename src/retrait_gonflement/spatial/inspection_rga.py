"""Inspection des cartes RGA : structure et valeurs distinctes, jamais de géométrie.

Lit chaque archive Shapefile directement (DuckDB spatial, /vsizip/), sans rien
décompresser sur le disque. Affiche uniquement : système de coordonnées, colonnes et
types, valeurs distinctes (avec nombre de polygones) des colonnes de faible cardinalité,
nombre total de polygones. Lancé à la main : le contenu de data/raw/ n'est jamais lu par Claude.

    uv run python -m retrait_gonflement.spatial.inspection_rga
"""

import argparse
import zipfile
from pathlib import Path

import duckdb

from retrait_gonflement.data.commun import ErreurDonnees, charger_config
from retrait_gonflement.data.rga import DOSSIER_RAW, MILLESIMES, noms_attendus

SEUIL_VALEURS = 30  # au-delà, on donne seulement le nombre de valeurs distinctes
TYPES_GEOMETRIE = {"GEOMETRY", "BLOB", "WKB_BLOB"}


def identifiant(nom: str) -> str:
    """Nom de colonne entre guillemets, pour SQL."""
    return '"' + nom.replace('"', '""') + '"'


def source_shp(archive: Path) -> str:
    """Chemin GDAL /vsizip/ du .shp, trouvé dans la liste des noms de l'archive."""
    with zipfile.ZipFile(archive) as z:
        shp = [n for n in z.namelist() if n.lower().endswith(".shp")]
    if len(shp) != 1:
        raise ErreurDonnees(f"{archive.name} : {len(shp)} fichier(s) .shp au lieu d'un")
    return f"/vsizip/{archive}/{shp[0]}"


def systeme_coordonnees(con: duckdb.DuckDBPyConnection, source: str) -> str:
    """Nom et code du système de coordonnées de la première couche."""
    ligne = con.execute(
        "SELECT layers[1].geometry_fields[1].crs FROM ST_Read_Meta(?)", [source]
    ).fetchone()
    crs = ligne[0] if ligne else None
    if not crs:
        return "non défini"
    return f"{crs.get('name')} ({crs.get('auth_name')}:{crs.get('auth_code')})"


def inspecter(con: duckdb.DuckDBPyConnection, archive: Path) -> None:
    source = source_shp(archive)
    print(f"  Coordonnées : {systeme_coordonnees(con, source)}")

    colonnes = con.execute("DESCRIBE SELECT * FROM ST_Read(?)", [source]).fetchall()
    attributs = [(nom, type_) for nom, type_, *_ in colonnes if type_.upper() not in TYPES_GEOMETRIE]
    total = con.execute("SELECT count(*) FROM ST_Read(?)", [source]).fetchone()[0]
    print(f"  Polygones : {total}")
    print("  Colonnes : " + ", ".join(f"{nom} [{type_}]" for nom, type_ in attributs))

    for nom, type_ in attributs:
        col = identifiant(nom)
        nb = con.execute(f"SELECT count(DISTINCT {col}) FROM ST_Read(?)", [source]).fetchone()[0]
        if nb > SEUIL_VALEURS:
            print(f"  - {nom} : {nb} valeurs distinctes (non listées)")
            continue
        valeurs = con.execute(
            f"SELECT {col}, count(*) FROM ST_Read(?) GROUP BY ALL ORDER BY 2 DESC", [source]
        ).fetchall()
        print(f"  - {nom} : {nb} valeurs distinctes")
        for valeur, effectif in valeurs:
            print(f"      {valeur!r} : {effectif}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Inspecte les cartes RGA (sans géométrie)")
    parser.add_argument("--millesime", choices=MILLESIMES, help="un seul millésime (défaut : tous)")
    args = parser.parse_args(argv)

    config = charger_config()
    con = duckdb.connect()
    con.execute("LOAD spatial")
    for millesime in [args.millesime] if args.millesime else MILLESIMES:
        try:
            attendus = noms_attendus(config, millesime)
        except ErreurDonnees as e:
            raise SystemExit(f"Erreur : {e}") from e
        for dep, nom in attendus.items():
            print(f"\n=== RGA {millesime} | département {dep} | {nom} ===")
            try:
                inspecter(con, (DOSSIER_RAW / millesime / nom).resolve())
            except (ErreurDonnees, duckdb.Error, OSError, zipfile.BadZipFile) as e:
                print(f"  Erreur : {e}")


if __name__ == "__main__":
    main()
