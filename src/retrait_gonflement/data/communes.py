"""Connecteur contours des communes (API Géo, issus d'ADMIN EXPRESS) : data/raw/communes/."""

import argparse
import json
from pathlib import Path

import httpx

from retrait_gonflement.data.commun import (
    RACINE,
    ErreurDonnees,
    charger_config,
    ecrire_atomique,
    url_configuree,
)

DOSSIER_RAW = RACINE / "data" / "raw" / "communes"

PROPRIETES_REQUISES = {"code", "nom"}


def construire_url(config: dict, departement: str) -> str:
    return url_configuree(config, "communes").format(departement=departement)


def valider_geojson(contenu: bytes) -> int:
    """Vérifie la structure du GeoJSON ; renvoie le nombre de communes."""
    try:
        donnees = json.loads(contenu)
    except ValueError as e:
        raise ErreurDonnees(f"GeoJSON communes illisible : {e}") from e
    if not isinstance(donnees, dict) or donnees.get("type") != "FeatureCollection":
        raise ErreurDonnees("GeoJSON communes : FeatureCollection attendue")
    entites = donnees.get("features") or []
    if not entites:
        raise ErreurDonnees("GeoJSON communes : aucune commune")
    for entite in entites:
        manquantes = PROPRIETES_REQUISES - set(entite.get("properties") or {})
        if manquantes:
            raise ErreurDonnees(f"propriétés communes manquantes : {sorted(manquantes)}")
        if not entite.get("geometry"):
            raise ErreurDonnees(f"commune sans contour : {entite['properties'].get('code')}")
    return len(entites)


def telecharger_communes(
    config: dict,
    client: httpx.Client | None = None,
    dossier: Path = DOSSIER_RAW,
    ecraser: bool = False,
) -> list[Path]:
    """Télécharge un GeoJSON par département ; renvoie les chemins écrits."""
    propre = client is None
    client = client or httpx.Client(timeout=120, follow_redirects=True)
    ecrits = []
    try:
        for dep in config["perimetre"]["departements"]:
            cible = dossier / f"communes_{dep}.geojson"
            if cible.exists() and not ecraser:
                continue
            reponse = client.get(construire_url(config, dep))
            reponse.raise_for_status()
            valider_geojson(reponse.content)
            ecrire_atomique(cible, reponse.content)
            ecrits.append(cible)
    finally:
        if propre:
            client.close()
    return ecrits


def resumer_fichier(chemin: Path) -> str:
    """Chemin, taille et nombre de communes. Jamais le contenu."""
    n = valider_geojson(chemin.read_bytes())
    return f"{chemin} | {chemin.stat().st_size / 1e6:.2f} Mo | {n} communes"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Télécharge les contours des communes (API Géo)")
    parser.add_argument("--departement", help="un département (défaut : tout le périmètre)")
    parser.add_argument("--ecraser", action="store_true", help="retélécharger un fichier déjà présent")
    args = parser.parse_args(argv)

    config = charger_config()
    if args.departement:
        config = {**config, "perimetre": {**config["perimetre"], "departements": [args.departement]}}

    telecharger_communes(config, ecraser=args.ecraser)
    for dep in config["perimetre"]["departements"]:
        print(resumer_fichier(DOSSIER_RAW / f"communes_{dep}.geojson"))


if __name__ == "__main__":
    main()
