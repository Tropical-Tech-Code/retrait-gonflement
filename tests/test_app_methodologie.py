import copy
import re

import pytest

import donnees
import textes
from conftest import coefficient, resume_test
from test_app_resultat import html_affiches, lancer

NB = textes.NBSP
# Noms propres numériques écrits dans les gabarits : la réforme de 2025, la carte 2026, les intervalles à 95 %
ECRITS_EN_DUR = {"95", "2025", "2026"}


def cartes(resume=None):
    return textes.cartes_methodologie(resume or resume_test())


def texte_des_cartes(resume=None, avec_rangs=True) -> str:
    morceaux = []
    for carte in cartes(resume):
        surtitre = carte["surtitre"] if avec_rangs else carte["surtitre"].split(" · ", 1)[1]
        morceaux += [surtitre, carte.get("titre") or "", *carte.get("paragraphes", []), *carte.get("items", [])]
    return " ".join(morceaux)


def decaler(valeur):
    """Change tous les nombres du résumé : entiers + 137, décimaux transformés, chiffres des textes décalés."""
    if isinstance(valeur, bool):
        return valeur
    if isinstance(valeur, int):
        return valeur + 137
    if isinstance(valeur, float):
        return valeur * 37 + 13.07
    if isinstance(valeur, str):
        return re.sub(r"\d", lambda m: str((int(m.group()) + 1) % 10), valeur)
    if isinstance(valeur, list):
        return [decaler(v) for v in valeur]
    if isinstance(valeur, dict):
        return {cle: decaler(v) for cle, v in valeur.items()}
    return valeur


def nombres(texte: str) -> set[str]:
    """Nombres écrits (décimales et milliers compris : « 1 000 » est un seul nombre)."""
    return set(re.findall(r"\d+(?:,\d+)?", re.sub(rf"(?<=\d){NB}(?=\d)", "", texte)))


def test_six_cartes_dans_l_ordre_de_la_maquette():
    c = cartes()
    assert [carte["surtitre"] for carte in c] == [
        "1 · Question testée", "2 · Données", "3 · Modèle", "4 · Robustesse", "5 · Écarts par commune", "6 · Limites",
    ]
    assert [bool(carte.get("beige")) for carte in c] == [False] * 5 + [True]
    assert c[0]["titre"] == "Zone forte contre zone moyenne" and c[5].get("titre") is None


def test_aucun_chiffre_en_dur_dans_les_cartes():
    # chaque nombre affiché doit changer quand on change les données (hors noms propres : 95 %, 2025, 2026)
    # (les numéros de rang 1 à 6 des cartes sont de la mise en page, pas des données)
    avant = nombres(texte_des_cartes(avec_rangs=False))
    autre = decaler(resume_test())
    autre["primes_communes"]["par_departement"] = {str(90 + i): {} for i in range(9)}   # le nombre de départements compte les clés, leurs codes s'affichent
    apres = nombres(texte_des_cartes(autre, avec_rangs=False))
    assert avant - ECRITS_EN_DUR
    assert (avant & apres) <= ECRITS_EN_DUR, avant & apres


def test_chiffres_lus_dans_le_resume():
    texte = texte_des_cartes()
    assert f"Dans ces quatre départements (31, 47, 77, 82), 48 à 53{NB}% des ventes sont en zone forte" in texte
    assert f"moins de 8{NB}% des ventes" in texte                    # (0,07 + 0,004) -> 7,4 % -> 8
    assert f"Sur 1{NB}000 transactions immobilières (DVF, 2021-2025), 300 ventes d'une seule maison sont retenues." in texte
    assert ("Exposition : carte RGA 2020, consultable par les acheteurs pendant toute la période ; "
            "la carte 2026 sert seulement de contrôle.") in texte
    assert ("Sinistres : arrêtés sécheresse 2015-2023 de GASPAR (Gestion assistée des procédures administratives "
            "relatives aux risques naturels et technologiques) ; les sécheresses plus récentes sont absentes de "
            "GASPAR à la date d'extraction (délai de reconnaissance probable).") in texte
    assert ("Estimation sur 280 ventes (celles seules dans leur commune et leur trimestre sont retirées)."
            in texte)
    assert "Régression du prix au m² (en logarithme, pour lire les écarts en %)" in texte
    assert f"Zone forte contre tout le reste : +0,7{NB}% [{textes.MOINS}3,0{NB}% ; +4,5{NB}%]." in texte
    assert f"(+1,4{NB}% [{textes.MOINS}3,5{NB}% ; +6,4{NB}%])" in texte
    assert (f"Ventes de 2025 : l'écart de la zone forte bouge de {textes.MOINS}1,2{NB}% "
            f"[{textes.MOINS}2,7{NB}% ; +0,3{NB}%], sans conclusion possible.") in texte
    assert ("Maisons passées en zone forte seulement avec la carte 2026 (853 ventes, 8 communes), vendues avant "
            f"que l'acheteur puisse le savoir : +3,6{NB}%, aucune décote ; les écarts viennent plutôt des "
            "quartiers (fourchette peu fiable : 8 communes).") in texte
    assert "ce que confirme le contrôle par la carte 2026." in texte
    assert (f"La limite de 3{NB}% est fragile : sans les ventes proches d'une limite de zone, "
            f"la borne basse passe à {textes.MOINS}3,5{NB}%.") in texte
    assert "erreurs groupées" not in texte        # le détail reste dans docs/method.md
    assert ("Parmi les 4 communes estimables (au moins 15 ventes en zone forte, 15 ailleurs, 50 au total), "
            "on compte 2 écarts significatifs (1 négatif, 1 positif) contre environ 0 attendus par hasard") in texte
    assert "Quatre départements très exposés : résultats non transposables à toute la France." in texte
    assert "Aucun arrêté sécheresse reconnu après 2023 (délai de reconnaissance probable)." in texte
    assert textes.LIMITE_CAUSALITE == "Corrélation, pas causalité ; aucun écart n'estime la valeur d'une maison."
    assert f"La carte 2026 change le niveau d'environ 2{NB}% des ventes, dans les deux sens." in texte
    assert textes.LIMITE_CARRES in texte and textes.LIMITE_CAUSALITE in texte


