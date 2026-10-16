# Application

Application Streamlit en français, déployée en ligne. Elle ne lit que
`data/processed/` : aucun appel réseau côté serveur, aucun agent, aucune extension
DuckDB, aucun calcul statistique. Tout est calculé par le pipeline (voir
`docs/method.md`) ; l'app filtre, affiche et rédige le texte automatique.

## Vocabulaire imposé (décision du 16/10)

- Les primes communales (colonne `prime`) sont des **« écarts de prix observés entre
  zone forte et reste de la commune »**. Jamais un « effet de l'argile », ni une « prime
  de risque » : la colonne garde son nom de fichier, pas ses libellés à l'écran (info-bulle,
  fiche, texte automatique, axes, tableau, simulateur, légende).
- L'expression **« prime de risque implicite »** est réservée au résultat global
  (bandeau, page Méthodologie, README) : le contraste « fort − moyen » et les modèles
  globaux.
- Les écarts communaux ne sont ni causaux ni une estimation de la valeur d'une maison.

## 1. Fichiers de `data/processed/`

Uniquement des agrégats par commune ; aucune vente individuelle.

| Fichier | Contenu | Obligatoire |
|---|---|---|
| `communes.parquet` | une ligne par commune du périmètre (environ 1 600) | oui |
| `contours.geojson` | contours simplifiés des communes, propriété `code_insee` seule | oui |
| `departements.geojson` | limites des 4 départements (union des contours des communes) | oui |
| `resume_global.json` | résultats du modèle global, nettoyage, tests multiples, seuils, sources | oui |
| `notes_communes.parquet` | notes des agents (30 communes au maximum) | non (bonus) |

### `communes.parquet`

| Colonne | Type | Description |
|---|---|---|
| `code_insee` | texte | code commune (même millésime COG que DVF et les contours) |
| `nom`, `departement` | texte | |
| `n_ventes` | entier | ventes retenues après nettoyage, 2021-2025 |
| `n_fort`, `n_moyen`, `n_faible`, `n_hors_zone` | entier | ventes par classe d'exposition 2020 |
| `prix_m2_median` | réel ou vide | vide si moins de 5 ventes (seuil dans la config) |
| `statut` | texte | `estimable` ou `non_estimable` |
| `motif` | texte ou vide | `une_seule_zone`, `effectifs_insuffisants` (vide si estimable) |
| `prime`, `ic_bas`, `ic_haut` | réel ou vide | prime « fort » contre tout le reste (faible, moyen, hors zone), exp(β) − 1 en fraction (−0,05 = −5 %) ; négatif = décote |
| `significatif` | texte ou vide | `decote` (IC < 0), `prime` (IC > 0), `non` (IC contient 0) ; sert aux tests multiples et à l'opacité de la carte |
| `statut_decote` | texte ou vide | `decote`, `pas_de_decote`, `indetermine` (définitions dans `docs/method.md`, section 6) |
| `catnat_total`, `catnat_depuis_2015` | entier | arrêtés CatNat sécheresse |
| `catnat_dernier` | date ou vide | date du dernier arrêté |
| `sinistralite_sup_mediane` | booléen ou vide | `catnat_depuis_2015` strictement supérieur à la médiane (communes estimables) |
| `quadrant` | texte ou vide | vide si non estimable ou `indetermine` (section 3) |

L'étape B (primes) écrit d'abord `primes_communes.parquet` : les colonnes ci-dessus qui en
dépendent (effectifs, prix médian, statut, motif, prime, IC, `significatif`,
`statut_decote`), pour les communes qui ont des ventes, plus `erreurs` (`sections` ou
`hc1`) et `n_sections`. Une étape suivante le fusionne avec les noms, les communes sans
vente, CatNat et les quadrants pour produire `communes.parquet` ; `primes_communes.parquet`
est alors retiré de `data/processed/`.

### `contours.geojson`

- Source : API Géo (ADMIN EXPRESS), un fichier par département, fusionnés par le pipeline.
- Simplification avec DuckDB `spatial` en Lambert-93 : `ST_SimplifyPreserveTopology`
  avec une tolérance de 50 m (dans la config), puis reprojection en WGS84 et
  coordonnées arrondies à 5 décimales (environ 1 m).
