"""Libellés, définitions, formats français et texte automatique de l'app.

Aucun appel à Streamlit ici (modules testables seuls) et aucun calcul statistique : les
chiffres viennent des fichiers de data/processed/ (lus par donnees.py), les textes sont
écrits une seule fois, ici. Vocabulaire imposé : docs/app.md, section « Vocabulaire imposé ».
"""

import math
import re
from bisect import bisect_right

import pandas as pd

NBSP = " "
MOINS = "−"

SURTITRE = "Retrait-gonflement des argiles × ventes DVF"
TITRE_APP = "Le marché distingue-t-il les zones d'argile forte et moyenne ?"
ONGLETS = ("Résultat", "Sinistralité × écart", "Carte", "Méthodologie et limites")

# Vocabulaire : « prime de risque implicite » est absente de l'app (décision du 22/10). README : une
# seule fois, comme question de départ non tranchée (voir docs/app.md, « Vocabulaire imposé »).
EXPRESSION_RESERVEE = "prime de risque implicite"
EXPRESSIONS_INTERDITES = ("effet de l'argile", "risque élevé", "valeur de votre maison", "prime de risque")
# Décret n° 2024-405 : il concerne le risque incendie, pas le RGA (vérifié le 23/10) ; plus de « réforme » à l'écran
EXPRESSIONS_ABSENTES = ("réforme", "état des risques", "placebo", "2024-405")

ECART = "écart de prix observé entre zone forte et reste de la commune"
ARRETES = "arrêtés sécheresse 2015-2023"
RAPPEL = (
    "Il s'agit d'un écart observé entre zone forte et reste de la commune, "
    "ni valeur de la maison, ni causalité."
)

# Zones de la carte en carrés : une grille par zone (pipeline spatial/carres.py). Doivent rester
# identiques à [carte.zones] de config/perimetre.toml (un test le vérifie) : l'app ne lit pas la config.
ZONES = {
    "Sud-Ouest · 31, 47, 82": ("31", "47", "82"),
    "Seine-et-Marne · 77": ("77",),
}
NOMS_DEPARTEMENTS = {
    "31": "Haute-Garonne", "47": "Lot-et-Garonne", "77": "Seine-et-Marne", "82": "Tarn-et-Garonne",
}


def zone_de(departement: str) -> str:
    """Libellé de la zone qui contient ce département."""
    for libelle, departements in ZONES.items():
        if departement in departements:
            return libelle
    raise KeyError(f"département hors des zones de la carte : {departement}")


def nom_departement(departement: str) -> str:
    return NOMS_DEPARTEMENTS.get(departement, departement)


STATUTS_DECOTE = {"decote": "décote", "pas_de_decote": "pas de décote", "indetermine": "indéterminé"}
QUADRANTS = ("Risque intégré", "Angle mort", "Décote à expliquer", "Cohérent")
# Les fichiers de data/processed/ gardent les valeurs ci-dessus ; l'écran affiche des libellés descriptifs
LIBELLES_QUADRANTS = {
    "Angle mort": "Sinistres sans décote",
    "Risque intégré": "Sinistres et décote",
    "Décote à expliquer": "Décote sans sinistres",
    "Cohérent": "Ni sinistres ni décote",
}


def libelle_quadrant(valeur: str) -> str:
    """Libellé affiché d'un quadrant (la valeur des fichiers si elle n'a pas de libellé propre)."""
    return LIBELLES_QUADRANTS.get(valeur, valeur)

# Bornes des cinq classes de écart (fraction), borne inférieure incluse. Doivent rester
# identiques à [carte] classes_prime de config/perimetre.toml (un test le vérifie) : l'app ne
# lit pas la config.
BORNES_CLASSES = (-0.10, -0.03, 0.03, 0.10)

# Palette unique de l'app (maquette de la carte) : orange = décote, bleu = écart positif, jamais
# de rouge ni de vert. Une classe « pâle » (OPACITE_PALE) = statut indéterminé ; gris = non estimable.
COULEURS_CLASSES = ("#A8431A", "#E99A68", "#BDB6A4", "#9DBEDD", "#4F7FB0")
# Même teintes, assombries pour le texte (chiffre de la fiche) : contraste suffisant sur fond blanc
COULEURS_TEXTE_CLASSES = ("#A8431A", "#B4501A", "#6B6552", "#3F6D99", "#2F5F94")
COULEUR_NON_ESTIMABLE = "#E4E6E2"   # gris très clair : les communes classées ressortent
OPACITE_PALE = 0.38

# Tableau des définitions (docs/method.md, section 6), repris à l'identique partout.
DEFINITIONS = (
    ("Décote globale « moyen »", "moyen", "faible ou hors zone argileuse"),
    ("Décote globale « fort »", "fort", "faible ou hors zone argileuse"),
    ("Décote globale « fort − moyen » (chiffre phare)", "fort", "moyen"),
    ("Global « fort contre tout le reste » (comparable aux écarts communaux)", "fort",
     "hors zone, faible ou moyen"),
    ("Écart par commune", "fort", "tout le reste : faible, moyen ou hors zone argileuse"),
)

