"""Étape C : sinistralité CatNat, quadrants et fichiers finaux de la carte (data/processed/).

À partir de primes_communes.parquet (étape B), de l'archive GASPAR et des contours des
communes, produit communes.parquet (une ligne par commune des contours), contours.geojson
et departements.geojson, et complète resume_global.json. Agrégats par commune seulement.

    uv run python -m retrait_gonflement.model.communes_finales
"""

import argparse
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from retrait_gonflement.data import catnat
from retrait_gonflement.data.commun import RACINE, ErreurDonnees, charger_config
from retrait_gonflement.data.gaspar import DOSSIER_RAW as DOSSIER_GASPAR, NOM_ARCHIVE
from retrait_gonflement.model.modele_global import CHEMIN_RESUME, ecrire_resume
from retrait_gonflement.model.primes_communes import CHEMIN_PRIMES, tableau
from retrait_gonflement.spatial import contours

DOSSIER_PROCESSED = RACINE / "data" / "processed"
DOSSIER_CONTOURS_RAW = RACINE / "data" / "raw" / "communes"

QUADRANTS = {
    (True, "decote"): "Risque intégré",
    (True, "pas_de_decote"): "Angle mort",
    (False, "decote"): "Décote à expliquer",
    (False, "pas_de_decote"): "Cohérent",
}
COLONNES = [
    "code_insee", "nom", "departement", "n_ventes", "n_fort", "n_moyen", "n_faible", "n_hors_zone",
    "prix_m2_median", "statut", "motif", "prime", "ic_bas", "ic_haut", "significatif", "statut_decote",
    "catnat_total", "catnat_depuis_2015", "catnat_dernier", "sinistralite_sup_mediane", "quadrant",
]


def quadrant(sinistralite_sup: bool, statut_decote: str) -> str | None:
    """Quadrant de la vue 2 ; None pour une commune « indéterminé » (comptée à part)."""
    return QUADRANTS.get((bool(sinistralite_sup), statut_decote))


