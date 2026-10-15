"""Éléments partagés par les connecteurs : config, erreur, écriture atomique."""

import tomllib
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
CONFIG_PAR_DEFAUT = RACINE / "config" / "perimetre.toml"


class ErreurDonnees(Exception):
    """Données reçues inattendues (colonnes manquantes, fichier illisible, URL vide)."""


def charger_config(chemin: Path = CONFIG_PAR_DEFAUT) -> dict:
    with open(chemin, "rb") as f:
        return tomllib.load(f)


def url_configuree(config: dict, source: str) -> str:
    """URL d'une source ; refuse une URL vide (source non confirmée)."""
    modele = config["sources"][source]["url"]
    if not modele:
        raise ErreurDonnees(f"URL vide dans la config pour la source « {source} »")
    return modele


def ecrire_atomique(cible: Path, contenu: bytes) -> None:
    """Écrit dans un .tmp puis renomme : jamais de fichier à moitié écrit."""
    cible.parent.mkdir(parents=True, exist_ok=True)
    temporaire = cible.with_suffix(cible.suffix + ".tmp")
    temporaire.write_bytes(contenu)
    temporaire.replace(cible)
