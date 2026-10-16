"""Connecteur GASPAR (Géorisques) : arrêtés CatNat, archive ZIP vers data/raw/gaspar/.

L'archive contient 8 tables ; seule la table des arrêtés (catnat_gaspar_<date>.csv) sert.
Aucun filtrage ici (sécheresse, depuis 2015) : il est fait au jour 2.
"""

import argparse
import csv
import fnmatch
import io
import zipfile
from pathlib import Path

import httpx

from retrait_gonflement.data.commun import (
    RACINE,
    ErreurDonnees,
    charger_config,
    ecrire_atomique,
    url_configuree,
)

DOSSIER_RAW = RACINE / "data" / "raw" / "gaspar"
NOM_ARCHIVE = "gaspar.zip"
SEPARATEUR = ";"
COLONNES_REQUISES = {"code_commune", "lib_risque_jo", "date_debut", "date_fin"}


def trouver_table(zf: zipfile.ZipFile, modele: str) -> str:
    """Nom de la table des arrêtés dans l'archive, cherché par modèle (le nom change)."""
    trouvees = [n for n in zf.namelist() if fnmatch.fnmatch(Path(n).name, modele)]
    if not trouvees:
        raise ErreurDonnees(f"table {modele} introuvable dans l'archive GASPAR")
    if len(trouvees) > 1:
        raise ErreurDonnees(f"plusieurs tables {modele} dans l'archive : {sorted(trouvees)}")
    return trouvees[0]


def valider_archive(source, config: dict) -> tuple[str, int]:
    """Vérifie l'archive (chemin ou octets) ; renvoie (nom de la table, nombre d'arrêtés)."""
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    try:
        with zipfile.ZipFile(source) as zf:
            nom = trouver_table(zf, config["sources"]["gaspar"]["table"])
            with zf.open(nom) as f:
                entete = f.readline().decode("utf-8-sig").strip()
                colonnes = next(csv.reader([entete], delimiter=SEPARATEUR))
                manquantes = COLONNES_REQUISES - set(colonnes)
                if manquantes:
                    raise ErreurDonnees(
                        f"colonnes GASPAR manquantes : {sorted(manquantes)} "
                        f"(séparateur attendu « {SEPARATEUR} »)"
                    )
                n = sum(1 for ligne in f if ligne.strip())
    except zipfile.BadZipFile as e:
        raise ErreurDonnees(f"archive GASPAR illisible : {e}") from e
    except UnicodeDecodeError as e:
        raise ErreurDonnees(f"table GASPAR : encodage inattendu ({e})") from e
    return Path(nom).name, n


def telecharger_gaspar(
    config: dict,
    client: httpx.Client | None = None,
    dossier: Path = DOSSIER_RAW,
    ecraser: bool = False,
) -> list[Path]:
    """Télécharge l'archive ; un fichier déjà présent n'est pas retéléchargé."""
    url = url_configuree(config, "gaspar")
    cible = dossier / NOM_ARCHIVE
    if cible.exists() and not ecraser:
        return []
    propre = client is None
    client = client or httpx.Client(timeout=300, follow_redirects=True)
    try:
        reponse = client.get(url)
        reponse.raise_for_status()
        valider_archive(reponse.content, config)
        ecrire_atomique(cible, reponse.content)
    finally:
        if propre:
            client.close()
    return [cible]


def resumer_fichier(chemin: Path, config: dict) -> str:
    """Archive, taille, table et nombre d'arrêtés. Jamais de données."""
    nom, n = valider_archive(chemin, config)
    return f"{chemin.name} | {chemin.stat().st_size / 1e6:.2f} Mo | table {nom} | {n} arrêtés"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Télécharge l'archive GASPAR (arrêtés CatNat)")
    parser.add_argument("--ecraser", action="store_true", help="retélécharger un fichier déjà présent")
    args = parser.parse_args(argv)

    config = charger_config()
    try:
        telecharger_gaspar(config, ecraser=args.ecraser)
        print(resumer_fichier(DOSSIER_RAW / NOM_ARCHIVE, config))
    except ErreurDonnees as e:
        raise SystemExit(f"Erreur : {e}") from e


if __name__ == "__main__":
    main()
