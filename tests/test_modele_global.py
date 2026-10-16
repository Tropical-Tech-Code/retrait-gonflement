import json

import duckdb
import numpy as np
import pandas as pd
import pytest

from retrait_gonflement.data.commun import ErreurDonnees
from retrait_gonflement.model import modele_global

# Effets multiplicatifs connus d'avance : -5 % en fort, -2 % en moyen, -3 % de plus en fort en 2025
EFFET_FORT = -0.05
EFFET_MOYEN = -0.02
EFFET_FORT_2025 = -0.03
# Sans terme 2025, le modèle principal estime la moyenne sur les cinq années : 2025 pèse 1/5 des ventes
EFFET_FORT_MOYEN_5_ANS = float(np.expm1(np.log1p(EFFET_FORT) + 0.2 * np.log1p(EFFET_FORT_2025)))


def simuler(seed: int = 1, communes: int = 40, par_cellule: int = 10) -> pd.DataFrame:
    """Ventes simulées : prix = effet commune × trimestre × exposition × taille × bruit."""
    rng = np.random.default_rng(seed)
    lignes = []
    for c in range(communes):
        for annee in range(2021, 2026):
            for trimestre in range(1, 5):
                niveau_cellule = rng.normal(7.5, 0.3)  # log du prix au m² propre à la cellule
                for _ in range(par_cellule):
                    lignes.append((
                        f"C{c:03d}", pd.Timestamp(annee, 3 * trimestre - 1, 15), annee, niveau_cellule,
                        rng.choice([0, 1, 2, 3], p=[0.05, 0.05, 0.5, 0.4]),
                    ))
    df = pd.DataFrame(lignes, columns=["code_commune", "date_mutation", "annee", "niveau_cellule", "rga_2020"])
    n = len(df)
    df["surface_bati"] = rng.uniform(60, 200, n)
    df["surface_terrain"] = np.where(rng.random(n) < 0.15, 0.0, rng.uniform(100, 3000, n))
    df["nombre_pieces"] = rng.integers(2, 8, n)
    # 6 % des ventes non fort en 2020 sont fort en 2026 (sans effet propre sur le prix)
    df["rga_2026"] = df["rga_2020"]
    bascule = (df["rga_2020"] != 3) & (rng.random(n) < 0.06)
    df.loc[bascule, "rga_2026"] = 3
    df["proche_limite_2020"] = rng.random(n) < 0.1
    log_prix = (
        df["niveau_cellule"]
        + np.log1p(EFFET_FORT) * (df["rga_2020"] == 3)
        + np.log1p(EFFET_MOYEN) * (df["rga_2020"] == 2)
        + np.log1p(EFFET_FORT_2025) * ((df["rga_2020"] == 3) & (df["annee"] == 2025))
        - 0.2 * np.log(df["surface_bati"] / 100)
        + 0.01 * np.log1p(df["surface_terrain"])
        + rng.normal(0, 0.1, n)
    )
    df["prix_m2"] = np.exp(log_prix)
    return df.drop(columns="niveau_cellule")


@pytest.fixture(scope="module")
def modeles():
    return modele_global.modeles_globaux(modele_global.preparer(simuler()))


def test_retrouve_la_decote_connue_en_fort_et_en_moyen(modeles):
    coefficients = modeles["principal"]["coefficients"]
    assert coefficients["fort"]["effet"] == pytest.approx(EFFET_FORT_MOYEN_5_ANS, abs=0.008)
    assert coefficients["moyen"]["effet"] == pytest.approx(EFFET_MOYEN, abs=0.012)
    bas, haut = coefficients["fort"]["ic95_effet"]
    assert bas < EFFET_FORT_MOYEN_5_ANS < haut


def test_contraste_fort_moins_moyen_retrouve_l_ecart_connu(modeles):
    for nom in ("principal", "sans_limite", "reforme_2025"):
        assert "contraste_fort_moins_moyen" in modeles[nom]
    contraste = modeles["principal"]["contraste_fort_moins_moyen"]
    attendu = (1 + EFFET_FORT_MOYEN_5_ANS) / (1 + EFFET_MOYEN) - 1  # environ −3,7 %
    assert contraste["effet"] == pytest.approx(attendu, abs=0.008)
    bas, haut = contraste["ic95_effet"]
    assert bas < attendu < haut
    assert contraste["p_valeur"] < 0.05
    assert "contraste_fort_moins_moyen" not in modeles["fort_contre_reste"]


def test_contraste_identique_a_un_modele_avec_moyen_en_reference():
    # Fort et « hors zone + faible » avec moyen en référence : β_fort est le contraste fort − moyen,
    # donc la variance groupée du contraste doit être celle de ce coefficient.
    df = modele_global.preparer(simuler(communes=20, par_cellule=6))
    df["reference_0_1"] = df["rga_2020"].isin([0, 1]).astype(float)
    contraste = modele_global.estimer(df, ["moyen", "fort"])["contraste_fort_moins_moyen"]
    direct = modele_global.estimer(df, ["fort", "reference_0_1"])["coefficients"]["fort"]
    assert contraste["beta"] == pytest.approx(direct["beta"], abs=1e-5)
    assert contraste["erreur_std"] == pytest.approx(direct["erreur_std"], abs=1e-5)
    assert contraste["p_valeur"] == pytest.approx(direct["p_valeur"], abs=1e-4)


