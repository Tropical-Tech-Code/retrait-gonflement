"""Nettoyage DVF : ventes simples d'une maison, écrites dans data/interim/travail.duckdb.

Règles dans docs/method.md (section 2), seuils dans config/perimetre.toml. Chaque mutation
est exclue pour un seul motif, le premier rencontré dans l'ordre de MOTIFS ; la table
`mutations_dvf` garde le motif de toutes les mutations, `ventes_maisons` les ventes retenues.
Le résumé affiché ne contient que des comptages.
"""

import argparse
from pathlib import Path

import duckdb

from retrait_gonflement.data.commun import RACINE, ErreurDonnees, charger_config

DOSSIER_DVF = RACINE / "data" / "raw" / "dvf"
BASE_PAR_DEFAUT = RACINE / "data" / "interim" / "travail.duckdb"

# (code, libellé) dans l'ordre d'application : une mutation compte pour le premier motif.
MOTIFS = [
    ("nature", "nature de mutation autre que « Vente »"),
    ("dispositions", "plusieurs dispositions"),
    ("valeur_absente", "valeur foncière absente"),
    ("sans_maison", "aucune maison"),
    ("autre_local", "autre local (appartement, local pro.)"),
    ("plusieurs_maisons", "plusieurs maisons"),
    ("sans_coordonnees", "sans coordonnées"),
    ("surface_bati", "surface bâtie hors bornes"),
    ("valeur_basse", "valeur foncière sous le minimum"),
    ("terrain_max", "terrain au-dessus du plafond"),
    ("prix_m2", "prix au m² hors quantiles (par département et année)"),
]

COLONNES_CONSERVEES = (
    "id_mutation, date_mutation, annee, code_commune, code_departement, id_parcelle, "
    "valeur_fonciere, surface_bati, nombre_pieces, surface_terrain, prix_m2, longitude, latitude"
)


def construire_mutations(con: duckdb.DuckDBPyConnection, fichiers: list[str]) -> None:
    """Une ligne par mutation : lignes DVF dédoublonnées, sans aucun motif encore."""
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE lignes_dvf AS
        SELECT * FROM read_csv(?, all_varchar = true, header = true,
                               union_by_name = true, filename = true)
        """,
        [fichiers],
    )
    # Terrain : une valeur par couple (parcelle, nature de culture), puis somme par mutation.
    # DVF répète ce couple sur chaque ligne de local : une somme brute compterait plusieurs fois.
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE terrains AS
        SELECT fichier, id_mutation, sum(surface) AS surface_terrain
        FROM (
            SELECT filename AS fichier, id_mutation, id_parcelle, nature_culture,
                   nature_culture_speciale,
                   max(try_cast(surface_terrain AS DOUBLE)) AS surface
            FROM lignes_dvf
            GROUP BY ALL
        )
        GROUP BY fichier, id_mutation
        """
    )
    # valeur_fonciere est répétée sur chaque ligne de la mutation : une seule valeur
    # (max), jamais une somme. Maison = code_type_local '1', dépendance = '4'.
    con.execute(
        """
        CREATE OR REPLACE TEMP TABLE mutations AS
        SELECT
            l.filename AS fichier,
            l.id_mutation,
            count(*) AS n_lignes,
            min(l.code_departement) AS code_departement,
            min(try_cast(l.date_mutation AS DATE)) AS date_mutation,
            min(l.nature_mutation) AS nature_mutation,
            count(DISTINCT l.numero_disposition) AS n_dispositions,
            max(try_cast(l.valeur_fonciere AS DOUBLE)) AS valeur_fonciere,
            count(DISTINCT l.id_parcelle || '|' || coalesce(l.surface_reelle_bati, '')
                  || '|' || coalesce(l.nombre_pieces_principales, ''))
                FILTER (WHERE l.code_type_local = '1') AS n_maisons,
            count(*) FILTER (WHERE l.code_type_local IS NOT NULL
                             AND l.code_type_local NOT IN ('1', '4')) AS n_autres_locaux,
            any_value(l.code_commune) FILTER (WHERE l.code_type_local = '1') AS code_commune,
            any_value(l.id_parcelle) FILTER (WHERE l.code_type_local = '1') AS id_parcelle,
            max(try_cast(l.surface_reelle_bati AS DOUBLE))
                FILTER (WHERE l.code_type_local = '1') AS surface_bati,
            max(try_cast(l.nombre_pieces_principales AS INTEGER))
                FILTER (WHERE l.code_type_local = '1') AS nombre_pieces,
            max(try_cast(l.longitude AS DOUBLE))
                FILTER (WHERE l.code_type_local = '1') AS longitude,
            max(try_cast(l.latitude AS DOUBLE))
                FILTER (WHERE l.code_type_local = '1') AS latitude,
            coalesce(max(t.surface_terrain), 0) AS surface_terrain
        FROM lignes_dvf l
        JOIN terrains t ON t.fichier = l.filename AND t.id_mutation = l.id_mutation
        GROUP BY l.filename, l.id_mutation
        """
    )


