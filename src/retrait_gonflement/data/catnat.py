"""Sinistralité CatNat sécheresse par commune, à partir de l'archive GASPAR (data/raw/gaspar/).

Seul le libellé de risque de la config (« Sécheresse ») est retenu. Un événement = un
triplet distinct (commune, date_debut, date_fin) : plusieurs arrêtés (reconnaissance,
modificatif) pour le même événement ne comptent qu'une fois. « Depuis 2015 » se lit sur
date_debut. Les codes de communes fusionnées peuvent être rapprochés par un fichier
optionnel `config/fusions_communes.csv` (colonnes ancien_code, nouveau_code).
"""

import csv
import zipfile
from pathlib import Path

import pandas as pd

from retrait_gonflement.data.commun import RACINE, ErreurDonnees
from retrait_gonflement.data.gaspar import COLONNES_REQUISES, SEPARATEUR, trouver_table

FUSIONS_PAR_DEFAUT = RACINE / "config" / "fusions_communes.csv"


def _dates(serie: pd.Series, nom: str) -> pd.Series:
    """Dates AAAA-MM-JJ (les 10 premiers caractères) ; un format inattendu est refusé, pas deviné."""
    texte = serie.fillna("").str.strip().str[:10]
    dates = pd.to_datetime(texte.where(texte != ""), format="%Y-%m-%d", errors="coerce")
    illisibles = int((dates.isna() & (texte != "")).sum())
    if illisibles:
        raise ErreurDonnees(f"GASPAR : {illisibles} valeurs de {nom} illisibles (format attendu AAAA-MM-JJ)")
    return dates


def lire_secheresse(archive: Path, config: dict) -> pd.DataFrame:
    """Lignes de la table des arrêtés pour le libellé retenu : code_commune, date_debut, date_fin."""
    libelle = config["sources"]["gaspar"]["libelle_risque"]
    try:
        with zipfile.ZipFile(archive) as zf:
            nom = trouver_table(zf, config["sources"]["gaspar"]["table"])
            with zf.open(nom) as f:
                table = pd.read_csv(
                    f, sep=SEPARATEUR, dtype=str, usecols=sorted(COLONNES_REQUISES), encoding="utf-8-sig"
                )
    except zipfile.BadZipFile as e:
        raise ErreurDonnees(f"archive GASPAR illisible : {e}") from e
    table = table[table["lib_risque_jo"].str.strip() == libelle]
    return pd.DataFrame({
        "code_commune": table["code_commune"].str.strip(),
        "date_debut": _dates(table["date_debut"], "date_debut"),
        "date_fin": _dates(table["date_fin"], "date_fin"),
    })


def charger_fusions(chemin: Path = FUSIONS_PAR_DEFAUT) -> dict[str, str]:
    """Table ancien code -> nouveau code ; vide si le fichier n'existe pas."""
    if not chemin.exists():
        return {}
    with chemin.open(encoding="utf-8-sig", newline="") as f:
        lecteur = csv.DictReader(f)
        if not lecteur.fieldnames or {"ancien_code", "nouveau_code"} - set(lecteur.fieldnames):
            raise ErreurDonnees(f"{chemin.name} : colonnes ancien_code et nouveau_code attendues")
        return {ligne["ancien_code"].strip(): ligne["nouveau_code"].strip() for ligne in lecteur}


def evenements(arrets: pd.DataFrame, fusions: dict[str, str] | None = None) -> pd.DataFrame:
    """Événements distincts (commune, début, fin) après rapprochement des communes fusionnées."""
    evt = arrets.copy()
    if fusions:
        evt["code_commune"] = evt["code_commune"].map(lambda c: fusions.get(c, c))
    return evt.drop_duplicates(["code_commune", "date_debut", "date_fin"]).reset_index(drop=True)


def compter_par_commune(evt: pd.DataFrame, depuis_annee: int) -> pd.DataFrame:
    """catnat_total, catnat_depuis_2015 (sur date_debut) et catnat_dernier (fin du dernier événement)."""
    evt = evt.assign(
        depuis=evt["date_debut"] >= pd.Timestamp(depuis_annee, 1, 1),
        fin=evt["date_fin"].fillna(evt["date_debut"]),
    )
    groupes = evt.groupby("code_commune")
    return pd.DataFrame({
        "catnat_total": groupes.size(),
        "catnat_depuis_2015": groupes["depuis"].sum().astype(int),
        "catnat_dernier": groupes["fin"].max(),
    })


def rapprocher(evt: pd.DataFrame, codes_contours: set[str], departements: list[str]) -> dict:
    """Codes GASPAR du périmètre (départements de la config) absents des contours : comptages."""
    codes = pd.Series(evt["code_commune"].unique())
    perimetre = codes[codes.str[:2].isin(departements)]
    non = perimetre[~perimetre.isin(codes_contours)]
    return {
        "n_codes_perimetre": int(len(perimetre)),
        "n_codes_non_rapproches": int(len(non)),
        "n_evenements_non_rapproches": int(evt["code_commune"].isin(non).sum()),
    }
