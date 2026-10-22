import json
import re

import pytest
import streamlit as st

import donnees
import textes
from conftest import communes_test, resume_test
from test_app_resultat import html_affiches, lancer

NB = textes.NBSP


def ouvrir(dossier, monkeypatch, resume=None):
    """Lance l'app avec l'onglet Sinistralité × écart ouvert (cache vidé : le dossier peut être relu avec un autre résumé)."""
    st.cache_data.clear()
    if resume is not None:
        (dossier / "resume_global.json").write_text(json.dumps(resume), encoding="utf-8")
    monkeypatch.setenv(donnees.VARIABLE_DOSSIER, str(dossier))
    app = lancer(dossier, monkeypatch)
    app.session_state["onglet"] = textes.ONGLETS[1]
    return app.run()


@pytest.fixture
def sinistralite(dossier_processed, monkeypatch):
    return ouvrir(dossier_processed, monkeypatch)


def test_effectifs_des_cases_lus_dans_les_donnees(dossier_processed, monkeypatch):
    resume = resume_test()
    resume["n_par_quadrant"] = {"Risque intégré": 7, "Angle mort": 1, "Décote à expliquer": 12, "Cohérent": 345}
    page = html_affiches(ouvrir(dossier_processed, monkeypatch, resume))
    for nom, n in resume["n_par_quadrant"].items():
        libelle = textes.libelle_quadrant(nom)
        assert re.search(rf">{libelle}</span><span[^>]*>{textes.entier(n)}</span>", page), nom
    assert ">Angle mort<" not in page and ">Risque non intégré<" in page
    for phrase in textes.PHRASES_QUADRANTS.values():
        assert phrase in page
    assert page.count('class="rg-quad-case rg-mis-en-avant"') == 1  # seul « Angle mort » est mis en avant


def test_phrases_des_cases_et_de_l_encadre_sombre(sinistralite):
    page = html_affiches(sinistralite)
    assert "Peu de sinistres, pas de décote." in page
    assert "Des sinistres reconnus, pas de décote." in page
    assert "Une décote sans sinistralité marquée : sans doute un effet de quartier plutôt que de l'argile." in page
    assert "Des sinistres et une décote." in page
    assert "aucune décote n'est mesurée entre zone forte et reste de la commune. Ce n'est pas une prédiction." in page


def test_indeterminees_et_signal_lus_dans_le_resume(sinistralite):
    page = html_affiches(sinistralite)
    assert (  # n_indetermine = 2
        "<strong>2</strong> communes ne sont pas classées : trop peu de ventes pour trancher "
        "entre décote et absence de décote."
    ) in page
    assert 'class="rg-sombre-nombre">1</span>' in page and "commune au risque non intégré" in page
    assert "Communes au risque non intégré, par sinistralité" in page
    assert "angle mort" not in page.lower()  # la valeur du fichier ne s'affiche jamais


@pytest.mark.parametrize(
    "mediane, bas, haut",
    [(2.0, "(0 à 2 arrêtés)", "(3 arrêtés ou plus)"), (3.5, "(0 à 3 arrêtés)", "(4 arrêtés ou plus)")],
)
def test_libelles_des_colonnes_selon_la_mediane(dossier_processed, monkeypatch, mediane, bas, haut):
    resume = resume_test()
    resume["mediane_sinistralite"] = mediane
    page = html_affiches(ouvrir(dossier_processed, monkeypatch, resume))
    assert f"Sinistralité ≤ médiane<br>{bas}" in page
    assert f"Sinistralité &gt; médiane<br>{haut}" in page


def test_tableau_trie_par_arretes_decroissants_puis_nom(dossier_processed, monkeypatch):
    communes = communes_test()
    communes.loc[communes["nom"] == "Cugnaux", ["quadrant", "catnat_depuis_2015"]] = ["Angle mort", 7]
    communes.loc[communes["nom"] == "Daux", ["quadrant", "catnat_depuis_2015"]] = ["Angle mort", 3]
    communes.to_parquet(dossier_processed / "communes.parquet", index=False)
    page = html_affiches(ouvrir(dossier_processed, monkeypatch))
    noms = re.findall(r"<span>(Cugnaux|Balma|Daux)</span>", page)
    assert noms == ["Cugnaux", "Balma", "Daux"]


