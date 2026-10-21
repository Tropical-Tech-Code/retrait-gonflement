"""Libellés, définitions, formats français et texte automatique de l'app.

Aucun appel à Streamlit ici (modules testables seuls) et aucun calcul statistique : les
chiffres viennent des fichiers de data/processed/ (lus par donnees.py), les textes sont
écrits une seule fois, ici. Vocabulaire imposé : docs/app.md, section « Vocabulaire imposé ».
"""

import math
from bisect import bisect_right

import pandas as pd

NBSP = " "
MOINS = "−"

SURTITRE = "Retrait-gonflement des argiles × ventes DVF"
TITRE_APP = "Le marché distingue-t-il les zones d'argile forte et moyenne ?"
ONGLETS = ("Résultat", "Sinistralité × écart", "Carte", "Méthodologie et limites")
EN_CONSTRUCTION = "En construction."

# Vocabulaire : « prime de risque implicite » est réservé au résultat global (page Méthodologie,
# README). Les écarts communaux ne portent jamais ce nom ni « effet de l'argile ».
EXPRESSION_RESERVEE = "prime de risque implicite"
EXPRESSIONS_INTERDITES = ("effet de l'argile", "risque élevé", "valeur de votre maison", "prime de risque")

ECART = "écart de prix observé entre zone forte et reste de la commune"
ARRETES = "arrêtés sécheresse 2015-2023"
FOND_DE_CARTE = "Fond de carte © CARTO, données © contributeurs OpenStreetMap"
PHRASE_CARTE_2026 = (
    "Dans ces quatre départements déjà très exposés, la carte 2026 change le niveau "
    "d'environ 1 % des ventes, dans les deux sens."
)
RAPPEL = (
    "Un écart moyen observé n'est ni une estimation de la valeur d'une maison, "
    "ni une preuve de causalité."
)

STATUTS_DECOTE = {"decote": "décote", "pas_de_decote": "pas de décote", "indetermine": "indéterminé"}
QUADRANTS = ("Risque intégré", "Angle mort", "Décote à expliquer", "Cohérent")

# Bornes des cinq classes de écart (fraction), borne inférieure incluse. Doivent rester
# identiques à [carte] classes_prime de config/perimetre.toml (un test le vérifie) : l'app ne
# lit pas la config.
BORNES_CLASSES = (-0.10, -0.03, 0.03, 0.10)

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


def date_fr(iso: str | None) -> str:
    """2026-10-15 -> 15/10/2026 ; « non renseignée » si absente."""
    if not iso:
        return "non renseignée"
    annee, mois, jour = str(iso)[:10].split("-")
    return f"{jour}/{mois}/{annee}"


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
LIBELLE_CHIFFRE = "Écart de prix des maisons en zone forte par rapport à la zone moyenne"
MENTION_IC = "IC 95 %"
TITRE_TESTE = "Ce qui a vraiment été testé"
TESTE_NEUTRE = "L'écart avec les maisons hors zone argileuse n'est pas une décote nette."
TESTE_CONCLUSION = (
    "L'étude ne dit donc pas si le marché fait payer le risque argileux. "
    "Elle dit qu'il ne distingue pas nettement exposition moyenne et forte."
)
TITRE_SIGNAL = "Signal faible"
SIGNAL_NOTE = "Des angles morts possibles, à surveiller. Une hypothèse, pas une prédiction."
BOUTON_SIGNAL = f"Voir {ONGLETS[1]} →"
PIED_CALCULS = "Calculs faits hors ligne"
PIED_CAUSALITE = "Corrélation, pas causalité"
# Sources citées au pied de l'onglet (clés de resume["sources"]["liste"]) ; la carte 2026 est
# réservée à la Méthodologie (elle ne sert pas au résultat principal).
SOURCES_PIED = ("dvf", "rga_2020", "gaspar", "communes")


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
        f"Les maisons des deux zones exposées se vendent {ecart}{NBSP}% moins cher que les rares maisons "
        "hors zone argileuse ou en zone faible. "
    )
    if p1 < 0.01:
        return debut + "Cet écart est net, mais ce petit groupe diffère par d'autres traits que l'argile."
    plage = f"p ≈ {_p(p1)}" if _p(p1) == _p(p2) else f"p ≈ {_p(p1)} à {_p(p2)}"
    return debut + f"Cet écart est fragile ({plage}), et ce petit groupe diffère par d'autres traits que l'argile."


def phrase_signal(n_angle_mort: int) -> str:
    """Texte à droite du grand nombre de l'encadré « Signal faible »."""
    verbe = "commune cumule" if n_angle_mort in (0, 1) else "communes cumulent"
    return f"{verbe} une sinistralité supérieure à la médiane du périmètre et l'absence de décote."


def sources_pied(resume: dict) -> str:
    noms = [s["nom"] for cle in SOURCES_PIED for s in resume["sources"]["liste"] if s["cle"] == cle]
    return " · ".join([f"Sources : {', '.join(noms)}" if noms else "Sources", PIED_CALCULS, PIED_CAUSALITE])


def phrase_estimables(n_estimables: int, n_communes: int) -> str:
    """Phrase sous la carte."""
    return (
        f"Seules {entier(n_estimables)} communes sur {entier(n_communes)} sont estimables "
        "(assez de ventes dans la zone forte et dans le reste de la commune) ; les autres sont en gris. "
        "Une couleur pâle signale une estimation incertaine : l'intervalle de confiance contient 0."
    )