def test_sigle_gaspar_developpe_une_seule_fois_dans_l_app(methodologie):
    assert texte_des_cartes().count(textes.GASPAR_DEVELOPPE) == 1
    assert html_affiches(methodologie).count(textes.GASPAR_DEVELOPPE) == 1
    sources = [p.read_text(encoding="utf-8") for p in (donnees.RACINE / "app").rglob("*.py")]
    assert sum(s.count("procédures administratives") for s in sources) == 1   # une seule constante


def test_annees_des_arretes_lues_dans_le_resume():
    resume = resume_test()
    resume["catnat"]["periode"] = "2012-2022"
    assert "arrêtés sécheresse 2012-2022 de GASPAR" in texte_des_cartes(resume)


def test_robustesse_tient_ou_depend_des_variantes():
    assert cartes()[3]["titre"] == textes.METHO_TITRE_TIENT
    assert "même conclusion" in " ".join(cartes()[3]["items"])
    resume = resume_test()
    resume["modeles_globaux"]["sans_limite"]["contraste_fort_moins_moyen"] = coefficient(-0.08, -0.14, -0.02)
    carte = cartes(resume)[3]
    assert carte["titre"] == textes.METHO_TITRE_DEPEND
    assert "autre conclusion" in " ".join(carte["items"])


def test_phrase_carte_2026_selon_les_sens_et_la_part():
    base = resume_test()["carte_2026"]
    def phrase(**changes):
        return textes.phrase_carte_2026({"carte_2026": base | changes})
    assert phrase() == f"La carte 2026 change le niveau d'environ 2{NB}% des ventes, dans les deux sens."
    assert phrase(n_vers_moins_fort=0) == f"La carte 2026 change le niveau d'environ 2{NB}% des ventes, vers un niveau plus fort."
    assert phrase(n_vers_plus_fort=0).endswith("vers un niveau moins fort.")
    assert phrase(part_change=0.003) == "La carte 2026 change le niveau de moins d'un pour cent des ventes, dans les deux sens."
    assert phrase(n_change=0, n_vers_plus_fort=0, n_vers_moins_fort=0, part_change=0.0) == (
        "La carte 2026 ne change le niveau d'aucune vente.")
    assert textes.phrase_carte_2026({}) is None
    assert textes.phrase_carte_2026({"carte_2026": base | {"part_change": None}}) is None


def test_phrase_des_zones_plage_et_plafond():
    assert textes.phrase_zones(resume_test()).startswith(f"48 à 53{NB}% des ventes sont en zone forte")
    une_seule = resume_test() | {"zones_rga": {"31": {"n_ventes": 9, "part_0": 0.0, "part_1": 0.0, "part_2": 0.6, "part_3": 0.4}}}
    assert textes.phrase_zones(une_seule).startswith(f"40{NB}% des ventes")
    assert f"moins de 1{NB}%" in textes.phrase_zones(une_seule)
    assert textes.phrase_zones({}) == ""


def test_cles_absentes_sans_plantage():
    resume = resume_test()
    for cle in ("zones_rga", "carte_2026"):
        resume.pop(cle)
    for cle in ("sans_limite", "reforme_2025", "placebo_bascule", "fort_contre_reste"):
        resume["modeles_globaux"].pop(cle)
    texte = texte_des_cartes(resume)
    assert "environ 2" not in texte and "des ventes sont en zone forte" not in texte
    assert "La comparaison porte sur les zones d'argile forte et moyenne." in texte
    assert cartes(resume)[3]["items"] == [] and cartes(resume)[3]["titre"] == textes.METHO_TITRE_TIENT


def test_carte_donnees_sans_carte_2026_n_ajoute_pas_de_comparaison():
    resume = resume_test()
    resume["sources"]["liste"] = [s for s in resume["sources"]["liste"] if s["cle"] != "rga_2026"]
    assert "de contrôle" not in textes.texte_donnees(resume)
    assert "consultable par les acheteurs pendant toute la période." in textes.texte_donnees(resume)
    assert "contrôle par la carte" not in textes.texte_communes(resume)