def test_ligne_du_tableau_ecart_ic_et_ventes_fort(sinistralite):
    page = html_affiches(sinistralite)
    # Balma : prime 0,02, IC [−0,01 ; 0,05], 3 arrêtés, 100 ventes dont 40 en zone forte
    assert (
        f"<span>Balma</span><span>31</span><span>3</span>"
        f"<span>+2,0{NB}% [{textes.MOINS}1,0{NB}% ; +5,0{NB}%]</span><span>100</span><span>40</span>"
    ) in page
    assert "<span>Ventes</span><span>dont zone forte</span>" in page and "Ventes en zone forte" not in page


def test_sans_angle_mort(dossier_processed, monkeypatch):
    communes = communes_test()
    communes["quadrant"] = None
    communes.to_parquet(dossier_processed / "communes.parquet", index=False)
    resume = resume_test()
    resume["n_par_quadrant"]["Angle mort"] = 0
    page = html_affiches(ouvrir(dossier_processed, monkeypatch, resume))
    assert textes.AUCUN_ANGLE_MORT in page
    assert "commune au risque non intégré" in page and 'class="rg-sombre-nombre">0</span>' in page


def test_definitions_des_statuts_avec_le_seuil_du_resume(dossier_processed, monkeypatch):
    page = html_affiches(ouvrir(dossier_processed, monkeypatch))
    assert (f"Décote : intervalle de confiance entièrement sous 0 ; "
            f"pas de décote : borne basse au-dessus de {textes.MOINS}3{NB}%.") in page
    assert "IC entièrement" not in page
    resume = resume_test()
    resume["seuil_pas_de_decote"] = -0.025
    page = html_affiches(ouvrir(dossier_processed, monkeypatch, resume))
    assert f"borne basse au-dessus de {textes.MOINS}2,5{NB}%." in page


def test_pied_commun_de_l_onglet(dossier_processed, monkeypatch):
    page = html_affiches(ouvrir(dossier_processed, monkeypatch))
    assert textes.pied_commun(resume_test()) in page


def test_vocabulaire_de_l_onglet(sinistralite):
    page = html_affiches(sinistralite).lower()
    for interdit in textes.EXPRESSIONS_INTERDITES:
        assert interdit not in page, f"« {interdit} » dans l'onglet Sinistralité × écart"


def test_correspondance_valeur_libelle_du_quadrant():
    assert textes.libelle_quadrant("Angle mort") == "Risque non intégré"
    for autre in ("Risque intégré", "Décote à expliquer", "Cohérent"):
        assert textes.libelle_quadrant(autre) == autre
    assert set(textes.LIBELLES_QUADRANTS) <= set(textes.QUADRANTS)


def test_signal_faible_du_resultat_utilise_le_nouveau_libelle(dossier_processed, monkeypatch):
    page = html_affiches(lancer(dossier_processed, monkeypatch))
    assert "Des risques peut-être non intégrés, à surveiller. Une hypothèse, pas une prédiction." in page


def test_css_cases_sans_hauteur_fixe_et_regles_communes_avec_le_resultat():
    import charte

    assert "grid-template-rows: auto minmax(104px, auto) minmax(104px, auto)" in charte.CSS  # le texte n'est jamais coupé
    assert "overflow: hidden; }" not in charte.CSS.split(".rg-quad-case {")[1].split("\n")[0]
    # même règle d'espacement et d'étirement que l'onglet Résultat
    assert ".st-key-droite, .stMain .block-container .st-key-droite_sinistralite { gap: 20px; }" in charte.CSS
    assert ".st-key-zone_sinistralite [data-testid=\"stHorizontalBlock\"]" in charte.CSS and "align-items: stretch" in charte.CSS
    assert ".st-key-zone_resultat [data-testid=\"stHorizontalBlock\"]" in charte.CSS
    # même taille que l'encadré gris ; 16 px de plus avant les en-têtes de colonnes
    assert "p.rg-explication { margin: 0 0 16px; font-size: 14px;" in charte.CSS


def test_en_construction_retire(sinistralite):
    assert not sinistralite.exception
    assert textes.TITRE_SINISTRALITE in html_affiches(sinistralite)


def test_le_bouton_du_resultat_ouvre_l_onglet(dossier_processed, monkeypatch):
    app = lancer(dossier_processed, monkeypatch)
    app.button(key="vers_sinistralite").click().run()
    assert not app.exception
    assert app.session_state["onglet"] == textes.ONGLETS[1]
    assert textes.TITRE_SINISTRALITE in html_affiches(app)