MOTIFS = {
    "une_seule_zone": "elle n'a pas de ventes dans les deux zones (zone forte et reste de la commune)",
    "effectifs_insuffisants": "ses effectifs sont insuffisants",
}


# ---------------------------------------------------------------- formats français

def _nombre(x: float, decimales: int) -> str:
    return f"{abs(x):,.{decimales}f}".replace(",", NBSP).replace(".", ",")


def entier(n: float) -> str:
    """82 525 (espace insécable pour les milliers)."""
    return (MOINS if n < 0 else "") + _nombre(round(n), 0)


def pct(fraction: float, decimales: int = 1, signe: bool = False) -> str:
    """Fraction en pourcentage français : -0,0289 -> « −2,9 % » ; signe=True ajoute le « + »."""
    valeur = round(fraction * 100, decimales)
    prefixe = MOINS if valeur < 0 else ("+" if signe and valeur > 0 else "")
    return f"{prefixe}{_nombre(valeur, decimales)}{NBSP}%"


def intervalle_pct(bas: float, haut: float) -> str:
    """[−2,9 % ; +4,9 %] : notation unique des intervalles, une décimale (signe + affiché, « 0,0 % » sans signe)."""
    return f"[{pct(bas, 1, True)} ; {pct(haut, 1, True)}]"


def pluriel(n: int, singulier: str, pluriel_: str | None = None) -> str:
    return f"{entier(n)} {singulier if n in (0, 1) else (pluriel_ or singulier + 's')}"


# ---------------------------------------------------------------- bandeau

def cas_chiffre_phare(contraste: dict, seuil: float) -> str:
    """decote | positif | aucune_decote | imprecis, d'après l'IC du contraste « fort − moyen ».

    Même définition que le statut des communes : « pas de décote » = borne basse strictement
    au-dessus de `seuil_pas_de_decote` (lu dans resume_global.json).
    """
    bas, haut = contraste["ic95_effet"]
    if haut < 0:
        return "decote"
    if bas > 0:
        return "positif"
    if bas > seuil:
        return "aucune_decote"
    return "imprecis"


def phrase_chiffre_phare(contraste: dict, seuil: float) -> str:
    bas, haut = contraste["ic95_effet"]
    cas = cas_chiffre_phare(contraste, seuil)
    if cas == "decote":
        return f"Décote mesurée : l'intervalle de confiance est entièrement sous 0 ({intervalle_pct(bas, haut)})."
    if cas == "positif":
        return f"Pas de décote : l'écart observé est positif ({intervalle_pct(bas, haut)})."
    if cas == "aucune_decote":
        x = max(1, math.floor(-bas * 100 + 0.5))
        return f"Aucune décote mesurable : si elle existe, elle ne dépasse pas environ {x}{NBSP}%."
    return (
        f"Trop imprécis pour conclure : l'intervalle de confiance ({intervalle_pct(bas, haut)}) "
        "ne permet pas d'exclure une décote notable."
    )


def chiffre_phare(contraste: dict) -> str:
    """+0,9 % (une décimale, comme les intervalles)."""
    return pct(contraste["effet"], 1, True)


# ---------------------------------------------------------------- onglet Résultat

SURTITRE_RESULTAT = "Résultat principal"
LIBELLE_CHIFFRE = (
    "Écart de prix des maisons en zone forte par rapport à la zone moyenne, "
    "à caractéristiques comparables (même commune, même trimestre)"
)
MENTION_IC = "intervalle de confiance à 95 %"
TITRE_TESTE = "Ce qui a vraiment été testé"
TESTE_NEUTRE = "L'écart avec les maisons hors zone argileuse n'est pas une décote nette."
TESTE_CONCLUSION = (
    "L'étude ne dit donc pas si le marché fait payer le risque argileux. "
    "Elle dit qu'il ne distingue pas nettement exposition moyenne et forte."
)
TITRE_SIGNAL = "Signal faible"
SIGNAL_NOTE = "Le marché ne tiendrait peut-être pas compte de ces sinistres. Une hypothèse, pas une prédiction."
BOUTON_SIGNAL = f"Voir {ONGLETS[1]} →"
# Pied commun aux quatre onglets : seul le mois de téléchargement vient du JSON
PIED_SOURCES = "Sources : DVF, RGA (Géorisques / BRGM), GASPAR, API Géo"
PIED_TELECHARGEMENT = "données téléchargées en {mois_annee}"
PIED_CALCULS = "calculs faits hors ligne"
PIED_CAUSALITE = "corrélation, pas causalité"


def phrase_reponse(contraste: dict, seuil: float) -> str:
    cas = cas_chiffre_phare(contraste, seuil)
    if cas == "decote":
        return "Les maisons en zone forte se vendent moins cher que celles en zone moyenne."
    if cas == "positif":
        return "Pas de décote : les maisons en zone forte ne se vendent pas moins cher que celles en zone moyenne."
    return "Pas de différence de prix détectable entre zone d'argile forte et zone moyenne."


def phrase_lecture(contraste: dict, seuil: float) -> str:
    """Lecture du chiffre phare (règle du 17/10 pour X) ; autres cas : phrase du bandeau."""
    if cas_chiffre_phare(contraste, seuil) != "aucune_decote":
        return phrase_chiffre_phare(contraste, seuil)
    x = max(1, math.floor(-contraste["ic95_effet"][0] * 100 + 0.5))
    return (
        f"Si une décote existe, elle ne dépasse probablement pas environ {x}{NBSP}%. "
        "Ne pas détecter de décote ne prouve pas qu'il n'y en a pas."
    )