def assembler(base: pd.DataFrame, primes: pd.DataFrame, sinistres: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """communes.parquet : base (code_insee, nom, departement) + primes + CatNat + quadrants.

    Renvoie aussi la médiane de `catnat_depuis_2015` parmi les communes estimables. Une commune
    sans aucune vente est « non estimable » (effectifs insuffisants), avec des effectifs à 0 ;
    une commune sans arrêté a 0 arrêté.
    """
    colonnes_primes = [c for c in primes.columns if c not in ("departement", "erreurs", "n_sections")]
    communes = base.merge(primes[colonnes_primes], on="code_insee", how="left")
    for colonne in ("n_ventes", "n_fort", "n_moyen", "n_faible", "n_hors_zone"):
        communes[colonne] = communes[colonne].fillna(0).astype(int)
    sans_vente = communes["statut"].isna()
    communes.loc[sans_vente, "statut"] = "non_estimable"
    communes.loc[sans_vente, "motif"] = "effectifs_insuffisants"

    communes = communes.merge(sinistres.rename_axis("code_insee").reset_index(), on="code_insee", how="left")
    for colonne in ("catnat_total", "catnat_depuis_2015"):
        communes[colonne] = communes[colonne].fillna(0).astype(int)

    estimable = communes["statut"] == "estimable"
    mediane = float(communes.loc[estimable, "catnat_depuis_2015"].median())
    sup = pd.Series(pd.NA, index=communes.index, dtype="boolean")
    sup[estimable] = (communes.loc[estimable, "catnat_depuis_2015"] > mediane).to_numpy()
    communes["sinistralite_sup_mediane"] = sup
    communes["quadrant"] = [
        quadrant(s, d) if pd.notna(s) and isinstance(d, str) else None
        for s, d in zip(communes["sinistralite_sup_mediane"], communes["statut_decote"])
    ]
    return communes[COLONNES], mediane


def resume_catnat(communes: pd.DataFrame, mediane: float, rapprochement: dict, annee_max: int | None, depuis: int) -> dict:
    """Clés ajoutées à resume_global.json (docs/method.md, section 8)."""
    quadrants = communes["quadrant"].value_counts()
    return {
        "mediane_sinistralite": mediane,
        "n_par_quadrant": {nom: int(quadrants.get(nom, 0)) for nom in QUADRANTS.values()},
        "catnat": {
            "libelle": "Sécheresse",
            "periode": f"{depuis}-{annee_max}" if annee_max else None,
            "annee_debut_max": annee_max,
            "codes_perimetre": rapprochement,
        },
    }


def distribution(valeurs: pd.Series) -> str:
    q = valeurs.quantile([0, 0.25, 0.5, 0.75, 1])
    return (f"min {q[0]:.0f} | Q1 {q[0.25]:.0f} | médiane {q[0.5]:.0f} | Q3 {q[0.75]:.0f} | max {q[1]:.0f} | "
            f"{int((valeurs == 0).sum())} communes à 0")


def lignes_resume(communes, rapprochement, evt, primes_non_rapprochees, mediane, tailles) -> list[str]:
    estimables = communes[communes["statut"] == "estimable"]
    n_quadrants = communes["quadrant"].value_counts()
    sortie = [
        "Arrêtés CatNat « Sécheresse » (événements distincts commune × date_debut × date_fin)",
        f"  périmètre : {int((evt['code_commune'].str[:2].isin(set(communes['departement']))).sum())} événements ; "
        f"date_debut la plus récente : {evt['date_debut'].max():%Y-%m-%d}",
        f"  codes GASPAR du périmètre : {rapprochement['n_codes_perimetre']} ; non rapprochés des contours : "
        f"{rapprochement['n_codes_non_rapproches']} ({rapprochement['n_evenements_non_rapproches']} événements)",
        f"  communes avec ventes absentes des contours : {primes_non_rapprochees['communes']} "
        f"({primes_non_rapprochees['ventes']} ventes)",
        "",
        f"catnat_depuis_2015, {len(communes)} communes : {distribution(communes['catnat_depuis_2015'])}",
        f"catnat_depuis_2015, {len(estimables)} communes estimables : {distribution(estimables['catnat_depuis_2015'])}",
        f"Seuil de sinistralité (médiane des communes estimables) : {mediane:g} arrêtés depuis 2015",
        "",
        "Communes par quadrant et par département",
    ]
    lignes = []
    for dep, groupe in communes.groupby("departement"):
        q = groupe["quadrant"].value_counts()
        lignes.append([dep, *[int(q.get(nom, 0)) for nom in QUADRANTS.values()],
                       int((groupe["statut_decote"] == "indetermine").sum()),
                       int((groupe["statut"] == "non_estimable").sum())])
    total = ["TOTAL"] + [sum(ligne[i] for ligne in lignes) for i in range(1, 7)]
    sortie += tableau(["dep", *QUADRANTS.values(), "indetermine", "non_estimable"], [*lignes, total])
    sortie += ["", f"Quadrants : {', '.join(f'{nom} {int(n_quadrants.get(nom, 0))}' for nom in QUADRANTS.values())}",
               "", "Fichiers produits"]
    sortie += [f"  {nom} : {taille / 1e6:.2f} Mo" for nom, taille in tailles.items()]
    return sortie


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="CatNat, quadrants et fichiers finaux de la carte")
    parser.add_argument("--sortie", type=Path, default=DOSSIER_PROCESSED)
    parser.add_argument("--primes", type=Path, default=CHEMIN_PRIMES)
    parser.add_argument("--resume", type=Path, default=CHEMIN_RESUME)
    parser.add_argument("--fusions", type=Path, default=catnat.FUSIONS_PAR_DEFAUT)
    args = parser.parse_args(argv)

    config = charger_config()
    departements = config["perimetre"]["departements"]
    depuis = int(config["sources"]["gaspar"]["depuis_annee"])
    try:
        # contours : communes du périmètre, simplifiées en Lambert-93
        liste = contours.lire_communes(DOSSIER_CONTOURS_RAW, departements)
        con = duckdb.connect()
        con.execute("LOAD spatial")
        contours.simplifier(con, liste, config["carte"]["tolerance_simplification_m"])
        fichiers = contours.exporter(
            con, args.sortie, config["carte"]["tolerance_simplification_m"], config["carte"]["decimales_coordonnees"]
        )
        con.close()
        base = pd.DataFrame(liste)[["code", "nom", "departement"]].rename(columns={"code": "code_insee"})

        # CatNat : événements rapprochés des contours, puis comptés par commune
        evt = catnat.evenements(
            catnat.lire_secheresse(DOSSIER_GASPAR / NOM_ARCHIVE, config), catnat.charger_fusions(args.fusions)
        )
        rapprochement = catnat.rapprocher(evt, set(base["code_insee"]), departements)
        sinistres = catnat.compter_par_commune(evt, depuis)

        primes = pd.read_parquet(args.primes)
        absentes = ~primes["code_insee"].isin(base["code_insee"])
        primes_non_rapprochees = {"communes": int(absentes.sum()), "ventes": int(primes.loc[absentes, "n_ventes"].sum())}
        communes, mediane = assembler(base, primes[~absentes], sinistres)
    except (ErreurDonnees, FileNotFoundError, duckdb.Error) as e:
        raise SystemExit(f"Erreur : {e}") from e

    chemin_communes = args.sortie / "communes.parquet"
    communes.to_parquet(chemin_communes, index=False)
    annee_max = int(evt["date_debut"].max().year) if len(evt) else None
    ecrire_resume(args.resume, resume_catnat(communes, mediane, rapprochement, annee_max, depuis))
    tailles = {p.name: p.stat().st_size for p in (chemin_communes, *fichiers)}
    print("\n".join(lignes_resume(communes, rapprochement, evt, primes_non_rapprochees, mediane, tailles)))


if __name__ == "__main__":
    main()
