"""Charte graphique de l'app : CSS injecté une fois, en-tête commun et encadrés.

Polices système uniquement (aucun lien externe). Les textes passent par html.escape avant
d'entrer dans le HTML : un texte automatique ne peut pas injecter de balise.
Spécification : docs/app.md, section « Charte ».
"""

import html

import streamlit as st

BEIGE = "#FBF3EC"
GRIS = "#EEF0EC"

CSS = """
[data-testid="stHeader"] { background: transparent; }
.stMain .block-container { padding: 0 48px 12px; max-width: none; }
.stMain .block-container [data-testid="stVerticalBlock"] { gap: 0.6rem; }
.rg-entete { background: #1B1F1D; margin: 0 -48px; padding: 18px 48px 12px; }
.stMarkdown .rg-entete .rg-surtitre { margin: 0 0 4px; padding: 0; font-size: 12px; line-height: 1.4; letter-spacing: 0.08em; text-transform: uppercase; color: #E99A68 !important; font-weight: 600; }
.stMarkdown .rg-entete h1.rg-titre { margin: 0 !important; padding: 0 !important; font-size: 26px !important; line-height: 1.2 !important; color: #FFFFFF !important; font-weight: 700 !important; }
[data-baseweb="tab-list"] { gap: 4px; }
[data-baseweb="tab"] { padding: 11px 20px; color: #4A514D; }
[data-baseweb="tab"][aria-selected="true"] { color: #1B1F1D; font-weight: 600; }
.rg-encadre { border-radius: 8px; padding: 14px 16px; font-size: 14px; line-height: 1.45; color: #2F3532; }
.rg-beige { background: #FBF3EC; }
.rg-gris { background: #EEF0EC; }
.stMain, .rg-encadre, [data-testid="stMetricValue"] { font-variant-numeric: tabular-nums; }
"""


def injecter_css() -> None:
    """À appeler une fois par exécution, avant tout autre élément."""
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def html_entete(surtitre: str, titre: str) -> str:
    return (
        '<div class="rg-entete">'
        f'<div class="rg-surtitre">{html.escape(surtitre, quote=False)}</div>'
        f'<h1 class="rg-titre">{html.escape(titre, quote=False)}</h1>'
        "</div>"
    )


def html_encadre(couleur: str, texte: str) -> str:
    """couleur : « beige » (note, prudence) ou « gris » (neutre)."""
    contenu = html.escape(texte, quote=False).replace("\n", "<br>")
    return f'<div class="rg-encadre rg-{couleur}">{contenu}</div>'


def entete(surtitre: str, titre: str) -> None:
    st.markdown(html_entete(surtitre, titre), unsafe_allow_html=True)


def encadre_beige(texte: str) -> None:
    st.markdown(html_encadre("beige", texte), unsafe_allow_html=True)


def encadre_gris(texte: str) -> None:
    st.markdown(html_encadre("gris", texte), unsafe_allow_html=True)