def effectifs_ventes(resume: dict) -> tuple[int, str]:
    """Ventes de l'estimation du modèle principal ; à défaut, ventes retenues par le nettoyage."""
    n = resume["modeles_globaux"]["principal"].get("n_ventes")
    if n is not None:
        return int(n), "ventes"
    return int(resume["nettoyage"]["n_ventes_retenues"]), "ventes retenues"


def ligne_effectifs(resume: dict, n_departements: int) -> str:
    n_ventes, libelle = effectifs_ventes(resume)
    debut, fin = resume["periode"]
    return (
        f"{LIBELLE_CHIFFRE} · {entier(n_ventes)} {libelle} · {pluriel(n_departements, 'département')} "
        f"· {debut}-{fin}"
    )


def _p(valeur: float) -> str:
    return _nombre(valeur, 2)


def paragraphe_teste(principal: dict) -> str:
    """Premier paragraphe de l'encadré « Ce qui a vraiment été testé » (modèle principal).

    Écarts « moyen » et « fort » contre la référence, rangés ; « fragile » seulement si les deux p
    sont au moins 0,01. Si un des deux effets est positif ou nul, « moins cher » serait faux : phrase neutre.
    """
    coefficients = [principal["coefficients"]["moyen"], principal["coefficients"]["fort"]]
    if any(c["effet"] >= 0 for c in coefficients):
        return TESTE_NEUTRE
    ecarts = sorted(round(-c["effet"] * 100, 1) for c in coefficients)
    p1, p2 = sorted(c["p_valeur"] for c in coefficients)
    ecart = _nombre(ecarts[0], 1) if ecarts[0] == ecarts[1] else f"{_nombre(ecarts[0], 1)} à {_nombre(ecarts[1], 1)}"
    debut = (
        f"Les maisons des deux zones exposées se vendraient {ecart}{NBSP}% moins cher que les rares maisons "
        "hors zone argileuse ou en zone faible. "
    )
    if p1 < 0.01:
        return debut + f"Cet écart est significatif, mais {PETIT_GROUPE}"
    plage = f"p ≈ {_p(p1)}" if _p(p1) == _p(p2) else f"p ≈ {_p(p1)} à {_p(p2)}"
    return debut + f"Écart fragile ({plage}) : {PETIT_GROUPE}"


PETIT_GROUPE = "ce petit groupe peut différer pour d'autres raisons : emplacement, type de maisons, quartier."


def _seuil_entier(seuil: float) -> str:
    """Seuil « pas de décote » sans signe, pour les phrases (−0,03 -> « 3 % »)."""
    return pct(abs(seuil), 0 if round(abs(seuil) * 100) == abs(seuil) * 100 else 1)


def phrase_signal(n_angle_mort: int, seuil: float) -> str:
    """Texte à droite du grand nombre de l'encadré « Signal faible » ; `seuil` est lu dans le JSON."""
    verbe = "commune cumule" if n_angle_mort in (0, 1) else "communes cumulent"
    return (
        f"{verbe} une sinistralité supérieure à la médiane du périmètre et aucune décote de plus de "
        f"{_seuil_entier(seuil)} (intervalle de confiance)."
    )


def mois_annee(iso: str | None) -> str | None:
    """2026-10-15 -> « octobre 2026 » ; None si la date manque ou n'est pas valide."""
    trouve = re.match(r"(\d{4})-(\d{2})", str(iso or ""))
    if not trouve or not 1 <= int(trouve.group(2)) <= 12:
        return None
    return f"{MOIS[int(trouve.group(2)) - 1]} {trouve.group(1)}"


def pied_commun(resume: dict) -> str:
    """Pied identique sur les quatre onglets ; le mois est celui du téléchargement le plus récent du JSON."""
    dates = [s.get("date_telechargement") for s in resume["sources"]["liste"] if mois_annee(s.get("date_telechargement"))]
    morceaux = [PIED_SOURCES]
    if dates:
        morceaux.append(PIED_TELECHARGEMENT.format(mois_annee=mois_annee(max(dates))))
    return " · ".join(morceaux + [PIED_CALCULS, PIED_CAUSALITE])


# ---------------------------------------------------------------- onglet Méthodologie et limites
# Les gabarits ne contiennent aucun chiffre : tout vient de resume_global.json. Seuls restent écrits
# les années 2025 et 2026 (ventes de 2025, carte 2026) et le niveau des intervalles (95 %). Le vocabulaire
# est celui de docs/app.md : on parle du « contraste fort − moyen », jamais d'une prime de risque.

URL_METHODE = "https://github.com/Tropical-Tech-Code/retrait-gonflement/blob/main/docs/method.md"
URL_DEPOT = "https://github.com/Tropical-Tech-Code/retrait-gonflement"
LIEN_DEPOT = "code source sur GitHub"
PIED_AVERTISSEMENT = "Outil indicatif et pédagogique : il ne remplace ni une étude géotechnique ni les documents officiels sur les risques."
PIED_AUTEUR = "© 2026 Tropical-Tech-Code"
LIEN_METHODE = "docs/method.md sur GitHub"
PIED_METHODE = "Méthode détaillée : "

