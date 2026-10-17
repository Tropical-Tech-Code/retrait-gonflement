import tomllib

import pytest

import textes
from conftest import coefficient, communes_test, resume_test
from retrait_gonflement.data.commun import CONFIG_PAR_DEFAUT

NB = textes.NBSP
MOINS = textes.MOINS
RESUME = resume_test()
COMMUNES = communes_test().set_index("code_insee")


def contraste(bas, haut, effet=0.0):
    return coefficient(effet, bas, haut)


# ---------------------------------------------------------------- formats

def test_formats_francais():
    assert textes.pct(-0.0289) == f"{MOINS}2,9{NB}%"
    assert textes.pct(0.0091, 2, True) == f"+0,91{NB}%"
    assert textes.pct(0.0, 1, True) == f"0,0{NB}%"
    assert textes.intervalle_pct(-0.0289, 0.0486, 2) == f"[{MOINS}2,89{NB}% ; +4,86{NB}%]"
    assert textes.entier(82525) == f"82{NB}525"
    assert textes.entier(193) == "193"
    assert textes.date_fr("2026-10-15") == "15/10/2026"
    assert textes.date_fr(None) == "non renseignée"
    assert textes.pluriel(1, "arrêté") == "1 arrêté" and textes.pluriel(3, "arrêté") == "3 arrêtés"


# ---------------------------------------------------------------- chiffre phare (seuil −3 %)

SEUIL = -0.03


@pytest.mark.parametrize("bas, haut, cas, fragment", [
    (-0.0289, 0.0486, "aucune_decote", f"environ 3{NB}%"),       # vraies valeurs du projet
    (-0.004, 0.03, "aucune_decote", f"environ 1{NB}%"),          # arrondi à 0 -> minimum 1 %
    (-0.0151, 0.02, "aucune_decote", f"environ 2{NB}%"),
    (-0.03, 0.05, "imprecis", "Trop imprécis"),                   # borne basse = seuil : pas « au-dessus »
    (-0.10, 0.05, "imprecis", "Trop imprécis"),
    (-0.08, -0.01, "decote", "Décote mesurée"),
    (0.01, 0.06, "positif", "Pas de décote"),
])
def test_phrase_chiffre_phare(bas, haut, cas, fragment):
    c = contraste(bas, haut)
    assert textes.cas_chiffre_phare(c, SEUIL) == cas
    assert fragment in textes.phrase_chiffre_phare(c, SEUIL)


def test_chiffre_phare_et_phrase_exacte_sur_les_valeurs_du_projet():
    c = RESUME["modeles_globaux"]["principal"]["contraste_fort_moins_moyen"]
    assert textes.chiffre_phare(c) == f"+0,91{NB}%"
    assert textes.phrase_chiffre_phare(c, SEUIL) == (
        f"Aucune décote mesurable : si elle existe, elle ne dépasse pas environ 3{NB}%."
    )


def test_details_et_estimables():
    lignes = textes.lignes_details(RESUME)
    assert len(lignes) == 5
    assert "« moyen »" in lignes[0] and "« fort »" in lignes[1]
    assert "attendues par hasard" in lignes[4] and "2 observées" in lignes[4]
    phrase = textes.phrase_estimables(193, 1607)
    assert f"193 communes sur 1{NB}607" in phrase and "en gris" in phrase and "pâle" in phrase


# ---------------------------------------------------------------- classes et légende

@pytest.mark.parametrize("prime, classe", [
    (-0.20, 0), (-0.10, 1), (-0.05, 1), (-0.03, 2), (0.0, 2), (0.0299, 2), (0.03, 3), (0.10, 4), (0.30, 4),
    (None, None), (float("nan"), None),
])
def test_classe_prime(prime, classe):
    assert textes.classe_prime(prime) == classe


def test_bornes_identiques_a_la_config():
    with open(CONFIG_PAR_DEFAUT, "rb") as f:
        assert list(textes.BORNES_CLASSES) == tomllib.load(f)["carte"]["classes_prime"]


