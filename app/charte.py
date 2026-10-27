"""Charte graphique de l'app : CSS injecté une fois, en-tête commun et encadrés.

Polices système uniquement (aucun lien externe). Les textes passent par html.escape avant
d'entrer dans le HTML : un texte automatique ne peut pas injecter de balise.
Spécification : docs/app.md, section « Charte ».
"""

import html
import math
from contextlib import contextmanager

import streamlit as st

import textes

BEIGE = "#FBF3EC"
GRIS = "#EEF0EC"

CSS = """
[data-testid="stHeader"] { background: transparent; }
.stMain .block-container { padding: 0 48px; max-width: none; }
.stMain .block-container [data-testid="stVerticalBlock"] { gap: 0.6rem; }
[data-testid="stHeaderActionElements"], .stMarkdown :is(h1, h2, h3, h4, h5, h6) > a[href^="#"] { display: none !important; }
.stMain .block-container [class*="st-key-page_"] { gap: 0; }
.stMain .block-container [class*="st-key-zone_"] [data-testid="stMarkdownContainer"] { margin-bottom: 0; }
.stMain .block-container .st-key-zone_resultat [data-testid="stHorizontalBlock"], .stMain .block-container .st-key-zone_sinistralite [data-testid="stHorizontalBlock"] { align-items: stretch; }
.stMain .block-container :is(.st-key-zone_resultat, .st-key-zone_sinistralite) [data-testid="stColumn"], .stMain .block-container :is(.st-key-zone_resultat, .st-key-zone_sinistralite) [data-testid="stColumn"] > [data-testid="stVerticalBlock"] { display: flex; flex-direction: column; padding-bottom: 0; }
.stMain .block-container :is(.st-key-zone_resultat, .st-key-zone_sinistralite) [data-testid="stColumn"] > [data-testid="stVerticalBlock"] { flex: 1 1 auto; }
.stMain .block-container :is(.st-key-zone_resultat, .st-key-zone_sinistralite) [data-testid="stColumn"] div:has(.rg-etire), .stMain .block-container :is(.st-key-zone_resultat, .st-key-zone_sinistralite) [data-testid="stColumn"] div:has(.st-key-signal), .stMain .block-container :is(.st-key-zone_resultat, .st-key-zone_sinistralite) .rg-etire, .stMain .block-container :is(.st-key-zone_resultat, .st-key-zone_sinistralite) .st-key-signal { display: flex; flex-direction: column; flex: 1 1 auto; }
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
.stMain .block-container .st-key-droite, .stMain .block-container .st-key-droite_sinistralite { gap: 20px; }
.stMain .block-container .st-key-signal { background: #1B1F1D; border-radius: 10px; padding: 24px 26px; gap: 16px; }
.stMain .block-container .st-key-signal [data-testid="stButton"] { margin: auto 0 0; }
.st-key-signal .rg-surtitre-signal { font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: #E99A68 !important; font-weight: 600; }
.st-key-signal .rg-signal-ligne { display: flex; align-items: center; gap: 18px; }
.st-key-signal .rg-signal-nombre { font-size: 64px; font-weight: 700; line-height: 1; color: #E99A68 !important; }
.st-key-signal .rg-signal-texte { font-size: 16px; line-height: 1.4; color: #F4F5F2 !important; }
.st-key-signal .rg-signal-note { margin: 0; font-size: 14px; color: #C9CDC7 !important; }
.st-key-signal button { background: #E99A68; color: #1B1F1D; border: 0; border-radius: 8px; padding: 12px 18px; font-weight: 600; }
.st-key-signal button:hover { background: #F0AC83; color: #1B1F1D; }
.st-key-signal button p { color: #1B1F1D !important; font-weight: 600; }
.stMain .block-container .rg-pied { padding: 24px 0 20px; font-size: 12px; line-height: 1.5; color: #4A514D; }
.stMain .block-container .rg-pied a { color: #C2410C; }
.stMain .block-container .rg-pied a:hover { color: #7A3410; }
.rg-tuile { background: #FFFFFF; border: 1px solid #DCDFDA; border-radius: 10px; padding: 6px 14px; }
.rg-tuile-libelle { font-size: 12px; color: #4A514D; }
.rg-tuile-valeur { font-size: 22px; font-weight: 700; line-height: 1.2; color: #1B1F1D; }
.rg-tuile-complement { font-size: 14px; font-weight: 500; color: #4A514D; }
.rg-sw { display: inline-block; width: 12px; height: 12px; border-radius: 3px; vertical-align: -1px; margin-right: 5px; box-shadow: inset 0 0 0 1px rgba(27, 31, 29, 0.12); }
.stMain .block-container .st-key-carte_gauche { --texte-legende: 12px; --couleur-legende: #2F3532; --texte-controle: 14px; background: #FFFFFF; border: 1px solid #DCDFDA; border-radius: 10px; padding: 10px 12px; gap: 6px; }
.st-key-carte_gauche [data-testid="stButtonGroup"] button, .st-key-carte_gauche [data-testid="stButtonGroup"] button p { font-size: var(--texte-controle); }
.st-key-carte_gauche [data-testid="stDeckGlJsonChart"] { border-radius: 6px; overflow: hidden; }
.rg-note-carte { margin: 0; font-size: var(--texte-legende); color: var(--couleur-legende); }
.rg-sous-carte { display: flex; flex-direction: column; gap: 6px; }
.rg-legende { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px; font-size: var(--texte-legende); color: var(--couleur-legende); }
.rg-legende > span { display: inline-flex; align-items: center; }
.rg-legende .rg-sw { vertical-align: middle; margin-right: 5px; flex: none; }
.rg-legende .rg-sw.rg-sw-anneau { margin: 0 9px 0 4px; }
.rg-phrase-carte { margin: 0; font-size: var(--texte-controle); color: #4A514D; }
.st-key-carte_gauche .rg-sous-carte p.rg-note-carte { font-size: var(--texte-legende) !important; color: var(--couleur-legende) !important; line-height: 1.4 !important; }
.st-key-carte_gauche .rg-sous-carte p.rg-phrase-carte { font-size: var(--texte-controle) !important; line-height: 1.4 !important; }
.stMain .block-container .st-key-fiche_vide { background: #FFFFFF; border: 1px solid #DCDFDA; border-radius: 10px; padding: 20px 22px; }
.st-key-fiche_vide [data-testid="stVerticalBlock"] { align-items: center; text-align: center; gap: 10px; }
.rg-invite { display: flex; flex-direction: column; align-items: center; gap: 10px; text-align: center; }
.rg-invite-rond { width: 56px; height: 56px; border-radius: 50%; background: #FBF3EC; display: flex; align-items: center; justify-content: center; }
.rg-invite-titre { margin: 0; font-size: 16px; font-weight: 700; color: #1F2420; }
.rg-invite-texte { margin: 0; font-size: 14px; color: #4A514D; max-width: 300px; }
.st-key-recherche [data-baseweb="select"] > div:first-child,
.st-key-recherche [data-testid="stSelectbox"] div[role="combobox"],
.st-key-recherche [data-testid="stSelectbox"] div:has(> input[role="combobox"]) { border: 1.5px solid #C2410C !important; }
.rg-fiche { background: #FFFFFF; border: 1px solid #DCDFDA; border-radius: 10px; padding: 20px 22px; display: flex; flex-direction: column; gap: 12px; }
.rg-fiche-dep { font-size: 13px; color: #4A514D; }
.rg-fiche-nom { font-size: 22px; font-weight: 700; line-height: 1.2; color: #1B1F1D; }
.rg-fiche-libelle { font-size: 13px; color: #4A514D; }
.rg-fiche-ecart { display: flex; align-items: baseline; gap: 12px; margin-top: -6px; }
.rg-fiche-chiffre { font-size: 44px; font-weight: 700; line-height: 1; }
.rg-fiche-ic { font-size: 15px; color: #2F3532; }
.rg-pastille { align-self: flex-start; background: #EEF0EC; border-radius: 999px; padding: 3px 12px; font-size: 13px; font-weight: 600; color: #2F3532; }
.rg-cases { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.rg-case { background: #F4F5F2; border-radius: 8px; padding: 8px 10px; }
.rg-case-libelle { font-size: 12px; color: #4A514D; line-height: 1.3; }
.rg-case-valeur { font-size: 18px; font-weight: 700; color: #1B1F1D; }
.rg-note { margin-top: 4px; }
.rg-note-titre { font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: #7A3410; font-weight: 700; margin-bottom: 6px; }
.rg-note p { margin: 0; font-size: 14px; color: #2F3532; }
.rg-carte-s { background: #FFFFFF; border: 1px solid #DCDFDA; border-radius: 10px; padding: 20px 28px; display: flex; flex-direction: column; gap: 10px; }
.stMain .block-container .rg-carte-s h2.rg-titre-s { margin: 0 !important; padding: 0 !important; font-size: 22px !important; font-weight: 700 !important; line-height: 1.2 !important; color: #1B1F1D !important; }
.stMain .block-container .rg-carte-s p.rg-explication { margin: 0 0 16px; font-size: 14px; line-height: 1.45; color: #4A514D; }
.rg-quad { display: grid; grid-template-columns: 112px minmax(0, 1fr) minmax(0, 1fr); grid-template-rows: auto minmax(104px, auto) minmax(104px, auto); gap: 8px; }
.rg-quad-colonne { font-size: 13px; font-weight: 600; color: #4A514D; text-align: center; }
.rg-quad-ligne { font-size: 13px; font-weight: 600; color: #4A514D; align-self: center; }
.rg-quad-case { border-radius: 8px; padding: 10px 14px; display: flex; flex-direction: column; gap: 2px; }
.rg-quad-case.rg-mis-en-avant { border: 2px solid #C2410C; padding: 9px 13px; }
.rg-quad-nom { font-size: 12px; letter-spacing: 0.06em; text-transform: uppercase; font-weight: 700; }
.rg-quad-nombre { font-size: 34px; font-weight: 700; line-height: 1.05; }
.rg-quad-phrase { font-size: 13px; line-height: 1.3; }
.stMain .block-container .rg-carte-s p.rg-note-s { margin: 0 0 2px; font-size: var(--texte-legende, 12px) !important; color: var(--couleur-legende, #2F3532) !important; line-height: 1.4 !important; }
.rg-indeterminees { background: #EEF0EC; border-radius: 8px; padding: 12px 16px; font-size: 14px; color: #2F3532; margin-top: auto; }
.rg-sombre { background: #1B1F1D; border-radius: 10px; padding: 20px 24px; display: flex; align-items: center; gap: 20px; }
.rg-sombre .rg-sombre-nombre { font-size: 60px; font-weight: 700; line-height: 1; color: #E99A68 !important; }
.rg-sombre .rg-sombre-titre { font-size: 20px; font-weight: 600; color: #F4F5F2 !important; }
.rg-sombre .rg-sombre-texte { font-size: 13px; color: #C9CDC7 !important; }
.rg-sombre > div { display: flex; flex-direction: column; gap: 4px; }
.rg-angles { background: #FFFFFF; border: 1px solid #DCDFDA; border-radius: 10px; padding: 16px 20px; display: flex; flex-direction: column; gap: 6px; }
.rg-angles-titre { font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: #4A514D; font-weight: 600; padding-bottom: 4px; }
.rg-angles { min-height: 220px; }
.rg-angles-corps { flex: 1 1 0; min-height: 120px; overflow-y: auto; }
.rg-angles-ligne { display: grid; grid-template-columns: minmax(0, 1fr) 32px 50px 160px 46px 88px; gap: 6px; font-size: 12px; padding: 4px 0; border-bottom: 1px solid #EEF0EC; }
.rg-angles-ligne span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rg-angles-ligne.rg-angles-entete { color: #4A514D; font-weight: 600; border-bottom: 1px solid #DCDFDA; padding: 0 0 6px; }
.rg-angles-ligne span:nth-child(n+3) { text-align: right; }
.rg-angles-vide { font-size: 13px; color: #4A514D; padding: 4px 0; }
.rg-methodo { --methodo-texte: 14px; --methodo-interligne: 21px; --methodo-espace: 16px; display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); align-items: stretch; gap: var(--methodo-espace); }
.rg-methodo-carte { background: #FFFFFF; border: 1px solid #DCDFDA; border-radius: 10px; padding: 18px var(--methodo-espace); display: flex; flex-direction: column; gap: 6px; }
.rg-methodo-carte.rg-beige { background: #FBF3EC; border-color: #FBF3EC; }
.rg-methodo-surtitre { font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: #4A514D; font-weight: 600; }
.rg-beige .rg-methodo-surtitre { color: #7A3410; font-weight: 700; }
.stMarkdown .rg-methodo-carte h2 { margin: 0; padding: 0; font-size: 17px; line-height: 1.3; font-weight: 700; color: #1B1F1D; }
.rg-methodo-carte p, .rg-methodo-carte li { margin: 0; font-size: var(--methodo-texte); line-height: var(--methodo-interligne); color: #2F3532; }
.rg-methodo-carte ul { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 4px; }
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
        '<section class="rg-carte rg-etire">'
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


def _lien_externe(libelle: str, url: str) -> str:
    return f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{_e(libelle)}</a>'


def html_pied(texte: str, lien: tuple[str, str] | None = None) -> str:
    """Pied commun sur deux lignes : sources, puis avertissement, auteur et lien du dépôt ; `lien` = (texte du
    lien, URL) s'ajoute en fin de deuxième ligne, seulement pour la Méthodologie."""
    ligne_2 = [_e(textes.PIED_AVERTISSEMENT), _e(textes.PIED_AUTEUR), _lien_externe(textes.LIEN_DEPOT, textes.URL_DEPOT)]
    if lien:
        ligne_2.append(_lien_externe(*lien))
    return f'<div class="rg-pied">{_e(texte)}<br>{" · ".join(ligne_2)}</div>'


