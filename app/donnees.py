"""Lecture de data/processed/ : le seul module de l'app qui touche aux fichiers.

Aucun calcul, aucun appel réseau. Chaque `lire_*` contrôle son fichier et lève
ErreurDonneesApp avec un message clair ; les `charger_*` ajoutent la mise en cache.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import streamlit as st

RACINE = Path(__file__).resolve().parents[1]
VARIABLE_DOSSIER = "RG_DONNEES"

COLONNES_COMMUNES = (
    "code_insee", "nom", "departement", "n_ventes", "n_fort", "n_moyen", "n_faible", "n_hors_zone",
    "prix_m2_median", "statut", "motif", "prime", "ic_bas", "ic_haut", "significatif", "statut_decote",
    "catnat_total", "catnat_depuis_2015", "catnat_dernier", "sinistralite_sup_mediane", "quadrant",
)
# Clés de premier niveau de resume_global.json dont l'app a besoin
CLES_RESUME = (
    "periode", "modeles_globaux", "date_generation", "n_communes_estimables", "n_significatives_decote",
    "n_significatives_prime", "n_attendu_hasard", "n_attendu_par_sens", "n_decote", "n_pas_de_decote",
    "n_indetermine", "seuil_pas_de_decote", "seuil_prix_median", "primes_communes", "mediane_sinistralite",
    "n_par_quadrant", "catnat", "nettoyage", "sources",
)


class ErreurDonneesApp(Exception):
    """Fichier ou champ manquant dans data/processed/ (message affiché tel quel à l'écran)."""


@dataclass(frozen=True)
class Donnees:
    communes: pd.DataFrame
    contours: dict
    departements: dict
    resume: dict
    notes: dict


def dossier() -> Path:
    """data/processed/, ou le dossier de la variable RG_DONNEES (tests)."""
    return Path(os.environ.get(VARIABLE_DOSSIER) or RACINE / "data" / "processed")


def _chemin(dossier_: Path, nom: str) -> Path:
    chemin = Path(dossier_) / nom
    if not chemin.is_file():
        raise ErreurDonneesApp(f"Fichier manquant : data/processed/{nom}. Lancez le pipeline pour le produire.")
    return chemin


def _json(dossier_: Path, nom: str) -> dict:
    try:
        return json.loads(_chemin(dossier_, nom).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ErreurDonneesApp(f"Fichier illisible : data/processed/{nom} ({e.msg}).") from e


def lire_communes(dossier_: Path) -> pd.DataFrame:
    communes = pd.read_parquet(_chemin(dossier_, "communes.parquet"))
    manquantes = [c for c in COLONNES_COMMUNES if c not in communes.columns]
    if manquantes:
        raise ErreurDonneesApp(f"Colonnes absentes de communes.parquet : {', '.join(manquantes)}.")
    return communes


def lire_geojson(dossier_: Path, nom: str, propriete: str | None = None) -> dict:
    geojson = _json(dossier_, nom)
    entites = geojson.get("features")
    if not entites:
        raise ErreurDonneesApp(f"Aucune entité dans data/processed/{nom}.")
    if propriete and any(propriete not in (e.get("properties") or {}) for e in entites):
        raise ErreurDonneesApp(f"Propriété « {propriete} » absente de data/processed/{nom}.")
    return geojson


def lire_resume(dossier_: Path) -> dict:
    resume = _json(dossier_, "resume_global.json")
    manquantes = [c for c in CLES_RESUME if c not in resume]
    principal = resume.get("modeles_globaux", {}).get("principal", {})
    if "contraste_fort_moins_moyen" not in principal:
        manquantes.append("modeles_globaux.principal.contraste_fort_moins_moyen")
    if "fort" not in resume.get("modeles_globaux", {}).get("fort_contre_reste", {}).get("coefficients", {}):
        manquantes.append("modeles_globaux.fort_contre_reste.coefficients.fort")
    if manquantes:
        raise ErreurDonneesApp(f"Clés absentes de resume_global.json : {', '.join(manquantes)}.")
    return resume


def lire_notes(dossier_: Path) -> dict[str, str]:
    """Notes des agents (bonus) : {code_insee: note}, vide si le fichier est absent."""
    chemin = Path(dossier_) / "notes_communes.parquet"
    if not chemin.is_file():
        return {}
    notes = pd.read_parquet(chemin)
    if not {"code_insee", "note"} <= set(notes.columns):
        raise ErreurDonneesApp("Colonnes code_insee et note absentes de notes_communes.parquet.")
    return dict(zip(notes["code_insee"], notes["note"]))


@st.cache_data(show_spinner=False)
def charger_communes(dossier_: str) -> pd.DataFrame:
    return lire_communes(Path(dossier_))


@st.cache_data(show_spinner=False)
def charger_contours(dossier_: str) -> dict:
    return lire_geojson(Path(dossier_), "contours.geojson", "code_insee")


@st.cache_data(show_spinner=False)
def charger_departements(dossier_: str) -> dict:
    return lire_geojson(Path(dossier_), "departements.geojson")


@st.cache_data(show_spinner=False)
def charger_resume(dossier_: str) -> dict:
    return lire_resume(Path(dossier_))


@st.cache_data(show_spinner=False)
def charger_notes(dossier_: str) -> dict[str, str]:
    return lire_notes(Path(dossier_))


def charger_tout() -> Donnees:
    d = str(dossier())
    return Donnees(charger_communes(d), charger_contours(d), charger_departements(d), charger_resume(d), charger_notes(d))
