import json

import duckdb
import numpy as np
import pandas as pd
import pytest

from retrait_gonflement.data.commun import charger_config
from retrait_gonflement.model import modele_global, primes_communes

ESTIMATION = {
    "min_ventes_fort": 15,
    "min_ventes_reference": 15,
    "min_ventes_total": 50,
    "seuil_prix_median": 5,
    "niveau_ic": 0.95,
    "seuil_pas_de_decote": -0.03,
    "min_sections_groupement": 10,
}

# code commune : (département, prime connue, nombre de sections, ventes par trimestre, part de ventes « fort »)
COMMUNES = {
    "31001": ("31", -0.20, 16, 10, 0.4),
    "31002": ("31", -0.10, 16, 10, 0.4),
    "31003": ("31", -0.05, 16, 10, 0.4),
    "31004": ("31", 0.00, 16, 10, 0.4),
    "47001": ("47", 0.00, 16, 10, 0.4),
    "47002": ("47", 0.05, 16, 10, 0.4),
    "47003": ("47", 0.10, 16, 10, 0.4),
    "47004": ("47", 0.20, 16, 10, 0.4),
    "77001": ("77", -0.15, 4, 10, 0.4),    # 4 sections seulement : erreurs HC1
    "77002": ("77", 0.00, 16, 10, 1.0),    # que du « fort » : une seule zone
    "77003": ("77", 0.00, 16, 2, 0.4),     # 40 ventes : effectifs insuffisants
}


def simuler(seed: int = 3) -> pd.DataFrame:
    """Ventes simulées avec une prime « fort contre tout le reste » connue par commune."""
    rng = np.random.default_rng(seed)
    lignes = []
    for code, (dep, prime, n_sections, par_trimestre, part_fort) in COMMUNES.items():
        for annee in range(2021, 2026):
            for trimestre in range(1, 5):
                niveau_cellule = rng.normal(7.5, 0.3)
                for _ in range(par_trimestre):
                    fort = rng.random() < part_fort
                    rga = 3 if fort else int(rng.choice([0, 1, 2], p=[0.1, 0.1, 0.8]))
                    section = int(rng.integers(0, n_sections))
                    surface = rng.uniform(60, 200)
                    lignes.append({
                        "code_commune": code, "code_departement": dep,
                        "id_parcelle": f"{code}000{section:02d}{int(rng.integers(1, 9999)):04d}",
                        "date_mutation": pd.Timestamp(annee, 3 * trimestre - 1, 15), "annee": annee,
                        "prix_m2": float(np.exp(
                            niveau_cellule + np.log1p(prime) * fort - 0.2 * np.log(surface / 100)
                            + rng.normal(0, 0.1)
                        )),
                        "surface_bati": surface, "surface_terrain": float(rng.uniform(100, 2000)),
                        "nombre_pieces": int(rng.integers(2, 8)), "rga_2020": rga, "rga_2026": rga,
                    })
    return modele_global.preparer(pd.DataFrame(lignes))


@pytest.fixture(scope="module")
def df():
    return simuler()


@pytest.fixture(scope="module")
def communes(df):
    return primes_communes.estimer_primes(df, primes_communes.classer_communes(df, ESTIMATION), ESTIMATION)


def test_config_reelle_contient_le_seuil_de_sections():
    assert charger_config()["estimation"]["min_sections_groupement"] == 10


def test_statut_et_motif_des_communes(communes):
    assert communes.loc["77002", ["statut", "motif"]].tolist() == ["non_estimable", "une_seule_zone"]
    assert communes.loc["77003", ["statut", "motif"]].tolist() == ["non_estimable", "effectifs_insuffisants"]
    assert (communes["statut"] == "estimable").sum() == 9
    assert communes.loc["77002", "prime"] != communes.loc["77002", "prime"]  # NaN : pas de prime publiée


def test_effectifs_par_classe(communes):
    ligne = communes.loc["31001"]
    assert ligne["n_ventes"] == 200
    assert ligne["n_fort"] + ligne["n_moyen"] + ligne["n_faible"] + ligne["n_hors_zone"] == 200
    assert ligne["prix_m2_median"] > 0


def test_retrouve_les_primes_communales_connues(communes):
    # écart (en log) entre prime estimée et prime connue, rapporté à l'erreur standard déduite de l'IC
    for code, (_, prime, *_reste) in COMMUNES.items():
        ligne = communes.loc[code]
        if ligne["statut"] != "estimable":
            continue
        demi_largeur = (np.log1p(ligne["ic_haut"]) - np.log1p(ligne["ic_bas"])) / 2
        ecart = abs(np.log1p(ligne["prime"]) - np.log1p(prime))
        assert ecart < demi_largeur * 1.7, f"{code} : prime estimée {ligne['prime']:+.3f} pour {prime:+.3f} attendu"
    assert np.corrcoef(
        communes.loc[communes["statut"] == "estimable", "prime"],
        [COMMUNES[c][1] for c in communes.index[communes["statut"] == "estimable"]],
    )[0, 1] > 0.95


def test_statuts_de_decote_des_primes_marquees(communes):
    assert communes.loc["31001", "statut_decote"] == "decote"      # −20 %
    assert communes.loc["31001", "significatif"] == "decote"
    assert communes.loc["47004", "statut_decote"] == "pas_de_decote"  # +20 %
    assert communes.loc["47004", "significatif"] == "prime"


def test_erreurs_hc1_si_peu_de_sections(communes):
    assert communes.loc["77001", "erreurs"] == "hc1"
    assert communes.loc["31001", "erreurs"] == "sections"
    assert communes.loc["77001", "n_sections"] == 4
    assert communes.loc["31001", "n_sections"] == 16


