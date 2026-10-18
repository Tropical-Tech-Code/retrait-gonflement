import pytest

import cartographie
import donnees
from conftest import communes_test, geojson_test

COMMUNES = communes_test()
LIGNES = COMMUNES.set_index("code_insee", drop=False)
CONTOURS = geojson_test(COMMUNES["code_insee"])


def entites():
    return cartographie.preparer_carte(COMMUNES, CONTOURS)


def par_code(liste):
    return {e["properties"]["code_insee"]: e["properties"] for e in liste}


# ---------------------------------------------------------------- couleurs

@pytest.mark.parametrize("code, classe, alpha", [
    ("31001", 0, cartographie.ALPHA_PLEIN),   # écart −12 %, significatif
    ("31003", 1, cartographie.ALPHA_PALE),    # écart −5 %, IC contient 0 : pâle
    ("31002", 2, cartographie.ALPHA_PALE),    # écart +2 %, IC contient 0 : pâle
    ("31004", 4, cartographie.ALPHA_PLEIN),   # écart +15 %, significatif
])
def test_couleur_estimable(code, classe, alpha):
    assert cartographie.couleur(LIGNES.loc[code]) == [*cartographie.COULEURS_CLASSES[classe], alpha]


def test_couleur_non_estimable_grise():
    assert cartographie.couleur(LIGNES.loc["31005"]) == [*cartographie.GRIS, cartographie.ALPHA_NON_ESTIMABLE]


def test_orange_pour_la_decote_bleu_pour_la_prime_sans_rouge_ni_vert():
    for r, g, b in cartographie.COULEURS_CLASSES[:2]:
        assert r > b                       # orange
    for r, g, b in cartographie.COULEURS_CLASSES[3:]:
        assert b > r                       # bleu
    for r, g, b in cartographie.COULEURS_CLASSES:
        assert not (g > r and g > b)       # jamais dominé par le vert
    assert len(set(cartographie.COULEURS_CLASSES)) == 5


def test_hex_classe():
    assert cartographie.hex_classe(None) == "#8c8c8c"
    assert cartographie.hex_classe(0) == "#b35406"


def est_couleur_valide(valeur) -> bool:
    return (isinstance(valeur, list) and len(valeur) == 4
            and all(type(c) is int and 0 <= c <= 255 for c in valeur))


def test_chaque_entite_porte_une_couleur_de_quatre_entiers():
    for entite in entites():
        assert est_couleur_valide(entite["properties"]["couleur"]), entite["properties"]
    # communes écartées par un filtre : même format
    for entite in cartographie.filtrer(entites(), ["77"], True):
        assert est_couleur_valide(entite["properties"]["couleur"])
    assert est_couleur_valide(cartographie.COULEUR_ECARTEE)


def test_contours_fins_et_clairs_en_pixels_limites_departements_marquees():
    communes, departements = cartographie.options_couches()
    assert communes["line_width_units"] == departements["line_width_units"] == "'pixels'"   # guillemets : voir cartographie.py
    assert 0.5 <= communes["get_line_width"] <= 1
    r, g, b, alpha = communes["get_line_color"]
    assert min(r, g, b) >= 200 and alpha < 255              # clair et semi-transparent
    r, g, b, alpha = departements["get_line_color"]
    assert max(r, g, b) <= 80 and alpha == 255              # sombre et opaque
    assert departements["get_line_width"] >= 2 * communes["get_line_width"]
    assert est_couleur_valide(communes["get_line_color"]) and est_couleur_valide(departements["get_line_color"])
    assert communes["get_fill_color"] == "properties.couleur"


def test_limites_exterieures_sans_les_trous():
    exterieur = [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]
    trou_1, trou_2 = [[1, 1], [2, 1], [2, 2], [1, 1]], [[3, 3], [3.5, 3], [3.5, 3.5], [3, 3]]
    departements = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"departement": "31"},
         "geometry": {"type": "Polygon", "coordinates": [exterieur, trou_1, trou_2]}},
        {"type": "Feature", "properties": {"departement": "77"},
         "geometry": {"type": "MultiPolygon", "coordinates": [[exterieur, trou_1], [exterieur]]}},
    ]}
    resultat = cartographie.limites_exterieures(departements)
    assert resultat["features"][0]["geometry"]["coordinates"] == [exterieur]
    assert resultat["features"][1]["geometry"]["coordinates"] == [[exterieur], [exterieur]]
    assert resultat["features"][0]["properties"] == {"departement": "31"}
    # le fichier lu n'est pas modifié
    assert len(departements["features"][0]["geometry"]["coordinates"]) == 3