def classer_mutations(con: duckdb.DuckDBPyConnection, nettoyage: dict) -> None:
    """Attribue à chaque mutation son premier motif d'exclusion (NULL = retenue)."""
    p = float(nettoyage["percentile_exclu"])
    surface_min = float(nettoyage["surface_bati_min"])
    surface_max = float(nettoyage["surface_bati_max"])
    valeur_min = float(nettoyage["valeur_fonciere_min"])
    terrain_max = float(nettoyage["terrain_max_m2"])
    con.execute(
        f"""
        CREATE OR REPLACE TEMP TABLE avant_quantiles AS
        SELECT *, year(date_mutation) AS annee, valeur_fonciere / surface_bati AS prix_m2,
            CASE
                WHEN nature_mutation IS DISTINCT FROM 'Vente' THEN 'nature'
                WHEN n_dispositions > 1 THEN 'dispositions'
                WHEN valeur_fonciere IS NULL THEN 'valeur_absente'
                WHEN n_maisons = 0 THEN 'sans_maison'
                WHEN n_autres_locaux > 0 THEN 'autre_local'
                WHEN n_maisons > 1 THEN 'plusieurs_maisons'
                WHEN longitude IS NULL OR latitude IS NULL THEN 'sans_coordonnees'
                WHEN surface_bati IS NULL OR surface_bati < {surface_min}
                     OR surface_bati > {surface_max} THEN 'surface_bati'
                WHEN valeur_fonciere < {valeur_min} THEN 'valeur_basse'
                WHEN surface_terrain > {terrain_max} THEN 'terrain_max'
            END AS motif
        FROM mutations
        """
    )
    # Quantiles du prix au m² calculés sur les mutations encore retenues, après les bornes.
    con.execute(
        f"""
        CREATE OR REPLACE TABLE mutations_dvf AS
        WITH bornes AS (
            SELECT code_departement, annee,
                   quantile_cont(prix_m2, {p}) AS bas, quantile_cont(prix_m2, {1 - p}) AS haut
            FROM avant_quantiles WHERE motif IS NULL
            GROUP BY code_departement, annee
        )
        SELECT a.* EXCLUDE (motif),
               CASE WHEN a.motif IS NULL AND (a.prix_m2 < b.bas OR a.prix_m2 > b.haut)
                    THEN 'prix_m2' ELSE a.motif END AS motif
        FROM avant_quantiles a
        LEFT JOIN bornes b ON b.code_departement = a.code_departement AND b.annee = a.annee
        """
    )
    con.execute(
        f"CREATE OR REPLACE TABLE ventes_maisons AS "
        f"SELECT {COLONNES_CONSERVEES} FROM mutations_dvf WHERE motif IS NULL"
    )


def nettoyer(con: duckdb.DuckDBPyConnection, fichiers: list[str], config: dict) -> None:
    if not fichiers:
        raise ErreurDonnees("aucun fichier DVF à nettoyer")
    construire_mutations(con, fichiers)
    classer_mutations(con, config["nettoyage"])


def resumer(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Comptages par département et par année. Aucune ligne de données."""
    motifs = ", ".join(
        f"count(*) FILTER (WHERE motif = '{code}')" for code, _ in MOTIFS
    )
    lignes = con.execute(
        f"""
        SELECT code_departement, annee, sum(n_lignes), count(*), {motifs},
               count(*) FILTER (WHERE motif IS NULL)
        FROM mutations_dvf GROUP BY ALL ORDER BY 1, 2
        """
    ).fetchall()
    entetes = ["dep", "année", "lignes", "mutations"] + [f"E{i}" for i in range(1, len(MOTIFS) + 1)]
    entetes.append("retenues")
    total = ["TOTAL", "", *[sum(ligne[i] for ligne in lignes) for i in range(2, len(entetes))]]
    tableau = [entetes] + [[str(c) for c in ligne] for ligne in lignes] + [[str(c) for c in total]]
    largeurs = [max(len(ligne[i]) for ligne in tableau) for i in range(len(entetes))]
    sortie = ["Motifs d'exclusion (chaque mutation compte pour le premier motif rencontré) :"]
    sortie += [f"  E{i} : {libelle}" for i, (_, libelle) in enumerate(MOTIFS, start=1)]
    sortie.append("")
    for ligne in tableau:
        sortie.append("  ".join(c.rjust(largeurs[i]) for i, c in enumerate(ligne)))
    return sortie


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Nettoie DVF vers data/interim/travail.duckdb")
    parser.add_argument("--base", type=Path, default=BASE_PAR_DEFAUT)
    args = parser.parse_args(argv)

    fichiers = sorted(str(f) for f in DOSSIER_DVF.glob("dvf_*.csv.gz"))
    args.base.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(args.base))
    try:
        nettoyer(con, fichiers, charger_config())
        print("\n".join(resumer(con)))
    except (ErreurDonnees, duckdb.Error) as e:
        raise SystemExit(f"Erreur : {e}") from e
    finally:
        con.close()


if __name__ == "__main__":
    main()
