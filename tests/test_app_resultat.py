import json

import pytest
from streamlit.testing.v1 import AppTest

import donnees
import textes
from conftest import coefficient, resume_test

APP = str(donnees.RACINE / "app" / "streamlit_app.py")


def lancer(dossier, monkeypatch, resume=None) -> AppTest:
    if resume is not None:
        (dossier / "resume_global.json").write_text(json.dumps(resume), encoding="utf-8")
    monkeypatch.setenv(donnees.VARIABLE_DOSSIER, str(dossier))
    return AppTest.from_file(APP, default_timeout=30).run()


@pytest.fixture
def resultat(dossier_processed, monkeypatch):
    return lancer(dossier_processed, monkeypatch)


def html_affiches(app) -> str:
    return " ".join(m.value for m in app.markdown)


def test_textes_lus_dans_les_donnees(resultat):
    assert not resultat.exception
    page = html_affiches(resultat)
    nb = textes.NBSP
    assert textes.SURTITRE_RESULTAT in page
    assert "Pas de différence de prix détectable entre zone d'argile forte et zone moyenne." in page
    assert f"+0,9{nb}%" in page and f"[{textes.MOINS}2,9{nb}% ; +4,9{nb}%]" in page and textes.MENTION_IC in page
    assert f"· 280 ventes · 1 département · 2021-2025" in page  # une seule valeur de « departement » dans communes_test
    assert f"elle ne dépasse probablement pas environ 3{nb}%" in page
    assert f"se vendent 3,4 à 2,5{nb}%" not in page and f"se vendent 2,5 à 3,4{nb}% moins cher" in page
    assert "p ≈ 0,50" in page
    assert textes.TESTE_CONCLUSION in page
    assert "Calculs faits hors ligne" in page and "Corrélation, pas causalité" in page
    assert "RGA 2026" not in page and "DVF géolocalisées (Etalab)" in page


def test_barre_de_fourchette_presente(resultat):
    assert 'class="rg-barre"' in html_affiches(resultat)


def test_signal_faible_lit_l_effectif_des_angles_morts(resultat):
    page = html_affiches(resultat)
    assert "rg-signal-nombre" in page and ">1</span>" in page  # n_par_quadrant["Angle mort"] = 1 dans resume_test
    assert "commune cumule une sinistralité supérieure à la médiane du périmètre" in page
    assert textes.SIGNAL_NOTE in page


def test_le_bouton_ouvre_l_onglet_sinistralite(resultat):
    bouton = resultat.button(key="vers_sinistralite")
    assert bouton.label == textes.BOUTON_SIGNAL
    bouton.click().run()
    assert not resultat.exception
    assert resultat.session_state["onglet"] == "Sinistralité × écart"


def test_variante_nette_de_l_encadre(dossier_processed, monkeypatch):
    resume = resume_test()
    resume["modeles_globaux"]["principal"]["coefficients"]["fort"] = coefficient(-0.025, -0.05, 0.0, p=0.004)
    page = html_affiches(lancer(dossier_processed, monkeypatch, resume))
    assert "Cet écart est net, mais ce petit groupe diffère" in page and "fragile" not in page


def test_repli_sur_les_ventes_retenues(dossier_processed, monkeypatch):
    resume = resume_test()
    del resume["modeles_globaux"]["principal"]["n_ventes"]
    page = html_affiches(lancer(dossier_processed, monkeypatch, resume))
    assert "· 300 ventes retenues ·" in page


def test_vocabulaire_de_l_onglet(resultat):
    page = html_affiches(resultat).lower()
    for interdit in textes.EXPRESSIONS_INTERDITES:
        assert interdit not in page, f"« {interdit} » dans l'onglet Résultat"
    assert "€" not in page and "euro" not in page


@pytest.mark.parametrize("effet", [0.01, 0.0])
def test_effet_positif_ou_nul_dans_la_reference_ne_fait_pas_planter(dossier_processed, monkeypatch, effet):
    resume = resume_test()
    resume["modeles_globaux"]["principal"]["coefficients"]["moyen"] = coefficient(effet, -0.02, 0.04)
    app = lancer(dossier_processed, monkeypatch, resume)
    assert not app.exception
    page = html_affiches(app)
    assert textes.TESTE_NEUTRE in page and "moins cher" not in page
    assert textes.TESTE_CONCLUSION in page
