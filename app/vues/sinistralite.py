"""Onglet Sinistralité × écart : tableau à quatre cases et communes au risque non intégré (docs/app.md, onglet 2)."""

import streamlit as st

import charte
import donnees
import textes


def afficher(tout: donnees.Donnees) -> None:
    resume = tout.resume
    mediane = resume["mediane_sinistralite"]
    effectifs = resume["n_par_quadrant"]
    n_angle_mort = int(effectifs["Angle mort"])

    cases = [
        charte.html_case_quadrant(
            nom, textes.libelle_quadrant(nom), textes.entier(effectifs[nom]),
            textes.PHRASES_QUADRANTS[nom], *textes.POSITIONS_QUADRANTS[nom],
        )
        for nom in textes.QUADRANTS
    ]
    nombre_indeterminees, suite_indeterminees = textes.indeterminees(int(resume["n_indetermine"]))
    lignes = [textes.ligne_angle_mort(ligne) for _, ligne in textes.angles_morts(tout.communes).iterrows()]

    with st.container(key="onglet_sinistralite"):
        gauche, droite = st.columns([1.1, 1], gap="small")
        # Conteneur à clé « gauche_sinistralite » : le CSS de charte.py étire la carte à la hauteur de la colonne de droite
        with gauche, st.container(key="gauche_sinistralite"):
            st.markdown(
                charte.html_carte_sinistralite(
                    textes.TITRE_SINISTRALITE,
                    textes.phrase_explication_sinistralite(mediane),
                    textes.libelles_colonnes_sinistralite(mediane),
                    textes.LIGNES_QUADRANTS,
                    cases,
                    nombre_indeterminees,
                    suite_indeterminees,
                ),
                unsafe_allow_html=True,
            )
        with droite, st.container(key="droite_sinistralite"):
            st.markdown(
                charte.html_signal_sombre(
                    textes.entier(n_angle_mort),
                    textes.titre_signal_sinistralite(n_angle_mort),
                    textes.SIGNAL_SINISTRALITE,
                ),
                unsafe_allow_html=True,
            )
            st.markdown(
                charte.html_tableau_angles(
                    textes.TITRE_TABLEAU_ANGLES, textes.EN_TETES_ANGLES, lignes, textes.AUCUN_ANGLE_MORT
                ),
                unsafe_allow_html=True,
            )
    st.markdown(charte.html_pied(textes.pied_sinistralite(resume["seuil_pas_de_decote"])), unsafe_allow_html=True)