METHO_TITRES = {
    "question": ("Question testée", "Zone forte contre zone moyenne"),
    "donnees": ("Données", "Ventes, exposition, sinistres"),
    "modele": ("Modèle", "Comparer des maisons voisines"),
    "robustesse": ("Robustesse", None),
    "communes": ("Écarts par commune", "Surtout des quartiers"),
    "limites": ("Limites", None),
}
METHO_TITRE_TIENT = "Le résultat tient dans les variantes"
METHO_TITRE_DEPEND = "Le résultat dépend des variantes"
METHO_REFERENCE = (
    "La référence « hors zone ou faible » pèse moins de {plafond} des ventes : "
    "c'est un petit groupe aux caractéristiques propres."
)
METHO_MODELE = (
    "Régression du prix au m² (en logarithme, pour lire les écarts en %) sur la surface, le terrain et les pièces, avec un effet fixe commune × trimestre : "
    "on compare des maisons vendues dans la même commune, au même moment. "
    "Erreurs groupées par commune, intervalles de confiance à 95 %."
)
METHO_COMMUNES_FIN = "plutôt des différences entre quartiers, ce que confirme le contrôle par la carte {carte}."
METHO_COMMUNES_FIN_SANS_CARTE = "plutôt des différences entre quartiers."
# Sigle développé une seule fois dans l'app (carte « Données » de la Méthodologie)
GASPAR_DEVELOPPE = "Gestion assistée des procédures administratives relatives aux risques naturels et technologiques"
LIMITE_CAUSALITE = "Corrélation, pas causalité ; aucun écart n'estime la valeur d'une maison."
LIMITE_CARRES = "Position des carrés de la carte approximative (quelques km)."
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre")


NOMBRES_EN_LETTRES = ("zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix", "onze",
                      "douze", "treize", "quatorze", "quinze", "seize")


def nombre_en_lettres(n: int) -> str:
    """Nombre en lettres jusqu'à seize (« quatre »), en chiffres au-delà."""
    return NOMBRES_EN_LETTRES[n] if 0 <= n < len(NOMBRES_EN_LETTRES) else entier(n)


def debut_phrase(n: int) -> str:
    """Nombre en début de phrase : en lettres jusqu'à seize (« Quatre »), en chiffres au-delà."""
    return nombre_en_lettres(n).capitalize()


def _contraste(resume: dict, nom: str) -> dict | None:
    return (resume["modeles_globaux"].get(nom) or {}).get("contraste_fort_moins_moyen")


def _coefficient(resume: dict, nom: str, cle: str) -> dict | None:
    return ((resume["modeles_globaux"].get(nom) or {}).get("coefficients") or {}).get(cle)


def _n_departements(resume: dict) -> int:
    return len(resume["primes_communes"]["par_departement"])


def _codes_departements(resume: dict) -> str:
    return ", ".join(sorted(resume["primes_communes"]["par_departement"]))


def _plage_zones(resume: dict) -> tuple[float, float, float] | None:
    """(part forte minimale, part forte maximale, part maximale de « hors zone + faible »), par département."""
    zones = resume.get("zones_rga")
    if not zones:
        return None
    forts = [z["part_3"] for z in zones.values()]
    return min(forts), max(forts), max(z["part_0"] + z["part_1"] for z in zones.values())


def phrase_zones(resume: dict) -> str:
    plage = _plage_zones(resume)
    if plage is None:
        return ""
    bas, haut, reference = plage
    forte = _nombre(round(bas * 100), 0) if round(bas * 100) == round(haut * 100) else (
        f"{_nombre(round(bas * 100), 0)} à {_nombre(round(haut * 100), 0)}")
    plafond = f"{entier(math.floor(reference * 100) + 1)}{NBSP}%"
    return (
        f"{forte}{NBSP}% des ventes sont en zone forte, les autres surtout en zone moyenne. "
        + METHO_REFERENCE.format(plafond=plafond)
    )


def phrase_carte_2026(resume: dict) -> str | None:
    """Part des ventes dont le niveau change entre les cartes 2020 et 2026 (clé `carte_2026`) ; None si absente."""
    c = resume.get("carte_2026")
    if not c or c.get("part_change") is None:
        return None
    if not c["n_change"]:
        return "La carte 2026 ne change le niveau d'aucune vente."
    plus, moins = c["n_vers_plus_fort"], c["n_vers_moins_fort"]
    sens = (", dans les deux sens" if plus and moins else
            ", vers un niveau plus fort" if plus else ", vers un niveau moins fort")
    part = round(c["part_change"] * 100)
    quantite = f"d'environ {entier(part)}{NBSP}%" if part >= 1 else "de moins d'un pour cent"
    return f"La carte 2026 change le niveau {quantite} des ventes{sens}."


def _ligne_modele(libelle: str, coefficient: dict | None) -> str | None:
    if not coefficient:
        return None
    bas, haut = coefficient["ic95_effet"]
    return f"{libelle} : {pct(coefficient['effet'], 1, True)} {intervalle_pct(bas, haut)}."