def html_grille_methodologie(cartes: list[dict]) -> str:
    """Grille 3 × 2 des cartes de Méthodologie (textes échappés). Carte : surtitre, titre, paragraphes ou items, beige."""
    blocs = []
    for carte in cartes:
        titre = f"<h2>{_e(carte['titre'])}</h2>" if carte.get("titre") else ""
        corps = "".join(f"<p>{_e(p)}</p>" for p in carte.get("paragraphes", []))
        if carte.get("items"):
            corps += "<ul>" + "".join(f"<li>{_e(i)}</li>" for i in carte["items"]) + "</ul>"
        classe = "rg-methodo-carte rg-beige" if carte.get("beige") else "rg-methodo-carte"
        blocs.append(f'<section class="{classe}"><div class="rg-methodo-surtitre">{_e(carte["surtitre"])}</div>{titre}{corps}</section>')
    return f'<div class="rg-methodo">{"".join(blocs)}</div>'

def html_pastille(couleur: str, opacite: float = 1.0) -> str:
    return f'<span class="rg-sw" style="background:{couleur};opacity:{opacite}"></span>'


def html_tuile(libelle: str, valeur: str, complement: str = "", couleur: str | None = None,
               opacite: float = 1.0) -> str:
    """Tuile du bandeau de l'onglet Carte (texte échappé ; `couleur` vient de textes.py)."""
    pastille = html_pastille(couleur, opacite) if couleur else ""
    suite = f' <span class="rg-tuile-complement">{_e(complement)}</span>' if complement else ""
    return (
        '<div class="rg-tuile">'
        f'<div class="rg-tuile-libelle">{pastille}{_e(libelle)}</div>'
        f'<div class="rg-tuile-valeur">{_e(valeur)}{suite}</div></div>'
    )


