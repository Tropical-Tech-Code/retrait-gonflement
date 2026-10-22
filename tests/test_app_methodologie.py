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
    autre["primes_communes"]["par_departement"] = {str(i): {} for i in range(9)}   # le nombre de départements compte les clés
    apres = nombres(texte_des_cartes(autre, avec_rangs=False))
    assert avant - ECRITS_EN_DUR
    assert (avant & apres) <= ECRITS_EN_DUR, avant & apres


def test_chiffres_lus_dans_le_resume():
    texte = texte_des_cartes()
    assert f"Dans ces 4 départements, 48 à 53{NB}% des ventes sont en zone forte" in texte
    assert f"moins de 8{NB}% des ventes" in texte                    # (0,07 + 0,004) -> 7,4 % -> 8
    assert f"Sur 1{NB}000 mutations DVF (2021-2025, un seul bien par vente), 300 ventes de maisons sont retenues." in texte
    assert "carte RGA 2020" in texte
    assert ("Sinistres : arrêtés sécheresse 2015-2023 de GASPAR (Gestion assistée des procédures administratives "
            "relatives aux risques naturels et technologiques) ; les sécheresses plus récentes ne sont pas encore "
            "reconnues.") in texte
    assert "Estimation sur 280 ventes." in texte
    assert f"Zone forte contre tout le reste : +0,7{NB}% [{textes.MOINS}3,0{NB}% ; +4,5{NB}%]." in texte
    assert f"(+1,4{NB}% [{textes.MOINS}3,5{NB}% ; +6,4{NB}%])" in texte
    assert "Réforme 2025 (RGA dans l'état des risques) : indice, une seule année après la réforme." in texte
    assert ("Placebo (ventes reclassées par la carte 2026) : indicatif, faible puissance (853 ventes, 8 communes) ; "
            "son écart positif évoque des différences de quartiers, pas un effet causal.") in texte
    assert "erreurs groupées" not in texte        # le détail reste dans docs/method.md
    assert ("Parmi les 4 communes estimables (15 ventes en zone forte, 15 ailleurs, 50 au total), "
            "on compte 2 écarts significatifs pour environ 0 attendus") in texte
    assert "Quatre départements déjà très exposés." in texte
    assert "Aucun arrêté sécheresse reconnu après 2023 (délai de reconnaissance)." in texte
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


def test_millesime_gaspar_devient_une_date_d_extraction():
    assert textes.date_extraction_gaspar("catnat_gaspar_2026-10-05.csv") == "extraction du 5 octobre 2026"
    assert textes.date_extraction_gaspar("catnat_gaspar_2025-01-31.csv") == "extraction du 31 janvier 2025"
    assert textes.date_extraction_gaspar("catnat_gaspar.csv") is None
    assert textes.date_extraction_gaspar("catnat_gaspar_2026-13-05.csv") is None
    assert textes.date_extraction_gaspar(None) is None


def test_sources_du_pied_sur_une_ligne_avec_noms_courts():
    pied = textes.sources_methodologie(resume_test())
    assert pied == (
        "DVF (Etalab, 15/10/2026) · RGA 2020 et 2026 (Géorisques / BRGM, 16/10/2026 et 15/10/2026) · "
        "GASPAR (extraction du 5 octobre 2026) · Contours (API Géo, non renseignée)"
    )
    assert "catnat_gaspar_2026-10-05.csv" not in pied and "\n" not in pied


def test_sources_dates_des_cartes_rga_identiques_et_gaspar_sans_date_dans_le_nom():
    resume = resume_test()
    for source in resume["sources"]["liste"]:
        source["date_telechargement"] = "2026-10-15"
        if source["cle"] == "gaspar":
            source["millesime"] = "catnat_gaspar.csv"
    pied = textes.sources_methodologie(resume)
    assert "RGA 2020 et 2026 (Géorisques / BRGM, 15/10/2026)" in pied and "GASPAR (15/10/2026)" in pied


def test_placebo_sans_ecart_positif_ne_parle_pas_de_quartiers():
    resume = resume_test()
    resume["modeles_globaux"]["placebo_bascule"]["coefficients"]["bascule"] = coefficient(-0.02, -0.05, 0.01)
    placebo = [i for i in cartes(resume)[3]["items"] if i.startswith("Placebo")][0]
    assert placebo.endswith("son écart n'est pas un effet causal.") and "quartiers" not in placebo


def test_nombres_en_debut_de_phrase_ecrits_en_lettres():
    assert [textes.debut_phrase(n) for n in (0, 1, 4, 16)] == ["Zéro", "Un", "Quatre", "Seize"]
    assert textes.debut_phrase(17) == "17"
    assert textes.limites(resume_test())[1] == "Quatre départements déjà très exposés."
    un = resume_test()
    un["primes_communes"]["par_departement"] = {"31": {}}
    assert textes.limites(un)[1] == "Un département déjà très exposé."


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
    assert "extraction du 5 octobre 2026" in page


def test_en_construction_supprime():
    assert not hasattr(textes, "EN_CONSTRUCTION") and not hasattr(textes, "PHRASE_CARTE_2026")
    source = (donnees.RACINE / "app" / "streamlit_app.py").read_text(encoding="utf-8")
    assert "en_construction" not in source


def test_texte_du_lien_echappe():
    import charte
    page = charte.html_pied_methodologie("a ", "<b>", 'https://x.test/?a="b"', "<i>")
    assert "<b>" not in page and "<i>" not in page and '"b"' not in page
