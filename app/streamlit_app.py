"""Point d'entrée : configuration de la page, en-tête commun et quatre onglets.

    uv run streamlit run app/streamlit_app.py
"""

import streamlit as st

import charte
import donnees
import textes
from vues import carte

st.set_page_config(page_title="Retrait-gonflement et prix des maisons", layout="wide")


def en_construction() -> None:
    charte.encadre_gris(textes.EN_CONSTRUCTION)


def afficher() -> None:
    charte.injecter_css()
    charte.entete(textes.SURTITRE, textes.TITRE_APP)
    try:
        tout = donnees.charger_tout()
    except donnees.ErreurDonneesApp as erreur:
        st.error(str(erreur))
        st.stop()

    # L'onglet actif est lu et écrit par st.session_state["onglet"] ; seul l'onglet ouvert est calculé
    resultat, sinistralite, vue_carte, methodologie = st.tabs(
        list(textes.ONGLETS), key="onglet", on_change="rerun"
    )
    with resultat:
        if resultat.open:
            carte.bandeau(tout.resume)  # provisoire, jusqu'à l'étape 4
    with sinistralite:
        if sinistralite.open:
            en_construction()
    with vue_carte:
        if vue_carte.open:
            carte.afficher(tout)
    with methodologie:
        if methodologie.open:
            en_construction()


afficher()