def _conclusion(coefficient: dict) -> str:
    """decote | positif | indetermine : la position de l'IC par rapport à 0 (le seuil de −3 % ne sert pas ici).

    Deux variantes ont « la même conclusion » si leurs intervalles sont du même côté de 0 ou contiennent 0 tous les deux.
    """
    bas, haut = coefficient["ic95_effet"]
    return "decote" if haut < 0 else "positif" if bas > 0 else "indetermine"


def items_robustesse(resume: dict) -> tuple[bool, list[str]]:
    """(le résultat tient dans les variantes, phrases de la carte Robustesse), toutes lues dans `modeles_globaux`."""
    modeles = resume["modeles_globaux"]
    principal = modeles["principal"]["contraste_fort_moins_moyen"]
    cas = _conclusion(principal)
    items, tient = [], True
    sans_limite = _contraste(resume, "sans_limite")
    if sans_limite:
        meme = _conclusion(sans_limite) == cas
        tient &= meme
        bas, haut = sans_limite["ic95_effet"]
        items.append(
            f"Sans les ventes proches d'une limite de zone : {'même' if meme else 'autre'} conclusion "
            f"({pct(sans_limite['effet'], 1, True)} {intervalle_pct(bas, haut)})."
        )
    contre_reste = _coefficient(resume, "fort_contre_reste", "fort")
    if contre_reste:
        tient &= _conclusion(contre_reste) == cas
        items.append(_ligne_modele("Zone forte contre tout le reste", contre_reste))
    seuil = resume.get("seuil_pas_de_decote")
    if sans_limite and seuil is not None and sans_limite["ic95_effet"][0] <= seuil:
        items.append(
            f"La limite de {_seuil_entier(seuil)} est fragile : sans les ventes proches d'une limite de zone, "
            f"la borne basse passe à {pct(sans_limite['ic95_effet'][0], 1, True)}."
        )
    fort_2025 = _coefficient(resume, "reforme_2025", "fort_2025")
    if fort_2025:
        bas, haut = fort_2025["ic95_effet"]
        items.append(
            f"Ventes de 2025 : l'écart de la zone forte bouge de {pct(fort_2025['effet'], 1, True)} "
            f"{intervalle_pct(bas, haut)}, sans conclusion possible."
        )
    placebo = modeles.get("placebo_bascule")
    if placebo:
        items.append(_ligne_bascule(placebo, _millesime(resume, "rga_2026")))
    return tient, items


def _communes_placebo(placebo: dict) -> int | None:
    """Nombre de communes du test des ventes « fort » seulement en 2026.

    Seule trace : le nombre qui suit « ventes, » dans le statut « … (N ventes, K communes) » du JSON.
    La clé `n_communes` du modèle compte toutes les communes de l'estimation, pas celles du test : ignorée.
    None si le statut a un autre format (l'app n'affiche alors aucun nombre de communes).
    """
    trouve = re.search(r"ventes?,\s*(\d[\d\s  ]*?)\s*communes?", str(placebo.get("statut", "")))
    return int(re.sub(r"\D", "", trouve.group(1))) if trouve else None


def _ligne_bascule(placebo: dict, carte: str | None) -> str:
    """Puce du contrôle par la carte plus récente ; `carte` = son millésime, lu dans les sources du JSON."""
    debut = f"Maisons passées en zone forte seulement avec la carte {carte}" if carte else (
        "Maisons passées en zone forte seulement avec la carte plus récente")
    bascule = (placebo.get("coefficients") or {}).get("bascule")
    if not bascule:
        return f"{debut} : écart non estimé."
    n_ventes, n_communes = bascule.get("n_ventes_terme"), _communes_placebo(placebo)
    effectifs = ""
    if n_ventes is not None and n_communes is not None:
        effectifs = f" ({entier(n_ventes)} ventes, {pluriel(n_communes, 'commune')})"
    elif n_ventes is not None:
        effectifs = f" ({pluriel(int(n_ventes), 'vente')})"
    ecart = pct(bascule["effet"], 1, True)
    if bascule["effet"] > 0:
        fin = f"{ecart}, aucune décote ; les écarts viennent plutôt des quartiers"
    else:
        fin = f"{ecart}, écart non causal"
    fiabilite = f" (fourchette peu fiable : {pluriel(n_communes, 'commune')})" if n_communes is not None else (
        " (fourchette peu fiable)")
    return f"{debut}{effectifs}, vendues avant que l'acheteur puisse le savoir : {fin}{fiabilite}."


def _millesime(resume: dict, cle: str) -> str | None:
    return next((s.get("millesime") for s in resume["sources"]["liste"] if s["cle"] == cle), None)


