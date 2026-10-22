"""Métadonnées affichées par l'app : effectifs du nettoyage DVF et sources des données.

Complète resume_global.json (clés `nettoyage` et `sources`) pour que l'app n'écrive aucun
chiffre ni aucune date en dur. Ne lit jamais le contenu des fichiers bruts : seulement leur
date de modification, le nom de la table GASPAR et les comptages de `mutations_dvf`.

    uv run python -m retrait_gonflement.model.metadonnees
"""

import argparse
import zipfile
from datetime import date
from pathlib import Path

import duckdb

from retrait_gonflement.data import gaspar
from retrait_gonflement.data.commun import RACINE, ErreurDonnees, charger_config
from retrait_gonflement.data.nettoyage_dvf import BASE_PAR_DEFAUT, MOTIFS
from retrait_gonflement.data.rga import MILLESIMES
from retrait_gonflement.model.modele_global import CHEMIN_RESUME, ecrire_resume

DOSSIER_RAW = RACINE / "data" / "raw"
NOTE_DATE = (
    "Date de téléchargement (ou de dépôt pour les cartes RGA), lue sur la date du fichier local."
)


def effectifs_nettoyage(con: duckdb.DuckDBPyConnection) -> dict:
    """Mutations DVF restantes après chaque motif d'exclusion (table `mutations_dvf`)."""
    n_lignes, n_mutations = con.execute("SELECT coalesce(sum(n_lignes), 0), count(*) FROM mutations_dvf").fetchone()
    par_motif = dict(con.execute("SELECT motif, count(*) FROM mutations_dvf WHERE motif IS NOT NULL GROUP BY motif").fetchall())
    par_annee = con.execute("SELECT annee, count(*) FROM mutations_dvf WHERE motif IS NULL GROUP BY annee ORDER BY annee").fetchall()
    etapes, restantes = [], int(n_mutations)
    for code, libelle in MOTIFS:
        exclues = int(par_motif.get(code, 0))
        restantes -= exclues
        etapes.append({"code": code, "libelle": libelle, "exclues": exclues, "restantes": restantes})
    return {
        "n_lignes_dvf": int(n_lignes),
        "n_mutations": int(n_mutations),
        "etapes": etapes,
        "n_ventes_retenues": restantes,
        "ventes_retenues_par_annee": {str(int(annee)): int(n) for annee, n in par_annee},
    }


def table_existe(con: duckdb.DuckDBPyConnection, nom: str) -> bool:
    return con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [nom]).fetchone()[0] > 0


def repartition_zones(con: duckdb.DuckDBPyConnection) -> dict:
    """Part des ventes par niveau RGA 2020 (0 à 3), par département (table `ventes_rga`).

    Fractions entre 0 et 1 ; l'app en tire la plage de la zone forte et la part maximale de la référence.
    """
    lignes = con.execute(
        "SELECT code_departement, count(*), "
        + ", ".join(f"count(*) FILTER (WHERE rga_2020 = {n})" for n in range(4))
        + " FROM ventes_rga GROUP BY code_departement ORDER BY code_departement"
    ).fetchall()
    return {
        str(dep): {"n_ventes": int(total), **{f"part_{n}": effectif / total for n, effectif in enumerate(par_niveau)}}
        for dep, total, *par_niveau in lignes
    }


def changements_carte_2026(con: duckdb.DuckDBPyConnection) -> dict:
    """Ventes dont le niveau RGA change entre la carte 2020 et la carte 2026, dans les deux sens."""
    n_ventes, n_change, plus, moins = con.execute(
        "SELECT count(*), count(*) FILTER (WHERE rga_2020 <> rga_2026), "
        "count(*) FILTER (WHERE rga_2026 > rga_2020), count(*) FILTER (WHERE rga_2026 < rga_2020) FROM ventes_rga"
    ).fetchone()
    return {
        "n_ventes": int(n_ventes),
        "n_change": int(n_change),
        "n_vers_plus_fort": int(plus),
        "n_vers_moins_fort": int(moins),
        "part_change": n_change / n_ventes if n_ventes else None,
    }


def date_fichiers(fichiers: list[Path]) -> str | None:
    """Date (ISO) du fichier le plus récent ; None s'il n'y a aucun fichier."""
    if not fichiers:
        return None
    return date.fromtimestamp(max(f.stat().st_mtime for f in fichiers)).isoformat()


def nom_table_gaspar(archive: Path, config: dict) -> str | None:
    """Nom de la table des arrêtés dans l'archive (sert de millésime) ; None si illisible."""
    try:
        with zipfile.ZipFile(archive) as zf:
            return Path(gaspar.trouver_table(zf, config["sources"]["gaspar"]["table"])).name
    except (zipfile.BadZipFile, ErreurDonnees, FileNotFoundError):
        return None


