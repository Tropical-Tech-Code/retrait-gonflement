import html
import json
from urllib.parse import unquote

import pytest
from streamlit.testing.v1 import AppTest

import cartographie
import charte
import donnees
import textes
from vues import carte as vue_carte

APP = str(donnees.RACINE / "app" / "streamlit_app.py")
SUD_OUEST, SEINE_ET_MARNE = list(textes.ZONES)
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


def fiches(app) -> list[str]:
    return [m.value for m in app.markdown if 'class="rg-fiche"' in m.value]


def tuiles(app) -> list[str]:
    return [m.value for m in app.markdown if 'class="rg-tuile"' in m.value]


def textes_affiches(app) -> list[str]:
    affiches = [e.value for t in TYPES_TEXTE for e in app.get(t)]
    for m in app.metric:
        affiches += [m.label, m.value]
    return affiches


def deck_carte(app) -> dict:
    """Description pydeck envoyée au navigateur (AppTest range la carte sous « deck_gl_json_chart »)."""
    return json.loads(app.get("deck_gl_json_chart")[0].proto.json)


def couche(app, id_: str) -> dict:
    return next(c for c in deck_carte(app)["layers"] if c["id"] == id_)


def codes_carres(app) -> set[str]:
    return {f["properties"]["code_insee"] for f in couche(app, "communes")["data"]["features"]}


# ---------------------------------------------------------------- tuiles, réglages, carte

def test_quatre_tuiles_avec_les_effectifs_des_fichiers(at):
    contenu = tuiles(at)
    assert len(contenu) == 4
    assert all(libelle in "".join(contenu) for libelle in (
        textes.TUILE_ESTIMABLES, textes.TUILE_DECOTE, textes.TUILE_PAS_DE_DECOTE, textes.TUILE_INDETERMINEES))
    assert "sur 6" in contenu[0]
    assert [t.split('rg-tuile-valeur">')[1].split("<")[0].strip() for t in contenu] == ["4", "1", "1", "2"]


def test_liste_des_communes_decotes_en_tete_separateur_puis_les_autres(at):
    options = at.selectbox[0].options
    assert options == [
        "Aucamville (31) · décote",                       # les communes en décote d'abord, avec leur statut
        "── Autres communes ──",
        "Balma (31)", "Cugnaux (31)", "Daux (31)", "Escalquens (31)", "Fonsorbes (77)",    # nom seul
    ]
    autres = [o.split(" (")[0] for o in options[2:]]
    assert autres == sorted(autres)
    assert sum("Aucamville" in o for o in options) == 1       # une commune n'apparaît qu'une fois : recherche par nom
    assert textes.SEPARATEUR_LISTE == options[1]


def test_choisir_le_separateur_ne_change_rien(at):
    at.selectbox[0].select("31002").run()
    avant = (at.session_state["commune"], at.segmented_control[0].value, fiches(at))
    at.selectbox[0].select(textes.CODE_SEPARATEUR).run()
    assert not at.exception
    assert at.selectbox[0].value == "31002"                  # sélection précédente conservée
    assert (at.session_state["commune"], at.segmented_control[0].value, fiches(at)) == avant


def test_choisir_le_separateur_sans_commune_ne_selectionne_rien(at):
    at.selectbox[0].select(textes.CODE_SEPARATEUR).run()
    assert not at.exception and at.selectbox[0].value is None
    assert not fiches(at) and "selection_noir" not in [c["id"] for c in deck_carte(at)["layers"]]


def test_recherche_d_une_commune_en_decote_selectionne_sa_fiche(at):
    at.selectbox[0].select("31001").run()
    assert not at.exception and "Aucamville" in fiches(at)[0]


def test_recherche_sans_libelle_invite_et_contour_d_accent_limites_a_ce_selectbox(at):
    champ = at.selectbox[0]
    assert champ.label == "Commune" and champ.proto.label_visibility.value == 2        # libellé masqué
    assert champ.placeholder == "Chercher une commune"
    regle = charte.CSS[charte.CSS.index(".st-key-recherche"):].split("}")[0]
    assert "1.5px solid #C2410C !important" in regle
    assert ":focus" not in regle and ":hover" not in regle              # visible au repos, pas seulement au clic
    assert 'div:has(> input[role="combobox"])' in regle                  # le champ de cette version de Streamlit
    assert "red" not in regle.lower()               # couleur d'accent du thème, pas de rouge
    # tous les sélecteurs de la règle sont limités au conteneur « recherche » (aucun autre champ n'est touché)
    assert all(s.strip().startswith(".st-key-recherche") for s in regle.split("{")[0].split(","))


