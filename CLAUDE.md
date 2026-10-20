# Retrait-Gonflement

Les règles communes sont dans `../CLAUDE.md`.

## Objectif
Question réellement testée : le marché fait-il une différence de prix entre zone
d'exposition forte et zone moyenne au retrait-gonflement des argiles (RGA) ? Résultat
global (« prime de risque implicite ») : pas de différence détectable ; si une décote
existe, elle ne dépasse probablement pas environ 3 %. Par commune : l'écart de prix
observé entre la zone forte et le reste de la commune, croisé avec la sinistralité.
Livrable : application Streamlit en français en quatre onglets (Résultat, Sinistralité
× écart, Carte, Méthodologie et limites), pour un recruteur ou un analyste en données
alternatives. Spécification dans `docs/app.md`. Projet court : 3 jours.

## Règles du projet
- **Ne jamais lire `data/raw/` ni `data/interim/`.**
- **L'app déployée ne lit que `data/processed/` : aucun appel réseau, aucun agent, aucune extension DuckDB.**
- Le code lit et écrit `data/raw/` et `data/interim/`, mais Claude ne les ouvre jamais ; les tests utilisent des réponses simulées dans `tests/fixtures/`.
- Les téléchargements réels sont lancés par moi, pas par Claude.
- Les pipelines tournent en local et écrivent leurs résultats dans `data/processed/`.
- `data/processed/` est suivi par Git (l'app déployée le lit) ; `data/raw/` et `data/interim/` sont ignorés.
- Aucune vente individuelle dans `data/processed/` : uniquement des agrégats par commune.
- Le README s'adresse aux lecteurs : ne jamais y renvoyer vers `CLAUDE.md`.
- Modifier un fichier uniquement avec l'outil d'édition (Edit/Write), jamais avec `cat >>`, `sed` ou une redirection : chaque modification doit apparaître sous forme de différences. Lancer les commandes une par une.

## Sources de données
| Source | Usage | Accès |
|---|---|---|
| DVF géolocalisées (Etalab) | Ventes de maisons, prix, surfaces, coordonnées | Libre, sans clé |
| Carte d'exposition RGA 2020 (Géorisques / BRGM) | Exposition connue du marché | Libre, sans clé |
| Carte d'exposition RGA 2026 (Géorisques / BRGM) | Communes qui basculent | Libre, sans clé (dépôt manuel) |
| GASPAR (Géorisques) | Arrêtés CatNat sécheresse par commune | Libre, sans clé |
| Contours des communes (API Géo, issus d'ADMIN EXPRESS IGN) | Carte de l'app | Libre, sans clé |

## Arborescence
```
src/retrait_gonflement/  paquet Python (déclaré dans pyproject.toml)
  data/                  connecteurs de collecte (DVF, RGA, GASPAR, communes)
  spatial/               jointures spatiales, contours simplifiés
  model/                 régression hédonique, primes par commune
app/                     application Streamlit (lit data/processed/)
tests/                   tests pytest ; réponses simulées dans tests/fixtures/
docs/                    method.md (méthode), app.md (spécification de l'app)
config/                  perimetre.toml (départements, années, URL, seuils)
data/raw/                données brutes, ignorées par Git, jamais lues par Claude
data/interim/            ventes nettoyées, travail.duckdb ; ignoré par Git, jamais lu par Claude
data/processed/          agrégats prêts pour l'app, suivis par Git
```
Pas de `__init__.py` directement dans `src/`. Import : `import retrait_gonflement`,
`from retrait_gonflement.data import ...`.

## Feuille de route
1. **Jour 1 : cadrage et données.** Nettoyage de la copie, `pyproject.toml`, `docs/method.md`,
   `docs/app.md`, `config/perimetre.toml`, connecteurs DVF, RGA, GASPAR et communes testés
   sur `tests/fixtures/`. Téléchargements réels lancés par moi.
2. **Jour 2 : traitement, modèle, carte.** Nettoyage DVF avec DuckDB, jointures spatiales 2020 et 2026,
   comptage des communes mixtes avant d'écrire le modèle, régression, primes par commune,
   CatNat, contours simplifiés, fichiers de `data/processed/`, vue 1 (carte).
3. **Jour 3 : livraison.** Vue 2 (sinistralité × décote), page Méthodologie et limites,
   README, déploiement, relecture.

## Décisions

- 14/10/2026 : projet créé par copie de phyto-freight ; suppression des fichiers phyto-freight validée ; paquet `retrait_gonflement` ; `.git` conservé (issu de mon `git init`).
- 14/10/2026 : `data/interim/` pour les ventes nettoyées et la base DuckDB de travail ; ignoré par Git ; Claude ne l'ouvre jamais, comme `data/raw/`.
- 14/10/2026 : dépendances principales limitées à ce que lit l'app (streamlit, pydeck, pandas, pyarrow) ; groupe `pipeline` (httpx, duckdb, pyfixest) ; groupe `agents` (claude-agent-sdk) ; groupe `dev` (pytest). Extension DuckDB `spatial` installée à la main, jamais utilisée par l'app.
- 14/10/2026 : périmètre : départements 31, 47, 77, 82 dans `config/perimetre.toml`. Dès les données disponibles, compter les communes mixtes (ventes dans les deux zones) avant d'écrire le modèle.
- 14/10/2026 : carte RGA 2026 : URL laissées vides dans la config, je les vérifie à la main (pistes : Shapefile officiel Géorisques ou fichiers départementaux `alearg_2025_<dep>_l93`). PMTiles de data.gouv exclu (tuiles d'affichage simplifiées).
- 14/10/2026 : contours des communes via l'API Géo (GeoJSON par département, issu d'ADMIN EXPRESS) ; ADMIN EXPRESS brut en repli.
- 14/10/2026 : agents en bonus au jour 3 : Analyste + Critique, 30 communes au maximum, une révision, texte automatique sinon.
- 14/10/2026 : quadrants de la vue 2 : « Risque intégré », « Angle mort », « Décote à expliquer », « Cohérent ».
- 14/10/2026 : couleurs de la prime : orange pour une décote, bleu pour une prime, gris si non estimable (pas de rouge/vert).
- 14/10/2026 : zone de référence : modèle global à trois catégories (référence = faible ou hors zone argileuse, coefficients « moyen » et « fort ») ; prime par commune = « fort » contre tout le reste (voir la décision du 16/10 sur la référence). Même définition partout (app, simulateur, README) ; simulateur réservé aux communes estimables.
- 14/10/2026 : tests multiples : `resume_global.json` donne le nombre de communes significatives observé et le nombre attendu par hasard (5 % des communes estimables) ; écrit dans les limites.
- 14/10/2026 : ventes DVF de 2021 à 2025 : la carte 2020 était disponible pour le marché sur toute la période.
- 15/10/2026 : nuances de `docs/method.md` validées (tests multiples sur les communes estimables ; « carte disponible pour le marché », sans obligation pour chaque vente).
- 15/10/2026 : variante « réforme 2025 » du modèle global : terme fort × (vente en 2025), car le décret n° 2024-405 (à vérifier sur Légifrance) ajoute le RGA à l'état des risques remis à l'acheteur au 1er janvier 2025. Variante à part pour garder β_fort identique partout ; résultat dans `resume_global.json` uniquement, présenté comme un indice (une seule année après la réforme).
- 15/10/2026 : fond de carte Carto conservé (chargé par le navigateur du visiteur, pas par le serveur) ; mention de la source sous la carte ; carte lisible sans fond (communes colorées + limites des départements, fichier `departements.geojson`).
- 15/10/2026 : seuil de sinistralité = médiane de `catnat_depuis_2015` parmi les communes estimables, calculée par le pipeline ; « supérieure » = strictement au-dessus. Libellé dans l'app : « sinistralité supérieure à la médiane du périmètre », jamais « risque élevé ».
- 15/10/2026 : trois statuts de décote calculés par le pipeline : « décote » (IC entièrement sous 0), « pas de décote » (borne basse de l'IC au-dessus de `seuil_pas_de_decote`, −3 % par défaut, dans `config/perimetre.toml`), « indéterminé » (le reste). Quadrants limités à « décote » et « pas de décote » ; indéterminées affichées à part (points creux) et comptées. « Angle mort » = sinistralité supérieure à la médiane ET « pas de décote ».
- 15/10/2026 : cartes RGA en dépôt manuel (pas d'URL stable, formulaire Géorisques) : le connecteur `data/rga.py` ne télécharge rien, il vérifie la présence et la validité des archives (5 fichiers du Shapefile) dans `data/raw/rga/<millésime>/`. Noms attendus dans `config/perimetre.toml` (clé `fichier`).
- 15/10/2026 : éléments communs des connecteurs (config, `ErreurDonnees`, écriture atomique) dans `data/commun.py` ; chaque connecteur a un client httpx injectable, une validation avant écriture, une ligne de commande qui n'affiche jamais le contenu.
- 16/10/2026 : jointure RGA : colonne `niveau` pour les deux millésimes, convertie en entier ; catégories 0 = hors zone argileuse (aucun polygone de niveau 0 : un point hors de tout polygone), 1 = faible, 2 = moyen, 3 = fort ; référence du modèle = 0 ou 1. Les deux cartes sont traitées comme EPSG:2154 (même projection Lambert 93, codes d'autorité différents : IGNF:LAMB93 en 2020). DVF est en WGS84 : ordre des axes à surveiller à la reprojection ; test avec un point connu (centre de Toulouse).
- 16/10/2026 : pas de polygone « faible » dans 77 et 82 (2020 et 2026) ni dans 47 (2026) : dans ces départements la référence est composée uniquement de maisons hors zone argileuse (limite ajoutée à `docs/method.md`).
- 16/10/2026 : référence de la prime par commune = « fort » contre tout le reste (niveaux 0+1+2 : hors zone, faible, moyen) ; seuils inchangés (15 fort, 15 référence, 50 au total), 193 communes estimables. La référence est très majoritairement « moyen » (hors zone et faible < 8 % des ventes) : la décote mesurée est l'écart fort contre moyen, entre deux zones exposées (limite ajoutée à `docs/method.md`). Jointure RGA validée : `autre_dep` = 0 partout, reprojection correcte.
- 16/10/2026 : transitions 2020 → 2026 lues : 861 ventes basculent vers fort (1 %), dans 8 communes (3 en 31, 5 en 77, aucune en 47 et 82) ; la carte 2026 reclasse aussi vers le bas (3→2 : 378 en 31, 187 en 77). Couche « bascule 2020 → 2026 » retirée de la vue 1 (colonne `n_bascule` retirée de `communes.parquet`) ; à la place, une phrase dans la page Méthodologie et le bandeau des résultats globaux : « Dans ces quatre départements déjà très exposés, la carte 2026 change le niveau d'environ 1 % des ventes, dans les deux sens. » Test placebo conservé dans `resume_global.json` uniquement, marqué « indicatif, faible puissance (861 ventes, 8 communes) ».
- 16/10/2026 : `min_ventes_faible_moyen` renommé `min_ventes_reference` (config, code, tests).
- 16/10/2026 : modèle global (`model/modele_global.py`) : pyfixest, effet fixe commune × trimestre, erreurs groupées par commune ; ventes seules dans leur commune × trimestre retirées avant l'estimation ; pièces en indicatrices (0 ou absent = « inconnu », 6 et plus regroupés, la plus fréquente en référence) ; `effet` = exp(β) − 1 en fraction dans le JSON (−0,05 = −5 %) ; quatre estimations (principal, sans les ventes proches d'une limite, placebo bascule « indicatif, faible puissance », réforme 2025 « indice ») ; `resume_global.json` est fusionné clé par clé (les étapes suivantes ajoutent leurs clés sans écraser celles-ci), sous la clé `modeles_globaux`.
- 16/10/2026 : chiffre phare = contraste « fort − moyen » (variance groupée par commune, Student à communes − 1 ddl) dans chaque modèle contenant moyen et fort ; modèle « fort contre tout le reste » ajouté (même définition que les primes par commune) ; placebo : avertissements dans le JSON et `docs/method.md` (IC sur 8 communes, signe positif = hétérogénéité de quartiers, non causal) ; limite ajoutée : la référence « hors zone + faible » est un petit groupe aux caractéristiques propres.
- 16/10/2026 : primes par commune (`model/primes_communes.py`) : une régression, un terme « fort » par commune estimable + un terme commun pour les autres communes ; erreurs groupées par section cadastrale (`id_parcelle[:10]`), repli HC1 sous `min_sections_groupement` = 10 sections (config), documenté dans `docs/method.md` ; statuts `decote` / `pas_de_decote` / `indetermine` ; tests multiples (observé contre 5 % des estimables) dans `resume_global.json` (clés de premier niveau de `docs/method.md`, section 8, plus `primes_communes`) ; sortie `data/processed/primes_communes.parquet`, fusionnée dans `communes.parquet` (noms, communes sans vente, CatNat, quadrants) par l'étape C ; le fichier est conservé (décision suivante sur les primes).
- 16/10/2026 : résultats des primes lus : 16 décote et 15 prime significatives contre 4,8 attendues par sens (31 pour environ 10 au total, symétrique) ; 81 communes sur 193 en HC1. Diagnostic par type d'erreurs : part de significatives proche (sections 17,0 % / HC1 14,8 %), IC plus larges en HC1 (25,7 contre 21,3 points) : le repli HC1 n'explique pas l'excès. Statuts conservés tels quels. Interprétation : hétérogénéité de quartiers au sein des communes, cohérente avec le placebo (limite ajoutée à `docs/method.md`) ; le tableau de diagnostic est dans `resume_global.json` (`primes_communes.diagnostic_erreurs`).
- 16/10/2026 : vocabulaire : les primes communales sont des « écarts de prix observés entre zone forte et reste de la commune », jamais un « effet de l'argile » ; « prime de risque implicite » réservé au résultat global (section « Vocabulaire imposé » de `docs/app.md`, README, objectif de ce fichier).
- 16/10/2026 : CatNat : libellé « Sécheresse » seul (« Mouvement de Terrain » écarté : 35 à 165 par an, ne suit pas les sécheresses) ; aucune sécheresse reconnue après 2023 (délai de reconnaissance) : indicateur 2015-2023, libellé « arrêtés sécheresse 2015-2023 », limite dans `docs/method.md` ; événement = (commune, `date_debut`, `date_fin`) distinct, « depuis 2015 » sur `date_debut` (`depuis_annee` dans la config) ; fusions de communes rapprochées par un fichier optionnel `config/fusions_communes.csv` (aucune table de fusions fournie : on regarde d'abord le nombre de codes non rapprochés) ; communes sans vente = non estimables (effectifs insuffisants), sans arrêté = 0.
- 16/10/2026 : résultats de l'étape C lus : 5 838 événements sécheresse, dernier début le 2023-12-31, 0 code GASPAR non rapproché, 0 vente sans commune, seuil médian = 2 arrêtés, quadrants : risque intégré 2, angle mort 9, décote à expliquer 14, cohérent 18 ; contours 1,57 Mo. « Sinistralité supérieure à la médiane » = 3 arrêtés ou plus depuis 2015 (libellé de l'app, `docs/app.md` et `docs/method.md`). Les décotes sont surtout dans les communes peu sinistrées (14 contre 2), cohérent avec l'interprétation « écarts entre quartiers » (`docs/method.md`).
- 16/10/2026 : `data/processed/primes_communes.parquet` est conservé (entrée de l'étape C, agrégats par commune seulement, non lu par l'app) ; `docs/app.md` ne prévoit plus sa suppression.
- 16/10/2026 : nettoyage DVF (`data/nettoyage_dvf.py`) : une mutation = (fichier, `id_mutation`), exclue pour son premier motif (nature, plusieurs dispositions, valeur absente, aucune maison, autre local, plusieurs maisons, sans coordonnées, surface bâtie hors bornes, valeur sous le minimum, terrain au-dessus du plafond, quantiles de prix) ; maisons distinctes comptées par (parcelle, surface, pièces) ; `valeur_fonciere` = une valeur par mutation, jamais sommée ; terrain = somme des couples (parcelle, nature de culture, nature de culture spéciale) distincts ; plafond `terrain_max_m2 = 10000` dans la config ; tables `mutations_dvf` (motif de chaque mutation) et `ventes_maisons` dans `data/interim/travail.duckdb`.
- 17/10/2026 : app, bandeau : la phrase du chiffre phare utilise `seuil_pas_de_decote` lu dans le JSON (même définition que le statut des communes) ; borne basse strictement au-dessus du seuil : « ne dépasse pas environ X % », X arrondi à l'entier, minimum 1 % ; sinon « trop imprécis » ; IC entièrement sous 0 : « décote mesurée » ; IC entièrement au-dessus de 0 : « pas de décote, écart positif ». Les bornes des classes de couleur restent dans `app/textes.py` (l'app ne lit pas la config), un test vérifie qu'elles sont identiques à `config/perimetre.toml`.
- 17/10/2026 : app : texte long de la page Méthodologie dans `app/methodologie.md` (étape 4), avec le même test de vocabulaire que les textes de `textes.py` ; l'app n'écrit aucun chiffre ni aucune date en dur (effectifs du nettoyage et sources lus dans `resume_global.json`, clés `nettoyage` et `sources`, produites par `model/metadonnees.py`). Seule exception provisoire : « environ 1 % » (voir Points ouverts).
- 17/10/2026 : 150 des 193 communes estimables sont « indéterminées » : résultat assumé, dit clairement dans l'app (phrase sous la carte, bandeau) ; la vue 2 aura une option pour masquer les indéterminées.
- 18/10/2026 : carte : les communes écartées par un filtre restent affichées, grisées ; le fond de carte est coché par défaut (réglage dans la barre latérale) avec la mention Carto visible tant qu'il est coché.
- 18/10/2026 : pydeck interprète toute chaîne comme une expression JavaScript (`"pixels"` devient `@@=pixels`) : les constantes textuelles transmises à une couche s'écrivent avec des guillemets internes, `"'pixels'"` (`UNITE_LIGNES` dans `app/cartographie.py`). Contours en pixels : communes fins et clairs, départements plus marqués.
- 18/10/2026 : limites des départements réduites à l'anneau extérieur à l'affichage (`limites_exterieures` dans `app/cartographie.py`) : `departements.geojson` compte 760 à 1 767 anneaux par département (interstices entre communes), tracés en sombre ils redessinaient les frontières communales. Le fichier n'est pas modifié.
- 19/10/2026 : objectif reformulé : la question testée est « le marché fait-il une différence de prix entre zone forte et zone moyenne ? » ; pas de différence détectable ; si une décote existe, elle ne dépasse probablement pas environ 3 % ; absence de décote détectable ≠ absence de décote ; moyen et fort ≈ −3 % contre hors zone (p ≈ 0,06, référence petite et particulière).
- 19/10/2026 : public : recruteur ou analyste en données alternatives (2-3 minutes, ordinateur, depuis le README) ; le particulier n'est pas visé ; app en français.
- 19/10/2026 : parcours en quatre onglets (Résultat, Sinistralité × écart, Carte, Méthodologie et limites), chacun sans défilement à 1 280 × 800 ; pas de barre latérale ; spécification complète dans `docs/app.md`, maquettes du Projet claude.ai historiques.
- 19/10/2026 : simulateur abandonné (convertir en euros un écart non attribuable à l'argile induirait en erreur).
- 19/10/2026 : onglet Résultat en cinq niveaux (phrase-réponse, chiffre phare, lecture, encadré « ce qui a vraiment été testé », signal faible) ; titre « Le marché distingue-t-il les zones d'argile forte et moyenne ? » ; la phrase « environ 1 % des ventes » va dans la Méthodologie seule (remplace la décision du 16/10 qui la plaçait aussi dans le bandeau).
- 19/10/2026 : prix médian au m² retiré de la fiche commune ; colonne retirée du pipeline (souhaitable).
- 19/10/2026 : carte : couleur pâle = statut « indéterminé » (remplace « opacité réduite si l'IC contient 0 ») ; non estimables en gris #C4C8C3 ; limites des départements marquées ; info-bulle simple au survol (nom et statut, en texte).
- 19/10/2026 : carte en deux zones (Sud-Ouest 31, 47, 82 ; Seine-et-Marne 77), zoom minimal par zone pour empêcher le dézoom jusqu'à l'Europe ; recherche de commune (souhaitable) = même effet qu'un clic.
- 19/10/2026 : onglet 2 en tableau à quatre cases (statut × sinistralité) à la place du nuage de points ; indéterminées comptées sous le tableau.
- 19/10/2026 : Méthodologie en six cartes courtes, renvoi vers `docs/method.md` ; `app/methodologie.md` abandonné (remplace la décision du 17/10).
- 19/10/2026 : agents abandonnés dans ce projet (apport faible sur des écarts surtout indéterminés) ; réservés au projet suivant, conçu autour d'eux ; nettoyage de `pyproject.toml` (groupe `agents`) et `.env.example` (`ANTHROPIC_API_KEY`) dans un commit séparé.
- 20/10/2026 : onglets `st.tabs` natifs (clé `onglet`, `on_change="rerun"`) sous un bandeau sombre ; onglets inactifs en gris foncé #4A514D (le gris clair de la maquette est illisible sur fond clair) ; polices système ; maquette dans `docs/maquette/`, `docs/app.md` fait foi.
- 19/10/2026 : charte : thème sans rouge dans `.streamlit/config.toml`, encadrés beige et gris (jamais `st.info`), chiffres tabulaires, notation unique des IC « [a % ; b %] » ; IBM Plex Mono et Google Fonts abandonnés ; Public Sans servie depuis le dépôt si le temps le permet. Mise à jour du 20/10 : l'app garde la police par défaut de Streamlit (servie par l'app, aucun appel externe) ; le CSS de `charte.py` n'impose aucune police ni sélecteur universel (une police imposée à tous les éléments écrase la police d'icônes : « _arrow_right » s'affichait en texte), un test le vérifie.

## Avancement

- Jour 1 terminé le 16/10/2026 : config, quatre connecteurs (DVF, communes, RGA, GASPAR) testés et vérifiés sur les vraies données.
- Fait :
  - cadrage, `pyproject.toml`, `docs/method.md`, `docs/app.md` (commits `93002ec`, `b40eb9d`) ;
  - `config/perimetre.toml` et connecteur DVF avec ligne de commande (`de26142`) ;
  - connecteur communes (API Géo) et `data/commun.py` (`ea53c98`) ;
  - connecteur RGA en dépôt manuel, procédure dans le README (`b7b2fab`) ;
  - connecteur GASPAR : archive ZIP (8 tables) téléchargée dans `data/raw/gaspar/gaspar.zip`, table `catnat_gaspar_*.csv` trouvée par modèle, séparateur « ; », colonnes requises validées ; aucun filtrage (sécheresse, depuis 2015) avant le jour 2 ;
  - `uv run pytest` : 52 tests verts, aucun appel réseau ; fixtures écrites à la main dans `tests/fixtures/` ;
  - 16/10/2026 : téléchargements réels OK : DVF complet (20 fichiers, 2021-2025) ; communes (586, 319, 507 et 195 communes pour 31, 47, 77, 82) ;
  - cartes RGA 2026 déposées et vérifiées (31, 47, 77, 82) ; carte RGA 2020 trouvée sur la page dédiée de Géorisques (même format), déposée dans `data/raw/rga/2020/` (modèle `AleaRG{departement}_L93.zip`), vérifiée avec le connecteur : 4 archives valides ; le 6e fichier est un `.qix` (index spatial), sans incidence ;
  - extension DuckDB `spatial` installée.
- Jour 2 terminé le 16/10/2026 : nettoyage DVF, jointure RGA, modèle global, primes par commune, CatNat et fichiers finaux de `data/processed/` ; `uv run pytest` : 123 tests verts.
- Détail du jour 2 :
  - script d'inspection des cartes RGA lancé par moi sur les vraies cartes, commité (`db7a974`) ; décisions de jointure et limite sur la référence commitées (`f646247`) ;
  - nettoyage DVF écrit (`data/nettoyage_dvf.py`, `tests/test_nettoyage_dvf.py`, `tests/fixtures/dvf_nettoyage.csv`, `terrain_max_m2` dans la config) ; `uv run pytest` : 60 tests verts ;
  - résumé du nettoyage lancé par moi et validé : 82 525 ventes retenues sur 366 760 mutations, totaux cohérents (vérifiés sur 31/2021), plafond de terrain ≈ 2 % d'exclusions en 31/77 et ≈ 8 % en 47/82, quantiles ≈ 2 %, 2025 complète ; nettoyage commité ; `docs/method.md` mis à jour.
  - jointure spatiale écrite (`spatial/jointure_rga.py`, `tests/test_jointure_rga.py`, point de Toulouse testé) et lancée par moi : table `ventes_rga` dans `data/interim/travail.duckdb` ; `autre_dep` = 0 partout (reprojection correcte) ; ventes hors zone : 1,4 à 7,3 % ; quasi aucune en faible ; 37 à 53 % en fort ; 808 communes mixtes, dont 193 passent les seuils (15 fort, 15 référence, 50 au total) en référence large ;
  - décisions appliquées : référence large (0+1+2), seuils inchangés, limite « décote = fort contre moyen » ajoutée à `docs/method.md` et `docs/app.md` mis à jour ;
  - transitions et bascules lues par moi : 861 ventes vers fort (1 %), 8 communes ; couche bascule retirée de la vue 1 (`docs/app.md`), phrase ajoutée, placebo indicatif dans `resume_global.json` (`docs/method.md`) ;
  - `min_ventes_faible_moyen` renommé `min_ventes_reference` ; `uv run pytest` : 67 tests verts ;
  - jointure commitée (`283cb5b`) ;
  - modèle global (étape A) écrit (`model/modele_global.py`, `tests/test_modele_global.py` : données simulées avec décote connue de −5 % en fort, retrouvée) ; `uv run pytest` : 82 tests verts ; contraste fort − moyen, modèle fort contre tout le reste et avertissements du placebo ajoutés après lecture d'un premier résumé ; résumé lancé par moi et validé : contraste fort − moyen +0,91 % [−2,89 ; +4,86] (p = 0,64), stable dans toutes les variantes ; fort contre tout le reste +0,70 % [−2,97 ; +4,51] : pas de décote détectable au niveau global ; commité (`e1eda37`) avec `data/processed/resume_global.json` (agrégats seulement) (`uv run python -m retrait_gonflement.model.modele_global`, écrit `data/processed/resume_global.json`).
  - étape B écrite (`model/primes_communes.py`, `tests/test_primes_communes.py` : primes communales connues retrouvées sur données simulées) ; `uv run pytest` : 103 tests verts ; lancée par moi, résumé et diagnostic par type d'erreurs lus (décisions ci-dessus), `diagnostic_erreurs` inscrit dans `resume_global.json` ; commitée (`33dd38d`) (`uv run python -m retrait_gonflement.model.primes_communes`, écrit `data/processed/primes_communes.parquet` et complète `resume_global.json`) ;
  - étape C écrite (`data/catnat.py`, `spatial/contours.py`, `model/communes_finales.py`, `tests/test_catnat.py`, `tests/test_communes_finales.py`) ; `uv run pytest` : 123 tests verts ; lancée par moi, résumé validé (`uv run python -m retrait_gonflement.model.communes_finales` écrit `communes.parquet`, `contours.geojson` (1,57 Mo), `departements.geojson` dans `data/processed/` et complète `resume_global.json`) ; commitée (`af8802a`).
- Jour 3 en cours (17/10/2026) :
  - métadonnées de l'app (`model/metadonnees.py`, `tests/test_metadonnees.py`) : effectifs du nettoyage (82 525 ventes retenues) et 5 sources (millésimes, dates) ajoutés à `resume_global.json`, lancé par moi, commité (`a832d8a`) ; date de téléchargement = date du fichier local ;
  - étape 1 de l'app : `app/donnees.py` (lecture et contrôle de `data/processed/`, cache, dossier réglable par `RG_DONNEES`), `app/textes.py` (formats français, bandeau, classes de couleur, légende, texte automatique, vocabulaire imposé), `tests/conftest.py` (petites données construites dans les tests), `pythonpath = ["app"]` dans `pyproject.toml` ; `uv run pytest` : 176 tests verts ; commitée (`cb3ed5a`) ;
  - étape 2 de l'app (18/10/2026) : `app/cartographie.py` (couleurs, info-bulle, filtres, cadrage, contours), `app/vues/carte.py` (bandeau, carte pydeck, fiche commune, phrases sous la carte), `app/streamlit_app.py` (navigation), `tests/test_app_cartographie.py`, `tests/test_app_carte.py` (`streamlit.testing`) ; écrite et vérifiée au navigateur par moi (`uv run streamlit run app/streamlit_app.py`) ; `uv run pytest` : 215 tests verts.
- 19/10/2026 : cahier des charges de l'app tranché et écrit dans `docs/app.md` (aucun code) ; agents et simulateur abandonnés.
- 20/10/2026 : nettoyage des agents : groupe `agents` de `pyproject.toml` et `ANTHROPIC_API_KEY` de `.env.example` retirés ; lecture des notes d'agents retirée de l'app (`lire_notes`, `charger_notes`, champ `notes`, argument de `fiche`), la fiche affiche le texte automatique seul ; deux tests retirés ; sous-paquet `src/retrait_gonflement/agents/` (un `__init__.py` vide) supprimé avec `git rm`, dans le commit `2047471` ; `uv run pytest` : 213 tests verts.
- 20/10/2026 : étape 3a (socle) écrite : `.streamlit/config.toml` (thème, `gatherUsageStats = false`, `toolbarMode = "minimal"`), `app/charte.py` (CSS, en-tête, encadrés beige et gris échappés), `streamlit_app.py` en quatre `st.tabs` (clé `onglet`, `on_change="rerun"`, seul l'onglet ouvert est calculé) ; barre latérale et `st.info` supprimés (réglages en colonnes au-dessus de la carte, légende dessous) ; bandeau provisoirement dans Résultat ; `docs/app.md` pointe vers `docs/maquette/` ; `uv run pytest` : 233 tests verts ; reste à relire au navigateur (hauteur de la carte : 560 px, défilement probable à 1 280 × 800, à traiter en 3b-2).
- Pas de bloquant.
- Reprise :
  1. commit de cette spécification : fait (`3674361`) ;
  2. nettoyage des agents : fait (`2047471`) ;
  3. corrections relevées au navigateur et indispensables de la charte :
     - 3a socle (20/10) : fait, à relire au navigateur puis commit (voir « Avancement ») ;
     - 3b-1 (pipeline : carrés) et 3b-2 (app : carrés, retrait du fond de carte, tuiles, zones, recherche, retrait de la case « significatives seulement »), puis 3c (fiche à droite) : à faire ;
  4. onglet Résultat ;
  5. onglet Sinistralité × écart ;
  6. onglet Méthodologie ;
  7. README et déploiement ;
  8. relecture (Opus) ;
  9. souhaitables.
- Points ouverts :
  - vérifier sur Légifrance le décret n° 2024-405 du 29 avril 2024 (RGA dans l'état des risques au 1er janvier 2025) ;
  - créer le dépôt GitHub et faire le premier push (après confirmation) ;
  - « environ 1 % des ventes » : phrase fixe dans `app/textes.py` (`PHRASE_CARTE_2026`) ; à calculer dans le pipeline et écrire dans `resume_global.json`, pour l'onglet Méthodologie seul (la phrase parle des deux sens, 861 ventes vers « fort » ne couvrent qu'un sens) ;
  - retouches de fin : couleur noire du bandeau, bouton de zone sélectionné, ajustements de textes, limites des départements à distinguer du contour de sélection ;
  - vérifications de la sous-section « À vérifier avant le code » de `docs/app.md` ;
  - remplir les trous de `departements.geojson` dans `spatial/contours.py` (pipeline, plus tard : fichier plus léger, plus besoin de `limites_exterieures`) ;
  - corrections relevées au navigateur (étape 2), à reprendre à l'étape 3 de la Reprise : le fond de carte ne se retire pas ; info-bulle en HTML brut ; cadrage (initial et par zone) ; étiquettes du fond en anglais (style Carto sans étiquettes à envisager) ; fiche commune (arrêtés dans leur case, « — » si non estimable). Tranchés le 19/10, voir `docs/app.md` : prix médian, couleur pâle, charte, contenu de la fiche ; remplacer `st.info` de la fiche par l'encadré beige ; adapter `test_fiche_commune_estimable` et `test_fiche_commune_non_estimable`, qui lisent `at.info[0]` ;
  - relecture (étape 8, Opus) : « prime de risque implicite » nomme le contraste fort − moyen, alors que l'étude ne dit pas si le marché fait payer le risque (comparaison entre deux zones exposées) ; options : réserver l'expression à l'écart des zones exposées contre hors zone, ou l'abandonner partout (vocabulaire imposé, README, onglets) ;
  - test « aucun prix médian sous 5 ventes » dans `data/processed/` : à garder tant que la colonne `prix_m2_median` existe, à retirer avec elle ;
  - vérifier si pyfixest retire `terrain_nul` (multicolinéarité) sur les vraies données des primes par commune, comme dans `test_statut_et_motif_des_communes`, et le documenter dans `docs/method.md` le cas échéant.
