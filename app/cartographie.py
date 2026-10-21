"""Carte en carrés : couleurs, info-bulles, cadrage, étiquettes. Fonctions pures (sans Streamlit).

Orange = décote, bleu = écart positif, gris = non estimable (pas de rouge ni de vert). Une couleur
pâle signale un statut « indéterminé ». La palette et les libellés viennent de textes.py.
"""

import math

import donnees
import textes

# pydeck traite toute chaîne comme une expression JavaScript (« pixels » deviendrait « @@=pixels ») :
# les constantes textuelles s'écrivent avec des guillemets internes, retirés par pydeck.
UNITE_PIXELS = "'pixels'"
ALPHA_PLEIN, ALPHA_PALE = 255, round(255 * textes.OPACITE_PALE)

# Fond de carte Carto clair (chargé par le navigateur du visiteur, pas par le serveur) : aide à se situer.
STYLE_FOND = "light"
# Zoom avant et déplacement seulement : la molette et le pavé tactile sont désactivés, car la limite
# min_zoom n'est pas imposée par Streamlit (le dézoom partirait vers le monde entier). Les boutons + et −
# de la carte restent.
CONTROLEUR = {"scrollZoom": False}
LARGEUR_CARTE_PX = 758
NIVEAUX_ZOOM_COMMUNE = 1       # niveaux de zoom ajoutés au calage commun des carrés (carrés d'environ 50 px)
CONTOUR_NOIR = {"couleur": [27, 31, 29, 255], "largeur": 4.5}
CONTOUR_BLANC = {"couleur": [255, 255, 255, 255], "largeur": 1.8}
ETIQUETTE = {"couleur": [74, 81, 77, 255], "fond": [255, 255, 255, 190], "taille": 11, "police": "'sans-serif'"}


def rgb(hexa: str) -> tuple[int, int, int]:
    return int(hexa[1:3], 16), int(hexa[3:5], 16), int(hexa[5:7], 16)


def hex_classe(classe: int | None) -> str:
    """Couleur pleine d'une classe (légende, tuiles) ; gris pour une commune non estimable."""
    return textes.COULEUR_NON_ESTIMABLE if classe is None else textes.COULEURS_CLASSES[classe]


def couleur_texte(classe: int) -> str:
    """Teinte assombrie de la classe, lisible sur fond blanc (chiffre de la fiche)."""
    return textes.COULEURS_TEXTE_CLASSES[classe]


def couleur(ligne) -> list[int]:
    """RGBA d'un carré : couleur de la classe de l'écart, pâle si indéterminé, gris si non estimable."""
    if ligne["statut"] != "estimable":
        return [*rgb(textes.COULEUR_NON_ESTIMABLE), ALPHA_PLEIN]
    alpha = ALPHA_PALE if ligne["statut_decote"] == "indetermine" else ALPHA_PLEIN
    return [*rgb(textes.COULEURS_CLASSES[textes.classe_prime(ligne["prime"])]), alpha]


def preparer_carres(communes, carres: dict) -> list[dict]:
    """Entités GeoJSON des carrés avec leurs propriétés d'affichage, jointes sur code_insee."""
    lignes = {ligne["code_insee"]: ligne for _, ligne in communes.iterrows()}
    codes_carres = {e["properties"]["code_insee"] for e in carres["features"]}
    sans_carre = sorted(set(lignes) - codes_carres)
    sans_commune = sorted(codes_carres - set(lignes))
    if sans_carre or sans_commune:
        raise donnees.ErreurDonneesApp(
            f"Communes et carrés ne correspondent pas : {len(sans_carre)} commune(s) sans carré, "
            f"{len(sans_commune)} carré(s) sans commune."
        )
    entites = []
    for entite in carres["features"]:
        code = entite["properties"]["code_insee"]
        ligne = lignes[code]
        proprietes = {
            # propriétés minimales : tout est renvoyé au navigateur à chaque exécution (le nom est dans « info »)
            "code_insee": code, "departement": ligne["departement"],
            "couleur": couleur(ligne), "info": textes.texte_info_bulle(ligne),
        }
        entites.append({"type": "Feature", "geometry": entite["geometry"], "properties": proprietes})
    return entites


def carres_de_la_zone(entites: list[dict], zone: str) -> list[dict]:
    departements = textes.ZONES[zone]
    return [e for e in entites if e["properties"]["departement"] in departements]


