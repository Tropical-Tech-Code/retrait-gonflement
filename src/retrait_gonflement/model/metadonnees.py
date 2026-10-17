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


def lignes_resume(nettoyage: dict, sources: list[dict]) -> list[str]:
    sortie = [f"Nettoyage DVF : {nettoyage['n_mutations']} mutations -> {nettoyage['n_ventes_retenues']} ventes retenues"]
    sortie += [f"  {e['libelle']} : -{e['exclues']} (reste {e['restantes']})" for e in nettoyage["etapes"]]
    sortie += ["", "Sources"]
    sortie += [f"  {s['nom']} : millésime {s['millesime'] or 'non renseigné'}, date {s['date_telechargement'] or 'non renseignée'}" for s in sources]
    return sortie


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ajoute les effectifs du nettoyage et les sources à resume_global.json")
    parser.add_argument("--base", type=Path, default=BASE_PAR_DEFAUT)
    parser.add_argument("--resume", type=Path, default=CHEMIN_RESUME)
    parser.add_argument("--raw", type=Path, default=DOSSIER_RAW)
    args = parser.parse_args(argv)
    try:
        con = duckdb.connect(str(args.base), read_only=True)
        try:
            nettoyage = effectifs_nettoyage(con)
        finally:
            con.close()
        sources = decrire_sources(charger_config(), args.raw)
    except (ErreurDonnees, duckdb.Error) as e:
        raise SystemExit(f"Erreur : {e}") from e
    ecrire_resume(args.resume, {"nettoyage": nettoyage, "sources": {"note_date": NOTE_DATE, "liste": sources}})
    print("\n".join(lignes_resume(nettoyage, sources)))


if __name__ == "__main__":
    main()
