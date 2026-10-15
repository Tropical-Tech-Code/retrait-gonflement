"""Connecteur cartes d'exposition RGA (Géorisques / BRGM) : mode « dépôt manuel ».

Il n'y a pas d'URL stable (formulaire Géorisques) : ce module ne télécharge rien.
Les Shapefile compressés (un par département) sont déposés à la main dans
data/raw/rga/<millésime>/ ; le module vérifie qu'ils sont tous là et lisibles.
Voir la procédure dans le README et dans config/perimetre.toml.
"""

import argparse
import io
import zipfile
from pathlib import Path

from retrait_gonflement.data.commun import RACINE, ErreurDonnees, charger_config

DOSSIER_RAW = RACINE / "data" / "raw" / "rga"
MILLESIMES = ("2020", "2026")
EXTENSIONS_REQUISES = {".shp", ".shx", ".dbf", ".prj", ".cpg"}


def noms_attendus(config: dict, millesime: str) -> dict[str, str]:
    """Nom de fichier attendu pour chaque département du périmètre."""
    if millesime not in MILLESIMES:
        raise ErreurDonnees(f"millésime RGA inconnu : {millesime}")
    modele = config["sources"][f"rga_{millesime}"]["fichier"]
    if not modele:
        raise ErreurDonnees(
            f"carte RGA {millesime} : nom de fichier non défini dans la config "
            "(source pas encore trouvée)"
        )
    return {dep: modele.format(departement=dep) for dep in config["perimetre"]["departements"]}


def valider_zip_shapefile(contenu: bytes) -> list[str]:
    """Vérifie que l'archive est lisible et contient les 5 fichiers du Shapefile."""
    try:
        with zipfile.ZipFile(io.BytesIO(contenu)) as z:
            noms = z.namelist()
    except zipfile.BadZipFile as e:
        raise ErreurDonnees(f"archive illisible : {e}") from e
    manquantes = EXTENSIONS_REQUISES - {Path(n).suffix.lower() for n in noms}
    if manquantes:
        raise ErreurDonnees(f"fichiers du Shapefile manquants : {sorted(manquantes)}")
    return noms


def verifier_depot(config: dict, millesime: str, dossier: Path | None = None) -> list[Path]:
    """Vérifie les fichiers du périmètre ; renvoie leurs chemins.

    Signale en une seule fois tous les départements absents, puis les fichiers invalides.
    """
    dossier = dossier or DOSSIER_RAW / millesime
    attendus = noms_attendus(config, millesime)
    absents = [dep for dep, nom in attendus.items() if not (dossier / nom).exists()]
    if absents:
        details = ", ".join(f"{dep} ({attendus[dep]})" for dep in absents)
        raise ErreurDonnees(
            f"carte RGA {millesime} : département(s) manquant(s) dans {dossier} : {details}"
        )
    chemins = [dossier / nom for nom in attendus.values()]
    for chemin in chemins:
        try:
            valider_zip_shapefile(chemin.read_bytes())
        except ErreurDonnees as e:
            raise ErreurDonnees(f"{chemin.name} : {e}") from e
    return chemins


def resumer_fichier(chemin: Path) -> str:
    """Nom, taille et nombre de fichiers dans l'archive. Jamais le contenu."""
    noms = valider_zip_shapefile(chemin.read_bytes())
    return f"{chemin.name} | {chemin.stat().st_size / 1e6:.2f} Mo | {len(noms)} fichiers"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Vérifie le dépôt manuel d'une carte RGA")
    parser.add_argument("--millesime", required=True, choices=MILLESIMES)
    args = parser.parse_args(argv)

    try:
        chemins = verifier_depot(charger_config(), args.millesime)
    except ErreurDonnees as e:
        raise SystemExit(f"Erreur : {e}") from e
    for chemin in chemins:
        print(resumer_fichier(chemin))


if __name__ == "__main__":
    main()
