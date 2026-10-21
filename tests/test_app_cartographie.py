import pytest

import cartographie
import donnees
import textes
from conftest import communes_test, geojson_test, resume_test

COMMUNES = communes_test()
LIGNES = COMMUNES.set_index("code_insee", drop=False)
CARRES = geojson_test(COMMUNES["code_insee"])
SUD_OUEST, SEINE_ET_MARNE = list(textes.ZONES)


def entites():
    return cartographie.preparer_carres(COMMUNES, CARRES)


def par_code(liste):
    return {e["properties"]["code_insee"]: e["properties"] for e in liste}


# ---------------------------------------------------------------- couleurs

@pytest.mark.parametrize("code, classe, alpha", [
    ("31001", 0, cartographie.ALPHA_PLEIN),   # écart −12 %, décote
    ("31002", 2, cartographie.ALPHA_PLEIN),   # écart +2 %, pas de décote : couleur franche
    ("31003", 1, cartographie.ALPHA_PALE),    # écart −5 %, indéterminé : pâle
    ("31004", 4, cartographie.ALPHA_PLEIN),   # écart +15 %, pas de décote
])
def test_couleur_estimable_selon_la_classe_et_le_statut(code, classe, alpha):
    assert cartographie.couleur(LIGNES.loc[code]) == [*cartographie.rgb(textes.COULEURS_CLASSES[classe]), alpha]


def test_couleur_non_estimable_grise_et_opaque():
    assert cartographie.couleur(LIGNES.loc["31005"]) == [*cartographie.rgb("#E4E6E2"), cartographie.ALPHA_PLEIN]


def test_pale_est_a_38_pour_cent():
    assert cartographie.ALPHA_PALE == round(255 * 0.38) == 97


def test_palette_de_la_maquette_seule_palette():
    assert textes.COULEURS_CLASSES == ("#A8431A", "#E99A68", "#BDB6A4", "#9DBEDD", "#4F7FB0")
    assert not hasattr(cartographie, "COULEURS_CLASSES") and not hasattr(cartographie, "GRIS")


def test_orange_pour_la_decote_bleu_pour_la_prime_sans_rouge_ni_vert():
    couleurs = [cartographie.rgb(c) for c in textes.COULEURS_CLASSES]
    for r, g, b in couleurs[:2]:
        assert r > b                       # orange
    for r, g, b in couleurs[3:]:
        assert b > r                       # bleu
    for r, g, b in couleurs:
        assert not (g > r and g > b)       # jamais dominé par le vert
    assert len(set(couleurs)) == 5


def luminance(hexa: str) -> float:
    def lineaire(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lineaire(c) for c in cartographie.rgb(hexa))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


@pytest.mark.parametrize("classe", range(5))
def test_chiffre_de_la_fiche_lisible_sur_fond_blanc(classe):
    contraste = 1.05 / (luminance(cartographie.couleur_texte(classe)) + 0.05)
    assert contraste >= 4.5


def test_hex_classe():
    assert cartographie.hex_classe(None) == "#E4E6E2"
    assert cartographie.hex_classe(0) == "#A8431A"


def est_couleur_valide(valeur) -> bool:
    return (isinstance(valeur, list) and len(valeur) == 4
            and all(type(c) is int and 0 <= c <= 255 for c in valeur))


def test_chaque_entite_porte_une_couleur_de_quatre_entiers():
    for entite in entites():
        assert est_couleur_valide(entite["properties"]["couleur"]), entite["properties"]
    for style in (cartographie.CONTOUR_NOIR, cartographie.CONTOUR_BLANC):
        assert est_couleur_valide(style["couleur"])


# ---------------------------------------------------------------- info-bulle et préparation

def test_info_bulle_en_texte_simple_nom_et_statut():
    assert textes.texte_info_bulle(LIGNES.loc["31001"]) == "Aucamville (31)\nDécote"
    assert textes.texte_info_bulle(LIGNES.loc["31002"]) == "Balma (31)\nPas de décote"
    assert textes.texte_info_bulle(LIGNES.loc["31003"]) == "Cugnaux (31)\nIndéterminé"
    assert textes.texte_info_bulle(LIGNES.loc["31005"]) == "Escalquens (31)\nNon estimable"
    assert "<" not in entites()[0]["properties"]["info"]


