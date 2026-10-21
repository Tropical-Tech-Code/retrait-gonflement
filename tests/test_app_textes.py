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
    assert textes.intervalle_pct(-0.0289, 0.0486) == f"[{MOINS}2,9{NB}% ; +4,9{NB}%]"
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
    assert textes.chiffre_phare(c) == f"+0,9{NB}%"
    assert textes.phrase_chiffre_phare(c, SEUIL) == (
        f"Aucune décote mesurable : si elle existe, elle ne dépasse pas environ 3{NB}%."
    )


def test_phrase_tests_multiples():
    resume = RESUME | {"n_significatives_decote": 16, "n_significatives_prime": 15, "n_attendu_hasard": 9.65}
    phrase = textes.phrase_tests_multiples(resume | {"n_communes_estimables": 193})
    assert phrase == (
        "Sur 193 communes, 31 montrent un écart net, contre une dizaine attendue par hasard. "
        "Ces écarts vont autant dans un sens que dans l'autre (16 décotes, 15 primes) : ils reflètent surtout "
        "des différences entre quartiers, plutôt qu'un problème de terrains argileux."
    )
    autre = textes.phrase_tests_multiples(resume | {"n_attendu_hasard": 4.6, "n_significatives_prime": 1})
    assert "contre 5 attendues par hasard" in autre and "(16 décotes, 1 prime)" in autre
    assert "Cliquez" not in phrase


def test_liste_de_recherche_decotes_puis_separateur_puis_autres():
    codes = textes.codes_liste(communes_test())
    assert codes == ["31001", textes.CODE_SEPARATEUR, "31002", "31003", "31004", "31005", "31006"]
    lignes = communes_test().set_index("code_insee", drop=False)
    assert textes.libelle_liste(lignes.loc["31001"]) == "Aucamville (31) · décote"
    assert textes.libelle_liste(lignes.loc["31002"]) == "Balma (31)"
    assert textes.libelle_liste(lignes.loc["31005"]) == "Escalquens (31)"


def test_noms_de_departements_identiques_a_ceux_du_pipeline():
    from retrait_gonflement.spatial import carres      # le pipeline estime la largeur des étiquettes avec ces noms
    assert carres.NOMS_DEPARTEMENTS == textes.NOMS_DEPARTEMENTS


def test_zones_et_departements_identiques_a_la_config():
    with open(CONFIG_PAR_DEFAUT, "rb") as f:
        config = tomllib.load(f)
    zones = config["carte"]["zones"]
    assert sorted(textes.ZONES.values()) == sorted(tuple(departements) for departements in zones.values())
    perimetre = config["perimetre"]["departements"]
    assert sorted(textes.NOMS_DEPARTEMENTS) == sorted(perimetre)
    assert all(textes.zone_de(dep) for dep in perimetre)


# ---------------------------------------------------------------- onglet Résultat

def principal(effet_moyen, p_moyen, effet_fort, p_fort):
    return {"coefficients": {"moyen": coefficient(effet_moyen, -0.1, 0.1, p_moyen),
                             "fort": coefficient(effet_fort, -0.1, 0.1, p_fort)}}


def test_paragraphe_teste_variante_fragile_ecarts_et_p_ranges():
    # moyen -3,38 %, fort -2,50 % : écarts rangés du plus petit au plus grand ; p égaux à deux décimales : un seul
    assert textes.paragraphe_teste(principal(-0.0338, 0.058, -0.0250, 0.061)) == (
        f"Les maisons des deux zones exposées se vendent 2,5 à 3,4{NB}% moins cher que les rares maisons "
        "hors zone argileuse ou en zone faible. Cet écart est fragile (p ≈ 0,06), "
        "et ce petit groupe diffère par d'autres traits que l'argile."
    )
    # p rangés quand ils diffèrent à deux décimales, quel que soit l'ordre moyen / fort
    assert "p ≈ 0,05 à 0,12" in textes.paragraphe_teste(principal(-0.03, 0.12, -0.02, 0.05))


