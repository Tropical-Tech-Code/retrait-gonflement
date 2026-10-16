"""Modèle global (étape A) : décote moyenne des maisons en zone « moyen » et « fort ».

Régression de log(prix au m²) sur les indicatrices d'exposition (carte 2020 ; référence =
hors zone argileuse + faible), des contrôles de taille et un effet fixe commune × trimestre,
erreurs groupées par commune (docs/method.md, section 5). Quatre estimations : le modèle
principal et trois variantes (sans les ventes proches d'une limite de zone, placebo
« bascule », réforme 2025). Le résultat est écrit dans data/processed/resume_global.json :
coefficients et effectifs seulement, jamais une vente.

    uv run python -m retrait_gonflement.model.modele_global
"""

import argparse
import json
from datetime import date
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pyfixest as pf
from scipy import stats

from retrait_gonflement.data.commun import RACINE, ErreurDonnees, charger_config
from retrait_gonflement.data.nettoyage_dvf import BASE_PAR_DEFAUT

CHEMIN_RESUME = RACINE / "data" / "processed" / "resume_global.json"
ANNEE_REFORME = 2025
STATUT_PLACEBO = "indicatif, faible puissance ({n_ventes} ventes, {n_communes} communes)"
STATUT_REFORME = "indice : une seule année après la réforme"