# ---------------------------------------------------------------- info-bulle

def test_info_bulle_estimable():
    html = cartographie.info_bulle(LIGNES.loc["31001"])
    assert html.startswith("<b>Aucamville (31)</b><br/>")
    assert "Écart de prix observé" in html and "40 en zone forte, 60 dans le reste" in html
    assert "5 arrêtés sécheresse 2015-2023" in html


def test_info_bulle_non_estimable_donne_le_motif():
    html = cartographie.info_bulle(LIGNES.loc["31005"])
    assert "Non estimable : ses effectifs sont insuffisants" in html and "Écart de prix" not in html


def test_info_bulle_echappe_le_html():
    ligne = LIGNES.loc["31001"].copy()
    ligne["nom"] = "<script>alert(1)</script>"
    html = cartographie.info_bulle(ligne)
    assert "<script>" not in html and "&lt;script&gt;" in html


# ---------------------------------------------------------------- préparation et filtres

def test_preparer_carte_une_entite_par_commune():
    proprietes = par_code(entites())
    assert set(proprietes) == set(COMMUNES["code_insee"])
    p = proprietes["31001"]
    assert p["estimable"] and p["significatif"] and p["departement"] == "31"
    assert len(p["couleur"]) == 4 and p["info"].startswith("<b>")
    assert not proprietes["31005"]["estimable"]


def test_preparer_carte_refuse_des_contours_incoherents():
    sans_un_contour = {"type": "FeatureCollection", "features": CONTOURS["features"][:-1]}
    with pytest.raises(donnees.ErreurDonneesApp, match="1 commune\\(s\\) sans contour"):
        cartographie.preparer_carte(COMMUNES, sans_un_contour)
    with pytest.raises(donnees.ErreurDonneesApp, match="1 contour\\(s\\) sans commune"):
        cartographie.preparer_carte(COMMUNES.iloc[:-1], CONTOURS)


def test_filtre_departement_grise_les_autres():
    avant = entites()
    apres = par_code(cartographie.filtrer(avant, ["77"], False))
    assert all(p["couleur"] == cartographie.COULEUR_ECARTEE for p in apres.values())
    assert "hors filtre" in apres["31001"]["info"]
    # les entités d'origine ne sont pas modifiées
    assert par_code(avant)["31001"]["couleur"] != cartographie.COULEUR_ECARTEE
    gardees = par_code(cartographie.filtrer(avant, ["31", "77"], False))
    assert gardees["31001"]["couleur"] == par_code(avant)["31001"]["couleur"]


def test_filtre_significatives_seulement():
    apres = par_code(cartographie.filtrer(entites(), ["31"], True))
    gardees = {c for c, p in apres.items() if p["couleur"] != cartographie.COULEUR_ECARTEE}
    assert gardees == {"31001", "31004"}      # decote et prime significatives
    sans_filtre = par_code(cartographie.filtrer(entites(), ["31"], False))
    assert all(p["couleur"] != cartographie.COULEUR_ECARTEE for p in sans_filtre.values())


# ---------------------------------------------------------------- cadrage et clic

def test_vue_initiale_centre_et_zoom():
    toutes = entites()
    vue = cartographie.vue_initiale(toutes)
    assert 43.0 < vue["latitude"] < 43.1 and 1.0 < vue["longitude"] < 2.1
    une_seule = cartographie.vue_initiale(toutes[:1])
    assert une_seule["zoom"] > vue["zoom"]            # moins d'étendue : zoom plus fort
    assert cartographie.vue_initiale([]) == cartographie.CENTRE_PAR_DEFAUT


def test_vue_initiale_lit_les_multipolygones():
    multi = {"geometry": {"type": "MultiPolygon", "coordinates": [[[[1.0, 43.0], [2.0, 43.0], [2.0, 44.0], [1.0, 43.0]]]]}}
    vue = cartographie.vue_initiale([multi])
    assert vue["longitude"] == 1.5 and vue["latitude"] == 43.5


@pytest.mark.parametrize("evenement, attendu", [
    ({"selection": {"objects": {"communes": [{"properties": {"code_insee": "31002"}}]}}}, "31002"),
    ({"selection": {"objects": {"communes": [{"code_insee": "31003"}]}}}, "31003"),
    ({"selection": {"objects": {}}}, None),
    ({"selection": {"objects": {"communes": []}}}, None),
    ({}, None),
    (None, None),
])
def test_code_selectionne(evenement, attendu):
    assert cartographie.code_selectionne(evenement) == attendu
