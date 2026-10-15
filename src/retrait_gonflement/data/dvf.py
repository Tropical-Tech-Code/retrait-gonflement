"""Connecteur DVF géolocalisées (Etalab) : téléchargement vers data/raw/dvf/."""

import argparse
import gzip
import io
from pathlib import Path

import httpx

from retrait_gonflement.data.commun import (
    RACINE,
    ErreurDonnees,
    charger_config,
    ecrire_atomique,
    url_configuree,
)

DOSSIER_RAW = RACINE / "data" / "raw" / "dvf"

# Colonnes dont dépend le nettoyage décrit dans docs/method.md
COLONNES_REQUISES = {
    "id_mutation", "date_mutation", "nature_mutation", "valeur_fonciere",
    "code_commune", "nom_commune", "code_departement", "id_parcelle",
    "code_type_local", "type_local", "surface_reelle_bati",
    "nombre_pieces_principales", "code_nature_culture", "nature_culture",
    "surface_terrain", "longitude", "latitude",
}


def construire_url(config: dict, annee: int, departement: str) -> str:
    return url_configuree(config, "dvf").format(annee=annee, departement=departement)


def valider_colonnes(contenu_gz: bytes) -> None:
    """Lit seulement l'en-tête du CSV compressé et vérifie les colonnes requises."""
    try:
        with gzip.open(io.BytesIO(contenu_gz), "rt", encoding="utf-8") as f:
            entete = f.readline().strip().split(",")
    except (OSError, EOFError, UnicodeDecodeError) as e:
        raise ErreurDonnees(f"fichier DVF illisible : {e}") from e
    manquantes = COLONNES_REQUISES - set(entete)
    if manquantes:
        raise ErreurDonnees(f"colonnes DVF manquantes : {sorted(manquantes)}")


def telecharger_dvf(
    config: dict,
    client: httpx.Client | None = None,
    dossier: Path = DOSSIER_RAW,
    ecraser: bool = False,
) -> list[Path]:
    """Télécharge un fichier par (année, département) ; renvoie les chemins écrits.

    Un fichier déjà présent est conservé, sauf si ecraser=True.
    """
    perimetre = config["perimetre"]
    annees = range(perimetre["annee_debut"], perimetre["annee_fin"] + 1)
    dossier.mkdir(parents=True, exist_ok=True)
    propre = client is None
    client = client or httpx.Client(timeout=120, follow_redirects=True)
    ecrits = []
    try:
        for annee in annees:
            for dep in perimetre["departements"]:
                cible = dossier / f"dvf_{annee}_{dep}.csv.gz"
                if cible.exists() and not ecraser:
                    continue
                reponse = client.get(construire_url(config, annee, dep))
                reponse.raise_for_status()
                valider_colonnes(reponse.content)
                ecrire_atomique(cible, reponse.content)
                ecrits.append(cible)
    finally:
        if propre:
            client.close()
    return ecrits


def resumer_fichier(chemin: Path) -> str:
    """Chemin, taille et nombre de lignes de données (sans l'en-tête). Jamais le contenu."""
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        lignes = sum(1 for _ in f) - 1
    return f"{chemin} | {chemin.stat().st_size / 1e6:.2f} Mo | {lignes} lignes"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Télécharge des fichiers DVF vers data/raw/dvf/")
    parser.add_argument("--departement", help="un département (défaut : tout le périmètre)")
    parser.add_argument("--annee", type=int, help="une année (défaut : toute la période)")
    parser.add_argument("--ecraser", action="store_true", help="retélécharger un fichier déjà présent")
    args = parser.parse_args(argv)

    config = charger_config()
    perimetre = dict(config["perimetre"])
    if args.departement:
        perimetre["departements"] = [args.departement]
    if args.annee:
        perimetre["annee_debut"] = perimetre["annee_fin"] = args.annee
    config = {**config, "perimetre": perimetre}

    telecharger_dvf(config, ecraser=args.ecraser)
    for annee in range(perimetre["annee_debut"], perimetre["annee_fin"] + 1):
        for dep in perimetre["departements"]:
            print(resumer_fichier(DOSSIER_RAW / f"dvf_{annee}_{dep}.csv.gz"))


if __name__ == "__main__":
    main()