def texte_donnees(resume: dict) -> str:
    debut, fin = resume["periode"]
    nettoyage = resume["nettoyage"]
    catnat = resume["catnat"]
    rga, rga_2026 = _millesime(resume, "rga_2020"), _millesime(resume, "rga_2026")
    exposition = f"carte RGA {rga}" if rga else "carte RGA"
    controle = f" ; la carte {rga_2026} sert seulement de contrôle" if rga_2026 else ""
    return (
        f"Sur {entier(nettoyage['n_mutations'])} transactions immobilières (DVF, {debut}-{fin}), "
        f"{entier(nettoyage['n_ventes_retenues'])} ventes d'une seule maison sont retenues. "
        f"Exposition : {exposition}, consultable par les acheteurs pendant toute la période{controle}. "
        f"Sinistres : arrêtés {catnat['libelle'].lower()} {catnat['periode']} de GASPAR ({GASPAR_DEVELOPPE}) ; "
        "les sécheresses plus récentes sont absentes de GASPAR à la date d'extraction (délai de reconnaissance probable)."
    )


def texte_modele(resume: dict) -> str:
    n = resume["modeles_globaux"]["principal"].get("n_ventes")
    return METHO_MODELE + (
        f" Estimation sur {entier(n)} ventes (celles seules dans leur commune et leur trimestre sont retirées)."
        if n is not None else ""
    )


def texte_communes(resume: dict) -> str:
    seuils = resume["primes_communes"]["seuils"]
    decotes, primes = int(resume["n_significatives_decote"]), int(resume["n_significatives_prime"])
    carte = _millesime(resume, "rga_2026")
    fin = METHO_COMMUNES_FIN.format(carte=carte) if carte else METHO_COMMUNES_FIN_SANS_CARTE
    return (
        f"Parmi les {entier(int(resume['n_communes_estimables']))} communes estimables "
        f"(au moins {seuils['min_ventes_fort']} ventes en zone forte, {seuils['min_ventes_reference']} ailleurs, "
        f"{seuils['min_ventes_total']} au total), on compte "
        f"{pluriel(decotes + primes, 'écart significatif', 'écarts significatifs')} "
        f"({pluriel(decotes, 'négatif')}, {pluriel(primes, 'positif')}) contre environ "
        f"{entier(round(resume['n_attendu_hasard']))} attendus par hasard : {fin}"
    )


def limites(resume: dict) -> list[str]:
    catnat = resume["catnat"]
    items = [
        LIMITE_CAUSALITE,
        f"{debut_phrase(_n_departements(resume))} "
        + (
            "département très exposé : résultats non transposables à toute la France."
            if _n_departements(resume) in (0, 1)
            else "départements très exposés : résultats non transposables à toute la France."
        ),
        f"Aucun arrêté {catnat['libelle'].lower()} reconnu après {catnat['annee_debut_max']} "
        "(délai de reconnaissance probable).",
    ]
    carte = phrase_carte_2026(resume)
    if carte:
        items.append(carte)
    return items + [LIMITE_CARRES]


def cartes_methodologie(resume: dict) -> list[dict]:
    """Les six cartes de l'onglet : rang, surtitre, titre, paragraphes ou items, `beige` pour les limites."""
    tient, robustesse = items_robustesse(resume)
    question = (
        f"Dans ces {nombre_en_lettres(_n_departements(resume))} "
        f"{'département' if _n_departements(resume) in (0, 1) else 'départements'} ({_codes_departements(resume)}), "
        + phrase_zones(resume)
        if phrase_zones(resume) else "La comparaison porte sur les zones d'argile forte et moyenne."
    )
    cartes = [
        {"paragraphes": [question]},
        {"paragraphes": [texte_donnees(resume)]},
        {"paragraphes": [texte_modele(resume)]},
        {"items": robustesse, "titre": METHO_TITRE_TIENT if tient else METHO_TITRE_DEPEND},
        {"paragraphes": [texte_communes(resume)]},
        {"items": limites(resume), "beige": True},
    ]
    cles = list(METHO_TITRES)
    for rang, (cle, carte) in enumerate(zip(cles, cartes), start=1):
        surtitre, titre = METHO_TITRES[cle]
        carte.setdefault("titre", titre)
        carte["surtitre"] = f"{rang} · {surtitre}"
    return cartes


def phrase_tests_multiples(resume: dict) -> str:
    """Phrase unique sous la carte : écarts nets observés contre attendus par hasard (tous les chiffres du JSON).

    La colonne `significatif` = prime des fichiers est dite « écart positif » à l'écran (jamais « prime »).
    """
    decotes, primes = int(resume["n_significatives_decote"]), int(resume["n_significatives_prime"])
    attendues = round(resume["n_attendu_hasard"])
    attendu = "une dizaine attendue" if attendues == 10 else f"{pluriel(attendues, 'attendue')}"
    return (
        f"Sur {entier(resume['n_communes_estimables'])} communes, {entier(decotes + primes)} montrent un écart "
        f"significatif, contre {attendu} par hasard. Ils vont dans les deux sens "
        f"({pluriel(decotes, 'zone forte moins chère', 'zones fortes moins chères')}, "
        f"{pluriel(primes, 'plus chère')}) : si l'argile jouait, on verrait surtout des décotes ; "
        "ce sont plutôt des différences entre quartiers."
    )


# ---------------------------------------------------------------- carte

