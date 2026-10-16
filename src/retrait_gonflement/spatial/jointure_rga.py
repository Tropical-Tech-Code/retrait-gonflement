"""Jointure spatiale des ventes (data/interim/travail.duckdb) avec les cartes RGA 2020 et 2026.

Les polygones sont lus directement dans les archives (voir inspection_rga), puis chaque
vente reçoit un niveau par millésime : 0 = hors zone argileuse, 1 = faible, 2 = moyen,
3 = fort. Le point de la vente (WGS84) est reprojeté en EPSG:2154, avec `always_xy` : sans
lui, PROJ lit EPSG:4326 comme (latitude, longitude) et les coordonnées sortent fausses.
Le résumé affiché ne contient que des comptages.

    uv run python -m retrait_gonflement.spatial.jointure_rga
"""

import argparse
from pathlib import Path

import duckdb

from retrait_gonflement.data.commun import ErreurDonnees, charger_config
from retrait_gonflement.data.nettoyage_dvf import BASE_PAR_DEFAUT
from retrait_gonflement.data.rga import DOSSIER_RAW, MILLESIMES, noms_attendus, verifier_depot
from retrait_gonflement.spatial.inspection_rga import source_shp

NIVEAUX = (0, 1, 2, 3)


def charger_polygones(con: duckdb.DuckDBPyConnection, config: dict, dossier: Path = DOSSIER_RAW) -> None:
    """Table rga_polygones (millésime, département, niveau, géométrie, limite) en Lambert 93."""
    con.execute(
        "CREATE OR REPLACE TABLE rga_polygones (millesime VARCHAR, departement VARCHAR, "
        "niveau INTEGER, geom GEOMETRY, limite GEOMETRY)"
    )
    for millesime in MILLESIMES:
        for dep, nom in noms_attendus(config, millesime).items():
            source = source_shp((dossier / millesime / nom).resolve())
            con.execute(
                "INSERT INTO rga_polygones "
                "SELECT ?, ?, CAST(niveau AS INTEGER), geom, ST_Boundary(geom) FROM ST_Read(?)",
                [millesime, dep, source],
            )
    invalides = con.execute(
        "SELECT DISTINCT millesime, niveau FROM rga_polygones "
        "WHERE niveau IS NULL OR niveau NOT IN (1, 2, 3)"
    ).fetchall()
    if invalides:
        raise ErreurDonnees(f"niveaux RGA inattendus (millésime, niveau) : {invalides}")