def test_reglages_zone_et_commune_seulement(at):
    assert not at.checkbox and not at.multiselect          # ni fond de carte, ni filtres
    assert not at.sidebar.children
    assert at.segmented_control[0].options == list(textes.ZONES)
    assert at.segmented_control[0].value == SUD_OUEST
    assert at.selectbox[0].key == "commune"


def test_la_carte_montre_les_carres_de_la_zone_choisie(at):
    assert codes_carres(at) == {"31001", "31002", "31003", "31004", "31005"}
    at.segmented_control[0].set_value(SEINE_ET_MARNE).run()
    assert not at.exception
    assert codes_carres(at) == {"31006"}


def test_aucun_fond_de_carte_ni_limites(at):
    deck = deck_carte(at)
    # fond Carto clair (décision du 21/10 : il aide à se situer), avec sa mention et la note de position
    assert deck["mapStyle"].endswith("positron-gl-style/style.json") and deck["mapProvider"] == "carto"
    assert [c["id"] for c in deck["layers"]] == ["communes", "etiquettes"]      # ni limites ni autre couche
    bloc = next(m.value for m in at.markdown if m.value.startswith('<div class="rg-sous-carte">'))
    assert "Fond de carte © CARTO · © OpenStreetMap" in bloc
    assert "Position des carrés approximative (quelques km)." in bloc
    assert bloc.index("approximative") < bloc.index('class="rg-legende"')


def test_zoom_avant_seulement_molette_et_pave_tactile_desactives(at):
    # min_zoom n'est pas imposé par Streamlit : la molette (et le pavé tactile) sont désactivés ; boutons + et − gardés
    deck = deck_carte(at)
    assert deck["views"] == [{"@@type": "MapView", "controller": {"scrollZoom": False}}]
    assert cartographie.CONTROLEUR == {"scrollZoom": False}
    assert deck["initialViewState"]["minZoom"] == deck["initialViewState"]["zoom"]      # toujours transmis


def test_couleurs_envoyees_au_navigateur(at):
    for entite in couche(at, "communes")["data"]["features"]:
        couleur = entite["properties"]["couleur"]
        assert len(couleur) == 4 and all(isinstance(c, int) and 0 <= c <= 255 for c in couleur)
    par_code = {f["properties"]["code_insee"]: f["properties"]["couleur"] for f in couche(at, "communes")["data"]["features"]}
    assert par_code["31003"][3] == cartographie.ALPHA_PALE         # indéterminée : pâle
    assert par_code["31001"][3] == cartographie.ALPHA_PLEIN        # décote : franche
    assert par_code["31005"][:3] == list(cartographie.rgb("#E4E6E2"))      # non estimable : gris très clair


def test_etiquettes_des_departements_en_pixels_avec_accents(at):
    etiquettes = couche(at, "etiquettes")
    assert etiquettes["data"] == [{"position": [1.4, 43.05], "texte": "HAUTE-GARONNE · 31"}]
    assert etiquettes["sizeUnits"] == "pixels" and etiquettes["characterSet"] == "auto"
    assert etiquettes["background"] is True and etiquettes["getBackgroundColor"][3] < 255
    assert etiquettes["fontFamily"] == "sans-serif"          # police de l'app, pas la monospace par défaut


def test_vue_de_la_zone_avec_zoom_minimal_egal_au_zoom_initial(at):
    vue = deck_carte(at)["initialViewState"]
    assert vue["minZoom"] == vue["zoom"]
    avant = vue["zoom"]
    at.segmented_control[0].set_value(SEINE_ET_MARNE).run()
    assert deck_carte(at)["initialViewState"]["zoom"] != avant       # chaque zone a son cadrage


