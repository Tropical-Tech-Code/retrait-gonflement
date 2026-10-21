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


def test_intervalle_pct_une_decimale():
    assert textes.intervalle_pct(-0.0289, 0.0486) == f"[−2,9{textes.NBSP}% ; +4,9{textes.NBSP}%]"
    with pytest.raises(TypeError):
        textes.intervalle_pct(-0.0289, 0.0486, 2)


def test_barre_fourchette_positions_et_axe():
    sortie = charte.html_barre_fourchette(0.0091, -0.0289, 0.0486, -0.03, "description")
    # axe de −6 % à +6 % : 0 au milieu, seuil (−3 %) à 25 %, estimation (+0,91 %) à 57,58 %
    assert 'left:50.00%;top:16px' in sortie and 'left:25.00%;top:10px' in sortie
    assert 'left:57.58%;top:23px' in sortie
    assert f"{textes.MOINS}3{textes.NBSP}% : seuil" in sortie and 'aria-label="description"' in sortie


def test_barre_fourchette_elargit_l_axe_si_l_ic_depasse():
    etroit = charte.html_barre_fourchette(0.0, -0.01, 0.01, -0.03, "d")
    large = charte.html_barre_fourchette(0.0, -0.10, 0.05, -0.03, "d")
    assert f"{textes.MOINS}6{textes.NBSP}%" in etroit and f"{textes.MOINS}12{textes.NBSP}%" in large


def test_composants_echappent_le_texte():
    assert "<i>" not in charte.html_bloc_gris("t <i>", ["a <i>"])
    assert "<i>" not in charte.html_signal("t <i>", "9", "x <i>", "y <i>")
    assert "<i>" not in charte.html_pied("a <i>")


def test_css_espacements_de_l_onglet_resultat():
    # même spécificité que la règle générale des blocs verticaux (sinon elle l'emporte)
    assert ".stMain .block-container .st-key-droite { gap: 20px; }" in charte.CSS
    assert ".stMain .block-container .st-key-signal {" in charte.CSS and "gap: 16px;" in charte.CSS
    assert '.st-key-signal [data-testid="stButton"] { margin: auto 0 0; }' in charte.CSS


def test_css_colonne_de_droite_etiree_et_limitee_aux_conteneurs_a_cle():
    regles = [r for r in charte.CSS.splitlines() if "st-key-resultat" in r or "st-key-droite div" in r]
    assert regles, "règles d'étirement absentes"
    for regle in regles:
        # chaque sélecteur de ces règles est précédé du préfixe de la règle générale (charte.py:21)
        for selecteur in regle.split("{")[0].split(","):
            assert selecteur.strip().startswith(".stMain .block-container .st-key-"), selecteur
    assert "align-items: stretch" in charte.CSS and "flex: 1 1 auto" in charte.CSS
    # marge et padding bas des colonnes à 0 (écart de 20 px sous l'encadré sombre)
    assert "> :last-child" in charte.CSS and "{ padding-bottom: 0; }" in charte.CSS and "{ margin-bottom: 0; }" in charte.CSS


def test_css_pied_de_page_24px_au_dessus():
    assert ".stMain .block-container .rg-pied { padding: 24px 0 0;" in charte.CSS


def test_colonnes_de_l_onglet_resultat_en_gap_small():
    source = (APP / "vues" / "resultat.py").read_text(encoding="utf-8")
    assert 'st.columns([1.5, 1], gap="small")' in source and 'st.container(key="droite")' in source


def test_css_du_signal_limite_au_conteneur_a_cle():
    assert ".st-key-signal button" in charte.CSS and "#E99A68" in charte.CSS
    assert "\nbutton" not in charte.CSS
