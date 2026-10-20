import ast
import tomllib

import pytest

import charte
import donnees
import textes

APP = donnees.RACINE / "app"
COULEURS = {
    "backgroundColor": "#F4F5F2",
    "textColor": "#1B1F1D",
    "primaryColor": "#C2410C",
    "secondaryBackgroundColor": "#FFFFFF",
}


def test_config_streamlit_contient_les_quatre_couleurs_de_la_charte():
    config = tomllib.loads((donnees.RACINE / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert config["theme"] == COULEURS
    assert config["browser"]["gatherUsageStats"] is False
    assert config["client"]["toolbarMode"] == "minimal"


def test_aucune_police_externe():
    config = (donnees.RACINE / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert "font" not in config.lower()
    assert "http" not in charte.CSS and "@import" not in charte.CSS


@pytest.mark.parametrize("chemin", sorted(APP.rglob("*.py")), ids=lambda c: c.name)
def test_ni_sidebar_ni_st_info_dans_app(chemin):
    arbre = ast.parse(chemin.read_text(encoding="utf-8"))
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Attribute) and isinstance(noeud.value, ast.Name) and noeud.value.id == "st":
            assert noeud.attr not in ("sidebar", "info"), f"st.{noeud.attr} dans {chemin.name}:{noeud.lineno}"


def test_css_sans_selecteur_universel_ni_police_imposee():
    # une police imposée à tous les éléments écrase la police d'icônes de Streamlit (« _arrow_right »)
    assert "font-family" not in charte.CSS
    for regle in charte.CSS.split("{")[:-1]:
        selecteur = regle.split("}")[-1]
        assert "*" not in selecteur.replace('[class*="', ""), f"sélecteur universel : {selecteur.strip()}"


def test_titre_de_l_entete_a_une_couleur_et_des_marges_forcees():
    regle = next(r for r in charte.CSS.splitlines() if "h1.rg-titre" in r)
    assert regle.startswith(".stMarkdown .rg-entete ")
    assert "color: #FFFFFF !important" in regle and "margin: 0 !important" in regle


def test_encadre_echappe_le_texte():
    sortie = charte.html_encadre("beige", '<script>alert("x")</script> & <b>gras</b>')
    assert "<script>" not in sortie and "<b>" not in sortie
    assert "&lt;script&gt;" in sortie and "&amp;" in sortie
    assert sortie.startswith('<div class="rg-encadre rg-beige">')


def test_encadre_garde_les_apostrophes_et_les_sauts_de_ligne():
    sortie = charte.html_encadre("gris", "l'écart\nsuivant")
    assert "l'écart<br>suivant" in sortie and 'class="rg-encadre rg-gris"' in sortie


def test_entete_echappe_le_texte():
    sortie = charte.html_entete("a <i>", "b & c")
    assert "<i>" not in sortie and "&amp;" in sortie and "rg-titre" in sortie


def test_css_definit_les_encadres_et_les_chiffres_tabulaires():
    assert charte.BEIGE in charte.CSS and charte.GRIS in charte.CSS
    assert "tabular-nums" in charte.CSS


# Notation unique des intervalles : « [−2,9 % ; +4,9 % ] » sans espace avant le crochet fermant
@pytest.mark.parametrize(
    ("bas", "haut", "attendu"),
    [
        (-0.029, 0.049, "[−2,9 % ; +4,9 %]"),
        (-0.046, 0.0, "[−4,6 % ; 0,0 %]"),
        (0.0, 0.0, "[0,0 % ; 0,0 %]"),
        (-0.0004, 0.0004, "[0,0 % ; 0,0 %]"),
        (-0.12, -0.03, "[−12,0 % ; −3,0 %]"),
        (0.01, 0.05, "[+1,0 % ; +5,0 %]"),
    ],
)
def test_intervalle_pct_cas_limites(bas, haut, attendu):
    assert textes.intervalle_pct(bas, haut) == attendu.replace(" %", f"{textes.NBSP}%")


def test_intervalle_pct_jamais_de_zero_signe():
    for fraction in (0.0, -0.0004, 0.0004, -0.0):
        sortie = textes.intervalle_pct(fraction, fraction)
        assert "+0,0" not in sortie and f"{textes.MOINS}0,0" not in sortie


def test_intervalle_pct_deux_decimales():
    assert textes.intervalle_pct(-0.0289, 0.0486, 2) == f"[−2,89{textes.NBSP}% ; +4,86{textes.NBSP}%]"