def test_phrase_unique_sous_la_carte_apres_la_legende(at):
    blocs = [m.value for m in at.markdown if m.value.startswith('<div class="rg-sous-carte">')]
    assert len(blocs) == 1
    bloc = blocs[0]
    assert bloc.count('class="rg-phrase-carte"') == 1 and "par hasard" in bloc
    assert "Sur 4 communes, 2 montrent un écart net, contre 0 attendue par hasard." in bloc    # chiffres de communes_test
    assert "(1 décote, 1 prime)" in bloc and "Cliquez" not in bloc
    assert bloc.index('class="rg-legende"') < bloc.index('class="rg-phrase-carte"')
    assert "Seules" not in " ".join(m.value for m in at.markdown)


def test_legende_complete_dont_la_selection(at):
    legende = next(m.value for m in at.markdown if 'class="rg-legende"' in m.value)
    for libelle in (textes.LEGENDE_PALE, textes.LEGENDE_NON_ESTIMABLE, textes.LEGENDE_SELECTION):
        assert libelle in legende
    assert legende.count('class="rg-sw') == 8        # 5 classes, pâle, gris, sélection


def test_mise_en_page_espacements_de_la_maquette():
    css = charte.CSS
    assert ".st-key-onglet_carte { gap: 16px; }" in css                 # tuiles / bloc carte + fiche
    assert ".rg-sous-carte { display: flex; flex-direction: column; gap: 12px; }" in css    # légende / phrase
    # la marge négative de Streamlit sous un bloc de texte faisait chevaucher les blocs
    assert '.st-key-onglet_carte [data-testid="stMarkdownContainer"] { margin-bottom: 0; }' in css


# ---------------------------------------------------------------- recherche et clic

def test_fiche_vide_avant_le_choix(at):
    assert not fiches(at) and not selection_presente(at)
    vides = [m.value for m in at.markdown if m.value.startswith('<div class="rg-invite">')]
    assert len(vides) == 1
    vide = vides[0]
    assert "<svg" in vide and 'width="32"' in vide and "#C2410C" in vide        # icône de clic en SVG inline
    assert f'<p class="rg-invite-titre">{textes.TITRE_INVITE}</p>' in vide
    assert ("Pour afficher la fiche d'une commune, zoomez puis cliquez sur un carré de la carte, "
            "ou cherchez-la par son nom.") in vide
    assert vide.index("rg-invite-titre") < vide.index("rg-invite-texte")        # titre au-dessus du texte
    assert "width: 56px; height: 56px; border-radius: 50%; background: #FBF3EC" in charte.CSS
    # bloc réduit à son contenu : aucune hauteur imposée
    assert not hasattr(vue_carte, "HAUTEUR_FICHE_VIDE")
    at.selectbox[0].select("31002").run()
    assert len(fiches(at)) == 1 and not [m for m in at.markdown if m.value.startswith('<div class="rg-invite">')]


def test_fiche_vide_echappe_le_texte():
    html_vide = charte.html_fiche_vide("<b>x</b>", "a & b")
    assert "&lt;b&gt;x&lt;/b&gt;" in html_vide and "a &amp; b" in html_vide


def selection_presente(app) -> bool:
    return "selection_noir" in [c["id"] for c in deck_carte(app)["layers"]]


def test_recherche_dans_la_zone_courante_ne_change_pas_la_zone(at):
    at.selectbox[0].select("31002").run()
    assert at.segmented_control[0].value == SUD_OUEST
    assert selection_presente(at)
    ids = [c["id"] for c in deck_carte(at)["layers"]]
    assert ids.index("selection_noir") < ids.index("selection_blanc")      # liseré blanc au-dessus du noir


def test_recherche_d_une_commune_de_l_autre_zone_change_de_zone(at):
    at.selectbox[0].select("31006").run()
    assert not at.exception
    assert at.segmented_control[0].value == SEINE_ET_MARNE
    assert codes_carres(at) == {"31006"} and selection_presente(at)
    assert "Seine-et-Marne (77)" in fiches(at)[0]
    at.selectbox[0].select("31001").run()
    assert at.segmented_control[0].value == SUD_OUEST