def collection(entites: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": entites}


def etiquettes_zone(resume: dict, zone: str) -> list[dict]:
    """Une étiquette par département de la zone : texte en capitales et position (lon, lat)."""
    etiquettes = resume["carres"]["etiquettes"]
    return [
        {"position": [etiquettes[dep]["lon"], etiquettes[dep]["lat"]],
         "texte": f"{textes.nom_departement(dep)} · {dep}".upper()}
        for dep in textes.ZONES[zone] if dep in etiquettes
    ]


def _points(coordonnees):
    """Tous les points (lon, lat) d'une géométrie Polygon ou MultiPolygon."""
    if coordonnees and isinstance(coordonnees[0], (int, float)):
        yield coordonnees
    else:
        for element in coordonnees:
            yield from _points(element)


def _mercator(latitude: float) -> float:
    return math.log(math.tan(math.pi / 4 + math.radians(latitude) / 2))


def emprise_de_zone(resume: dict, zone: str) -> list[float] | None:
    """[lon_min, lat_min, lon_max, lat_max] des carrés et des étiquettes de la zone (pipeline), None si absente."""
    for z in resume["carres"].get("zones", {}).values():
        if tuple(z.get("departements", ())) == textes.ZONES[zone]:
            return z.get("emprise")
    return None


def vue_commune(vue: dict, entite: dict, resume: dict, zone: str) -> dict:
    """Vue centrée sur le carré d'une commune, avec des carrés de la même taille à l'écran dans toutes les zones.

    Taille visée = `NIVEAUX_ZOOM_COMMUNE` niveaux de plus que le plus grand `largeur_carre_px` de la clé
    `carres` (la zone aux carrés les plus gros) ; zoom = zoom de la zone + log2(taille visée / taille de la
    zone). Le zoom minimal reste celui de la zone.
    """
    zones = resume["carres"].get("zones", {})
    tailles = [z["largeur_carre_px"] for z in zones.values() if z.get("largeur_carre_px")]
    actuelle = next((z.get("largeur_carre_px") for z in zones.values()
                     if tuple(z.get("departements", ())) == textes.ZONES[zone]), None)
    points = list(_points(entite["geometry"]["coordinates"]))
    lons, lats = [p[0] for p in points], [p[1] for p in points]
    zoom = vue["zoom"]
    if tailles and actuelle:
        zoom += math.log2(max(tailles) / actuelle) + NIVEAUX_ZOOM_COMMUNE
    milieu = (_mercator(min(lats)) + _mercator(max(lats))) / 2
    return {
        **vue,
        "latitude": round(math.degrees(2 * math.atan(math.exp(milieu)) - math.pi / 2), 5),
        "longitude": round((min(lons) + max(lons)) / 2, 5),
        "zoom": round(zoom, 2),
    }


def vue_zone(entites: list[dict], largeur_px: int = LARGEUR_CARTE_PX, hauteur_px: int = 370,
             emprise: list[float] | None = None) -> dict:
    """Centre, zoom et zoom minimal (deck.gl) qui cadrent la zone.

    Le cadrage contient les carrés et, si `emprise` est donnée, les étiquettes des départements.
    Le zoom minimal est le zoom du cadrage : on ne peut pas dézoomer au-delà de la zone.
    """
    points = [p for e in entites for p in _points(e["geometry"]["coordinates"])]
    if emprise:
        points += [[emprise[0], emprise[1]], [emprise[2], emprise[3]]]
    if not points:
        return {"latitude": 46.6, "longitude": 2.4, "zoom": 5.0, "min_zoom": 4.0}
    lons, lats = [p[0] for p in points], [p[1] for p in points]
    largeur = (max(lons) - min(lons)) / 360                          # part de la largeur du monde
    hauteur = (_mercator(max(lats)) - _mercator(min(lats))) / (2 * math.pi)
    marge = 0.94                                                      # un peu d'air autour de la zone
    zoom = min(
        math.log2(largeur_px * marge / (512 * max(largeur, 1e-6))),
        math.log2(hauteur_px * marge / (512 * max(hauteur, 1e-6))),
        12.0,
    )
    milieu = (_mercator(min(lats)) + _mercator(max(lats))) / 2
    return {
        "latitude": round(math.degrees(2 * math.atan(math.exp(milieu)) - math.pi / 2), 5),
        "longitude": round((min(lons) + max(lons)) / 2, 5),
        "zoom": round(zoom, 2),
        "min_zoom": round(zoom, 2),
    }


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
