"""Page d'accueil : bandeau des résultats globaux, carte des communes et fiche commune."""

import pandas as pd
import pydeck as pdk
import streamlit as st

import cartographie
import donnees
import textes


@st.cache_data(show_spinner=False)
def entites_carte(dossier: str) -> list[dict]:
    return cartographie.preparer_carte(donnees.charger_communes(dossier), donnees.charger_contours(dossier))


def bandeau(resume: dict) -> None:
    contraste = resume["modeles_globaux"]["principal"]["contraste_fort_moins_moyen"]
    bas, haut = contraste["ic95_effet"]
    st.subheader(textes.TITRE_BANDEAU)
    st.metric("Maisons en zone forte contre maisons en zone moyenne", textes.chiffre_phare(contraste))
    st.caption(f"Intervalle de confiance à 95 % : {textes.intervalle_pct(bas, haut, 2)}")
    st.markdown(f"**{textes.phrase_chiffre_phare(contraste, resume['seuil_pas_de_decote'])}**")
    with st.expander("Détails"):
        for ligne in textes.lignes_details(resume):
            st.markdown(f"- {ligne}")
        st.warning(textes.AVERTISSEMENT_REFERENCE)
        st.markdown(textes.phrase_indeterminees(resume))
        st.markdown(textes.PHRASE_CARTE_2026)


def legende() -> None:
    st.sidebar.markdown(f"**{textes.LEGENDE_TITRE}**")
    case = '<span style="display:inline-block;width:14px;height:14px;background:{};border:1px solid #888;margin-right:6px"></span>{}'
    lignes = [case.format(cartographie.hex_classe(classe), libelle) for classe, libelle in textes.legende()]
    lignes.append(case.format(cartographie.hex_classe(None), textes.LEGENDE_NON_ESTIMABLE))
    st.sidebar.markdown("<br/>".join(lignes), unsafe_allow_html=True)
    st.sidebar.caption(textes.LEGENDE_PALE)
    st.sidebar.caption(textes.LEGENDE_FILTRE)


def carte(entites: list[dict], departements: dict, fond: bool) -> object:
    options_communes, options_limites = cartographie.options_couches()
    communes = pdk.Layer(
        "GeoJsonLayer", id="communes", data={"type": "FeatureCollection", "features": entites},
        pickable=True, auto_highlight=True, stroked=True, filled=True, **options_communes,
    )
    limites = pdk.Layer(
        "GeoJsonLayer", id="departements", data=departements, pickable=False, stroked=True, filled=False,
        **options_limites,
    )
    deck = pdk.Deck(
        layers=[communes, limites],
        initial_view_state=pdk.ViewState(**cartographie.vue_initiale(entites)),
        map_style="light" if fond else None,
        tooltip={"html": "{info}", "style": {"fontSize": "13px"}},
    )
    return st.pydeck_chart(deck, on_select="rerun", selection_mode="single-object", key="carte", height=560)


def fiche(ligne: pd.Series, resume: dict, notes: dict) -> None:
    st.subheader(f"{ligne['nom']} ({ligne['departement']})")
    estimable = ligne["statut"] == "estimable"
    colonnes = st.columns(4)
    if estimable:
        colonnes[0].metric("Écart de prix observé", textes.pct(ligne["prime"], 1, True))
        colonnes[0].caption(f"IC à 95 % : {textes.intervalle_pct(ligne['ic_bas'], ligne['ic_haut'])}")
        colonnes[1].metric("Statut", textes.STATUTS_DECOTE[ligne["statut_decote"]])
    else:
        colonnes[0].metric("Écart de prix observé", "non estimable")
        colonnes[1].metric("Statut", "non estimable")
    colonnes[1].caption(ligne["quadrant"] if isinstance(ligne["quadrant"], str) else "pas de quadrant")
    colonnes[2].metric("Ventes retenues", textes.entier(ligne["n_ventes"]))
    colonnes[2].caption(f"dont {textes.entier(ligne['n_fort'])} en zone forte")
    prix = ligne["prix_m2_median"]
    colonnes[3].metric("Prix médian au m²", "—" if pd.isna(prix) else f"{textes.entier(prix)} €")
    colonnes[3].caption(f"{textes.pluriel(int(ligne['catnat_depuis_2015']), 'arrêté')} sécheresse 2015-2023")
    note = notes.get(ligne["code_insee"])
    st.info(note if note else textes.texte_commune(ligne, resume))


def afficher() -> None:
    try:
        dossier = str(donnees.dossier())
        tout = donnees.charger_tout()
        entites = entites_carte(dossier)
    except donnees.ErreurDonneesApp as erreur:
        st.error(str(erreur))
        st.stop()

    communes, resume = tout.communes, tout.resume
    st.title("Retrait-gonflement des argiles et prix des maisons")
    bandeau(resume)

    st.sidebar.header("Filtres")
    options = sorted(communes["departement"].unique())
    choisis = st.sidebar.multiselect(textes.LIBELLE_DEPARTEMENTS, options, default=options)
    significatives = st.sidebar.checkbox(textes.LIBELLE_SIGNIFICATIVES)
    fond = st.sidebar.checkbox(textes.LIBELLE_FOND, value=True)
    legende()

    visibles = cartographie.filtrer(entites, choisis, significatives)
    evenement = carte(visibles, cartographie.limites_exterieures(tout.departements), fond)
    if fond:
        st.caption(textes.FOND_DE_CARTE)
    st.markdown(textes.phrase_estimables(resume["n_communes_estimables"], len(communes)))
    st.markdown(textes.phrase_indeterminees(resume))

    # Un clic sur la carte remplace la sélection de la liste (une seule fois par clic)
    clic = cartographie.code_selectionne(evenement)
    if clic and clic != st.session_state.get("dernier_clic"):
        st.session_state["dernier_clic"] = clic
        st.session_state["commune"] = clic

    lignes = communes.set_index("code_insee", drop=False)
    codes = list(communes.sort_values("nom")["code_insee"])
    choix = st.selectbox(
        "Commune", codes, index=None, key="commune", placeholder="Rechercher une commune",
        format_func=lambda c: f"{lignes.loc[c, 'nom']} ({lignes.loc[c, 'departement']})",
    )
    if choix:
        fiche(lignes.loc[choix], resume, tout.notes)
    else:
        st.caption(textes.INVITE_COMMUNE)


afficher()