def centre_du_carre(app, code: str) -> tuple[float, float]:
    entite = next(e for e in couche(app, "communes")["data"]["features"] if e["properties"]["code_insee"] == code)
    points = list(cartographie._points(entite["geometry"]["coordinates"]))
    lons, lats = [p[0] for p in points], [p[1] for p in points]
    return ((min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2)       # centre du carré


def test_vue_centree_sur_la_commune_choisie_puis_vue_d_ensemble(at):
    densemble = deck_carte(at)["initialViewState"]
    at.selectbox[0].select("31002").run()
    vue = deck_carte(at)["initialViewState"]
    lon, lat = centre_du_carre(at, "31002")
    assert abs(vue["longitude"] - lon) < 0.01 and abs(vue["latitude"] - lat) < 0.01
    # Sud-Ouest : carrés de 13 px, 52 px visés (26 px de la zone aux gros carrés, un niveau de plus) : +3 niveaux
    assert vue["zoom"] == pytest.approx(densemble["zoom"] + 2 + cartographie.NIVEAUX_ZOOM_COMMUNE - 1, abs=0.01)
    assert vue["minZoom"] == densemble["minZoom"]                  # le dézoom reste borné à la zone
    at.session_state["commune"] = None                             # commune effacée
    at.run()
    assert deck_carte(at)["initialViewState"] == densemble


def test_zoom_de_la_commune_un_niveau_de_plus_dans_la_zone_aux_gros_carres(at):
    at.selectbox[0].select("31006").run()                          # commune de Seine-et-Marne (carrés de 26 px)
    vue = deck_carte(at)["initialViewState"]
    assert at.segmented_control[0].value == SEINE_ET_MARNE
    assert vue["zoom"] == pytest.approx(vue["minZoom"] + 1, abs=0.01)


def test_vue_commune_zoom_calcule_depuis_les_largeurs_de_la_cle_carres():
    resume = {"carres": {"zones": {"a": {"departements": ["31", "47", "82"], "largeur_carre_px": 10.0},
                                   "b": {"departements": ["77"], "largeur_carre_px": 40.0}}}}
    carre = {"geometry": {"coordinates": [[[0, 43], [0.1, 43], [0.1, 43.1], [0, 43.1], [0, 43]]]}}
    vue = cartographie.vue_commune({"zoom": 7.0, "min_zoom": 7.0, "latitude": 0, "longitude": 0}, carre, resume, SUD_OUEST)
    assert vue["zoom"] == pytest.approx(10.0) and vue["min_zoom"] == 7.0      # log2(40 / 10) = 2, plus un niveau
    assert vue["longitude"] == pytest.approx(0.05) and 43.0 < vue["latitude"] < 43.1


def test_reclic_sur_la_zone_efface_la_commune_et_garde_la_zone(at):
    at.selectbox[0].select("31002").run()
    at.segmented_control[0].set_value(None).run()                  # recliquer sur la zone active la désélectionne
    assert not at.exception
    assert at.segmented_control[0].value == SUD_OUEST
    assert at.selectbox[0].value is None and not fiches(at)


CLIC = {"selection": {"objects": {"communes": [{"properties": {"code_insee": "31002"}}]}}}


def cle_courante(app) -> str:
    """Clé du graphique dans l'état de l'AppTest (`cle_carte` a besoin du contexte d'une exécution)."""
    return f"carte_{app.session_state['version_carte'] if 'version_carte' in app.session_state else 0}"


def cliquer(app, evenement) -> None:
    """Simule un clic : l'événement est écrit sous la clé courante du graphique."""
    app.session_state[cle_courante(app)] = evenement


def test_clic_sur_un_carre_selectionne_la_commune(at):
    cliquer(at, CLIC)
    at.run()
    assert not at.exception
    assert at.selectbox[0].value == "31002"
    assert "Balma" in fiches(at)[0]


def test_apres_un_clic_aucune_selection_streamlit_ne_reste_active(at):
    """La clé du graphique change : la carte repart sans sélection (sinon Streamlit atténue les carrés)."""
    ancienne = cle_courante(at)
    cliquer(at, CLIC)
    at.run()
    assert at.selectbox[0].value == "31002" and selection_presente(at)    # notre contour reste
    assert cle_courante(at) != ancienne
    assert cartographie.code_selectionne(
        at.session_state[cle_courante(at)] if cle_courante(at) in at.session_state else None) is None


def test_un_clic_ne_declenche_qu_un_recalcul_et_laisse_la_page_stable(at, monkeypatch):
    """Le clic est traité une fois ; un recalcul de plus (par le navigateur) ne change rien à la page."""
    executions = []
    original = vue_carte.afficher
    monkeypatch.setattr(vue_carte, "afficher", lambda tout: (executions.append(1), original(tout))[1])
    cliquer(at, CLIC)
    at.run()
    assert len(executions) == 1                       # un clic = une exécution de l'onglet, pas de st.rerun
    apres_clic = at.get("deck_gl_json_chart")[0].proto.json
    etat = (at.session_state["commune"], at.session_state["zone"], at.session_state["version_carte"])
    assert etat == ("31002", SUD_OUEST, 1)
    for _ in range(3):                                # recalculs répétés
        at.run()
        assert at.get("deck_gl_json_chart")[0].proto.json == apres_clic
        assert (at.session_state["commune"], at.session_state["zone"], at.session_state["version_carte"]) == etat
    assert len(executions) == 4 and not at.exception


def test_la_selection_d_un_autre_carre_remplace_la_commune_sans_boucle(at):
    cliquer(at, CLIC)
    at.run()
    autre = {"selection": {"objects": {"communes": [{"properties": {"code_insee": "31004"}}]}}}
    cliquer(at, autre)
    at.run()
    assert at.selectbox[0].value == "31004"


def test_le_code_de_l_app_ne_force_aucun_recalcul():
    sources = [p.read_text(encoding="utf-8") for p in (donnees.RACINE / "app").rglob("*.py")]
    assert not [s for s in sources if "st.rerun" in s or "experimental_rerun" in s]


# ---------------------------------------------------------------- fiche

def test_fiche_commune_estimable(at):
    at.selectbox[0].select("31001").run()
    assert not at.exception
    fiche = fiches(at)[0]
    assert "Haute-Garonne (31)" in fiche and "Aucamville" in fiche
    assert html.escape(textes.LIBELLE_ECART_FICHE, quote=False) in fiche
    assert f"{textes.MOINS}12,0{textes.NBSP}%" in fiche
    assert f"[{textes.MOINS}20,0{textes.NBSP}% ; {textes.MOINS}3,0{textes.NBSP}%]" in fiche
    assert 'class="rg-pastille">Décote<' in fiche
    # trois cases : ventes, dont zone forte, arrêtés
    for libelle, valeur in zip(textes.LIBELLE_CASES, ("100", "40", "5")):
        assert f'rg-case-libelle">{libelle}</div><div class="rg-case-valeur">{valeur}<' in fiche
    # chiffre coloré selon sa classe (−12 % : première classe)
    assert f"color:{cartographie.couleur_texte(0)}" in fiche
    assert 'class="rg-encadre rg-beige rg-note"' in fiche
    assert "ni valeur de la maison, ni causalité." in fiche


def test_fiche_commune_non_estimable(at):
    at.selectbox[0].select("31005").run()
    assert not at.exception
    fiche = fiches(at)[0]
    assert "—" in fiche and 'class="rg-pastille">Non estimable<' in fiche
    assert "rg-fiche-ic" not in fiche and "rg-beige" not in fiche
    assert 'class="rg-encadre rg-gris rg-note"' in fiche and "effectifs sont insuffisants" in fiche


def test_fiche_sans_prix_median(at):
    at.selectbox[0].select("31002").run()
    assert "médian" not in fiches(at)[0].lower() and "€" not in fiches(at)[0]


def test_fichier_manquant_message_clair(dossier_processed, monkeypatch):
    (dossier_processed / "resume_global.json").unlink()
    monkeypatch.setenv(donnees.VARIABLE_DOSSIER, str(dossier_processed))
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert not app.exception
    assert "Fichier manquant : data/processed/resume_global.json" in app.error[0].value


def test_carres_manquants_message_clair(dossier_processed, monkeypatch):
    (dossier_processed / "carres.geojson").unlink()
    monkeypatch.setenv(donnees.VARIABLE_DOSSIER, str(dossier_processed))
    app = AppTest.from_file(APP, default_timeout=30).run()
    assert "Fichier manquant : data/processed/carres.geojson" in app.error[0].value


def test_vocabulaire_de_la_page(at):
    at.selectbox[0].select("31002").run()
    carte_affichee = textes_affiches(at) + [fiches(at)[0]]
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