def html_legende(elements: list[tuple[str, str, float, bool]], prefixe: str = "") -> str:
    """Légende sous la carte : (couleur, libellé, opacité, avec anneau de sélection) ; « · » entre les groupes.

    `prefixe` dit ce que mesurent les couleurs (texte placé avant le premier élément).
    """
    morceaux = [f"<span>{_e(prefixe)}</span>"] if prefixe else []
    for couleur, libelle, opacite, anneau in elements:
        if not couleur:
            morceaux.append('<span style="color:#4A514D">·</span>')
            continue
        style = f"background:{couleur};opacity:{opacite}" + (";box-shadow:0 0 0 2px #FFFFFF,0 0 0 4px #1B1F1D" if anneau else "")
        classe = "rg-sw rg-sw-anneau" if anneau else "rg-sw"
        morceaux.append(f'<span><span class="{classe}" style="{style}"></span>{_e(libelle)}</span>')
    return f'<div class="rg-legende">{"".join(morceaux)}</div>'


def html_phrase_carte(texte: str) -> str:
    return f'<p class="rg-phrase-carte">{_e(texte)}</p>'


def html_note_carte(texte: str) -> str:
    return f'<p class="rg-note-carte">{_e(texte)}</p>'


# Icône de clic (flèche de pointage et trois traits de clic), 32 px, tracée en SVG : l'icône Material
# de Streamlit impose sa couleur et sa taille et ne se laisse pas styler
SVG_CLIC = (
    '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#C2410C" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M9 9l10 4-4.2 1.6L13 19z" fill="#C2410C"/>'
    '<path d="M7.2 3.8l1 2.4M3.8 7.2l2.4 1M4.2 3.2l2.2 2.2"/></svg>'
)