PREFIXE_LEGENDE = "Écart zone forte / reste :"
LEGENDE_PALE = "pâle : indéterminé"
LEGENDE_NON_ESTIMABLE = "gris clair : non estimable"
LEGENDE_SELECTION = "sélection"
LIBELLE_ZONE = "Zone affichée"
LIBELLE_COMMUNE = "Commune"
PLACEHOLDER_COMMUNE = "Chercher une commune"
FOND_DE_CARTE = "Fond de carte © CARTO · © OpenStreetMap"
NOTE_POSITION = "Position des carrés approximative (quelques km)."
INVITE_COMMUNE = (
    "Pour afficher la fiche d'une commune, zoomez puis cliquez sur un carré de la carte, "
    "ou cherchez-la par son nom."
)
TITRE_INVITE = "Choisissez une commune"
TUILE_ESTIMABLES = "Communes estimables"
TUILE_DECOTE = "Décote"
TUILE_PAS_DE_DECOTE = "Pas de décote"
TUILE_INDETERMINEES = "Indéterminées"
LIBELLE_ECART_FICHE = "Écart de prix observé entre zone forte et reste de la commune"
LIBELLE_CASES = ("Ventes de maisons", "dont en zone forte", "Arrêtés sécheresse 2015-2023")
TITRE_NOTE = "Note"
NON_ESTIMABLE = "Non estimable"


def statut_commune(ligne) -> str:
    """« décote », « pas de décote », « indéterminé » ou « non estimable »."""
    return NON_ESTIMABLE.lower() if ligne["statut"] != "estimable" else STATUTS_DECOTE[ligne["statut_decote"]]


CODE_SEPARATEUR = "__autres_communes__"
SEPARATEUR_LISTE = "── Autres communes ──"


def libelle_liste(ligne) -> str:
    """Entrée de la liste de recherche : « Chelles (77) · décote » pour une décote, « Chelles (77) » sinon."""
    base = f"{ligne['nom']} ({ligne['departement']})"
    return f"{base} · {STATUTS_DECOTE['decote']}" if ligne["statut"] == "estimable" and ligne["statut_decote"] == "decote" else base


def codes_liste(communes: pd.DataFrame) -> list[str]:
    """Codes de la liste de recherche : les communes en décote (ordre alphabétique), le séparateur, les autres."""
    en_decote = (communes["statut"] == "estimable") & (communes["statut_decote"] == "decote")
    ordonnees = communes.sort_values("nom")
    return [*ordonnees.loc[en_decote, "code_insee"], CODE_SEPARATEUR, *ordonnees.loc[~en_decote, "code_insee"]]


def texte_info_bulle(ligne) -> str:
    """Info-bulle d'une commune, en texte simple : nom et statut."""
    return f"{ligne['nom']} ({ligne['departement']})\n{statut_commune(ligne).capitalize()}"


def classe_prime(prime: float | None, bornes: tuple[float, ...] = BORNES_CLASSES) -> int | None:
    """Classe 0 à 4 de la colonne `prime` (borne inférieure incluse) ; None si non estimable."""
    if pd.isna(prime):
        return None
    return bisect_right(bornes, prime)


def legende(bornes: tuple[float, ...] = BORNES_CLASSES) -> list[tuple[int, str]]:
    """(classe, libellé) des cinq classes, de la plus basse à la plus haute."""
    b = [pct(x, 0, True) for x in bornes]
    return [
        (0, f"inférieur à {b[0]}"),
        (1, f"de {b[0]} à {b[1]}"),
        (2, f"de {b[1]} à {b[2]}"),
        (3, f"de {b[2]} à {b[3]}"),
        (4, f"supérieur à {b[3]}"),
    ]


def seuil_arretes(mediane: float) -> int:
    """Nombre d'arrêtés à partir duquel la sinistralité est « supérieure à la médiane »."""
    return math.floor(mediane) + 1


def libelle_sinistralite(mediane: float) -> str:
    return (
        "sinistralité supérieure à la médiane du périmètre "
        f"({seuil_arretes(mediane)} arrêtés ou plus depuis 2015, {ARRETES})"
    )


# ---------------------------------------------------------------- onglet Sinistralité × écart

TITRE_SINISTRALITE = "Sinistralité constatée et écart de prix"
LIGNES_QUADRANTS = ("Pas de décote", "Décote")
# (ligne, colonne) de chaque case : colonne 0 = sinistralité ≤ médiane, 1 = > médiane
POSITIONS_QUADRANTS = {"Cohérent": (0, 0), "Angle mort": (0, 1), "Décote à expliquer": (1, 0), "Risque intégré": (1, 1)}
PHRASES_QUADRANTS = {
    "Cohérent": "Peu de sinistres et pas de décote.",
    "Angle mort": "Des sinistres reconnus dans la commune, pas de décote en zone forte.",
    "Décote à expliquer": "Une décote sans sinistralité marquée : peut-être un effet de quartier plutôt que de l'argile.",
    "Risque intégré": "Des sinistres reconnus dans la commune, une décote en zone forte.",
}
NOTE_ARRETES = (
    "Un arrêté sécheresse vise toute la commune : on ne sait pas si les maisons sinistrées étaient "
    "dans sa zone forte ou ailleurs."
)


def signal_sinistralite(seuil: float) -> str:
    """Encadré sombre ; `seuil` (seuil « pas de décote ») est lu dans le JSON."""
    return (
        "Hypothèse à surveiller : ces communes ont souvent été reconnues en sécheresse, mais leurs maisons "
        "en zone forte ne se vendent pas nettement moins cher (une décote de plus de "
        f"{_seuil_entier(seuil)} est exclue). Le marché ne tiendrait peut-être pas compte de ces sinistres."
    )