def test_mois_et_annee_du_pied():
    assert textes.mois_annee("2026-10-15") == "octobre 2026"
    assert textes.mois_annee("2025-01-31") == "janvier 2025"
    assert textes.mois_annee("2026-13-05") is None and textes.mois_annee(None) is None and textes.mois_annee("") is None


def test_placebo_sans_ecart_positif_ne_parle_pas_de_quartiers():
    resume = resume_test()
    resume["modeles_globaux"]["placebo_bascule"]["coefficients"]["bascule"] = coefficient(-0.02, -0.05, 0.01)
    placebo = [i for i in cartes(resume)[3]["items"] if i.startswith("Maisons passées")][0]
    assert "écart non causal" in placebo and "quartiers" not in placebo


def test_placebo_sans_nombre_de_communes_dans_le_statut_ni_n_communes():
    resume = resume_test()
    resume["modeles_globaux"]["placebo_bascule"]["statut"] = "autre format"
    placebo = [i for i in cartes(resume)[3]["items"] if i.startswith("Maisons passées")][0]
    assert "(853 ventes)" in placebo and "commune" not in placebo


def test_placebo_lit_le_nombre_de_communes_apres_ventes_et_ignore_n_communes():
    # chaîne réelle du JSON ; la clé n_communes (1276) compte les communes du modèle, pas celles du test
    resume = resume_test()
    placebo_json = resume["modeles_globaux"]["placebo_bascule"]
    placebo_json["statut"] = "indicatif, faible puissance (853 ventes, 8 communes)"
    placebo_json["n_communes"] = 1276
    placebo = [i for i in cartes(resume)[3]["items"] if i.startswith("Maisons passées")][0]
    assert "(853 ventes, 8 communes)" in placebo and "1 276" not in placebo and "1276" not in placebo


def test_puce_limite_de_3_pour_cent_seulement_si_la_borne_passe_sous_le_seuil():
    resume = resume_test()
    resume["modeles_globaux"]["sans_limite"]["contraste_fort_moins_moyen"] = coefficient(0.0137, -0.0250, 0.0640)
    assert not [i for i in cartes(resume)[3]["items"] if "fragile" in i]


def test_variante_2025_sans_mot_reforme():
    texte = texte_des_cartes().lower()
    for absent in textes.EXPRESSIONS_ABSENTES:
        assert absent not in texte


def test_nombres_en_debut_de_phrase_ecrits_en_lettres():
    assert [textes.debut_phrase(n) for n in (0, 1, 4, 16)] == ["Zéro", "Un", "Quatre", "Seize"]
    assert textes.debut_phrase(17) == "17"
    assert textes.limites(resume_test())[1] == "Quatre départements très exposés : résultats non transposables à toute la France."
    un = resume_test()
    un["primes_communes"]["par_departement"] = {"31": {}}
    assert textes.limites(un)[1] == "Un département très exposé : résultats non transposables à toute la France."


def test_aucune_phrase_ne_commence_par_un_chiffre():
    autre = decaler(resume_test())
    autre["primes_communes"]["par_departement"] = {str(i): {} for i in range(9)}
    for resume in (resume_test(), autre):
        for carte in cartes(resume):
            for texte in [*carte.get("paragraphes", []), *carte.get("items", [])]:
                for phrase in re.split(r"(?<=[.!?])\s+", texte):
                    assert not phrase[:1].isdigit(), phrase


@pytest.fixture
def methodologie(dossier_processed, monkeypatch):
    import streamlit as st
    st.cache_data.clear()
    monkeypatch.setenv(donnees.VARIABLE_DOSSIER, str(dossier_processed))
    app = lancer(dossier_processed, monkeypatch)
    app.session_state["onglet"] = textes.ONGLETS[3]
    return app.run()


def test_onglet_affiche_les_cartes_et_le_pied(methodologie):
    assert not methodologie.exception
    page = html_affiches(methodologie)
    for carte in cartes():
        assert carte["surtitre"] in page
    assert page.count('<section class="rg-methodo-carte') == 6 and page.count('class="rg-methodo-carte rg-beige"') == 1
    assert "En construction" not in page
    assert f'href="{textes.URL_METHODE}"' in page and textes.LIEN_METHODE in page
    assert textes.pied_commun(resume_test()) in page           # pied commun, sans dates précises
    assert "extraction du" not in page and "15/10/2026" not in page


def test_en_construction_supprime():
    assert not hasattr(textes, "EN_CONSTRUCTION") and not hasattr(textes, "PHRASE_CARTE_2026")
    source = (donnees.RACINE / "app" / "streamlit_app.py").read_text(encoding="utf-8")
    assert "en_construction" not in source


def test_texte_du_lien_echappe():
    import charte
    page = charte.html_pied("<i>", ("a ", "<b>", 'https://x.test/?a="b"'))
    assert "<b>" not in page and "<i>" not in page and '"b"' not in page