def html_fiche_vide(titre: str, texte: str) -> str:
    """Fiche sans commune : icône de clic dans un rond beige, titre en gras, invite."""
    return (
        '<div class="rg-invite">'
        f'<div class="rg-invite-rond">{SVG_CLIC}</div>'
        f'<p class="rg-invite-titre">{_e(titre)}</p>'
        f'<p class="rg-invite-texte">{_e(texte)}</p>'
        '</div>'
    )


def html_sous_carte(note: str, legende: str, phrase: str) -> str:
    """Légende sur une ligne, puis note de position et fond de carte, puis phrase des tests multiples,
    séparées de 6 px (HTML déjà échappé par leurs fabriques)."""
    return f'<div class="rg-sous-carte">{legende}{note}{phrase}</div>'


def html_fiche(departement: str, nom: str, libelle: str, chiffre: str, couleur_chiffre: str, ic: str,
               statut: str, cases: list[tuple[str, str]], note: str, titre_note: str, estimable: bool) -> str:
    """Fiche d'une commune (colonne de droite). Estimable : note beige ; sinon encadré gris sans titre."""
    cases_html = "".join(
        f'<div class="rg-case"><div class="rg-case-libelle">{_e(l)}</div><div class="rg-case-valeur">{_e(v)}</div></div>'
        for l, v in cases
    )
    if estimable:
        encadre = (
            '<div class="rg-encadre rg-beige rg-note">'
            f'<div class="rg-note-titre">{_e(titre_note)}</div><p>{_e(note)}</p></div>'
        )
    else:
        encadre = f'<div class="rg-encadre rg-gris rg-note"><p>{_e(note)}</p></div>'
    ic_html = f'<span class="rg-fiche-ic">{_e(ic)}</span>' if ic else ""
    return (
        '<aside class="rg-fiche">'
        f'<div><div class="rg-fiche-dep">{_e(departement)}</div><div class="rg-fiche-nom">{_e(nom)}</div></div>'
        f'<div class="rg-fiche-libelle">{_e(libelle)}</div>'
        f'<div class="rg-fiche-ecart"><span class="rg-fiche-chiffre" style="color:{couleur_chiffre}">{_e(chiffre)}</span>{ic_html}</div>'
        f'<span class="rg-pastille">{_e(statut)}</span>'
        f'<div class="rg-cases">{cases_html}</div>{encadre}</aside>'
    )