- Objectif : moins de 3 Mo. La simplification commune par commune peut laisser de
  petits interstices entre communes voisines, visibles seulement en zoom fort :
  accepté pour une carte de synthèse.
- Le pipeline vérifie que chaque `code_insee` de `communes.parquet` a un contour, et
  inversement.
- `departements.geojson` : union des contours des communes de chaque département
  (`ST_Union_Agg`), simplifiée avec la même tolérance.

### `resume_global.json`

Contenu défini dans `docs/method.md` (section 8), plus :
- `mediane_sinistralite` et `seuil_pas_de_decote` : seuils de la vue 2 (section 3) ;
- `n_decote`, `n_pas_de_decote`, `n_indetermine` et effectifs par quadrant ;
- `seuil_prix_median` : effectif minimal pour publier un prix médian ;
- `sources` : pour chaque source, URL, date de téléchargement et millésime ;
- `date_generation` : date de production des fichiers.

### `notes_communes.parquet` (bonus)

`code_insee`, `note`, `revisee` (booléen : le Critique a demandé une révision),
`date`. Si le fichier est absent ou qu'une commune n'y figure pas, l'app affiche le
texte automatique.

## 2. Vue 1 : carte

- Carte pydeck (`GeoJsonLayer`) des communes, centrée sur le périmètre, avec une
  seconde couche pour les limites des départements (trait sombre, sans remplissage).
- **Fond de carte** (décision du 15/10) : tuiles Carto, chargées par le navigateur du
  visiteur et non par le serveur. Mention de la source sous la carte :
  « Fond de carte © CARTO, données © contributeurs OpenStreetMap ».
- **Lisible sans fond** : communes colorées et limites des départements suffisent à
  lire la carte si les tuiles ne se chargent pas. Vérifié pendant le développement en
  affichant la carte sans fond (`map_style=None`).
- **Couleur** (décision du 14/10) : orange pour une décote, bleu pour une prime, gris
  si non estimable. Cinq classes fixes de `prime` : décote < −10 %, −10 à −3 %,
  −3 à +3 %, +3 à +10 %, > +10 % (bornes dans la config). La classe centrale est
  très claire.
- **Significativité** : une commune dont l'IC contient 0 est affichée avec une opacité
  réduite ; le texte de la légende le dit.
