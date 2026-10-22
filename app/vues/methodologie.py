"""Onglet Méthodologie et limites : six cartes courtes et un renvoi vers docs/method.md (docs/app.md, onglet 4)."""

import streamlit as st

import charte
import donnees
import textes


def afficher(tout: donnees.Donnees) -> None:
    resume = tout.resume
    st.markdown(charte.html_grille_methodologie(textes.cartes_methodologie(resume)), unsafe_allow_html=True)
    st.markdown(
        charte.html_pied_methodologie(
            textes.PIED_METHODE, textes.LIEN_METHODE, textes.URL_METHODE,
            textes.PIED_SOURCES + textes.sources_methodologie(resume),
        ),
        unsafe_allow_html=True,
    )
