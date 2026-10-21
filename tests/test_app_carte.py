import html
import json

import pytest
from streamlit.testing.v1 import AppTest

import cartographie
import donnees
import textes

APP = str(donnees.RACINE / "app" / "streamlit_app.py")
TYPES_TEXTE = ("title", "subheader", "markdown", "caption", "warning", "error")


@pytest.fixture
def resultat(dossier_processed, monkeypatch):
    """Point d'entrée, onglet Résultat (ouvert au démarrage)."""
    monkeypatch.setenv(donnees.VARIABLE_DOSSIER, str(dossier_processed))
    return AppTest.from_file(APP, default_timeout=30).run()


@pytest.fixture
def at(dossier_processed, monkeypatch):
    """Point d'entrée, onglet Carte ouvert."""
    monkeypatch.setenv(donnees.VARIABLE_DOSSIER, str(dossier_processed))
    app = AppTest.from_file(APP, default_timeout=30)
    app.session_state["onglet"] = "Carte"
    return app.run()


def encadres_beiges(app) -> list[str]:
    return [m.value for m in app.markdown if 'class="rg-encadre rg-beige"' in m.value]


def textes_affiches(app) -> list[str]:
    affiches = [e.value for t in TYPES_TEXTE for e in app.get(t)]
    for m in app.metric:
        affiches += [m.label, m.value]
    return affiches


def deck_carte(app) -> dict:
    """Description pydeck envoyée au navigateur (AppTest range la carte sous « deck_gl_json_chart »)."""
    return json.loads(app.get("deck_gl_json_chart")[0].proto.json)


def donnees_carte(app) -> dict:
    """Données de la couche « communes » telle qu'elle est envoyée au navigateur."""
    couche = next(c for c in deck_carte(app)["layers"] if c["id"] == "communes")
    return couche["data"]


def test_phrases_sous_la_carte(at):
    contenu = [m.value for m in at.markdown]
    assert any(m.startswith("Seules 4 communes sur 6 sont estimables") and "en gris" in m and "pâle" in m for m in contenu)
    assert any("2 sont indéterminées" in m for m in contenu)


def test_la_carte_a_une_entite_par_commune(at):
    assert len(donnees_carte(at)["features"]) == 6


def test_contours_envoyes_au_navigateur_en_pixels(at):
    couches = {c["id"]: c for c in deck_carte(at)["layers"]}
    communes, limites = couches["communes"], couches["departements"]
    assert communes["lineWidthUnits"] == limites["lineWidthUnits"] == "pixels"
    assert communes["getLineWidth"] == cartographie.LIGNE_COMMUNES["largeur"]
    assert communes["getLineColor"] == cartographie.LIGNE_COMMUNES["couleur"]
    assert limites["getLineWidth"] == cartographie.LIGNE_DEPARTEMENTS["largeur"] > communes["getLineWidth"]
    assert limites["getLineColor"] == cartographie.LIGNE_DEPARTEMENTS["couleur"]
    for entite in donnees_carte(at)["features"]:
        couleur = entite["properties"]["couleur"]
        assert len(couleur) == 4 and all(isinstance(c, int) and 0 <= c <= 255 for c in couleur)


def test_fond_de_carte_coche_par_defaut_avec_la_mention_carto(at):
    assert at.checkbox[1].label == textes.LIBELLE_FOND and at.checkbox[1].value
    assert textes.FOND_DE_CARTE in [c.value for c in at.caption]
    assert deck_carte(at).get("mapStyle")
    at.checkbox[1].uncheck().run()
    assert textes.FOND_DE_CARTE not in [c.value for c in at.caption]
    assert deck_carte(at).get("mapStyle") is None
    assert not at.exception


def test_filtre_significatives_grise_les_autres(at):
    at.checkbox[0].check().run()
    couleurs = {f["properties"]["code_insee"]: f["properties"]["couleur"] for f in donnees_carte(at)["features"]}
    gardees = {c for c, couleur in couleurs.items() if couleur != cartographie.COULEUR_ECARTEE}
    assert gardees == {"31001", "31004"}


def test_aucune_fiche_avant_le_choix(at):
    assert not encadres_beiges(at)
    assert textes.INVITE_COMMUNE in [c.value for c in at.caption]


def test_fiche_commune_estimable(at):
    at.selectbox[0].select("31001").run()
    assert not at.exception
    assert at.subheader[-1].value == "Aucamville (31)"
    note = encadres_beiges(at)[0]
    assert "Statut : décote" in note and html.escape(textes.RAPPEL, quote=False) in note
    valeurs = {m.label: m.value for m in at.metric}
    assert valeurs["Écart de prix observé"] == f"{textes.MOINS}12,0{textes.NBSP}%"
    assert valeurs["Statut"] == "décote"


def test_fiche_commune_non_estimable(at):
    at.selectbox[0].select("31005").run()
    assert not at.exception
    valeurs = {m.label: m.value for m in at.metric}
    assert valeurs["Écart de prix observé"] == "non estimable"
    assert "n'est pas estimable" in encadres_beiges(at)[0]


def test_fichier_manquant_message_clair(dossier_processed, monkeypatch):
    (dossier_processed / "resume_global.json").unlink()
    monkeypatch.setenv(donnees.VARIABLE_DOSSIER, str(dossier_processed))
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    assert "Fichier manquant : data/processed/resume_global.json" in app.error[0].value


def test_vocabulaire_de_la_page(at):
    at.selectbox[0].select("31002").run()
    carte_affichee = textes_affiches(at)
    # l'onglet Carte ne dit jamais « prime de risque implicite » (réservé au résultat global)
    assert not [t for t in carte_affichee if textes.EXPRESSION_RESERVEE in t.lower()]
    for texte in carte_affichee:
        for interdit in textes.EXPRESSIONS_INTERDITES:
            assert interdit not in texte.lower(), f"« {interdit} » dans : {texte}"


def test_demarrage_par_le_point_d_entree(resultat):
    assert not resultat.exception
    assert [t.label for t in resultat.tabs] == list(textes.ONGLETS)
    assert any(textes.TITRE_APP in m.value and textes.SURTITRE in m.value for m in resultat.markdown)
    assert not resultat.sidebar.children