def phrase_indeterminees(resume: dict) -> str:
    """Résultat assumé : la plupart des communes estimables sont indéterminées."""
    return (
        f"Sur {entier(resume['n_communes_estimables'])} communes estimables, "
        f"{entier(resume['n_indetermine'])} sont indéterminées : leur intervalle de confiance est trop "
        "large pour conclure à une décote comme à son absence. "
        f"Au total : {entier(resume['n_decote'])} en décote, {entier(resume['n_pas_de_decote'])} en pas de décote, "
        f"{entier(resume['n_indetermine'])} indéterminées. "
        "À l'échelle d'une commune, les ventes ne permettent le plus souvent pas de trancher."
    )


# ---------------------------------------------------------------- carte

LEGENDE_TITRE = "Écart de prix observé entre zone forte et reste de la commune"
LEGENDE_NON_ESTIMABLE = "Non estimable"
LEGENDE_PALE = "Couleur pâle : estimation incertaine (l'intervalle de confiance contient 0)."
LEGENDE_FILTRE = "Gris très pâle : commune écartée par un filtre."
LIBELLE_FOND = "Afficher le fond de carte"
LIBELLE_SIGNIFICATIVES = "Communes significatives seulement"
LIBELLE_DEPARTEMENTS = "Départements"
INVITE_COMMUNE = "Choisissez une commune (liste, ou clic sur la carte) pour voir sa fiche."


def lignes_info_bulle(ligne) -> list[str]:
    """Lignes de l'info-bulle d'une commune (texte brut, mis en forme par cartographie.py)."""
    titre = f"{ligne['nom']} ({ligne['departement']})"
    effectifs = f"Ventes : {entier(ligne['n_fort'])} en zone forte, {entier(int(ligne['n_ventes']) - int(ligne['n_fort']))} dans le reste"
    arretes = f"{pluriel(int(ligne['catnat_depuis_2015']), 'arrêté')} sécheresse 2015-2023"
    if ligne["statut"] != "estimable":
        motif = MOTIFS.get(ligne["motif"], "données insuffisantes")
        return [titre, f"Non estimable : {motif}", effectifs, arretes]
    ecart = f"Écart de prix observé : {pct(ligne['prime'], 1, True)} {intervalle_pct(ligne['ic_bas'], ligne['ic_haut'])}"
    return [titre, ecart, effectifs, arretes]

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


# ---------------------------------------------------------------- texte automatique

def _arretes(ligne, mediane: float) -> str:
    n = int(ligne["catnat_depuis_2015"])
    if n == 0:
        base = "Aucun arrêté sécheresse reconnu sur 2015-2023"
    else:
        base = f"{pluriel(n, 'arrêté')} sécheresse sur 2015-2023"
    sup = ligne.get("sinistralite_sup_mediane")
    if pd.isna(sup):
        return base + "."
    if bool(sup):
        return f"{base} : sinistralité supérieure à la médiane du périmètre ({seuil_arretes(mediane)} arrêtés ou plus)."
    return (
        f"{base} : sinistralité inférieure ou égale à la médiane du périmètre "
        f"({seuil_arretes(mediane) - 1} arrêtés ou moins)."
    )


def texte_commune(ligne, resume: dict) -> str:
    """Texte déterministe d'une commune, à partir de sa ligne de communes.parquet."""
    nom = ligne["nom"]
    mediane = resume["mediane_sinistralite"]
    seuils = resume["primes_communes"]["seuils"]
    phrases = []
    if ligne["statut"] != "estimable":
        motif = MOTIFS.get(ligne["motif"], "ses données ne permettent pas l'estimation")
        phrases.append(f"{nom} n'est pas estimable : {motif}.")
        if ligne["motif"] == "effectifs_insuffisants":
            phrases.append(
                f"Elle compte {pluriel(int(ligne['n_ventes']), 'vente retenue', 'ventes retenues')}, dont "
                f"{entier(ligne['n_fort'])} en zone forte ; il faut au moins {seuils['min_ventes_fort']} ventes en "
                f"zone forte, {seuils['min_ventes_reference']} dans le reste de la commune et "
                f"{seuils['min_ventes_total']} au total."
            )
        phrases.append(_arretes(ligne, mediane))
        phrases.append(RAPPEL)
        return " ".join(phrases)

    n_reste = int(ligne["n_ventes"]) - int(ligne["n_fort"])
    phrases.append(
        f"À {nom}, l'{ECART} est de {pct(ligne['prime'], 1, True)} "
        f"(intervalle de confiance à 95 % : {intervalle_pct(ligne['ic_bas'], ligne['ic_haut'])})."
    )
    phrases.append(
        f"Il repose sur {pluriel(int(ligne['n_fort']), 'vente')} en zone forte et "
        f"{pluriel(n_reste, 'vente')} dans le reste de la commune."
    )
    statut = ligne["statut_decote"]
    if statut == "decote":
        phrases.append("Statut : décote (l'intervalle est entièrement sous 0).")
    elif statut == "pas_de_decote":
        phrases.append(
            f"Statut : pas de décote (la borne basse de l'intervalle est au-dessus de "
            f"{pct(resume['seuil_pas_de_decote'], 0, True)} : une décote éventuelle serait au plus faible)."
        )
    else:
        phrases.append("Statut : indéterminé (l'intervalle est trop large pour conclure).")
    phrases.append(_arretes(ligne, mediane))
    quadrant = ligne.get("quadrant")
    if isinstance(quadrant, str) and quadrant:
        phrases.append(f"Quadrant : {quadrant}.")
    else:
        phrases.append("Pas de quadrant : commune indéterminée.")
    phrases.append(RAPPEL)
    return " ".join(phrases)