# Couleurs des quatre cases de l'onglet Sinistralité × écart : (fond, bordure, titre, nombre, phrase)
COULEURS_QUADRANTS = {
    "Cohérent": ("#FFFFFF", "1px solid #DCDFDA", "#4A514D", "#1B1F1D", "#4A514D"),
    "Angle mort": ("#FBE3D3", None, "#8A2E0B", "#8A2E0B", "#7A3410"),
    "Décote à expliquer": ("#F7F2EA", None, "#6B5A40", "#6B5A40", "#6B5A40"),
    "Risque intégré": ("#EEF3F0", None, "#2E5A48", "#2E5A48", "#2E5A48"),
}


def html_case_quadrant(nom: str, libelle: str, nombre: str, phrase: str, ligne: int, colonne: int) -> str:
    """Une case du tableau 2 × 2 (placée dans la grille par ligne et colonne, la 1re étant l'en-tête).

    `nom` est la valeur du quadrant dans les fichiers (clé des couleurs), `libelle` le texte affiché."""
    fond, bordure, c_nom, c_nombre, c_phrase = COULEURS_QUADRANTS[nom]
    mis_en_avant = nom == "Angle mort"
    style = f"background:{fond};grid-row:{ligne + 2};grid-column:{colonne + 2};"
    if bordure:
        style += f"border:{bordure};"
    classe = "rg-quad-case rg-mis-en-avant" if mis_en_avant else "rg-quad-case"
    return (
        f'<div class="{classe}" style="{style}">'
        f'<span class="rg-quad-nom" style="color:{c_nom}">{_e(libelle)}</span>'
        f'<span class="rg-quad-nombre" style="color:{c_nombre}">{_e(nombre)}</span>'
        f'<span class="rg-quad-phrase" style="color:{c_phrase}">{_e(phrase)}</span></div>'
    )