TITRE_TABLEAU_ANGLES = "Communes avec sinistres sans décote, par sinistralité"
EN_TETES_ANGLES = ("Commune", "Dép.", "Arrêtés", "Écart [IC 95 %]", "Ventes", "dont zone forte")
AUCUN_ANGLE_MORT = "Aucune commune avec sinistres sans décote."


def libelles_colonnes_sinistralite(mediane: float) -> tuple[tuple[str, str], tuple[str, str]]:
    """Deux lignes par colonne : k = partie entière de la médiane (arrêtés entiers)."""
    k = seuil_arretes(mediane) - 1
    return (
        ("Sinistralité ≤ médiane", f"(0 à {k} arrêtés)"),
        ("Sinistralité > médiane", f"({k + 1} arrêtés ou plus)"),
    )


def phrase_explication_sinistralite(mediane: float, seuil: float) -> str:
    """Explication de la carte ; `seuil` (seuil « pas de décote », lu dans le JSON) sert aux définitions des statuts."""
    return (
        "Chaque commune estimable est classée par son statut (décote ou pas de décote) et par sa "
        f"sinistralité : {ARRETES}, au-dessus ou non de la médiane du périmètre "
        f"({seuil_arretes(mediane)} arrêtés ou plus). "
        "Décote : la zone forte se vend moins cher, c'est certain (fourchette entièrement sous 0). "
        f"Pas de décote : si elle se vend moins cher, c'est de {_seuil_entier(seuil)} au plus."
    )


def indeterminees(n: int) -> tuple[str, str]:
    """(nombre, suite de la phrase) de l'encadré gris sous le tableau."""
    fin = " : trop peu de ventes pour trancher."
    return entier(n), (" commune non classée" if n in (0, 1) else " communes non classées") + fin


def titre_signal_sinistralite(n: int) -> str:
    return "commune avec sinistres sans décote" if n in (0, 1) else "communes avec sinistres sans décote"


def angles_morts(communes: pd.DataFrame) -> pd.DataFrame:
    """Communes dont le quadrant est « Angle mort » (affiché « Sinistres sans décote »), arrêtés décroissants puis nom."""
    angles = communes[communes["quadrant"] == "Angle mort"]
    return angles.sort_values(["catnat_depuis_2015", "nom"], ascending=[False, True])


def ligne_angle_mort(ligne) -> tuple[str, str, str, str, str, str]:
    if pd.isna(ligne["prime"]) or pd.isna(ligne["ic_bas"]) or pd.isna(ligne["ic_haut"]):
        ecart = "—"
    else:
        ecart = f"{pct(ligne['prime'], 1, True)} {intervalle_pct(ligne['ic_bas'], ligne['ic_haut'])}"
    return (
        str(ligne["nom"]), str(ligne["departement"]), entier(ligne["catnat_depuis_2015"]),
        ecart, entier(ligne["n_ventes"]), entier(ligne["n_fort"]),
    )


# ---------------------------------------------------------------- texte automatique

def texte_commune(ligne, resume: dict) -> str:
    """Texte déterministe de la fiche d'une commune, à partir de sa ligne de communes.parquet.

    Estimable : une phrase sur l'intervalle, le quadrant s'il existe, puis RAPPEL. Non estimable :
    le motif et les seuils (encadré gris, sans RAPPEL : il n'y a pas d'écart à interpréter).
    """
    seuils = resume["primes_communes"]["seuils"]
    if ligne["statut"] != "estimable":
        motif = MOTIFS.get(ligne["motif"], "ses données ne permettent pas l'estimation")
        phrases = [f"{ligne['nom']} n'est pas estimable : {motif}."]
        if ligne["motif"] == "effectifs_insuffisants":
            phrases.append(
                f"Elle compte {pluriel(int(ligne['n_ventes']), 'vente retenue', 'ventes retenues')}, dont "
                f"{entier(ligne['n_fort'])} en zone forte ; il faut au moins {seuils['min_ventes_fort']} ventes en "
                f"zone forte, {seuils['min_ventes_reference']} dans le reste de la commune et "
                f"{seuils['min_ventes_total']} au total."
            )
        return " ".join(phrases)

    intervalle = f"L'intervalle va de {pct(ligne['ic_bas'], 1, True)} à {pct(ligne['ic_haut'], 1, True)}"
    statut = ligne["statut_decote"]
    if statut == "decote":
        phrases = [f"{intervalle} : entièrement sous 0, une décote est mesurée."]
    elif statut == "pas_de_decote":
        phrases = [
            f"{intervalle} : sa borne basse dépasse {pct(resume['seuil_pas_de_decote'], 0, True)}, "
            "une décote éventuelle serait faible."
        ]
    else:
        phrases = [f"{intervalle} : trop large pour conclure."]
    quadrant = ligne.get("quadrant")
    if isinstance(quadrant, str) and quadrant:
        phrases.append(f"Quadrant : {libelle_quadrant(quadrant)}.")
    phrases.append(RAPPEL)
    return " ".join(phrases)