- **Légende** dans la barre latérale (pydeck n'en fournit pas).
- **Filtres** : départements ; « communes significatives seulement ». Pas de couche
  « bascule 2020 → 2026 » (décision du 16/10, voir la phrase du bandeau).
- **Info-bulle** : nom, prime et IC (ou motif si non estimable), ventes « fort » et
  de référence (tout le reste), arrêtés CatNat.
- **Fiche commune** sous la carte : choix par liste déroulante (avec recherche),
  et par clic sur la carte si la version de Streamlit le permet. Elle affiche les
  chiffres de la ligne, puis la note de l'agent ou le texte automatique.
- **Bandeau des résultats globaux** au-dessus de la carte : chiffre phare = contraste
  « fort − moyen » avec IC, puis décote globale « moyen » et « fort » avec IC ; communes estimables ; significatives observées contre attendues
  par hasard. Phrase fixe : « Dans ces quatre départements déjà très exposés, la carte
  2026 change le niveau d'environ 1 % des ventes, dans les deux sens. »

### Texte automatique

Gabarit déterministe, une phrase par élément, à partir de la ligne de la commune :
statut et motif, écart de prix observé et IC, effectifs des deux zones, statut de décote, arrêtés
CatNat (« sinistralité supérieure à la médiane du périmètre », jamais « risque
élevé »), quadrant. Il se termine toujours par un rappel : un écart moyen observé
n'est ni une estimation de la valeur d'une maison, ni une preuve de causalité.

## 3. Vue 2 : sinistralité × décote

- Nuage de points (Altair, fourni avec Streamlit), communes estimables uniquement :
  en abscisse, `catnat_depuis_2015` ; en ordonnée, l'écart de prix observé (`prime`) avec
  son IC en barre d'erreur. Une ligne à 0, une ligne pointillée au seuil `seuil_pas_de_decote`
  (−3 %) et une ligne verticale à la médiane de sinistralité.
- **Statut de décote** (décision du 15/10), calculé par le pipeline : « décote »,
  « pas de décote », « indéterminé » (définitions dans `docs/method.md`, section 6).
  Points pleins pour « décote » et « pas de décote », **points creux** pour
  « indéterminé ».
- **Quadrants** (décision du 14/10), calculés par le pipeline, communes « décote » et
  « pas de décote » seulement :

| | Décote | Pas de décote |
|---|---|---|
| **Sinistralité supérieure à la médiane du périmètre** | Risque intégré | Angle mort |
| **Sinistralité inférieure ou égale à la médiane du périmètre** | Décote à expliquer | Cohérent |

- **Médiane** de `catnat_depuis_2015` parmi les communes estimables, calculée par le
  pipeline et lue dans `resume_global.json`. Libellé imposé : « sinistralité
  supérieure à la médiane du périmètre », jamais « risque élevé ».
- Le statut repose sur l'IC, pas sur l'estimation ponctuelle, pour ne pas classer du
  bruit : une commune peu informative reste « indéterminée ».
- Au-dessus du graphique, rappel des tests multiples : nombre de communes
  significatives observé contre nombre attendu par hasard.
- Sous le graphique : effectif par quadrant **et nombre de communes indéterminées**,
  puis tableau filtrable des communes (nom, prime, IC, arrêtés, statut de décote,
  quadrant), téléchargeable en CSV.

## 4. Vue 3 : simulateur (bonus)

- Liste limitée aux communes estimables (la prime par commune a pour référence
  « tout le reste » : faible, moyen, hors zone).
- Saisie d'un prix de maison ; affichage de l'écart moyen observé en euros et de son
  IC : prix × prime, prix × ic_bas, prix × ic_haut.
- Formulation imposée : « écart moyen observé entre zones dans cette commune », jamais
  « valeur de votre maison ».

## 5. Page Méthodologie et limites

- Résumé lisible de `docs/method.md` : sources, période, nettoyage (avec le nombre de
  ventes à chaque étape lu dans `resume_global.json`), exposition, modèle, prime par
  commune.
- Tableau des définitions, identique au README.
- Phrase sur la carte 2026 : « Dans ces quatre départements déjà très exposés, la carte
  2026 change le niveau d'environ 1 % des ventes, dans les deux sens. » (la même que
  dans le bandeau des résultats globaux).
- Résultats complémentaires : test placebo (bascule), « indicatif, faible puissance
  (861 ventes, 8 communes) », et variante « réforme 2025 », présentée comme un indice.
- Limites : reprises de la section 9 de `docs/method.md`.
- Sources avec dates de téléchargement et millésimes.

## 6. Organisation du code

```
app/
  streamlit_app.py   navigation (st.navigation) et configuration de la page
  donnees.py         lecture de data/processed/ (st.cache_data), contrôle des colonnes
  textes.py          définitions, libellés, légende, texte automatique
  vues/
    carte.py
    sinistralite.py
    simulateur.py
    methodologie.py
```

- Les définitions et libellés sont écrits une seule fois, dans `textes.py`.
- Nombres au format français (virgule décimale, espace pour les milliers, « % »).
- Si un fichier obligatoire manque ou qu'une colonne attendue est absente, l'app
  affiche un message clair au lieu d'une erreur Python.

## 7. Tests

- `donnees.py` : lecture de petits fichiers de test dans `tests/fixtures/processed/`,
  détection d'une colonne manquante.
- `textes.py` : texte automatique pour une commune estimable, une non estimable, une
  sans arrêté CatNat ; formatage des nombres.
- Pipeline : contrôle que `data/processed/` ne contient que des agrégats (aucune
  colonne de vente individuelle, prix médian vide sous le seuil).
- Pipeline : statut de décote aux bornes (IC haut juste sous 0, IC bas égal au seuil
  de −3 %), sinistralité égale à la médiane (classée « inférieure ou égale »),
  aucune commune indéterminée dans un quadrant.

## 8. Déploiement

- Streamlit Community Cloud, depuis le dépôt GitHub ; dépendances principales
  seulement (streamlit, pydeck, pandas, pyarrow). La prise en charge de `uv.lock`
  par la plateforme est à vérifier au moment du déploiement (sinon,
  `requirements.txt` généré par `uv export`).
- Fond de carte : tuiles Carto chargées par le navigateur (section 2) ; le serveur de
  l'app ne fait aucun appel réseau.
