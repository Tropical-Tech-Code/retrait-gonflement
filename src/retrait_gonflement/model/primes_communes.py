"""Étape B : prime « fort contre tout le reste » de chaque commune estimable.

Une seule régression, la spécification du modèle `fort_contre_reste` (docs/method.md,
section 6) : un terme « fort » propre à chaque commune qui passe les seuils, un terme
commun pour les ventes « fort » des autres communes, mêmes contrôles et mêmes effets fixes
commune × trimestre. Les erreurs sont groupées par section cadastrale (10 premiers
caractères de id_parcelle), puisqu'une prime communale ne repose que sur une commune ;
une commune qui compte trop peu de sections prend des erreurs robustes HC1.

Sorties : data/processed/primes_communes.parquet (une ligne par commune avec des ventes) et
les résultats agrégés dans data/processed/resume_global.json. Aucune vente individuelle.

    uv run python -m retrait_gonflement.model.primes_communes
"""

import argparse
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pyfixest as pf
from scipy import stats

from retrait_gonflement.data.commun import RACINE, ErreurDonnees, charger_config
from retrait_gonflement.data.nettoyage_dvf import BASE_PAR_DEFAUT
from retrait_gonflement.model.modele_global import (
    CHEMIN_RESUME,
    colonnes_controles,
    ecrire_resume,
    preparer,
    retirer_singletons,
)

CHEMIN_PRIMES = RACINE / "data" / "processed" / "primes_communes.parquet"
LONGUEUR_SECTION = 10  # code commune (5) + préfixe (3) + section (2) dans id_parcelle
MOTIFS = ("une_seule_zone", "effectifs_insuffisants")