@pytest.mark.parametrize(
    ("ic_bas", "ic_haut", "attendu"),
    [
        (-0.30, -0.10, "decote"),
        (-0.10, -0.001, "decote"),
        (-0.10, 0.0, "indetermine"),     # IC qui touche 0 : pas une décote
        (-0.20, 0.10, "indetermine"),    # IC large
        (-0.029, 0.08, "pas_de_decote"),
        (-0.03, 0.08, "indetermine"),    # borne basse égale au seuil : pas strictement au-dessus
        (0.02, 0.12, "pas_de_decote"),
    ],
)
def test_statut_decote(ic_bas, ic_haut, attendu):
    assert primes_communes.statut_decote(ic_bas, ic_haut, -0.03) == attendu


@pytest.mark.parametrize(
    ("ic_bas", "ic_haut", "attendu"),
    [(-0.2, -0.05, "decote"), (0.01, 0.2, "prime"), (-0.05, 0.05, "non")],
)
def test_significatif(ic_bas, ic_haut, attendu):
    assert primes_communes.significatif(ic_bas, ic_haut) == attendu


def test_tests_multiples(communes):
    t = primes_communes.tests_multiples(communes)
    assert t["n_communes_estimables"] == 9
    assert t["n_attendu_hasard"] == pytest.approx(0.45)
    assert t["n_attendu_par_sens"] == pytest.approx(0.225)
    assert t["n_significatives_decote"] >= 3  # −20 %, −10 % et −15 % sont nettement sous 0
    assert t["n_significatives_prime"] >= 2   # +10 % et +20 %


def test_resume_json_et_fichiers_sans_vente_individuelle(communes, tmp_path):
    resume = primes_communes.resume_json(communes, ESTIMATION)
    assert resume["n_decote"] + resume["n_pas_de_decote"] + resume["n_indetermine"] == 9
    assert resume["primes_communes"]["n_non_estimables"] == {"une_seule_zone": 1, "effectifs_insuffisants": 1}
    assert resume["primes_communes"]["erreurs"]["n_hc1"] == 1
    assert resume["primes_communes"]["par_departement"]["77"]["n_estimables"] == 1

    chemin = tmp_path / "resume_global.json"
    chemin.write_text(json.dumps({"modeles_globaux": {"principal": 1}}), encoding="utf-8")
    modele_global.ecrire_resume(chemin, resume)
    contenu = json.loads(chemin.read_text(encoding="utf-8"))
    assert contenu["modeles_globaux"] == {"principal": 1}  # clés de l'étape A conservées
    assert "n_significatives_decote" in contenu
    texte = chemin.read_text(encoding="utf-8")
    assert "id_parcelle" not in texte and "31001" not in texte  # agrégats par département seulement

    sortie = communes.rename_axis("code_insee").reset_index()
    sortie.to_parquet(tmp_path / "primes.parquet", index=False)
    colonnes = set(pd.read_parquet(tmp_path / "primes.parquet").columns)
    assert not colonnes & {"id_parcelle", "section", "prix_m2", "date_mutation", "longitude", "latitude"}


def test_diagnostic_par_type_d_erreurs(communes):
    diagnostic = primes_communes.diagnostic_erreurs(communes)
    sections, hc1 = diagnostic["sections"], diagnostic["hc1"]
    assert sections["n_estimables"] == 8 and hc1["n_estimables"] == 1
    # statuts : decote + pas_de_decote + indetermine = estimables
    for d in (sections, hc1):
        assert d["n_decote"] + d["n_pas_de_decote"] + d["n_indetermine"] == d["n_estimables"]
    signif = sections["n_significatives_decote"] + sections["n_significatives_prime"]
    assert sections["part_significatives"] == pytest.approx(signif / 8, abs=1e-4)
    est = communes[communes["erreurs"] == "sections"]
    assert sections["largeur_ic_mediane"] == pytest.approx((est["ic_haut"] - est["ic_bas"]).median(), abs=1e-4)
    assert hc1["n_decote"] == 1  # la commune à −15 % est en décote
    # le tableau est dans le JSON et dans le texte affiché
    resume = primes_communes.resume_json(communes, ESTIMATION)
    assert resume["primes_communes"]["diagnostic_erreurs"] == diagnostic
    sortie = "\n".join(primes_communes.lignes_resume(communes, resume))
    assert "Diagnostic par type d'erreurs" in sortie and "part_signif" in sortie


def test_resume_texte_sans_ligne_par_commune(communes):
    resume = primes_communes.resume_json(communes, ESTIMATION)
    sortie = "\n".join(primes_communes.lignes_resume(communes, resume))
    assert "TOTAL" in sortie and "attendues par hasard" in sortie and "HC1" in sortie
    assert "31001" not in sortie


def test_charger_depuis_duckdb(df):
    brut = df[[
        "code_commune", "code_departement", "id_parcelle", "date_mutation", "annee", "prix_m2",
        "surface_bati", "surface_terrain", "nombre_pieces", "rga_2020", "rga_2026",
    ]]
    con = duckdb.connect()
    con.register("simule", brut)
    con.execute("CREATE TABLE ventes_rga AS SELECT * FROM simule")
    charge = primes_communes.charger(con)
    assert len(charge) == len(df) and {"ct", "fort", "log_prix"} <= set(charge.columns)
    assert primes_communes.ajouter_section(charge)["section"].str.len().eq(10).all()