def test_paragraphe_teste_variante_nette():
    texte = textes.paragraphe_teste(principal(-0.0338, 0.004, -0.0250, 0.2))
    assert texte.endswith("Cet écart est net, mais ce petit groupe diffère par d'autres traits que l'argile.")
    assert "fragile" not in texte and "p ≈" not in texte


def test_paragraphe_teste_fragile_seulement_si_les_deux_p_au_moins_0_01():
    assert "fragile" in textes.paragraphe_teste(principal(-0.03, 0.01, -0.02, 0.5))
    assert "net" in textes.paragraphe_teste(principal(-0.03, 0.0099, -0.02, 0.5))


def test_paragraphe_teste_ecarts_identiques():
    assert f"se vendent 3,0{NB}% moins cher" in textes.paragraphe_teste(principal(-0.03, 0.05, -0.03, 0.06))


@pytest.mark.parametrize("effet_moyen, effet_fort", [(0.01, -0.02), (-0.02, 0.01), (0.0, -0.02)])
def test_paragraphe_teste_phrase_neutre_si_un_effet_est_positif_ou_nul(effet_moyen, effet_fort):
    texte = textes.paragraphe_teste(principal(effet_moyen, 0.05, effet_fort, 0.05))
    assert texte == textes.TESTE_NEUTRE and "moins cher" not in texte


def test_phrase_lecture_et_reponse():
    c = contraste(-0.0289, 0.0486)
    assert textes.phrase_lecture(c, SEUIL) == (
        f"Si une décote existe, elle ne dépasse probablement pas environ 3{NB}%. "
        "Ne pas détecter de décote ne prouve pas qu'il n'y en a pas."
    )
    assert textes.phrase_reponse(c, SEUIL) == "Pas de différence de prix détectable entre zone d'argile forte et zone moyenne."
    assert "Trop imprécis" in textes.phrase_lecture(contraste(-0.1, 0.05), SEUIL)
    assert "moins cher" in textes.phrase_reponse(contraste(-0.08, -0.01), SEUIL)


def test_ligne_effectifs_lit_les_ventes_du_modele_puis_le_nettoyage():
    assert textes.ligne_effectifs(RESUME, 4).endswith(f"· 280 ventes · 4 départements · 2021-2025")
    sans_modele = {**RESUME, "modeles_globaux": {"principal": {}}}
    assert f"· 300 ventes retenues ·" in textes.ligne_effectifs(sans_modele, 1)
    assert "· 1 département ·" in textes.ligne_effectifs(sans_modele, 1)


def test_phrase_signal_accord():
    assert textes.phrase_signal(1).startswith("commune cumule ")
    assert textes.phrase_signal(9).startswith("communes cumulent ")


def test_sources_du_pied_sans_la_carte_2026():
    pied = textes.sources_pied(RESUME)
    assert "DVF géolocalisées" in pied and "RGA 2020" in pied and "2026" not in pied
    assert pied.endswith("Calculs faits hors ligne · Corrélation, pas causalité")


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


def test_texte_commune_en_decote():
    t = texte("31001")
    assert f"L'intervalle va de {MOINS}20,0{NB}% à {MOINS}3,0{NB}% : entièrement sous 0, une décote est mesurée." in t
    assert "Quadrant : Risque intégré." in t


def test_texte_commune_pas_de_decote_cite_le_seuil():
    t = texte("31002")
    assert f"au-dessus de {MOINS}3{NB}%, une décote éventuelle serait faible" in t
    assert "Quadrant : Angle mort." in t


def test_texte_commune_indeterminee_sans_quadrant():
    t = texte("31003")
    assert "trop large pour conclure" in t and "Quadrant" not in t


def test_texte_commune_ne_parle_ni_d_arretes_ni_de_prix_median():
    # les arrêtés sont dans une case de la fiche ; le prix médian n'est plus affiché
    for code in ("31001", "31004", "31005"):
        assert "arrêté" not in texte(code) and "médian" not in texte(code)