def charger(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Ventes de ventes_rga avec les variables du modèle et la section cadastrale."""
    df = con.execute(
        "SELECT code_commune, code_departement, id_parcelle, date_mutation, annee, prix_m2, "
        "surface_bati, surface_terrain, nombre_pieces, rga_2020, rga_2026 FROM ventes_rga"
    ).df()
    return preparer(df)


def ajouter_section(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    section = df["id_parcelle"].astype("string").str[:LONGUEUR_SECTION]
    df["section"] = section.fillna(df["code_commune"].astype("string"))
    return df


def classer_communes(df: pd.DataFrame, estimation: dict) -> pd.DataFrame:
    """Effectifs par commune, estimable ou non, et motif (docs/method.md, section 6)."""
    ventes = df.assign(reference=(df["rga_2020"] != 3))
    communes = ventes.groupby("code_commune").agg(
        departement=("code_departement", "first"),
        n_ventes=("prix_m2", "size"),
        n_fort=("rga_2020", lambda s: int((s == 3).sum())),
        n_moyen=("rga_2020", lambda s: int((s == 2).sum())),
        n_faible=("rga_2020", lambda s: int((s == 1).sum())),
        n_hors_zone=("rga_2020", lambda s: int((s == 0).sum())),
        prix_m2_median=("prix_m2", "median"),
    )
    communes.loc[communes["n_ventes"] < estimation["seuil_prix_median"], "prix_m2_median"] = np.nan
    n_reference = communes["n_ventes"] - communes["n_fort"]
    une_zone = (communes["n_fort"] == 0) | (n_reference == 0)
    insuffisant = (
        (communes["n_fort"] < estimation["min_ventes_fort"])
        | (n_reference < estimation["min_ventes_reference"])
        | (communes["n_ventes"] < estimation["min_ventes_total"])
    )
    communes["motif"] = np.where(une_zone, "une_seule_zone", np.where(insuffisant, "effectifs_insuffisants", None))
    communes["statut"] = np.where(communes["motif"].isna(), "estimable", "non_estimable")
    return communes


def statut_decote(ic_bas: float, ic_haut: float, seuil: float) -> str:
    """« decote » : IC entièrement sous 0 ; « pas_de_decote » : borne basse au-dessus du seuil."""
    if ic_haut < 0:
        return "decote"
    if ic_bas > seuil:
        return "pas_de_decote"
    return "indetermine"


def significatif(ic_bas: float, ic_haut: float) -> str:
    if ic_haut < 0:
        return "decote"
    if ic_bas > 0:
        return "prime"
    return "non"


def estimer_primes(df: pd.DataFrame, communes: pd.DataFrame, estimation: dict) -> pd.DataFrame:
    """Régression unique ; ajoute à `communes` prime, IC, statuts et type d'erreurs."""
    df = retirer_singletons(ajouter_section(df))
    estimables = list(communes.index[communes["statut"] == "estimable"])
    termes = {}
    for code in estimables:
        colonne = ((df["code_commune"] == code) & (df["fort"] == 1)).astype(float)
        if colonne.sum() > 0:
            termes[f"f_{code}"] = colonne
    autres = ((df["fort"] == 1) & ~df["code_commune"].isin(estimables)).astype(float)
    if autres.sum() > 0:
        termes["fort_autres"] = autres
    df = pd.concat([df, pd.DataFrame(termes, index=df.index)], axis=1)

    formule = f"log_prix ~ {' + '.join([*termes, *colonnes_controles(df)])} | ct"
    ajuste = pf.feols(formule, data=df, vcov={"CRV1": "section"})
    noms = [str(n) for n in ajuste._coefnames]
    beta = dict(zip(noms, np.asarray(ajuste._beta_hat, dtype=float)))
    se_groupee = dict(zip(noms, np.sqrt(np.diag(np.asarray(ajuste._vcov, dtype=float)))))
    ajuste.vcov("HC1")  # remplace la matrice de variance : à lire après les erreurs groupées
    se_hc1 = dict(zip(noms, np.sqrt(np.diag(np.asarray(ajuste._vcov, dtype=float)))))

    niveau = float(estimation["niveau_ic"])
    min_sections = int(estimation["min_sections_groupement"])
    seuil = float(estimation["seuil_pas_de_decote"])
    sections = df.groupby("code_commune")["section"].nunique()
    ventes = df.groupby("code_commune").size()

    resultats = communes.copy()
    for colonne in ("prime", "ic_bas", "ic_haut", "n_sections"):
        resultats[colonne] = np.nan
    for colonne in ("significatif", "statut_decote", "erreurs"):
        resultats[colonne] = None
    for code in estimables:
        terme = f"f_{code}"
        b = beta.get(terme)
        n_sections = int(sections.get(code, 0))
        groupees = n_sections >= min_sections
        se = (se_groupee if groupees else se_hc1).get(terme)
        if b is None or se is None or not np.isfinite(b) or not np.isfinite(se) or se <= 0:
            # coefficient écarté par pyfixest (colinéaire) ou sans variance : commune non estimable
            resultats.loc[code, ["statut", "motif"]] = ["non_estimable", "effectifs_insuffisants"]
            continue
        ddl = n_sections - 1 if groupees else int(ventes[code]) - 1
        marge = stats.t.ppf(1 - (1 - niveau) / 2, ddl) * se
        bas, haut = float(np.expm1(b - marge)), float(np.expm1(b + marge))
        resultats.loc[code, "prime"] = float(np.expm1(b))
        resultats.loc[code, "ic_bas"] = bas
        resultats.loc[code, "ic_haut"] = haut
        resultats.loc[code, "significatif"] = significatif(bas, haut)
        resultats.loc[code, "statut_decote"] = statut_decote(bas, haut, seuil)
        resultats.loc[code, "erreurs"] = "sections" if groupees else "hc1"
        resultats.loc[code, "n_sections"] = n_sections
    return resultats


def tests_multiples(communes: pd.DataFrame) -> dict:
    """Significatives observées contre attendues par hasard (5 % des communes estimables)."""
    estimables = communes[communes["statut"] == "estimable"]
    n = len(estimables)
    return {
        "n_communes_estimables": n,
        "n_significatives_decote": int((estimables["significatif"] == "decote").sum()),
        "n_significatives_prime": int((estimables["significatif"] == "prime").sum()),
        "n_attendu_hasard": round(0.05 * n, 3),
        "n_attendu_par_sens": round(0.025 * n, 3),
    }


def resume_json(communes: pd.DataFrame, estimation: dict) -> dict:
    estimables = communes[communes["statut"] == "estimable"]
    statuts = estimables["statut_decote"].value_counts()
    primes = estimables["prime"]
    par_dep = {}
    for dep, groupe in communes.groupby("departement"):
        est = groupe[groupe["statut"] == "estimable"]
        par_dep[str(dep)] = {
            "n_communes_avec_ventes": int(len(groupe)),
            "n_estimables": int(len(est)),
            "n_une_seule_zone": int((groupe["motif"] == "une_seule_zone").sum()),
            "n_effectifs_insuffisants": int((groupe["motif"] == "effectifs_insuffisants").sum()),
            "n_decote": int((est["statut_decote"] == "decote").sum()),
            "n_pas_de_decote": int((est["statut_decote"] == "pas_de_decote").sum()),
            "n_indetermine": int((est["statut_decote"] == "indetermine").sum()),
        }
    return {
        **tests_multiples(communes),
        "n_decote": int(statuts.get("decote", 0)),
        "n_pas_de_decote": int(statuts.get("pas_de_decote", 0)),
        "n_indetermine": int(statuts.get("indetermine", 0)),
        "seuil_pas_de_decote": float(estimation["seuil_pas_de_decote"]),
        "seuil_prix_median": int(estimation["seuil_prix_median"]),
        "primes_communes": {
            "definition": "fort contre tout le reste (niveaux 0+1+2), carte 2020",
            "seuils": {k: int(estimation[k]) for k in ("min_ventes_fort", "min_ventes_reference", "min_ventes_total")},
            "n_non_estimables": {m: int((communes["motif"] == m).sum()) for m in MOTIFS},
            "erreurs": {
                "min_sections_groupement": int(estimation["min_sections_groupement"]),
                "n_groupees_par_section": int((estimables["erreurs"] == "sections").sum()),
                "n_hc1": int((estimables["erreurs"] == "hc1").sum()),
            },
            "diagnostic_erreurs": diagnostic_erreurs(communes),
            "distribution_primes": {
                "q1": round(float(primes.quantile(0.25)), 6) if len(primes) else None,
                "mediane": round(float(primes.median()), 6) if len(primes) else None,
                "q3": round(float(primes.quantile(0.75)), 6) if len(primes) else None,
            },
            "par_departement": par_dep,
        },
    }


def tableau(entetes: list[str], lignes: list[list]) -> list[str]:
    cellules = [entetes] + [[str(c) for c in ligne] for ligne in lignes]
    largeurs = [max(len(ligne[i]) for ligne in cellules) for i in range(len(entetes))]
    return ["  ".join(c.rjust(largeurs[i]) for i, c in enumerate(ligne)) for ligne in cellules]


def diagnostic_erreurs(communes: pd.DataFrame) -> dict[str, dict]:
    """Communes estimables par type d'erreurs (sections / hc1) : statuts, significatives, largeur d'IC.

    `largeur_ic_mediane` = médiane de ic_haut − ic_bas (fraction de prime ; 0,25 = 25 points).
    Sert à vérifier que le repli HC1 n'explique pas l'excès de communes significatives.
    """
    estimables = communes[communes["statut"] == "estimable"]
    diagnostic = {}
    for type_erreurs in ("sections", "hc1"):
        groupe = estimables[estimables["erreurs"] == type_erreurs]
        n = len(groupe)
        decote = int((groupe["significatif"] == "decote").sum())
        prime = int((groupe["significatif"] == "prime").sum())
        diagnostic[type_erreurs] = {
            "n_estimables": n,
            "n_decote": int((groupe["statut_decote"] == "decote").sum()),
            "n_pas_de_decote": int((groupe["statut_decote"] == "pas_de_decote").sum()),
            "n_indetermine": int((groupe["statut_decote"] == "indetermine").sum()),
            "n_significatives_decote": decote,
            "n_significatives_prime": prime,
            "part_significatives": round((decote + prime) / n, 4) if n else None,
            "largeur_ic_mediane": round(float((groupe["ic_haut"] - groupe["ic_bas"]).median()), 4) if n else None,
            "ventes_mediane": float(groupe["n_ventes"].median()) if n else None,
        }
    return diagnostic


def lignes_diagnostic(diagnostic: dict[str, dict]) -> list[list]:
    """Lignes du tableau affiché (largeur d'IC en points de pourcentage)."""
    def pourcent(x, decimales=1):
        return "-" if x is None else f"{x * 100:.{decimales}f}"

    return [
        [type_erreurs, d["n_estimables"], d["n_decote"], d["n_pas_de_decote"], d["n_indetermine"],
         d["n_significatives_decote"], d["n_significatives_prime"],
         "-" if d["part_significatives"] is None else f"{pourcent(d['part_significatives'])} %",
         pourcent(d["largeur_ic_mediane"]),
         "-" if d["ventes_mediane"] is None else f"{d['ventes_mediane']:.0f}"]
        for type_erreurs, d in diagnostic.items()
    ]


def lignes_resume(communes: pd.DataFrame, resume: dict) -> list[str]:
    """Comptages et distribution : aucune ligne par commune."""
    entetes = ["dep", "avec_ventes", "estimables", "une_zone", "effectifs", "decote", "pas_decote",
               "indetermine", "signif_decote", "signif_prime"]
    lignes = []
    for dep, groupe in communes.groupby("departement"):
        est = groupe[groupe["statut"] == "estimable"]
        s = resume["primes_communes"]["par_departement"][str(dep)]
        lignes.append([dep, s["n_communes_avec_ventes"], s["n_estimables"], s["n_une_seule_zone"],
                       s["n_effectifs_insuffisants"], s["n_decote"], s["n_pas_de_decote"], s["n_indetermine"],
                       int((est["significatif"] == "decote").sum()), int((est["significatif"] == "prime").sum())])
    total = ["TOTAL"] + [sum(ligne[i] for ligne in lignes) for i in range(1, len(entetes))]
    sortie = ["Communes par statut et par département (prime = fort contre tout le reste, carte 2020)"]
    sortie += tableau(entetes, [*lignes, total])
    d = resume["primes_communes"]["distribution_primes"]
    e = resume["primes_communes"]["erreurs"]
    sortie += [
        "",
        f"Primes des {resume['n_communes_estimables']} communes estimables (exp(β) − 1) : "
        f"médiane {d['mediane'] * 100:+.2f} %, quartiles [{d['q1'] * 100:+.2f} ; {d['q3'] * 100:+.2f}] %",
        f"Significatives : {resume['n_significatives_decote']} en décote et {resume['n_significatives_prime']} en prime ; "
        f"attendues par hasard : {resume['n_attendu_hasard']} au total, {resume['n_attendu_par_sens']} par sens",
        f"Erreurs : {e['n_groupees_par_section']} communes groupées par section, "
        f"{e['n_hc1']} en HC1 (moins de {e['min_sections_groupement']} sections)",
        "",
        "Diagnostic par type d'erreurs (communes estimables ; largeur d'IC = médiane de ic_haut − ic_bas,",
        "en points de pourcentage de prime ; ventes = médiane des ventes par commune)",
    ]
    sortie += tableau(
        ["erreurs", "estimables", "decote", "pas_decote", "indetermine", "signif_decote", "signif_prime",
         "part_signif", "largeur_ic", "ventes"],
        lignes_diagnostic(resume["primes_communes"]["diagnostic_erreurs"]),
    )
    return sortie


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Primes par commune : fort contre tout le reste")
    parser.add_argument("--base", type=Path, default=BASE_PAR_DEFAUT)
    parser.add_argument("--sortie", type=Path, default=CHEMIN_PRIMES)
    parser.add_argument("--resume", type=Path, default=CHEMIN_RESUME)
    args = parser.parse_args(argv)

    estimation = charger_config()["estimation"]
    con = duckdb.connect(str(args.base), read_only=True)
    try:
        df = charger(con)
    except duckdb.Error as e:
        raise SystemExit(f"Erreur : {e}") from e
    finally:
        con.close()
    try:
        communes = estimer_primes(df, classer_communes(df, estimation), estimation)
    except ErreurDonnees as e:
        raise SystemExit(f"Erreur : {e}") from e

    resume = resume_json(communes, estimation)
    sortie = communes.rename_axis("code_insee").reset_index()
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.to_parquet(args.sortie, index=False)
    ecrire_resume(args.resume, resume)
    print("\n".join(lignes_resume(communes, resume)))


if __name__ == "__main__":
    main()