def test_preparer_carres_une_entite_par_commune():
    proprietes = par_code(entites())
    assert set(proprietes) == set(COMMUNES["code_insee"])
    p = proprietes["31001"]
    assert p["departement"] == "31" and len(p["couleur"]) == 4 and p["info"].startswith("Aucamville")


def test_preparer_carres_refuse_des_carres_incoherents():
    sans_un_carre = {"type": "FeatureCollection", "features": CARRES["features"][:-1]}
    with pytest.raises(donnees.ErreurDonneesApp, match="1 commune\\(s\\) sans carré"):
        cartographie.preparer_carres(COMMUNES, sans_un_carre)
    with pytest.raises(donnees.ErreurDonneesApp, match="1 carré\\(s\\) sans commune"):
        cartographie.preparer_carres(COMMUNES.iloc[:-1], CARRES)


# ---------------------------------------------------------------- zones

def test_zone_d_une_commune():
    assert textes.zone_de("31") == textes.zone_de("47") == textes.zone_de("82") == SUD_OUEST
    assert textes.zone_de("77") == SEINE_ET_MARNE
    with pytest.raises(KeyError):
        textes.zone_de("75")


def test_carres_de_la_zone():
    assert set(par_code(cartographie.carres_de_la_zone(entites(), SUD_OUEST))) == {
        "31001", "31002", "31003", "31004", "31005"}
    assert set(par_code(cartographie.carres_de_la_zone(entites(), SEINE_ET_MARNE))) == {"31006"}


def test_etiquettes_de_la_zone_en_capitales():
    etiquettes = cartographie.etiquettes_zone(resume_test(), SUD_OUEST)
    assert etiquettes == [{"position": [1.4, 43.05], "texte": "HAUTE-GARONNE · 31"}]    # 47 et 82 : sans étiquette
    assert cartographie.etiquettes_zone(resume_test(), SEINE_ET_MARNE)[0]["texte"] == "SEINE-ET-MARNE · 77"


# ---------------------------------------------------------------- cadrage et clic

def test_vue_zone_centre_et_zoom():
    toutes = entites()
    vue = cartographie.vue_zone(toutes)
    assert 43.0 < vue["latitude"] < 43.1 and 1.0 < vue["longitude"] < 2.1
    une_seule = cartographie.vue_zone(toutes[:1])
    assert une_seule["zoom"] > vue["zoom"]            # moins d'étendue : zoom plus fort
    assert vue["min_zoom"] == vue["zoom"]             # impossible de dézoomer au-delà du cadrage de la zone
    assert cartographie.vue_zone([])["zoom"] == 5.0


def test_vue_zone_cadre_aussi_les_etiquettes():
    toutes = entites()
    sans = cartographie.vue_zone(toutes)
    avec = cartographie.vue_zone(toutes, emprise=[0.2, 42.9, 3.5, 43.3])     # étiquettes plus larges que les carrés
    assert avec["zoom"] < sans["zoom"] and avec["min_zoom"] == avec["zoom"]
    assert avec["longitude"] == pytest.approx((0.2 + 3.5) / 2, abs=0.2)


def test_emprise_de_zone_lue_dans_le_resume():
    resume = resume_test()
    assert cartographie.emprise_de_zone(resume, SUD_OUEST) == [0.5, 42.9, 2.5, 43.3]
    assert cartographie.emprise_de_zone(resume, SEINE_ET_MARNE) == [1.8, 42.9, 2.6, 43.3]
    del resume["carres"]["zones"]["sud_ouest"]["emprise"]
    assert cartographie.emprise_de_zone(resume, SUD_OUEST) is None       # ancien fichier : cadrage sur les carrés


def test_vue_zone_tient_dans_la_carte():
    # la zone la plus large (ici 1,1 degré de long) tient dans 758 px, la plus haute dans la hauteur donnée
    carre = lambda lon, lat: {"geometry": {"type": "Polygon", "coordinates": [[[lon, lat], [lon + .01, lat + .01]]]}}
    large = cartographie.vue_zone([carre(0, 0), carre(2, 0)], 758, 370)
    haute = cartographie.vue_zone([carre(0, 0), carre(0, 2)], 758, 370)
    assert large["zoom"] > haute["zoom"]


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