def test_fort_contre_tout_le_reste():
    brut = simuler()
    df = modele_global.preparer(brut)
    modele = modele_global.estimer(df, ["fort"])
    # référence = niveaux 0, 1, 2 (effets 0, 0 et −2 %), pondérés par leurs effectifs
    reste = brut[brut["rga_2020"] != 3]
    effet_reste = (reste["rga_2020"] == 2).mean() * np.log1p(EFFET_MOYEN)
    attendu = np.expm1(np.log1p(EFFET_FORT_MOYEN_5_ANS) - effet_reste)
    assert modele["coefficients"]["fort"]["effet"] == pytest.approx(attendu, abs=0.008)


def test_placebo_avertit_du_nombre_de_communes(modeles):
    placebo = modeles["placebo_bascule"]
    assert f"repose sur {placebo['n_communes']} communes" in placebo["avertissements"][0]


def test_effet_est_exp_beta_moins_un(modeles):
    c = modeles["principal"]["coefficients"]["fort"]
    assert c["effet"] == pytest.approx(np.exp(c["beta"]) - 1, abs=1e-5)


def test_variante_sans_limite_retire_des_ventes(modeles):
    principal, sans_limite = modeles["principal"], modeles["sans_limite"]
    assert sans_limite["n_ventes"] < principal["n_ventes"]
    assert sans_limite["coefficients"]["fort"]["effet"] == pytest.approx(EFFET_FORT_MOYEN_5_ANS, abs=0.012)


def test_placebo_bascule_proche_de_zero_et_marque_indicatif(modeles):
    placebo = modeles["placebo_bascule"]
    assert abs(placebo["coefficients"]["bascule"]["effet"]) < 0.03
    assert placebo["statut"].startswith("indicatif, faible puissance (")
    assert f"{placebo['coefficients']['bascule']['n_ventes_terme']} ventes" in placebo["statut"]


def test_reforme_2025_retrouve_l_ecart_de_2025(modeles):
    reforme = modeles["reforme_2025"]
    assert reforme["statut"].startswith("indice")
    assert reforme["coefficients"]["fort"]["effet"] == pytest.approx(EFFET_FORT, abs=0.012)
    assert reforme["coefficients"]["fort_2025"]["beta"] == pytest.approx(np.log1p(EFFET_FORT_2025), abs=0.02)


def test_chaque_modele_donne_ses_effectifs(modeles):
    for modele in modeles.values():
        assert modele["n_ventes"] > 0 and modele["n_communes"] > 0


def test_ventes_seules_dans_leur_cellule_sont_retirees():
    df = modele_global.preparer(simuler(communes=3, par_cellule=3))
    seule = df.iloc[[0]].copy()
    seule["code_commune"] = "SEULE"
    donnees = pd.concat([df, seule], ignore_index=True)
    assert len(modele_global.retirer_singletons(modele_global.preparer(donnees))) == len(df)


def test_terme_sans_vente_refuse():
    brut = simuler(communes=3, par_cellule=3)
    brut["rga_2026"] = brut["rga_2020"]  # aucune bascule
    df = modele_global.preparer(brut)
    with pytest.raises(ErreurDonnees, match="bascule"):
        modele_global.estimer(df, ["moyen", "fort", "bascule"])
    assert modele_global.modeles_globaux(df)["placebo_bascule"]["statut"].startswith("non estimable")


def test_charger_depuis_duckdb():
    df = simuler(communes=2, par_cellule=2)
    con = duckdb.connect()
    con.register("simule", df)
    con.execute("CREATE TABLE ventes_rga AS SELECT * FROM simule")
    charge = modele_global.charger(con)
    assert {"ct", "log_prix", "fort", "moyen", "bascule", "fort_2025"} <= set(charge.columns)
    assert charge["ct"].iloc[0] == "C000-2021T1"


def test_resume_json_sans_vente_individuelle_et_fusion(tmp_path, modeles):
    chemin = tmp_path / "resume_global.json"
    chemin.write_text(json.dumps({"autre_cle": 1}), encoding="utf-8")
    modele_global.ecrire_resume(chemin, {"modeles_globaux": modeles})
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    assert contenu["autre_cle"] == 1  # clés des autres étapes conservées
    assert set(contenu["modeles_globaux"]) == {
        "principal", "fort_contre_reste", "sans_limite", "placebo_bascule", "reforme_2025",
    }
    texte = chemin.read_text(encoding="utf-8")
    assert "C000" not in texte and "prix_m2" not in texte


def test_lignes_resume_affiche_effets_en_pourcentage(modeles):
    sortie = "\n".join(modele_global.lignes_resume(modeles))
    assert "principal : " in sortie and "%" in sortie
    assert "indicatif, faible puissance" in sortie
