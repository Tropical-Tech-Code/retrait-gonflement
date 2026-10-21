"""Charte graphique de l'app : CSS injecté une fois, en-tête commun et encadrés.

Polices système uniquement (aucun lien externe). Les textes passent par html.escape avant
d'entrer dans le HTML : un texte automatique ne peut pas injecter de balise.
Spécification : docs/app.md, section « Charte ».
"""

import html
import math

import streamlit as st

import textes

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
.rg-carte { background: #FFFFFF; border: 1px solid #DCDFDA; border-radius: 10px; padding: 32px 36px; display: flex; flex-direction: column; gap: 18px; }
.rg-surtitre-carte { font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: #4A514D; font-weight: 600; }
.stMarkdown h2.rg-reponse { margin: 0 !important; padding: 0 !important; font-size: 32px !important; line-height: 1.18 !important; font-weight: 700 !important; color: #1B1F1D !important; }
.rg-chiffre-ligne { display: flex; align-items: baseline; gap: 18px; flex-wrap: wrap; }
.rg-chiffre { font-size: 56px; font-weight: 700; line-height: 1; color: #1B1F1D; }
.rg-chiffre-ic { font-size: 22px; font-weight: 500; color: #2F3532; }
.rg-chiffre-mention { font-size: 13px; color: #4A514D; }
.rg-detail { margin: -6px 0 0; font-size: 14px; color: #4A514D; }
.rg-lecture { margin: 0; font-size: 17px; line-height: 1.5; color: #2F3532; }
.rg-barre { position: relative; width: 100%; height: 76px; }
.rg-barre div { position: absolute; }
.rg-barre .rg-etiquette { top: 56px; font-size: 12px; color: #4A514D; transform: translateX(-50%); white-space: nowrap; }
.rg-bloc-gris { background: #EEF0EC; border-radius: 10px; padding: 24px 26px; display: flex; flex-direction: column; gap: 10px; }
.rg-bloc-gris p { margin: 0; font-size: 15px; color: #2F3532; }
.stMain .block-container .st-key-droite { gap: 20px; }
.stMain .block-container .st-key-signal { background: #1B1F1D; border-radius: 10px; padding: 24px 26px; gap: 16px; }
.stMain .block-container .st-key-signal [data-testid="stButton"] { margin: auto 0 0; }
.stMain .block-container .st-key-resultat [data-testid="stHorizontalBlock"] { align-items: stretch; }
.stMain .block-container .st-key-resultat [data-testid="stColumn"], .stMain .block-container .st-key-resultat [data-testid="stColumn"] > [data-testid="stVerticalBlock"] { padding-bottom: 0; }
.stMain .block-container .st-key-resultat [data-testid="stColumn"] [data-testid="stVerticalBlock"] > :last-child, .stMain .block-container .st-key-resultat [data-testid="stColumn"] [data-testid="stMarkdownContainer"] { margin-bottom: 0; }
.stMain .block-container .st-key-resultat [data-testid="stColumn"]:has(.st-key-droite) { display: flex; flex-direction: column; }
.stMain .block-container .st-key-resultat [data-testid="stColumn"] div:has(.st-key-droite), .stMain .block-container .st-key-droite, .stMain .block-container .st-key-droite div:has(.st-key-signal), .stMain .block-container .st-key-signal { display: flex; flex-direction: column; flex: 1 1 auto; min-height: 0; }
.st-key-signal .rg-surtitre-signal { font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: #E99A68 !important; font-weight: 600; }
.st-key-signal .rg-signal-ligne { display: flex; align-items: center; gap: 18px; }
.st-key-signal .rg-signal-nombre { font-size: 64px; font-weight: 700; line-height: 1; color: #E99A68 !important; }
.st-key-signal .rg-signal-texte { font-size: 16px; line-height: 1.4; color: #F4F5F2 !important; }
.st-key-signal .rg-signal-note { margin: 0; font-size: 14px; color: #C9CDC7 !important; }
.st-key-signal button { background: #E99A68; color: #1B1F1D; border: 0; border-radius: 8px; padding: 12px 18px; font-weight: 600; }
.st-key-signal button:hover { background: #F0AC83; color: #1B1F1D; }
.st-key-signal button p { color: #1B1F1D !important; font-weight: 600; }
.stMain .block-container .rg-pied { padding: 24px 0 0; font-size: 12px; color: #4A514D; }
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


def _e(texte: str) -> str:
    return html.escape(texte, quote=False)


def html_carte_resultat(surtitre: str, reponse: str, chiffre: str, ic: str, mention: str,
                        detail: str, barre: str, lecture: str) -> str:
    """Carte blanche de l'onglet Résultat (tous les textes sont échappés ; `barre` vient de html_barre_fourchette)."""
    return (
        '<section class="rg-carte">'
        f'<div class="rg-surtitre-carte">{_e(surtitre)}</div>'
        f'<h2 class="rg-reponse">{_e(reponse)}</h2>'
        '<div class="rg-chiffre-ligne">'
        f'<span class="rg-chiffre">{_e(chiffre)}</span><span class="rg-chiffre-ic">{_e(ic)}</span>'
        f'<span class="rg-chiffre-mention">{_e(mention)}</span></div>'
        f'<p class="rg-detail">{_e(detail)}</p>{barre}'
        f'<p class="rg-lecture">{_e(lecture)}</p></section>'
    )


def _etiquette_axe(valeur: float) -> str:
    return "0" if valeur == 0 else textes.pct(valeur / 100, 0, True)


def html_barre_fourchette(effet: float, bas: float, haut: float, seuil: float, description: str) -> str:
    """IC sur un axe en pourcentage de la largeur : 0, seuil « pas de décote » et estimation.

    L'axe est symétrique, de 3 en 3 points, et toujours plus large que l'IC et le seuil (minimum ±6 %).
    """
    plus_grand = max(abs(bas), abs(haut), abs(seuil)) * 100
    m = max(6.0, 3.0 * (math.floor(plus_grand / 3) + 1))

    def position(fraction: float) -> float:
        return (fraction * 100 + m) / (2 * m) * 100

    seuil_texte = textes.pct(seuil, 0 if round(seuil * 100) == seuil * 100 else 1, True)
    etiquettes = [(position(0), "0", "#1B1F1D", 600), (position(seuil), f"{seuil_texte} : seuil", "#C2410C", 600)]
    graduation = -m
    while graduation <= m:
        if graduation != 0 and abs(graduation - seuil * 100) >= 1.5:
            etiquettes.append((position(graduation / 100), _etiquette_axe(graduation), "#4A514D", 400))
        graduation += 3
    textes_axe = "".join(
        f'<div class="rg-etiquette" style="left:{x:.2f}%;color:{couleur};font-weight:{poids}">{_e(t)}</div>'
        for x, t, couleur, poids in etiquettes
    )
    gauche, droite = position(bas), position(haut)
    return (
        f'<div class="rg-barre" role="img" aria-label="{html.escape(description)}">'
        '<div style="left:0;top:26px;width:100%;height:14px;background:#EEF0EC;border-radius:7px"></div>'
        f'<div style="left:{gauche:.2f}%;top:26px;width:{droite - gauche:.2f}%;height:14px;background:#BDB6A4;border-radius:7px"></div>'
        f'<div style="left:{position(0):.2f}%;top:16px;width:2px;height:34px;margin-left:-1px;background:#1B1F1D"></div>'
        f'<div style="left:{position(seuil):.2f}%;top:10px;width:0;height:46px;border-left:2px dashed #C2410C"></div>'
        f'<div style="left:{position(effet):.2f}%;top:23px;width:12px;height:20px;margin-left:-6px;border-radius:3px;background:#1B1F1D"></div>'
        f'{textes_axe}</div>'
    )


def html_bloc_gris(titre: str, paragraphes: list[str]) -> str:
    corps = "".join(f"<p>{_e(p)}</p>" for p in paragraphes)
    return f'<section class="rg-bloc-gris"><div class="rg-surtitre-carte">{_e(titre)}</div>{corps}</section>'


def html_signal(titre: str, nombre: str, texte: str, note: str) -> str:
    return (
        f'<div class="rg-surtitre-signal">{_e(titre)}</div>'
        f'<div class="rg-signal-ligne"><span class="rg-signal-nombre">{_e(nombre)}</span>'
        f'<span class="rg-signal-texte">{_e(texte)}</span></div>'
        f'<p class="rg-signal-note">{_e(note)}</p>'
    )


def html_pied(texte: str) -> str:
    return f'<div class="rg-pied">{_e(texte)}</div>'


def entete(surtitre: str, titre: str) -> None:
    st.markdown(html_entete(surtitre, titre), unsafe_allow_html=True)


def encadre_beige(texte: str) -> None:
    st.markdown(html_encadre("beige", texte), unsafe_allow_html=True)


def encadre_gris(texte: str) -> None:
    st.markdown(html_encadre("gris", texte), unsafe_allow_html=True)
