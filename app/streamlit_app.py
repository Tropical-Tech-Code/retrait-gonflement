"""Point d'entrée : configuration de la page et navigation.

    uv run streamlit run app/streamlit_app.py
"""

import streamlit as st

st.set_page_config(page_title="Retrait-gonflement et prix des maisons", layout="wide")

page = st.navigation([st.Page("vues/carte.py", title="Carte", default=True)])
page.run()