def joindre(con: duckdb.DuckDBPyConnection, config: dict) -> None:
    """Crée ventes_rga : les ventes, plus rga_<millésime> et ses indicateurs de contrôle.

    Pour chaque millésime :
    - niveau : plus haut niveau parmi les polygones du département de la vente qui
      contiennent le point (0 s'il n'y en a aucun) ;
    - hors_dep : le point est dans un polygone d'un autre département, et dans aucun du sien ;
    - multi : le point est dans plusieurs polygones (sur une limite ou un chevauchement) ;
    - proche_limite : à moins de `distance_limite_zone_m` de la limite du polygone qui
      contient la vente ; pour une vente hors zone, un polygone du département à moins de cette distance.
    """
    distance = float(config["nettoyage"]["distance_limite_zone_m"])
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE points AS
        SELECT *, ST_Buffer(pt, {distance}) AS disque FROM (
            SELECT row_number() OVER () AS rid, *,
                   ST_Transform(ST_Point(longitude, latitude), 'EPSG:4326', 'EPSG:2154',
                                always_xy := true) AS pt
            FROM ventes_maisons
        )
        """
    )
    for millesime in MILLESIMES:
        con.execute(
            f"CREATE OR REPLACE TEMP TABLE polygones_{millesime} AS "
            f"SELECT * FROM rga_polygones WHERE millesime = '{millesime}'"
        )
        con.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE jointure_{millesime} AS
            WITH paires AS (
                SELECT p.rid, p.code_departement AS dep, g.departement AS dep_poly, g.niveau,
                       ST_Intersects(p.pt, g.geom) AS contient,
                       CASE WHEN ST_Intersects(p.pt, g.geom)
                            THEN ST_Distance(p.pt, g.limite) END AS dist_limite
                FROM points p
                LEFT JOIN polygones_{millesime} g ON ST_Intersects(p.disque, g.geom)
            ),
            par_vente AS (
                SELECT rid,
                    coalesce(max(niveau) FILTER (WHERE contient AND dep_poly = dep), 0) AS niveau,
                    coalesce(bool_or(contient AND dep_poly <> dep), false) AS dans_autre_dep,
                    count(*) FILTER (WHERE contient AND dep_poly = dep) AS n_contenants,
                    min(dist_limite) FILTER (WHERE dep_poly = dep) AS dist_min,
                    coalesce(bool_or(dep_poly = dep), false) AS polygone_proche
                FROM paires GROUP BY rid
            )
            SELECT rid, niveau AS rga_{millesime},
                   niveau = 0 AND dans_autre_dep AS hors_dep_{millesime},
                   n_contenants > 1 AS multi_{millesime},
                   CASE WHEN niveau >= 1 THEN coalesce(dist_min < {distance}, false)
                        ELSE polygone_proche END AS proche_limite_{millesime}
            FROM par_vente
            """
        )
    colonnes = [c[0] for c in con.execute("DESCRIBE ventes_maisons").fetchall()]
    liste = ", ".join(f"p.{c}" for c in colonnes)
    con.execute(
        f"""
        CREATE OR REPLACE TABLE ventes_rga AS
        SELECT {liste},
               a.rga_2020, a.hors_dep_2020, a.multi_2020, a.proche_limite_2020,
               b.rga_2026, b.hors_dep_2026, b.multi_2026, b.proche_limite_2026
        FROM points p
        JOIN jointure_2020 a USING (rid)
        JOIN jointure_2026 b USING (rid)
        """
    )


def comptage_communes(con: duckdb.DuckDBPyConnection, config: dict) -> list[tuple]:
    """Communes mixtes (carte 2020) par département, avant tout modèle.

    Référence = tout le reste que « fort » (niveaux 0, 1 et 2), comme la prime par commune.
    """
    est = config["estimation"]
    fort, ref, total = (int(est[k]) for k in ("min_ventes_fort", "min_ventes_reference", "min_ventes_total"))
    return con.execute(
        f"""
        WITH c AS (
            SELECT code_departement, code_commune,
                   count(*) FILTER (WHERE rga_2020 = 3) AS fort,
                   count(*) FILTER (WHERE rga_2020 IN (0, 1, 2)) AS reference,
                   count(*) AS total
            FROM ventes_rga GROUP BY ALL
        )
        SELECT code_departement, count(*),
               count(*) FILTER (WHERE fort > 0 AND reference > 0),
               count(*) FILTER (WHERE fort >= {fort} AND reference >= {ref} AND total >= {total})
        FROM c GROUP BY code_departement ORDER BY code_departement
        """
    ).fetchall()


