"""Carte des communes : couleurs, info-bulles, filtres, cadrage. Fonctions pures (sans Streamlit).

Orange = décote, bleu = prime, gris = non estimable (pas de rouge ni de vert). Une couleur pâle
signale un intervalle de confiance qui contient 0. Les libellés viennent de textes.py.
"""

import html
import math

import donnees
import textes

# Cinq classes de l'écart observé (textes.BORNES_CLASSES), de la décote la plus forte à la plus forte prime
COULEURS_CLASSES = ((179, 84, 6), (241, 163, 64), (233, 236, 239), (143, 184, 222), (43, 108, 176))
GRIS = (140, 140, 140)
ALPHA_PLEIN, ALPHA_PALE, ALPHA_NON_ESTIMABLE = 230, 110, 100
COULEUR_ECARTEE = [225, 225, 225, 45]

# Contours en pixels (donc indépendants du zoom) : communes fines et claires, départements marqués.
# En mètres (unité par défaut de deck.gl), les traits deviendraient énormes à l'échelle du périmètre.
# pydeck traite toute chaîne comme une expression JavaScript (« pixels » deviendrait « @@=pixels ») :
# les guillemets internes, retirés par pydeck, envoient la valeur littérale 'pixels'.
UNITE_LIGNES = "'pixels'"
LIGNE_COMMUNES = {"couleur": [255, 255, 255, 150], "largeur": 0.7}
LIGNE_DEPARTEMENTS = {"couleur": [30, 30, 30, 255], "largeur": 2.0}


def options_couches() -> tuple[dict, dict]:
    """Options pydeck des couches (communes, limites des départements) : couleurs et traits."""
    communes = {
        "get_fill_color": "properties.couleur",
        "get_line_color": LIGNE_COMMUNES["couleur"],
        "get_line_width": LIGNE_COMMUNES["largeur"],
        "line_width_units": UNITE_LIGNES,
    }
    departements = {
        "get_line_color": LIGNE_DEPARTEMENTS["couleur"],
        "get_line_width": LIGNE_DEPARTEMENTS["largeur"],
        "line_width_units": UNITE_LIGNES,
    }
    return communes, departements
CENTRE_PAR_DEFAUT = {"latitude": 46.6, "longitude": 2.4, "zoom": 5.0}


def hex_classe(classe: int | None) -> str:
    """Couleur de la légende (pleine opacité)."""
    r, g, b = GRIS if classe is None else COULEURS_CLASSES[classe]
    return f"#{r:02x}{g:02x}{b:02x}"


def couleur(ligne) -> list[int]:
    """RGBA d'une commune : classe de l'écart, opacité réduite si l'IC contient 0, gris si non estimable."""
    if ligne["statut"] != "estimable":
        return [*GRIS, ALPHA_NON_ESTIMABLE]
    classe = textes.classe_prime(ligne["prime"])
    alpha = ALPHA_PLEIN if ligne["significatif"] in ("decote", "prime") else ALPHA_PALE
    return [*COULEURS_CLASSES[classe], alpha]


def info_bulle(ligne) -> str:
    """HTML de l'info-bulle (texte échappé : les noms viennent des données)."""
    lignes = [html.escape(t) for t in textes.lignes_info_bulle(ligne)]
    return f"<b>{lignes[0]}</b><br/>" + "<br/>".join(lignes[1:])


def preparer_carte(communes, contours: dict) -> list[dict]:
    """Entités GeoJSON avec leurs propriétés d'affichage (couleur, info-bulle) jointes sur code_insee."""
    lignes = {ligne["code_insee"]: ligne for _, ligne in communes.iterrows()}
    codes_contours = {e["properties"]["code_insee"] for e in contours["features"]}
    sans_contour = sorted(set(lignes) - codes_contours)
    sans_commune = sorted(codes_contours - set(lignes))
    if sans_contour or sans_commune:
        raise donnees.ErreurDonneesApp(
            f"Communes et contours ne correspondent pas : {len(sans_contour)} commune(s) sans contour, "
            f"{len(sans_commune)} contour(s) sans commune."
        )
    entites = []
    for entite in contours["features"]:
        code = entite["properties"]["code_insee"]
        ligne = lignes[code]
        proprietes = {
            "code_insee": code, "nom": ligne["nom"], "departement": ligne["departement"],
            "estimable": bool(ligne["statut"] == "estimable"),
            "significatif": bool(ligne["significatif"] in ("decote", "prime")),
            "couleur": couleur(ligne), "info": info_bulle(ligne),
        }
        entites.append({"type": "Feature", "geometry": entite["geometry"], "properties": proprietes})
    return entites


def filtrer(entites: list[dict], departements: list[str], significatives_seulement: bool) -> list[dict]:
    """Les communes écartées par un filtre restent sur la carte, en gris très pâle."""
    resultat = []
    for entite in entites:
        p = entite["properties"]
        gardee = p["departement"] in departements and (p["significatif"] or not significatives_seulement)
        if not gardee:
            p = {**p, "couleur": COULEUR_ECARTEE, "info": f"<b>{html.escape(p['nom'])}</b><br/>hors filtre"}
        resultat.append({**entite, "properties": p})
    return resultat


def limites_exterieures(departements: dict) -> dict:
    """Limites des départements sans leurs trous : seul l'anneau extérieur de chaque polygone est gardé.

    L'union simplifiée des communes garde des centaines de trous (interstices entre communes
    voisines, docs/app.md) : tracés en sombre, ils redessineraient presque toutes les frontières
    communales. Affichage seulement : le fichier n'est pas modifié.
    """
    entites = []
    for entite in departements["features"]:
        geometrie = entite["geometry"]
        if geometrie["type"] == "MultiPolygon":
            nouvelle = {"type": "MultiPolygon", "coordinates": [[polygone[0]] for polygone in geometrie["coordinates"]]}
        else:
            nouvelle = {"type": "Polygon", "coordinates": [geometrie["coordinates"][0]]}
        entites.append({**entite, "geometry": nouvelle})
    return {**departements, "features": entites}


def _points(coordonnees):
    """Tous les points (lon, lat) d'une géométrie Polygon ou MultiPolygon."""
    if coordonnees and isinstance(coordonnees[0], (int, float)):
        yield coordonnees
    else:
        for element in coordonnees:
            yield from _points(element)


def vue_initiale(entites: list[dict], largeur_px: int = 900) -> dict:
    """Centre et zoom (deck.gl) qui cadrent les entités ; vue de la France si la liste est vide."""
    points = [p for e in entites for p in _points(e["geometry"]["coordinates"])]
    if not points:
        return dict(CENTRE_PAR_DEFAUT)
    lons, lats = [p[0] for p in points], [p[1] for p in points]
    etendue = max(max(lons) - min(lons), 1.6 * (max(lats) - min(lats)), 1e-3)
    zoom = min(12.0, math.log2(360 * largeur_px / 512 / etendue))
    return {"latitude": (min(lats) + max(lats)) / 2, "longitude": (min(lons) + max(lons)) / 2, "zoom": round(zoom - 0.2, 2)}


def code_selectionne(evenement) -> str | None:
    """code_insee de la commune cliquée, d'après l'événement de st.pydeck_chart (None sinon)."""
    try:
        objets = evenement["selection"]["objects"]
    except (KeyError, TypeError):
        return None
    for liste in objets.values():
        for objet in liste:
            proprietes = objet.get("properties", objet)
            if "code_insee" in proprietes:
                return proprietes["code_insee"]
    return None