def charger(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Colonnes de ventes_rga utiles au modèle, plus les variables dérivées."""
    df = con.execute(
        "SELECT code_commune, date_mutation, annee, prix_m2, surface_bati, surface_terrain, "
        "nombre_pieces, rga_2020, rga_2026, proche_limite_2020 FROM ventes_rga"
    ).df()
    return preparer(df)


def preparer(df: pd.DataFrame) -> pd.DataFrame:
    """Variables du modèle (docs/method.md, section 5)."""
    df = df.copy()
    trimestre = pd.to_datetime(df["date_mutation"]).dt.quarter
    df["ct"] = df["code_commune"].astype(str) + "-" + df["annee"].astype(int).astype(str) + "T" + trimestre.astype(str)
    df["log_prix"] = np.log(df["prix_m2"].astype(float))
    df["log_surface"] = np.log(df["surface_bati"].astype(float))
    df["log_terrain"] = np.log1p(df["surface_terrain"].astype(float))
    df["terrain_nul"] = (df["surface_terrain"] == 0).astype(float)
    df["moyen"] = (df["rga_2020"] == 2).astype(float)
    df["fort"] = (df["rga_2020"] == 3).astype(float)
    df["bascule"] = ((df["rga_2020"] != 3) & (df["rga_2026"] == 3)).astype(float)
    df["fort_2025"] = df["fort"] * (df["annee"] == ANNEE_REFORME)
    # Nombre de pièces : 1 à 5, puis « 6 et plus » ; 0 ou absent = « inconnu » (colonne pieces_0)
    pieces = df["nombre_pieces"].fillna(0).clip(lower=0, upper=6).astype(int)
    for k in range(7):
        df[f"pieces_{k}"] = (pieces == k).astype(float)
    return df


def retirer_singletons(df: pd.DataFrame) -> pd.DataFrame:
    """Retire les ventes seules dans leur commune × trimestre : elles n'informent pas l'estimation."""
    return df[df.groupby("ct")["ct"].transform("size") > 1]


def _arrondi(x: float) -> float:
    return round(float(x), 6)


def colonnes_controles(df: pd.DataFrame) -> list[str]:
    """Contrôles communs à tous les modèles (taille de la maison, terrain, nombre de pièces).

    Indicatrices de pièces : on écarte celles qui sont constantes, et la plus fréquente
    sert de référence (l'effet fixe absorbe le niveau commun).
    """
    pieces = [c for c in (f"pieces_{k}" for k in range(7)) if 0 < df[c].sum() < len(df)]
    if pieces:
        pieces.remove(max(pieces, key=lambda c: df[c].sum()))
    return ["log_surface", "log_terrain", "terrain_nul", *pieces]


def estimer(df: pd.DataFrame, termes: list[str]) -> dict:
    """Une régression ; renvoie coefficients des `termes`, effectifs et nombre de communes."""
    df = retirer_singletons(df)
    controles = colonnes_controles(df)
    for terme in termes:
        if df[terme].sum() == 0:
            raise ErreurDonnees(f"aucune vente pour le terme « {terme} »")
    formule = f"log_prix ~ {' + '.join([*termes, *controles])} | ct"
    ajuste = pf.feols(formule, data=df, vcov={"CRV1": "code_commune"})
    table = ajuste.tidy()
    coefficients = {}
    for terme in termes:
        ligne = table.loc[terme]
        coefficients[terme] = {
            **_resultat(float(ligne["Estimate"]), float(ligne["Std. Error"]), ajuste._df_t),
            "n_ventes_terme": int(df[terme].sum()),
        }
    resultat = {
        "n_ventes": int(len(df)),
        "n_communes": int(df["code_commune"].nunique()),
        "coefficients": coefficients,
    }
    if "moyen" in termes and "fort" in termes:
        resultat["contraste_fort_moins_moyen"] = _contraste(ajuste, "fort", "moyen")
    return resultat


def _resultat(beta: float, erreur_std: float, ddl: float) -> dict:
    """β, erreur standard, IC à 95 % (loi de Student, ddl = communes − 1), effet exp(β) − 1."""
    marge = stats.t.ppf(0.975, ddl) * erreur_std
    return {
        "beta": _arrondi(beta),
        "erreur_std": _arrondi(erreur_std),
        "ic95_beta": [_arrondi(beta - marge), _arrondi(beta + marge)],
        "effet": _arrondi(np.expm1(beta)),
        "ic95_effet": [_arrondi(np.expm1(beta - marge)), _arrondi(np.expm1(beta + marge))],
        "p_valeur": _arrondi(2 * stats.t.sf(abs(beta / erreur_std), ddl)),
    }


def _contraste(ajuste, terme: str, reference: str) -> dict:
    """β_terme − β_reference ; variance = V(a) + V(b) − 2 Cov(a, b), matrice groupée par commune."""
    noms = [str(n) for n in ajuste._coefnames]
    i, j = noms.index(terme), noms.index(reference)
    beta = np.asarray(ajuste._beta_hat, dtype=float)
    vcov = np.asarray(ajuste._vcov, dtype=float)
    variance = vcov[i, i] + vcov[j, j] - 2 * vcov[i, j]
    return _resultat(beta[i] - beta[j], float(np.sqrt(variance)), ajuste._df_t)


def modeles_globaux(df: pd.DataFrame) -> dict:
    """Modèle principal et trois variantes. `effet` = exp(β) − 1 (fraction : −0,05 = −5 %)."""
    principal = estimer(df, ["moyen", "fort"])
    sans_limite = estimer(df[~df["proche_limite_2020"].astype(bool)], ["moyen", "fort"])
    sans_limite["note"] = "sans les ventes à moins de 50 m d'une limite de zone"

    # Placebo : ventes non « fort » en 2020 et « fort » en 2026, comptées sur l'échantillon utilisé
    bascule_df = retirer_singletons(df)
    n_bascule = int(bascule_df["bascule"].sum())
    n_communes_bascule = int(bascule_df.loc[bascule_df["bascule"] == 1, "code_commune"].nunique())
    try:
        placebo = estimer(df, ["moyen", "fort", "bascule"])
        placebo["statut"] = STATUT_PLACEBO.format(n_ventes=n_bascule, n_communes=n_communes_bascule)
        placebo["avertissements"] = [
            f"l'IC repose sur {n_communes_bascule} communes : les erreurs groupées par commune "
            "sont peu fiables avec si peu de groupes",
        ]
        if placebo["coefficients"]["bascule"]["beta"] > 0:
            placebo["avertissements"].append(
                "le signe positif suggère une hétérogénéité de quartiers au sein des communes "
                "(écarts non causaux)"
            )
    except ErreurDonnees as e:
        placebo = {"statut": f"non estimable : {e}"}

    reforme = estimer(df, ["moyen", "fort", "fort_2025"])
    reforme["statut"] = STATUT_REFORME

    # Une seule indicatrice « fort » : référence = niveaux 0, 1 et 2, comme la prime par commune
    fort_contre_reste = estimer(df, ["fort"])
    fort_contre_reste["note"] = "fort contre tout le reste (niveaux 0+1+2), comme les primes par commune"
    return {
        "principal": principal,
        "fort_contre_reste": fort_contre_reste,
        "sans_limite": sans_limite,
        "placebo_bascule": placebo,
        "reforme_2025": reforme,
    }


def ecrire_resume(chemin: Path, blocs: dict) -> None:
    """Ajoute ou remplace des clés de resume_global.json sans toucher aux autres."""
    contenu = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
    contenu.update(blocs)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lignes_resume(modeles: dict) -> list[str]:
    """Texte affiché : une ligne par coefficient, avec l'effet en % et son IC à 95 %."""
    sortie = []
    for nom, modele in modeles.items():
        if "coefficients" not in modele:
            sortie.append(f"{nom} : {modele['statut']}")
            continue
        complement = modele.get("statut") or modele.get("note")
        sortie.append(
            f"{nom} : {modele['n_ventes']} ventes, {modele['n_communes']} communes"
            + (f" ({complement})" if complement else "")
        )
        lignes = {**modele["coefficients"]}
        if "contraste_fort_moins_moyen" in modele:
            lignes["fort − moyen"] = modele["contraste_fort_moins_moyen"]
        for terme, c in lignes.items():
            bas, haut = c["ic95_effet"]
            effectif = f"  ({c['n_ventes_terme']} ventes)" if "n_ventes_terme" in c else ""
            sortie.append(
                f"    {terme:<13} effet {c['effet'] * 100:+6.2f} %  IC95 [{bas * 100:+6.2f} ; {haut * 100:+6.2f}]"
                f"  p = {c['p_valeur']:.3f}{effectif}"
            )
        sortie += [f"    ! {texte}" for texte in modele.get("avertissements", [])]
    return sortie


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Modèle global : décote en zone moyen et fort")
    parser.add_argument("--base", type=Path, default=BASE_PAR_DEFAUT)
    parser.add_argument("--sortie", type=Path, default=CHEMIN_RESUME)
    args = parser.parse_args(argv)

    perimetre = charger_config()["perimetre"]
    con = duckdb.connect(str(args.base), read_only=True)
    try:
        df = charger(con)
        modeles = modeles_globaux(df)
    except (ErreurDonnees, duckdb.Error) as e:
        raise SystemExit(f"Erreur : {e}") from e
    finally:
        con.close()

    ecrire_resume(args.sortie, {
        "periode": [perimetre["annee_debut"], perimetre["annee_fin"]],
        "modeles_globaux": modeles,
        "date_generation": date.today().isoformat(),
    })
    print("\n".join(lignes_resume(modeles)))


if __name__ == "__main__":
    main()
