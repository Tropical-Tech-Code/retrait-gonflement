# Retrait-Gonflement

Les règles communes sont dans `../CLAUDE.md`.

## Objectif
Mesurer si le marché immobilier applique une décote aux maisons situées en zone
d'exposition forte au retrait-gonflement des argiles (RGA), et cartographier
cette « prime de risque implicite » par commune.
Livrable : application Streamlit (carte par commune, sinistralité × décote).
Projet court : 3 jours.

## Règles du projet
- **Ne jamais lire `data/raw/` ni `data/interim/`.**
- **L'app déployée ne lit que `data/processed/` : aucun appel réseau, aucun agent, aucune extension DuckDB.**
- Le code lit et écrit `data/raw/` et `data/interim/`, mais Claude ne les ouvre jamais ; les tests utilisent des réponses simulées dans `tests/fixtures/`.
- Les téléchargements réels sont lancés par moi, pas par Claude.
- Les pipelines et les agents tournent en local et écrivent leurs résultats dans `data/processed/`.
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
| Anthropic | Agents (Claude Agent SDK), hors ligne, bonus | `ANTHROPIC_API_KEY` |

## Arborescence
```
src/retrait_gonflement/  paquet Python (déclaré dans pyproject.toml)
  data/                  connecteurs de collecte (DVF, RGA, GASPAR, communes)
  spatial/               jointures spatiales, contours simplifiés
  model/                 régression hédonique, primes par commune
  agents/                agents Claude Agent SDK (local uniquement, bonus)
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

## Agents (bonus)
- Claude Agent SDK seul, groupe de dépendances `agents`, local uniquement.
- Analyste : note de 3 à 4 phrases par commune à partir de sa ligne chiffrée.
- Critique : vérifie la note contre les chiffres (IC, effectifs) ; une révision au maximum.
- 30 communes au maximum (angles morts et plus fortes décotes) ; sinon, texte automatique dans l'app.
- Les calculs restent du code déterministe ; les agents interprètent et rédigent.

## Feuille de route
1. **Jour 1 : cadrage et données.** Nettoyage de la copie, `pyproject.toml`, `docs/method.md`,
   `docs/app.md`, `config/perimetre.toml`, connecteurs DVF, RGA, GASPAR et communes testés
   sur `tests/fixtures/`. Téléchargements réels lancés par moi.
2. **Jour 2 : traitement, modèle, carte.** Nettoyage DVF avec DuckDB, jointures spatiales 2020 et 2026,
   comptage des communes mixtes avant d'écrire le modèle, régression, primes par commune,
   CatNat, contours simplifiés, fichiers de `data/processed/`, vue 1 (carte).
3. **Jour 3 : livraison.** Vue 2 (sinistralité × décote), page Méthodologie et limites,
   README, déploiement, relecture.
4. **Bonus si le temps le permet** : vue 3 (simulateur) et agents.

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
- 16/10/2026 : nettoyage DVF (`data/nettoyage_dvf.py`) : une mutation = (fichier, `id_mutation`), exclue pour son premier motif (nature, plusieurs dispositions, valeur absente, aucune maison, autre local, plusieurs maisons, sans coordonnées, surface bâtie hors bornes, valeur sous le minimum, terrain au-dessus du plafond, quantiles de prix) ; maisons distinctes comptées par (parcelle, surface, pièces) ; `valeur_fonciere` = une valeur par mutation, jamais sommée ; terrain = somme des couples (parcelle, nature de culture, nature de culture spéciale) distincts ; plafond `terrain_max_m2 = 10000` dans la config ; tables `mutations_dvf` (motif de chaque mutation) et `ventes_maisons` dans `data/interim/travail.duckdb`.

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
- Jour 2 en cours (16/10/2026) :
  - script d'inspection des cartes RGA lancé par moi sur les vraies cartes, commité (`db7a974`) ; décisions de jointure et limite sur la référence commitées (`f646247`) ;
  - nettoyage DVF écrit (`data/nettoyage_dvf.py`, `tests/test_nettoyage_dvf.py`, `tests/fixtures/dvf_nettoyage.csv`, `terrain_max_m2` dans la config) ; `uv run pytest` : 60 tests verts ;
  - résumé du nettoyage lancé par moi et validé : 82 525 ventes retenues sur 366 760 mutations, totaux cohérents (vérifiés sur 31/2021), plafond de terrain ≈ 2 % d'exclusions en 31/77 et ≈ 8 % en 47/82, quantiles ≈ 2 %, 2025 complète ; nettoyage commité ; `docs/method.md` mis à jour.
  - jointure spatiale écrite (`spatial/jointure_rga.py`, `tests/test_jointure_rga.py`, point de Toulouse testé) et lancée par moi : table `ventes_rga` dans `data/interim/travail.duckdb` ; `autre_dep` = 0 partout (reprojection correcte) ; ventes hors zone : 1,4 à 7,3 % ; quasi aucune en faible ; 37 à 53 % en fort ; 808 communes mixtes, dont 193 passent les seuils (15 fort, 15 référence, 50 au total) en référence large ;
  - décisions appliquées : référence large (0+1+2), seuils inchangés, limite « décote = fort contre moyen » ajoutée à `docs/method.md` et `docs/app.md` mis à jour ;
  - transitions et bascules lues par moi : 861 ventes vers fort (1 %), 8 communes ; couche bascule retirée de la vue 1 (`docs/app.md`), phrase ajoutée, placebo indicatif dans `resume_global.json` (`docs/method.md`) ;
  - `min_ventes_faible_moyen` renommé `min_ventes_reference` ; `uv run pytest` : 67 tests verts ;
  - jointure commitée (`283cb5b`) ;
  - modèle global (étape A) écrit (`model/modele_global.py`, `tests/test_modele_global.py` : données simulées avec décote connue de −5 % en fort, retrouvée) ; `uv run pytest` : 82 tests verts ; contraste fort − moyen, modèle fort contre tout le reste et avertissements du placebo ajoutés après lecture d'un premier résumé ; résumé lancé par moi et validé : contraste fort − moyen +0,91 % [−2,89 ; +4,86] (p = 0,64), stable dans toutes les variantes ; fort contre tout le reste +0,70 % [−2,97 ; +4,51] : pas de décote détectable au niveau global ; commité avec `data/processed/resume_global.json` (agrégats seulement) (`uv run python -m retrait_gonflement.model.modele_global`, écrit `data/processed/resume_global.json`).
- Pas de bloquant.
- Reprise : étape B (prime par commune : terme fort × commune, statuts de décote, sinistralité CatNat, fichiers de `data/processed/`).
- Points ouverts :
  - vérifier sur Légifrance le décret n° 2024-405 du 29 avril 2024 (RGA dans l'état des risques au 1er janvier 2025) ;
  - créer le dépôt GitHub et faire le premier push (après confirmation) ;
  - clé API Anthropic avant les agents (bonus).
