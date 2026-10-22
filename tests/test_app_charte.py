import ast
import inspect
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
    # règle partagée avec l'onglet Sinistralité × écart (même sélecteur groupé)
    assert ".stMain .block-container .st-key-droite, .stMain .block-container .st-key-droite_sinistralite { gap: 20px; }" in charte.CSS
    assert ".stMain .block-container .st-key-signal {" in charte.CSS and "gap: 16px;" in charte.CSS
    assert '.st-key-signal [data-testid="stButton"] { margin: auto 0 0; }' in charte.CSS


def regle(selecteur: str) -> str:
    """Corps de la première règle de charte.CSS dont le sélecteur commence par `selecteur`."""
    ligne = next(r for r in charte.CSS.splitlines() if r.startswith(selecteur))
    return ligne.split("{", 1)[1].rsplit("}", 1)[0]


def test_css_hauteur_naturelle_aucune_hauteur_liee_a_la_fenetre():
    page = regle(".stMain .block-container {")
    assert "min-height" not in page and "display: flex" not in page
    for lie_a_la_fenetre in ("vh", "vw", "--h-", "--ecart", "clamp("):
        assert lie_a_la_fenetre not in charte.CSS, lie_a_la_fenetre
    assert "flex: 1 1 auto" not in regle('.stMain .block-container [class*="st-key-page_"]')


def test_css_pied_apres_le_contenu_avec_espaces_communs():
    pied = regle(".stMain .block-container .rg-pied {")
    assert "padding: 24px 0 20px" in pied                                 # 24 px au-dessus, 20 px en dessous
    assert "gap: 0" in regle('.stMain .block-container [class*="st-key-page_"]')   # l'espace au-dessus est celui du pied
    source = inspect.getsource(charte.onglet)
    # zone puis pied : le pied suit directement le contenu
    assert source.index('key=f"zone_{cle}"') < source.index("html_pied(") and 'key=f"page_{cle}"' in source


def test_les_regles_d_etirement_ne_touchent_jamais_les_colonnes_elles_memes():
    # `div:has(...)` hors d'un descendant de colonne rendrait flex: 1 1 auto à la colonne (base de largeur écrasée,
    # colonne de droite renvoyée sous la gauche) : tout sélecteur `div:has(` doit être sous un stColumn
    regles = [r for r in charte.CSS.splitlines() if ".rg-etire" in r and "flex: 1 1 auto" in r]
    assert regles
    for ligne in regles:
        for selecteur in ligne.split("{")[0].split(","):
            if "div:has(" in selecteur:
                assert '[data-testid="stColumn"] div:has(' in selecteur, selecteur
    assert "stHorizontalBlock\"] { flex" not in charte.CSS


def test_css_colonnes_etirees_et_methodologie_a_rangees_naturelles():
    assert "align-items: stretch" in charte.CSS and ".rg-etire" in charte.CSS
    grille = regle(".rg-methodo {")
    assert "grid-template-rows" not in grille and "--methodo-texte: 14px" in grille   # rangée = carte la plus haute
    assert "overflow" not in grille and "overflow: hidden" not in regle(".rg-methodo-carte {")


def test_css_ancres_des_titres_masquees():
    assert '[data-testid="stHeaderActionElements"]' in charte.CSS


def test_chaque_onglet_utilise_la_mise_en_page_commune():
    for nom in ("resultat", "sinistralite", "carte", "methodologie"):
        source = (APP / "vues" / f"{nom}.py").read_text(encoding="utf-8")
        assert f'charte.onglet("{nom}"' in source and "html_pied" not in source


def test_colonnes_de_l_onglet_resultat_en_gap_small():
    source = (APP / "vues" / "resultat.py").read_text(encoding="utf-8")
    assert 'st.columns([1.5, 1], gap="small")' in source and 'st.container(key="droite")' in source


def test_css_du_signal_limite_au_conteneur_a_cle():
    assert ".st-key-signal button" in charte.CSS and "#E99A68" in charte.CSS
    assert "\nbutton" not in charte.CSS
