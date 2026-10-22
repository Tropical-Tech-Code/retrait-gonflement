"""Onglet Carte : tuiles, carte en carrés (une grille par zone), légende et fiche commune."""

import os

import pandas as pd
import pydeck as pdk
import streamlit as st

import cartographie
import charte
import donnees
import textes

HAUTEUR_CARTE = 330   # px ; hauteur du graphique pydeck (valeur fixe exigée), pas liée à la fenêtre
# Même règle que cartographie.UNITE_PIXELS : constantes textuelles entre guillemets internes
ANCRAGE, BASE_TEXTE, JEU_CARACTERES = "'middle'", "'center'", "'auto'"


@st.cache_data(show_spinner=False)
def entites_carte(dossier: str) -> list[dict]:
    return cartographie.preparer_carres(donnees.charger_communes(dossier), donnees.charger_carres(dossier))


def tuiles(communes: pd.DataFrame, resume: dict) -> None:
    colonnes = st.columns(4)
    contenus = [
        charte.html_tuile(textes.TUILE_ESTIMABLES, textes.entier(resume["n_communes_estimables"]),
                          f"sur {textes.entier(len(communes))}"),
        charte.html_tuile(textes.TUILE_DECOTE, textes.entier(resume["n_decote"]), couleur=cartographie.hex_classe(1)),
        charte.html_tuile(textes.TUILE_PAS_DE_DECOTE, textes.entier(resume["n_pas_de_decote"]),
                          couleur=cartographie.hex_classe(2)),
        charte.html_tuile(textes.TUILE_INDETERMINEES, textes.entier(resume["n_indetermine"]),
                          couleur=cartographie.hex_classe(1), opacite=textes.OPACITE_PALE),
    ]
    for colonne, contenu in zip(colonnes, contenus):
        colonne.markdown(contenu, unsafe_allow_html=True)


def legende() -> str:
    elements = [(cartographie.hex_classe(classe), libelle, 1.0, False) for classe, libelle in textes.legende()]
    elements += [
        (cartographie.hex_classe(1), textes.LEGENDE_PALE, textes.OPACITE_PALE, False),
        (cartographie.hex_classe(None), textes.LEGENDE_NON_ESTIMABLE, 1.0, False),
        ("#FFFFFF", textes.LEGENDE_SELECTION, 1.0, True),
    ]
    return charte.html_legende(elements)


def couches(entites_zone: list[dict], selection: dict | None, etiquettes: list[dict]) -> list[pdk.Layer]:
    """Carrés, contour de la commune sélectionnée (noir sous blanc) et noms des départements."""
    liste = [pdk.Layer(
        "GeoJsonLayer", id="communes", data=cartographie.collection(entites_zone), pickable=True,
        stroked=False, filled=True, get_fill_color="properties.couleur",
    )]
    if selection is not None:
        for id_, style in (("selection_noir", cartographie.CONTOUR_NOIR), ("selection_blanc", cartographie.CONTOUR_BLANC)):
            liste.append(pdk.Layer(
                "GeoJsonLayer", id=id_, data=cartographie.collection([selection]), pickable=False,
                stroked=True, filled=False, get_line_color=style["couleur"], get_line_width=style["largeur"],
                line_width_units=cartographie.UNITE_PIXELS,
            ))
    style = cartographie.ETIQUETTE
    liste.append(pdk.Layer(
        "TextLayer", id="etiquettes", data=etiquettes, pickable=False, get_position="position", get_text="texte",
        get_size=style["taille"], size_units=cartographie.UNITE_PIXELS, get_color=style["couleur"],
        get_text_anchor=ANCRAGE, get_alignment_baseline=BASE_TEXTE, background=True,
        get_background_color=style["fond"], background_padding=[4, 2], font_weight=600,
        font_family=style["police"], character_set=JEU_CARACTERES,
    ))
    return liste


def carte(entites_zone: list[dict], selection: dict | None, etiquettes: list[dict],
          emprise: list[float] | None, resume: dict, zone: str) -> object:
    vue = cartographie.vue_zone(entites_zone, cartographie.LARGEUR_CARTE_PX, HAUTEUR_CARTE, emprise)
    if selection is not None:                       # commune choisie : vue centrée sur son carré
        vue = cartographie.vue_commune(vue, selection, resume, zone)
    deck = pdk.Deck(
        layers=couches(entites_zone, selection, etiquettes),
        initial_view_state=pdk.ViewState(**vue, max_zoom=12),
        views=[pdk.View(type="MapView", controller=cartographie.CONTROLEUR)],
        map_style=cartographie.STYLE_FOND,
        tooltip={"text": "{info}", "style": {"fontSize": "13px", "whiteSpace": "pre-line"}},
    )
    return st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object", key=cle_carte(), height=HAUTEUR_CARTE)


def cle_carte() -> str:
    """Clé du graphique : elle change après chaque clic lu, ce qui efface la sélection de Streamlit.

    Tant qu'une sélection reste active, Streamlit atténue tous les autres carrés ; la commune choisie
    est marquée par notre contour, pas par la sélection du graphique.
    """
    return f"carte_{st.session_state.get('version_carte', 0)}"