def transitions(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    """Ventes par département et par couple (niveau 2020, niveau 2026)."""
    return con.execute(
        "SELECT code_departement, rga_2020, rga_2026, count(*) FROM ventes_rga "
        "GROUP BY ALL ORDER BY 1, 2, 3"
    ).fetchall()


def bascules_vers_fort(con: duckdb.DuckDBPyConnection) -> list[tuple]:
    """Par département : ventes et communes avec au moins une vente classée fort en 2026 seulement."""
    return con.execute(
        """
        SELECT code_departement,
               count(*) FILTER (WHERE rga_2020 <> 3 AND rga_2026 = 3),
               count(DISTINCT code_commune) FILTER (WHERE rga_2020 <> 3 AND rga_2026 = 3),
               count(DISTINCT code_commune)
        FROM ventes_rga GROUP BY code_departement ORDER BY code_departement
        """
    ).fetchall()


def tableau(entetes: list[str], lignes: list[tuple | list]) -> list[str]:
    cellules = [entetes] + [[str(c) for c in ligne] for ligne in lignes]
    largeurs = [max(len(ligne[i]) for ligne in cellules) for i in range(len(entetes))]
    return ["  ".join(c.rjust(largeurs[i]) for i, c in enumerate(ligne)) for ligne in cellules]


def avec_total(lignes: list[tuple], debut: int) -> list[tuple]:
    """Ajoute une ligne TOTAL qui somme les colonnes à partir de l'indice `debut`."""
    total = ["TOTAL"] + [""] * (debut - 1) + [sum(ligne[i] for ligne in lignes) for i in range(debut, len(lignes[0]))]
    return [*lignes, tuple(total)]


def resumer(con: duckdb.DuckDBPyConnection, config: dict) -> list[str]:
    """Comptages uniquement : aucune vente, aucune géométrie."""
    sortie = ["1. Ventes par niveau RGA (0 hors zone, 1 faible, 2 moyen, 3 fort)"]
    lignes = []
    for dep, in con.execute("SELECT DISTINCT code_departement FROM ventes_rga ORDER BY 1").fetchall():
        for m in MILLESIMES:
            comptes = [
                con.execute(
                    f"SELECT count(*) FROM ventes_rga WHERE code_departement = ? AND rga_{m} = ?",
                    [dep, n],
                ).fetchone()[0]
                for n in NIVEAUX
            ]
            lignes.append((dep, m, *comptes, sum(comptes)))
    sortie += tableau(["dep", "carte", "0", "1", "2", "3", "total"], lignes)

    sortie += ["", "2. Contrôles : dans un autre département (doit être proche de 0), sans polygone du",
               "   département (= niveau 0), sur plusieurs polygones, à moins de la distance limite"]
    lignes = []
    for dep, in con.execute("SELECT DISTINCT code_departement FROM ventes_rga ORDER BY 1").fetchall():
        for m in MILLESIMES:
            lignes.append((dep, m, *con.execute(
                f"""SELECT count(*) FILTER (WHERE hors_dep_{m}), count(*) FILTER (WHERE rga_{m} = 0),
                           count(*) FILTER (WHERE multi_{m}), count(*) FILTER (WHERE proche_limite_{m})
                    FROM ventes_rga WHERE code_departement = ?""", [dep]).fetchone()))
    sortie += tableau(["dep", "carte", "autre_dep", "niveau_0", "multi", "proche_limite"], lignes)

    sortie += ["", "3. Communes mixtes, carte 2020 (au moins une vente en fort ET en référence 0+1+2)",
               "   seuils : min_ventes_fort, min_ventes_reference, min_ventes_total"]
    lignes = avec_total(comptage_communes(con, config), 1)
    sortie += tableau(["dep", "communes", "mixtes", "passent_seuils"], lignes)

    sortie += ["", "4. Transitions 2020 → 2026 : ventes par couple (niveau 2020, niveau 2026)"]
    sortie += tableau(["dep", "2020", "2026", "ventes"], transitions(con))

    sortie += ["", "5. Bascules vers fort (non fort en 2020, fort en 2026) : ventes, communes concernées,",
               "   communes avec ventes"]
    lignes = avec_total(bascules_vers_fort(con), 1)
    sortie += tableau(["dep", "ventes", "communes_bascule", "communes"], lignes)
    return sortie


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Jointure ventes × cartes RGA 2020 et 2026")
    parser.add_argument("--base", type=Path, default=BASE_PAR_DEFAUT)
    args = parser.parse_args(argv)

    config = charger_config()
    con = duckdb.connect(str(args.base))
    try:
        con.execute("LOAD spatial")
        for millesime in MILLESIMES:
            verifier_depot(config, millesime)
        charger_polygones(con, config)
        joindre(con, config)
        print("\n".join(resumer(con, config)))
    except (ErreurDonnees, duckdb.Error) as e:
        raise SystemExit(f"Erreur : {e}") from e
    finally:
        con.close()


if __name__ == "__main__":
    main()
