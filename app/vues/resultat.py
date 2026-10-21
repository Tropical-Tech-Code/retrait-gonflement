"""Onglet Résultat : réponse, chiffre phare, ce qui a été testé et signal faible (docs/app.md, onglet 1)."""

import streamlit as st

import charte
import donnees
import textes


def ouvrir_sinistralite() -> None:
    """Rappel du bouton : ouvre l'onglet « Sinistralité × écart » (clé `onglet` de st.tabs)."""
    st.session_state["onglet"] = textes.ONGLETS[1]


def afficher(tout: donnees.Donnees) -> None:
    resume = tout.resume
    principal = resume["modeles_globaux"]["principal"]
    contraste = principal["contraste_fort_moins_moyen"]
    seuil = resume["seuil_pas_de_decote"]
    bas, haut = contraste["ic95_effet"]
    ic = textes.intervalle_pct(bas, haut)
    description = f"Intervalle de confiance {ic} ; seuil « pas de décote » à {textes.pct(seuil, 1, True)}"

    # Conteneur à clé « resultat » : le CSS de charte.py étire la colonne de droite à la hauteur de la gauche
    with st.container(key="resultat"):
        gauche, droite = st.columns([1.5, 1], gap="small")
        with gauche:
            st.markdown(
                charte.html_carte_resultat(
                    textes.SURTITRE_RESULTAT,
                    textes.phrase_reponse(contraste, seuil),
                    textes.chiffre_phare(contraste),
                    ic,
                    textes.MENTION_IC,
                    textes.ligne_effectifs(resume, tout.communes["departement"].nunique()),
                    charte.html_barre_fourchette(contraste["effet"], bas, haut, seuil, description),
                    textes.phrase_lecture(contraste, seuil),
                ),
                unsafe_allow_html=True,
            )
        with droite, st.container(key="droite"):
            st.markdown(
                charte.html_bloc_gris(
                    textes.TITRE_TESTE, [textes.paragraphe_teste(principal), textes.TESTE_CONCLUSION]
                ),
                unsafe_allow_html=True,
            )
            n_angle_mort = int(resume["n_par_quadrant"]["Angle mort"])
            with st.container(key="signal"):
                st.markdown(
                    charte.html_signal(
                        textes.TITRE_SIGNAL, textes.entier(n_angle_mort),
                        textes.phrase_signal(n_angle_mort), textes.SIGNAL_NOTE,
                    ),
                    unsafe_allow_html=True,
                )
                st.button(textes.BOUTON_SIGNAL, key="vers_sinistralite", on_click=ouvrir_sinistralite)
    st.markdown(charte.html_pied(textes.sources_pied(resume)), unsafe_allow_html=True)
