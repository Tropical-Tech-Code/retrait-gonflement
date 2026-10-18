import json

import pytest
from streamlit.testing.v1 import AppTest

import cartographie
import donnees
import textes

PAGE = str(donnees.RACINE / "app" / "vues" / "carte.py")
APP = str(donnees.RACINE / "app" / "streamlit_app.py")
TYPES_TEXTE = ("title", "subheader", "markdown", "caption", "info", "warning", "error")


@pytest.fixture
def at(dossier_processed, monkeypatch):
    monkeypatch.setenv(donnees.VARIABLE_DOSSIER, str(dossier_processed))
    return AppTest.from_file(PAGE, default_timeout=30).run()


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


def test_la_page_demarre_avec_le_bandeau(at):
    assert not at.exception
    assert at.title[0].value == "Retrait-gonflement des argiles et prix des maisons"
    assert at.subheader[0].value == textes.TITRE_BANDEAU
    assert at.metric[0].value == f"+0,91{textes.NBSP}%"
    phrase = f"Aucune décote mesurable : si elle existe, elle ne dépasse pas environ 3{textes.NBSP}%."
    assert any(phrase in m.value for m in at.markdown)
    assert at.expander[0].label == "Détails"


def test_le_bloc_details_contient_l_avertissement_et_les_effets(at):
    assert any("petit groupe" in w.value for w in at.warning)
    contenu = " ".join(m.value for m in at.markdown)
    assert "Décote globale « moyen »" in contenu and "Décote globale « fort »" in contenu
    assert textes.PHRASE_CARTE_2026 in contenu


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
    assert at.sidebar.checkbox[1].label == textes.LIBELLE_FOND and at.sidebar.checkbox[1].value
    assert textes.FOND_DE_CARTE in [c.value for c in at.caption]
    assert deck_carte(at).get("mapStyle")
    at.sidebar.checkbox[1].uncheck().run()
    assert textes.FOND_DE_CARTE not in [c.value for c in at.caption]
    assert deck_carte(at).get("mapStyle") is None
    assert not at.exception


def test_filtre_significatives_grise_les_autres(at):
    at.sidebar.checkbox[0].check().run()
    couleurs = {f["properties"]["code_insee"]: f["properties"]["couleur"] for f in donnees_carte(at)["features"]}
    gardees = {c for c, couleur in couleurs.items() if couleur != cartographie.COULEUR_ECARTEE}
    assert gardees == {"31001", "31004"}


def test_aucune_fiche_avant_le_choix(at):
    assert not at.info
    assert textes.INVITE_COMMUNE in [c.value for c in at.caption]


def test_fiche_commune_estimable(at):
    at.selectbox[0].select("31001").run()
    assert not at.exception
    assert at.subheader[-1].value == "Aucamville (31)"
    assert "Statut : décote" in at.info[0].value and at.info[0].value.endswith(textes.RAPPEL)
    valeurs = {m.label: m.value for m in at.metric}
    assert valeurs["Écart de prix observé"] == f"{textes.MOINS}12,0{textes.NBSP}%"
    assert valeurs["Statut"] == "décote"


def test_fiche_commune_non_estimable(at):
    at.selectbox[0].select("31005").run()
    assert not at.exception
    valeurs = {m.label: m.value for m in at.metric}
    assert valeurs["Écart de prix observé"] == "non estimable"
    assert "n'est pas estimable" in at.info[0].value


def test_la_note_de_l_agent_remplace_le_texte_automatique(dossier_processed, monkeypatch):
    import pandas as pd
    pd.DataFrame({"code_insee": ["31001"], "note": ["Note de l'analyste."]}).to_parquet(
        dossier_processed / "notes_communes.parquet", index=False
    )
    monkeypatch.setenv(donnees.VARIABLE_DOSSIER, str(dossier_processed))
    app = AppTest.from_file(PAGE, default_timeout=30).run()
    app.selectbox[0].select("31001").run()
    assert app.info[0].value == "Note de l'analyste."


def test_fichier_manquant_message_clair(dossier_processed, monkeypatch):
    (dossier_processed / "resume_global.json").unlink()
    monkeypatch.setenv(donnees.VARIABLE_DOSSIER, str(dossier_processed))
    app = AppTest.from_file(PAGE, default_timeout=30).run()
    assert not app.exception
    assert "Fichier manquant : data/processed/resume_global.json" in app.error[0].value


def test_vocabulaire_de_la_page(at):
    at.selectbox[0].select("31002").run()
    affiches = textes_affiches(at)
    # le titre du bandeau est le seul texte autorisé à dire « prime de risque implicite »
    assert [t for t in affiches if textes.EXPRESSION_RESERVEE in t.lower()] == [textes.TITRE_BANDEAU]
    for texte in affiches:
        if texte != textes.TITRE_BANDEAU:
            for interdit in textes.EXPRESSIONS_INTERDITES:
                assert interdit not in texte.lower(), f"« {interdit} » dans : {texte}"


def test_demarrage_par_le_point_d_entree(dossier_processed, monkeypatch):
    monkeypatch.setenv(donnees.VARIABLE_DOSSIER, str(dossier_processed))
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    assert app.metric[0].value == f"+0,91{textes.NBSP}%"
