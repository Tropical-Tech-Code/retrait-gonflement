# Application

Application Streamlit en français, déployée en ligne. Elle ne lit que
`data/processed/` : aucun appel réseau côté serveur, aucun agent, aucune extension
DuckDB, aucun calcul statistique. Tout est calculé par le pipeline (voir
`docs/method.md`) ; l'app filtre, affiche et rédige le texte automatique.

## Vocabulaire imposé (décision du 16/10)

- Les primes communales (colonne `prime`) sont des **« écarts de prix observés entre
  zone forte et reste de la commune »**. Jamais un « effet de l'argile », ni une « prime
  de risque » : la colonne garde son nom de fichier, pas ses libellés à l'écran (info-bulle,
  fiche, texte automatique, axes, tableau, légende).
- L'expression **« prime de risque implicite »** est réservée au résultat global
  (onglet Résultat, onglet Méthodologie et limites, README) : le contraste « fort − moyen »
  et les modèles globaux.
- Les écarts communaux ne sont ni causaux ni une estimation de la valeur d'une maison.

## Cahier des charges et parcours (19/10/2026)

Les quatre écrans de la maquette v2 sont dans `docs/maquette/` (source HTML à 1 280 × 800, chiffres d'exemple) : ils illustrent cette section, qui fait foi en cas de conflit.

Cette section fait foi. La maquette v2 (quatre écrans, Projet claude.ai, 19/10/2026) l'illustre ; les maquettes précédentes sont historiques.

### Objectif
Question réellement testée : le marché fait-il une différence de prix entre zone d'exposition forte et zone moyenne ? Résultat : pas de différence détectable ; si une décote existe, elle ne dépasse probablement pas environ 3 % ; ne pas détecter de décote ne prouve pas qu'il n'y en a pas. Les deux zones exposées se vendent environ 3 % moins cher que les maisons hors zone argileuse (p ≈ 0,06 ; groupe de référence petit et particulier) : l'étude ne dit pas si le marché fait payer le risque argileux.

### Public
Recruteur ou analyste en données alternatives, arrivé depuis le README, sur ordinateur, pour 2 à 3 minutes. La page Résultat doit se comprendre seule. Le particulier qui cherche sa commune n'est pas un public visé : l'app ne donne ni prix en euros ni estimation de valeur, et ses textes rappellent que les écarts communaux ne sont ni une valeur de maison ni un effet causal. Langue : français.

### Contraintes générales
- Navigation par onglets : Résultat (accueil), Sinistralité × écart, Carte, Méthodologie et limites.
- Chaque onglet tient sans défilement dans un écran de 1 280 × 800.
- Pas de barre latérale : les réglages de la carte sont au-dessus d'elle.
- En-tête commun : sur-titre « Retrait-gonflement des argiles × ventes DVF », titre « Le marché distingue-t-il les zones d'argile forte et moyenne ? ».
- Aucun chiffre ni aucune date en dur : tout est lu dans data/processed/ (les chiffres de ce document sont des exemples).
- Notation unique des intervalles : « [−2,9 % ; +4,9 %] », jamais « +0,0 % ».
- Aucun euro, aucun prix au m², aucune estimation de valeur.

### Onglet 1 : Résultat
- Phrase-réponse : « Pas de différence de prix détectable entre zone d'argile forte et zone moyenne. »
- Chiffre phare : contraste fort − moyen et son IC 95 %, avec les effectifs (ventes, départements, années).
- Barre de fourchette : l'IC sur un axe, avec 0 et le seuil « pas de décote » (−3 %, lu dans le JSON).
- Lecture : « Si une décote existe, elle ne dépasse probablement pas environ X %. Ne pas détecter de décote ne prouve pas qu'il n'y en a pas. » (X : règle du bandeau décidée le 17/10).
- Encadré gris « Ce qui a vraiment été testé » : écart des deux zones exposées par rapport aux maisons hors zone, sa fragilité (p), et la conclusion « l'étude ne dit pas si le marché fait payer le risque argileux ; elle dit qu'il ne distingue pas nettement exposition moyenne et forte ».
- Encadré sombre « Signal faible » : nombre de communes en angle mort, formulé comme une hypothèse à surveiller, lien vers l'onglet 2.
- Pied : sources, « Calculs faits hors ligne », « Corrélation, pas causalité ».
- Hors de cet onglet : variante réforme 2025, placebo et phrase « environ 1 % des ventes » (Méthodologie), tests multiples (Carte).

### Onglet 2 : Sinistralité × écart
- Tableau à quatre cases : colonnes « sinistralité ≤ médiane (0 à 2 arrêtés) » et « > médiane (3 arrêtés ou plus) » ; lignes « pas de décote » et « décote ». Cases : Cohérent, Angle mort (mis en avant), Décote à expliquer, Risque intégré, chacune avec son effectif et une phrase.
- Sous le tableau : nombre de communes indéterminées, non classées.
- À droite : encadré sombre (nombre d'angles morts, hypothèse sans prédiction) et tableau des communes en angle mort (commune, département, arrêtés, écart [IC 95 %], ventes en zone forte), trié par arrêtés décroissants.
- Le nuage de points est abandonné : les cases sont définies par le statut, pas par la valeur de l'écart.

### Onglet 3 : Carte
- Tuiles : communes estimables (sur le total), décote, pas de décote, indéterminées.
- Carte en carrés (décision du 20/10) : un carré par commune, sur une grille régulière par zone, placé par le pipeline (`carres.geojson`). Une rangée de cases vides sépare deux départements, avec le nom du département en capitales grises (police sans-serif de l'app, fond blanc semi-transparent), placé à côté de ses carrés et jamais dessus (position et cadrage lus dans `resume_global.json`, clé `carres`). Fond de carte Carto clair (décision du 21/10, qui revient sur celle du 20/10 : il aide à se situer), chargé par le navigateur du visiteur, avec la mention « Fond de carte © CARTO · © OpenStreetMap » et la note « Position des carrés approximative (quelques km). » sous la carte ; pas de trait de limite. Fiche sans commune : icône et invitation centrées, bloc réduit à son contenu. Champ de recherche : contour #C2410C permanent (liste décrite plus bas).
- Deux zones au choix (`st.segmented_control`) : Sud-Ouest · 31, 47, 82 et Seine-et-Marne · 77. Chaque zone a son cadrage (carrés et étiquettes) et un `min_zoom` égal au zoom initial, transmis mais non imposé par Streamlit : la molette et le pavé tactile sont donc désactivés (`scrollZoom` à faux), les boutons + et − de la carte restent (décision du 21/10) ; ces boutons peuvent encore dézoomer au-delà de la zone. Le déplacement à la souris n'est pas borné. Pas de bouton « recentrer » : rechoisir la zone recentre la carte.
- Couleurs (palette de la maquette, seule palette de l'app, dans `textes.py`) : 5 classes (bornes −10 / −3 / +3 / +10 %, orange = décote, bleu = écart positif) ; couleur franche = décote ou pas de décote ; pâle (38 % d'opacité) = indéterminé ; gris très clair #E4E6E2 = non estimable (pour que les communes classées ressortent) ; commune sélectionnée : sa couleur de classe, contour noir et liseré blanc.
- Info-bulle au survol : nom de la commune et statut, en texte simple (pas de HTML brut).
- Légende sous la carte (classes, pâle : indéterminé, gris clair : non estimable, sélection), puis une seule phrase, chiffres lus dans `resume_global.json` : « Sur {n_estimables} communes, {n} montrent un écart net, contre une dizaine attendue par hasard. Ces écarts vont autant dans un sens que dans l'autre ({n} décotes, {n} primes) : ils reflètent surtout des différences entre quartiers, plutôt qu'un problème de terrains argileux. » (« une dizaine » si l'attendu arrondi vaut 10, sinon en chiffres ; « primes » = écarts positifs, exception à la règle du vocabulaire limitée à cette phrase ; décision du 21/10).
- Liste de recherche : les communes en décote d'abord (« Nom (dép.) · décote », ordre alphabétique), l'option « ── Autres communes ── » (sans effet : la sélection précédente est conservée), puis toutes les autres, « Nom (dép.) », ordre alphabétique.
- Fiche à droite : département, nom, « Écart de prix observé entre zone forte et reste de la commune », chiffre coloré selon sa classe et IC, statut, trois cases (ventes de maisons, dont en zone forte, arrêtés sécheresse 2015-2023), note beige (texte automatique terminé par « ni valeur de la maison, ni causalité »). Non estimable : encadré gris avec le motif, « — » pour l'écart. Pas de prix médian.
- Recherche de commune (selectbox, clé `commune`) : même effet qu'un clic (changement de zone si nécessaire, sélection). Le clic est lu au début de l'exécution suivante, avant la création des widgets.

### Onglet 4 : Méthodologie et limites
- Six cartes courtes, sans défilement : Question testée, Données, Modèle, Robustesse, Écarts par commune, Limites (dont « la carte 2026 change le niveau d'environ 1 % des ventes, dans les deux sens »).
- Renvoi vers docs/method.md sur GitHub pour le détail. Pas de texte long dans l'app ; le test de vocabulaire s'applique aux textes des cartes.

### Charte
- .streamlit/config.toml, [theme] : backgroundColor #F4F5F2, textColor #1B1F1D, primaryColor #C2410C, secondaryBackgroundColor #FFFFFF (aucun rouge Streamlit).
- Encadrés beige (#FBF3EC, note et prudence) et gris (#EEF0EC, neutre) ; jamais st.info (le bleu signifie « écart positif »).
- Chiffres alignés par les chiffres tabulaires (font-variant-numeric: tabular-nums).
- Police : Public Sans servie depuis le dépôt (souhaitable), sinon polices système ; jamais Google Fonts.

### Priorités
- Indispensable : quatre onglets sans défilement à 1 280 × 800 ; en-tête ; onglet Résultat ; tableau à quatre cases ; carte en deux zones avec zoom minimal ; couleur par statut et gris des non estimables ; légende ; fiche sans prix médian ; notation unique des IC ; thème sans rouge ; encadrés sans bleu ; Méthodologie en six cartes ; vocabulaire imposé ; pluriels corrects dans les textes automatiques.
- Souhaitable, dans cet ordre : barre de fourchette ; tuiles par statut ; recherche de commune ; chiffre de la fiche coloré ; Public Sans ; affichage mobile non cassé ; retrait de la colonne de prix médian du pipeline ; résumé en anglais dans le README.
- Abandonné : simulateur ; agents ; euros et prix au m² ; recherche par adresse ; nuage de points ; couches CatNat et bascule ; IBM Plex Mono ; Google Fonts ; onglets dessinés à la main ; texte long de Méthodologie.

### À vérifier avant le code
- resume_global.json contient-il, pour le modèle à trois catégories, les écarts « moyen » et « fort » par rapport à la référence avec IC et p (encadré « Ce qui a vraiment été testé ») ? Sinon, ajout au pipeline.
- Comptes par statut et par case lus dans data/processed/.
- communes.parquet contient-il une colonne de prix médian ?
- Correspondance département → zone : constante dans app/textes.py, avec un test qui la compare à config/perimetre.toml (comme les bornes des classes).
- Le clic sur une commune de la carte fonctionne-t-il dans la version actuelle ?

## 1. Fichiers de `data/processed/`

Uniquement des agrégats par commune ; aucune vente individuelle.

| Fichier | Contenu | Obligatoire |
|---|---|---|
| `communes.parquet` | une ligne par commune du périmètre (environ 1 600) | oui |
| `contours.geojson` | contours simplifiés des communes, propriété `code_insee` seule | oui |
| `carres.geojson` | un carré par commune (grille par zone), propriété `code_insee` seule | oui |
| `departements.geojson` | limites des 4 départements ; produit, mais l'app ne le lit plus (suppression du pipeline : souhaitable) | non |
| `resume_global.json` | résultats du modèle global, nettoyage, tests multiples, seuils, sources | oui |

### `communes.parquet`

| Colonne | Type | Description |
|---|---|---|
| `code_insee` | texte | code commune (même millésime COG que DVF et les contours) |
| `nom`, `departement` | texte | |
| `n_ventes` | entier | ventes retenues après nettoyage, 2021-2025 |
| `n_fort`, `n_moyen`, `n_faible`, `n_hors_zone` | entier | ventes par classe d'exposition 2020 |
| `prix_m2_median` | réel ou vide | vide si moins de 5 ventes (seuil dans la config) ; **non affichée** (décision du 19/10), colonne à retirer du pipeline (souhaitable) |
| `statut` | texte | `estimable` ou `non_estimable` |
| `motif` | texte ou vide | `une_seule_zone`, `effectifs_insuffisants` (vide si estimable) |
| `prime`, `ic_bas`, `ic_haut` | réel ou vide | prime « fort » contre tout le reste (faible, moyen, hors zone), exp(β) − 1 en fraction (−0,05 = −5 %) ; négatif = décote |
| `significatif` | texte ou vide | `decote` (IC < 0), `prime` (IC > 0), `non` (IC contient 0) ; sert aux tests multiples |
| `statut_decote` | texte ou vide | `decote`, `pas_de_decote`, `indetermine` (définitions dans `docs/method.md`, section 6) ; détermine la couleur de la carte (pâle si indéterminé) |
| `catnat_total`, `catnat_depuis_2015` | entier | événements CatNat sécheresse distincts (libellé « Sécheresse » seul), au total et depuis le 1er janvier 2015 ; 0 si aucun. Libellé à l'écran : « arrêtés sécheresse 2015-2023 » (GASPAR ne contient rien après 2023) |
| `catnat_dernier` | date ou vide | date du dernier arrêté |
| `sinistralite_sup_mediane` | booléen ou vide | `catnat_depuis_2015` strictement supérieur à la médiane (communes estimables) |
| `quadrant` | texte ou vide | vide si non estimable ou `indetermine` (section 3) |

L'étape B (primes) écrit d'abord `primes_communes.parquet` : les colonnes ci-dessus qui en
dépendent (effectifs, prix médian, statut, motif, prime, IC, `significatif`,
`statut_decote`), pour les communes qui ont des ventes, plus `erreurs` (`sections` ou
`hc1`) et `n_sections`. L'étape C le fusionne avec les noms, les communes sans vente,
CatNat et les quadrants pour produire `communes.parquet`. Il reste dans `data/processed/`
(décision du 16/10) : c'est l'entrée de l'étape C, il ne contient que des agrégats par
commune, et l'app ne le lit pas.

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

### `carres.geojson`

- Produit par `spatial/carres.py` (section 2) à partir de `contours.geojson` et
  `communes.parquet` ; un carré par commune, 5 décimales, propriété `code_insee` seule.
- Contrôles du pipeline : contours et communes ont les mêmes codes ; chaque département
  a au moins autant de cases que de communes.

### `resume_global.json`

Contenu défini dans `docs/method.md` (section 8), plus :
- `mediane_sinistralite` et `seuil_pas_de_decote` : seuils de l'onglet Sinistralité × écart (section 3) ;
- `n_decote`, `n_pas_de_decote`, `n_indetermine` et effectifs par quadrant ;
- `sources` : pour chaque source, URL, date de téléchargement et millésime ;
- `date_generation` : date de production des fichiers ;
- `carres` : `zones` (maille en km, communes, écarts entre centre de la commune et carré, `emprise` [lon_min, lat_min, lon_max, lat_max] des carrés et des étiquettes, `directions_etiquettes`, par zone) et `etiquettes` (position `lon`, `lat` du centre du nom de chaque département). L'étiquette est placée à l'est, à l'ouest, au sud ou au nord des carrés du département (dans cet ordre), à 1,5 maille du bord : le premier emplacement dont le rectangle de texte estimé ne touche aucun carré ; sinon au centre des carrés.

## 2. Onglet Carte : détails de réalisation

Le contenu et la disposition de l'onglet sont dans le cahier des charges ci-dessus.

- Carte pydeck (`GeoJsonLayer`) des carrés de `carres.geojson`, sur le fond Carto clair
  (`map_style="light"`), sans couche de limites. Les noms des départements viennent de
  `resume_global.json` (clé `carres`), dessinés sur un fond blanc semi-transparent.
- **Placement des carrés** (pipeline `spatial/carres.py`, décision du 20/10) : une
  grille régulière par zone (`[carte.zones]` de la config) ; les cases d'un département
  sont celles dont le centre est dans le département, sauf, à chaque frontière, les
  cases du département au code le plus grand voisines (4 voisines) d'un autre
  département : couloir d'une seule rangée. Maille = la plus grande (à 1 m près) qui
  laisse au moins `marge_cases` × communes cases dans chaque département (dichotomie ;
  `marge_cases` dans la config, 1.0 au minimum, option `--marge` pour l'essayer).
  Chaque commune reçoit une case en minimisant la somme des distances au carré entre
  son centre et celui de la case (`scipy.optimize.linear_sum_assignment`), département
  par département. Carré dessiné = 85 % de la maille. L'écart entre centre de commune et
  carré est un artefact de lecture : la carte n'est pas à l'échelle.
- **Couleur** (décisions du 14/10 et du 19/10) : orange pour une décote, bleu pour un
  écart positif, gris si non estimable. Cinq classes fixes de `prime` : décote < −10 %,
  −10 à −3 %, −3 à +3 %, +3 à +10 %, > +10 % (bornes dans la config). Couleur franche
  pour les statuts « décote » et « pas de décote », pâle pour « indéterminé ».
- **Réglages** au-dessus de la carte (pas de barre latérale) : zone.
  Pas de couche « bascule 2020 → 2026 » (décision du 16/10).
- **Info-bulle** au survol : nom de la commune et statut, en texte.
- **Fiche commune** à droite : contenu défini dans le cahier. Choix par clic sur la
  carte si la version de Streamlit le permet, et par recherche de commune (souhaitable).

### Texte automatique

Gabarit déterministe, une phrase par élément, à partir de la ligne de la commune :
statut et motif, écart de prix observé et IC, effectifs des deux zones, statut de décote, arrêtés
CatNat (« sinistralité supérieure à la médiane du périmètre », jamais « risque
élevé »), quadrant. Il se termine toujours par un rappel : un écart moyen observé
n'est ni une estimation de la valeur d'une maison, ni une preuve de causalité.

## 3. Onglet Sinistralité × écart : définitions

L'affichage (tableau à quatre cases, communes en angle mort) est dans le cahier des
charges. Le nuage de points est abandonné.

- **Statut de décote** (décision du 15/10), calculé par le pipeline : « décote »,
  « pas de décote », « indéterminé » (définitions dans `docs/method.md`, section 6).
- **Quadrants** (décision du 14/10), calculés par le pipeline, communes « décote » et
  « pas de décote » seulement :

| | Décote | Pas de décote |
|---|---|---|
| **Sinistralité supérieure à la médiane du périmètre** | Risque intégré | Angle mort |
| **Sinistralité inférieure ou égale à la médiane du périmètre** | Décote à expliquer | Cohérent |

- **Médiane** de `catnat_depuis_2015` parmi les communes estimables, calculée par le
  pipeline et lue dans `resume_global.json`. Libellé imposé : « sinistralité
  supérieure à la médiane du périmètre », jamais « risque élevé ». Avec la médiane de 2
  arrêtés et « strictement au-dessus » sur des nombres entiers, **« supérieure à la
  médiane » signifie 3 arrêtés ou plus depuis 2015** (arrêtés sécheresse 2015-2023) ;
  l'app l'écrit ainsi à côté du libellé.
- Le statut repose sur l'IC, pas sur l'estimation ponctuelle, pour ne pas classer du
  bruit : une commune peu informative reste « indéterminée ».

## 4. Onglet Méthodologie et limites

Six cartes courtes et un renvoi vers `docs/method.md` (voir le cahier des charges). Les
effectifs du nettoyage et les sources sont lus dans `resume_global.json` (clés
`nettoyage` et `sources`). La phrase « environ 1 % des ventes » est calculée par le
pipeline et écrite dans `resume_global.json` (point ouvert du `CLAUDE.md`).

## 5. Organisation du code

```
.streamlit/
  config.toml        thème (charte)
app/
  streamlit_app.py   en-tête commun, onglets et configuration de la page
  donnees.py         lecture de data/processed/ (st.cache_data), contrôle des colonnes
  textes.py          définitions, libellés, légende, texte automatique, zones
  charte.py          CSS injecté une fois, en-tête commun, encadrés beige et gris (texte échappé)
  cartographie.py    couleurs, info-bulle, cadrage, carrés
  vues/
    resultat.py
    sinistralite.py
    carte.py
    methodologie.py
```

- Les définitions et libellés sont écrits une seule fois, dans `textes.py`.
- Nombres au format français (virgule décimale, espace pour les milliers, « % »).
- Si un fichier obligatoire manque ou qu'une colonne attendue est absente, l'app
  affiche un message clair au lieu d'une erreur Python.

## 6. Tests

- `donnees.py` : lecture de petits fichiers de test dans `tests/fixtures/processed/`,
  détection d'une colonne manquante.
- `textes.py` : texte automatique pour une commune estimable, une non estimable, une
  sans arrêté CatNat ; formatage des nombres ; pluriels ; vocabulaire imposé sur les
  cartes de Méthodologie.
- `textes.py` : correspondance département → zone identique à `config/perimetre.toml`,
  comme les bornes des classes de couleur.
- Pipeline : contrôle que `data/processed/` ne contient que des agrégats (aucune
  colonne de vente individuelle).
- Pipeline : statut de décote aux bornes (IC haut juste sous 0, IC bas égal au seuil
  de −3 %), sinistralité égale à la médiane (classée « inférieure ou égale »),
  aucune commune indéterminée dans un quadrant.

## 7. Déploiement

- Streamlit Community Cloud, depuis le dépôt GitHub ; dépendances principales
  seulement (streamlit, pydeck, pandas, pyarrow). La prise en charge de `uv.lock`
  par la plateforme est à vérifier au moment du déploiement (sinon,
  `requirements.txt` généré par `uv export`).
- Fond de carte : tuiles Carto chargées par le navigateur du visiteur ; le serveur de
  l'app ne fait aucun appel réseau.