def fiche(ligne: pd.Series, resume: dict) -> str:
    """HTML de la fiche d'une commune (colonne de droite) : écart, statut, trois cases, note."""
    estimable = ligne["statut"] == "estimable"
    cases = [
        (textes.LIBELLE_CASES[0], textes.entier(ligne["n_ventes"])),
        (textes.LIBELLE_CASES[1], textes.entier(ligne["n_fort"])),
        (textes.LIBELLE_CASES[2], textes.entier(ligne["catnat_depuis_2015"])),
    ]
    if estimable:
        chiffre = textes.pct(ligne["prime"], 1, True)
        couleur = cartographie.couleur_texte(textes.classe_prime(ligne["prime"]))
        ic = textes.intervalle_pct(ligne["ic_bas"], ligne["ic_haut"])
        statut = textes.STATUTS_DECOTE[ligne["statut_decote"]].capitalize()
    else:
        chiffre, couleur, ic, statut = "—", "#4A514D", "", textes.NON_ESTIMABLE
    return charte.html_fiche(
        f"{textes.nom_departement(ligne['departement'])} ({ligne['departement']})", ligne["nom"],
        textes.LIBELLE_ECART_FICHE, chiffre, couleur, ic, statut, cases,
        textes.texte_commune(ligne, resume), textes.TITRE_NOTE, estimable,
    )


def appliquer_clic(lignes: pd.DataFrame) -> None:
    """Un clic sur un carré remplace la commune choisie, puis la sélection du graphique est effacée.

    L'événement de la carte est lu dans l'état de la session au début de l'exécution suivante :
    à ce moment, le selectbox n'est pas encore créé et sa valeur peut être écrite. Le changement de
    clé du graphique (`cle_carte`) repart d'une carte sans sélection : un clic = un seul traitement.
    """
    clic = cartographie.code_selectionne(st.session_state.get(cle_carte()))
    if clic is None:
        return
    st.session_state["version_carte"] = st.session_state.get("version_carte", 0) + 1
    if clic in lignes.index:
        st.session_state["commune"] = clic
        st.session_state["zone"] = textes.zone_de(lignes.loc[clic, "departement"])


def commune_choisie(lignes: pd.DataFrame) -> None:
    """Rappel du selectbox : la zone suit la commune."""
    code = st.session_state.get("commune")
    if code == textes.CODE_SEPARATEUR:
        # le séparateur n'est pas une commune : on garde la sélection précédente, sans erreur
        st.session_state["commune"] = st.session_state.get("commune_precedente")
        return
    if code in lignes.index:
        st.session_state["zone"] = textes.zone_de(lignes.loc[code, "departement"])


def zone_choisie(zones: list[str]) -> None:
    """Rappel du bouton de zone : on revient à la vue d'ensemble (commune effacée), même en recliquant.

    Recliquer sur la zone active la désélectionne : on remet alors la zone précédente.
    """
    if st.session_state.get("zone") is None:
        st.session_state["zone"] = st.session_state.get("zone_precedente", zones[0])
    st.session_state["commune"] = None


def afficher(tout: donnees.Donnees) -> None:
    """Onglet Carte. `tout` vient de donnees.charger_tout()."""
    communes, resume = tout.communes, tout.resume
    if os.environ.get("RG_DIAGNOSTIC"):
        # RG_DIAGNOSTIC=1 : une ligne au terminal par exécution de l'onglet (repérer un recalcul sans fin)
        print(f"[diagnostic] onglet Carte exécuté ; clic lu : "
              f"{cartographie.code_selectionne(st.session_state.get(cle_carte()))}", flush=True)
    lignes = communes.set_index("code_insee", drop=False)
    zones = list(textes.ZONES)
    st.session_state.setdefault("zone", zones[0])
    appliquer_clic(lignes)

    with charte.onglet("carte", resume):
        tuiles(communes, resume)
        gauche, droite = st.columns([784, 380], gap="small")
        with gauche, st.container(key="carte_gauche"):
            reglages = st.columns([3, 2], vertical_alignment="center")
            zone = reglages[0].segmented_control(
                textes.LIBELLE_ZONE, zones, key="zone", label_visibility="collapsed",
                on_change=zone_choisie, args=(zones,),
            ) or zones[0]
            st.session_state["zone_precedente"] = zone
            with reglages[1], st.container(key="recherche"):      # la charte dessine le contour de ce conteneur
                choix = st.selectbox(
                    textes.LIBELLE_COMMUNE, textes.codes_liste(communes), index=None, key="commune",
                    placeholder=textes.PLACEHOLDER_COMMUNE, label_visibility="collapsed",
                    on_change=commune_choisie, args=(lignes,),
                    format_func=lambda c: textes.SEPARATEUR_LISTE if c == textes.CODE_SEPARATEUR
                    else textes.libelle_liste(lignes.loc[c]),
                )
            st.session_state["commune_precedente"] = choix
            entites_zone = cartographie.carres_de_la_zone(entites_carte(str(donnees.dossier())), zone)
            selection = next((e for e in entites_zone if e["properties"]["code_insee"] == choix), None)
            carte(entites_zone, selection, cartographie.etiquettes_zone(resume, zone),
                  cartographie.emprise_de_zone(resume, zone), resume, zone)
            st.markdown(
                charte.html_sous_carte(
                    charte.html_note_carte(f"{textes.NOTE_POSITION} {textes.FOND_DE_CARTE}"), legende(),
                    charte.html_phrase_carte(textes.phrase_tests_multiples(resume)),
                ),
                unsafe_allow_html=True,
            )
        with droite:
            if choix:
                st.markdown(fiche(lignes.loc[choix], resume), unsafe_allow_html=True)
            else:
                with st.container(key="fiche_vide"):
                    st.markdown(charte.html_fiche_vide(textes.TITRE_INVITE, textes.INVITE_COMMUNE),
                                unsafe_allow_html=True)