def test_texte_commune_non_estimable_effectifs():
    t = texte("31005")
    assert "n'est pas estimable" in t and "effectifs sont insuffisants" in t
    assert "30 ventes retenues, dont 8 en zone forte" in t and "au moins 15 ventes en zone forte" in t
    assert "Quadrant" not in t and "intervalle" not in t


def test_texte_commune_non_estimable_une_seule_zone():
    assert "pas de ventes dans les deux zones" in texte("31006")


@pytest.mark.parametrize("code", ["31001", "31002", "31003", "31004"])
def test_note_estimable_se_termine_par_le_rappel(code):
    assert texte(code).endswith("ni valeur de la maison, ni causalité.")
    assert texte(code).endswith(textes.RAPPEL)


@pytest.mark.parametrize("code", ["31005", "31006"])
def test_texte_non_estimable_sans_rappel(code):
    assert textes.RAPPEL not in texte(code)


# ---------------------------------------------------------------- vocabulaire imposé

def textes_resultat():
    principal = RESUME["modeles_globaux"]["principal"]
    net = {"coefficients": {"moyen": coefficient(-0.034, -0.07, 0.0, p=0.004), "fort": coefficient(-0.025, -0.05, 0.0, p=0.06)}}
    produits = [textes.paragraphe_teste(principal), textes.paragraphe_teste(net), textes.TESTE_CONCLUSION, textes.TESTE_NEUTRE]
    produits += [textes.phrase_reponse(contraste(bas, haut), SEUIL) for bas, haut in [(-0.0289, 0.0486), (-0.08, -0.01), (0.01, 0.06)]]
    produits += [textes.phrase_lecture(contraste(bas, haut), SEUIL) for bas, haut in [(-0.0289, 0.0486), (-0.1, 0.05)]]
    produits += [textes.phrase_signal(n) for n in (0, 1, 9)]
    produits += [textes.SURTITRE_RESULTAT, textes.LIBELLE_CHIFFRE, textes.SIGNAL_NOTE, textes.TITRE_SIGNAL, textes.BOUTON_SIGNAL]
    produits += [textes.ligne_effectifs(RESUME, 4), textes.sources_pied(RESUME)]
    return produits


def tous_les_textes():
    produits = [texte(code) for code in COMMUNES.index]
    produits += [textes.phrase_tests_multiples(RESUME), textes.PHRASE_CARTE_2026, textes.INVITE_COMMUNE,
                 textes.TITRE_INVITE]
    produits += [textes.texte_info_bulle(COMMUNES.reset_index().loc[i]) for i in range(len(COMMUNES))]
    produits += [textes.LEGENDE_PALE, textes.LEGENDE_NON_ESTIMABLE, textes.LEGENDE_SELECTION, textes.LIBELLE_ECART_FICHE]
    produits += list(textes.LIBELLE_CASES) + [textes.NOMS_DEPARTEMENTS[d] for d in textes.NOMS_DEPARTEMENTS]
    produits += textes_resultat()
    produits += [libelle for _, libelle in textes.legende()]
    produits += [t for definition in textes.DEFINITIONS for t in definition]
    produits += [textes.phrase_chiffre_phare(contraste(bas, haut), SEUIL)
                 for bas, haut in [(-0.0289, 0.0486), (-0.1, 0.05), (-0.08, -0.01), (0.01, 0.06)]]
    return produits


def test_aucune_expression_interdite():
    for t in tous_les_textes():
        for interdit in textes.EXPRESSIONS_INTERDITES:
            assert interdit not in t.lower(), f"« {interdit} » dans : {t}"


def test_prime_de_risque_implicite_absente_des_textes_actuels():
    # réservée au résultat global de la Méthodologie et au README : aucun texte de l'app ne la dit encore
    constantes = {nom: v for nom, v in vars(textes).items()
                  if isinstance(v, str) and not nom.startswith("_") and nom != "EXPRESSION_RESERVEE"}
    assert not {nom for nom, v in constantes.items() if textes.EXPRESSION_RESERVEE in v.lower()}
    for t in tous_les_textes():
        assert textes.EXPRESSION_RESERVEE not in t.lower()