def html_carte_sinistralite(titre: str, explication: str, colonnes: tuple, lignes: tuple, cases: list[str],
                            nombre_indeterminees: str, suite_indeterminees: str, note: str = "") -> str:
    """Carte blanche de gauche : tableau à quatre cases, `note` sous le tableau, puis encadré gris (`cases` vient de html_case_quadrant)."""
    en_tetes = "".join(f'<div class="rg-quad-colonne">{_e(a)}<br>{_e(b)}</div>' for a, b in colonnes)
    etiquettes = "".join(
        f'<div class="rg-quad-ligne" style="grid-row:{i + 2};grid-column:1">{_e(libelle)}</div>'
        for i, libelle in enumerate(lignes)
    )
    return (
        '<section class="rg-carte-s rg-etire">'
        f'<h2 class="rg-titre-s">{_e(titre)}</h2><p class="rg-explication">{_e(explication)}</p>'
        f'<div class="rg-quad"><div></div>{en_tetes}{etiquettes}{"".join(cases)}</div>'
        + (f'<p class="rg-note-s">{_e(note)}</p>' if note else "")
        + f'<div class="rg-indeterminees"><strong>{_e(nombre_indeterminees)}</strong>{_e(suite_indeterminees)}</div>'
        '</section>'
    )


def html_signal_sombre(nombre: str, titre: str, texte: str) -> str:
    return (
        '<section class="rg-sombre">'
        f'<span class="rg-sombre-nombre">{_e(nombre)}</span>'
        f'<div><span class="rg-sombre-titre">{_e(titre)}</span><span class="rg-sombre-texte">{_e(texte)}</span></div>'
        '</section>'
    )


def html_tableau_angles(titre: str, en_tetes: tuple, lignes: list[tuple], vide: str) -> str:
    """Tableau des communes en angle mort : en-tête fixe, corps qui défile seul s'il est trop long."""
    def rangee(valeurs, classe=""):
        return f'<div class="rg-angles-ligne {classe}">' + "".join(f"<span>{_e(v)}</span>" for v in valeurs) + "</div>"

    corps = "".join(rangee(v) for v in lignes) or f'<div class="rg-angles-vide">{_e(vide)}</div>'
    return (
        '<section class="rg-angles rg-etire">'
        f'<div class="rg-angles-titre">{_e(titre)}</div>{rangee(en_tetes, "rg-angles-entete")}'
        f'<div class="rg-angles-corps">{corps}</div></section>'
    )


@contextmanager
def onglet(cle: str, resume: dict, lien: tuple[str, str, str] | None = None):
    """Mise en page commune d'un onglet : hauteur naturelle du contenu (aucune hauteur liée à la fenêtre), puis
    pied commun (24 px au-dessus, 20 px en dessous). Les règles sont dans CSS (clés `page_*` et `zone_*`)."""
    with st.container(key=f"page_{cle}"):
        with st.container(key=f"zone_{cle}"):
            yield
        st.markdown(html_pied(textes.pied_commun(resume), lien), unsafe_allow_html=True)


def entete(surtitre: str, titre: str) -> None:
    st.markdown(html_entete(surtitre, titre), unsafe_allow_html=True)


def encadre_beige(texte: str) -> None:
    st.markdown(html_encadre("beige", texte), unsafe_allow_html=True)


def encadre_gris(texte: str) -> None:
    st.markdown(html_encadre("gris", texte), unsafe_allow_html=True)