def test_legende_cinq_classes():
    legende = textes.legende()
    assert [c for c, _ in legende] == [0, 1, 2, 3, 4]
    assert legende[0][1] == f"inférieur à {MOINS}10{NB}%"
    assert legende[4][1] == f"supérieur à +10{NB}%"


def test_seuil_arretes():
    assert textes.seuil_arretes(2.0) == 3   # « strictement au-dessus de 2 » = 3 arrêtés ou plus
    assert textes.seuil_arretes(2.5) == 3
    assert "3 arrêtés ou plus" in textes.libelle_sinistralite(2.0)


# ---------------------------------------------------------------- texte automatique

def texte(code):
    return textes.texte_commune(COMMUNES.loc[code], RESUME)


def test_texte_commune_en_decote_sinistree():
    t = texte("31001")
    assert f"{MOINS}12,0{NB}%" in t and "60 ventes dans le reste de la commune" in t
    assert "Statut : décote" in t and "Quadrant : Risque intégré" in t
    assert "5 arrêtés sécheresse sur 2015-2023" in t
    assert "supérieure à la médiane du périmètre (3 arrêtés ou plus)" in t


def test_texte_commune_pas_de_decote_cite_le_seuil():
    t = texte("31002")
    assert f"Statut : pas de décote (la borne basse de l'intervalle est au-dessus de {MOINS}3{NB}%" in t
    assert "Quadrant : Angle mort" in t


def test_texte_commune_indeterminee_sans_quadrant():
    t = texte("31003")
    assert "Statut : indéterminé" in t and "Pas de quadrant" in t
    assert "inférieure ou égale à la médiane du périmètre (2 arrêtés ou moins)" in t


def test_texte_commune_sans_arrete():
    t = texte("31004")
    assert "Aucun arrêté sécheresse reconnu sur 2015-2023" in t


def test_texte_commune_non_estimable_effectifs():
    t = texte("31005")
    assert "n'est pas estimable" in t and "effectifs sont insuffisants" in t
    assert "30 ventes retenues, dont 8 en zone forte" in t and "au moins 15 ventes en zone forte" in t
    assert "1 arrêté sécheresse" in t and "Quadrant" not in t and "écart de prix observé" not in t


def test_texte_commune_non_estimable_une_seule_zone():
    assert "pas de ventes dans les deux zones" in texte("31006")


@pytest.mark.parametrize("code", list(COMMUNES.index))
def test_texte_se_termine_par_le_rappel(code):
    assert texte(code).endswith(textes.RAPPEL)


# ---------------------------------------------------------------- vocabulaire imposé

def tous_les_textes():
    produits = [texte(code) for code in COMMUNES.index]
    produits += textes.lignes_details(RESUME)
    produits += [textes.phrase_estimables(193, 1607), textes.AVERTISSEMENT_REFERENCE, textes.PHRASE_CARTE_2026]
    produits += [libelle for _, libelle in textes.legende()]
    produits += [t for definition in textes.DEFINITIONS for t in definition]
    produits += [textes.phrase_chiffre_phare(contraste(bas, haut), SEUIL)
                 for bas, haut in [(-0.0289, 0.0486), (-0.1, 0.05), (-0.08, -0.01), (0.01, 0.06)]]
    return produits


def test_aucune_expression_interdite():
    for t in tous_les_textes():
        for interdit in textes.EXPRESSIONS_INTERDITES:
            assert interdit not in t.lower(), f"« {interdit} » dans : {t}"


def test_prime_de_risque_implicite_reservee_au_bandeau():
    assert textes.EXPRESSION_RESERVEE in textes.TITRE_BANDEAU.lower()
    constantes = {nom: v for nom, v in vars(textes).items()
                  if isinstance(v, str) and not nom.startswith("_") and nom != "EXPRESSION_RESERVEE"}
    avec_expression = {nom for nom, v in constantes.items() if textes.EXPRESSION_RESERVEE in v.lower()}
    assert avec_expression == {"TITRE_BANDEAU"}
    for t in tous_les_textes():
        assert textes.EXPRESSION_RESERVEE not in t.lower()