def decrire_sources(config: dict, racine: Path = DOSSIER_RAW) -> list[dict]:
    """Une entrée par source : nom, usage, accès, millésime, date de téléchargement."""
    perimetre = config["perimetre"]
    sources = config["sources"]
    dvf = sorted((racine / "dvf").glob("dvf_*.csv.gz"))
    communes = sorted(p for p in (racine / "communes").glob("*") if p.is_file())
    liste = [
        {
            "cle": "dvf", "nom": "DVF géolocalisées (Etalab)", "usage": "Ventes de maisons : prix, surfaces, coordonnées",
            "acces": sources["dvf"]["url"], "millesime": f"ventes {perimetre['annee_debut']}-{perimetre['annee_fin']}",
            "date_telechargement": date_fichiers(dvf),
        },
    ]
    for millesime in MILLESIMES:
        zips = sorted((racine / "rga" / millesime).glob("*.zip"))
        liste.append({
            "cle": f"rga_{millesime}", "nom": f"Carte d'exposition RGA {millesime} (Géorisques / BRGM)",
            "usage": "Exposition connue du marché" if millesime == "2020" else "Communes qui basculent",
            "acces": "dépôt manuel (formulaire Géorisques)", "millesime": millesime,
            "date_telechargement": date_fichiers(zips),
        })
    liste += [
        {
            "cle": "gaspar", "nom": "GASPAR (Géorisques)", "usage": "Arrêtés CatNat sécheresse par commune",
            "acces": sources["gaspar"]["url"], "millesime": nom_table_gaspar(racine / "gaspar" / gaspar.NOM_ARCHIVE, config),
            "date_telechargement": date_fichiers([racine / "gaspar" / gaspar.NOM_ARCHIVE] if (racine / "gaspar" / gaspar.NOM_ARCHIVE).exists() else []),
        },
        {
            "cle": "communes", "nom": "Contours des communes (API Géo, issus d'ADMIN EXPRESS IGN)", "usage": "Carte de l'app",
            "acces": sources["communes"]["url"], "millesime": "version de l'API Géo à la date de consultation",
            "date_telechargement": date_fichiers(communes),
        },
    ]
    return liste


def lignes_zones(zones: dict, carte_2026: dict) -> list[str]:
    sortie = ["Part des ventes par niveau RGA 2020 (%)", "  dep  ventes  hors zone  faible  moyen  fort"]
    for dep, z in zones.items():
        sortie.append(f"  {dep}  {z['n_ventes']}  " + "  ".join(f"{100 * z[f'part_{n}']:.1f}" for n in range(4)))
    part = carte_2026["part_change"]
    sortie += [
        "",
        f"Carte 2026 contre 2020 : {carte_2026['n_change']} ventes sur {carte_2026['n_ventes']} changent de niveau"
        + (f" ({100 * part:.2f} %)" if part is not None else "")
        + f", dont {carte_2026['n_vers_plus_fort']} vers un niveau plus fort et {carte_2026['n_vers_moins_fort']} vers un niveau moins fort",
    ]
    return sortie


def lignes_resume(nettoyage: dict, sources: list[dict]) -> list[str]:
    sortie = [f"Nettoyage DVF : {nettoyage['n_mutations']} mutations -> {nettoyage['n_ventes_retenues']} ventes retenues"]
    sortie += [f"  {e['libelle']} : -{e['exclues']} (reste {e['restantes']})" for e in nettoyage["etapes"]]
    sortie += ["", "Sources"]
    sortie += [f"  {s['nom']} : millésime {s['millesime'] or 'non renseigné'}, date {s['date_telechargement'] or 'non renseignée'}" for s in sources]
    return sortie


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Ajoute les effectifs du nettoyage, les sources, la répartition par zone et les changements "
        "de la carte 2026 à resume_global.json"
    )
    parser.add_argument("--base", type=Path, default=BASE_PAR_DEFAUT)
    parser.add_argument("--resume", type=Path, default=CHEMIN_RESUME)
    parser.add_argument("--raw", type=Path, default=DOSSIER_RAW)
    args = parser.parse_args(argv)
    zones = carte_2026 = None
    try:
        con = duckdb.connect(str(args.base), read_only=True)
        try:
            nettoyage = effectifs_nettoyage(con)
            if table_existe(con, "ventes_rga"):
                zones, carte_2026 = repartition_zones(con), changements_carte_2026(con)
        finally:
            con.close()
        sources = decrire_sources(charger_config(), args.raw)
    except (ErreurDonnees, duckdb.Error) as e:
        raise SystemExit(f"Erreur : {e}") from e
    ajout = {"nettoyage": nettoyage, "sources": {"note_date": NOTE_DATE, "liste": sources}}
    if zones is not None:
        ajout |= {"zones_rga": zones, "carte_2026": carte_2026}
    ecrire_resume(args.resume, ajout)
    sortie = lignes_resume(nettoyage, sources)
    if zones is not None:
        sortie += ["", *lignes_zones(zones, carte_2026)]
    else:
        sortie += ["", "Table ventes_rga absente : répartition par zone et carte 2026 non calculées"]
    print("\n".join(sortie))


if __name__ == "__main__":
    main()
