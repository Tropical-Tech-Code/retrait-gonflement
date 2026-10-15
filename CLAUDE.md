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
| Carte d'exposition RGA 2026 (Géorisques / BRGM) | Communes qui basculent (source à confirmer) | Libre, sans clé |
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
- 14/10/2026 : zone de référence : modèle global à trois catégories (référence = faible ou hors zone argileuse, coefficients « moyen » et « fort ») ; prime par commune = « fort » contre « faible + moyen ». Même définition partout (app, simulateur, README) ; simulateur réservé aux communes estimables.
- 14/10/2026 : tests multiples : `resume_global.json` donne le nombre de communes significatives observé et le nombre attendu par hasard (5 % des communes estimables) ; écrit dans les limites.
- 14/10/2026 : ventes DVF de 2021 à 2025 : la carte 2020 était disponible pour le marché sur toute la période.
- 15/10/2026 : nuances de `docs/method.md` validées (tests multiples sur les communes estimables ; « carte disponible pour le marché », sans obligation pour chaque vente).
- 15/10/2026 : variante « réforme 2025 » du modèle global : terme fort × (vente en 2025), car le décret n° 2024-405 (à vérifier sur Légifrance) ajoute le RGA à l'état des risques remis à l'acheteur au 1er janvier 2025. Variante à part pour garder β_fort identique partout ; résultat dans `resume_global.json` uniquement, présenté comme un indice (une seule année après la réforme).
- 15/10/2026 : fond de carte Carto conservé (chargé par le navigateur du visiteur, pas par le serveur) ; mention de la source sous la carte ; carte lisible sans fond (communes colorées + limites des départements, fichier `departements.geojson`).
- 15/10/2026 : seuil de sinistralité = médiane de `catnat_depuis_2015` parmi les communes estimables, calculée par le pipeline ; « supérieure » = strictement au-dessus. Libellé dans l'app : « sinistralité supérieure à la médiane du périmètre », jamais « risque élevé ».
- 15/10/2026 : trois statuts de décote calculés par le pipeline : « décote » (IC entièrement sous 0), « pas de décote » (borne basse de l'IC au-dessus de `seuil_pas_de_decote`, −3 % par défaut, dans `config/perimetre.toml`), « indéterminé » (le reste). Quadrants limités à « décote » et « pas de décote » ; indéterminées affichées à part (points creux) et comptées. « Angle mort » = sinistralité supérieure à la médiane ET « pas de décote ».
- 15/10/2026 : cartes RGA en dépôt manuel (pas d'URL stable, formulaire Géorisques) : le connecteur `data/rga.py` ne télécharge rien, il vérifie la présence et la validité des archives (5 fichiers du Shapefile) dans `data/raw/rga/<millésime>/`. Noms attendus dans `config/perimetre.toml` (clé `fichier`).
- 15/10/2026 : éléments communs des connecteurs (config, `ErreurDonnees`, écriture atomique) dans `data/commun.py` ; chaque connecteur a un client httpx injectable, une validation avant écriture, une ligne de commande qui n'affiche jamais le contenu.

## Avancement

- Jour 1 terminé en grande partie, session du 15/10/2026 close.
- Fait :
  - cadrage, `pyproject.toml`, `docs/method.md`, `docs/app.md` (commits `93002ec`, `b40eb9d`) ;
  - `config/perimetre.toml` et connecteur DVF avec ligne de commande (`de26142`) ;
  - connecteur communes (API Géo) et `data/commun.py` (`ea53c98`) ;
  - connecteur RGA en dépôt manuel, procédure dans le README (`b7b2fab`) ;
  - `uv run pytest` : 36 tests verts, aucun appel réseau ; fixtures écrites à la main dans `tests/fixtures/` ;
  - téléchargement réel DVF 82/2024 OK (18 071 lignes) ; cartes RGA 2026 déposées et vérifiées pour 31, 47, 77, 82.
- En attente :
  - test réel du connecteur communes ;
  - connecteur GASPAR : URL officielle trouvée (`https://www.data.gouv.fr/api/1/datasets/r/d6fb9e18-b66b-499c-8284-46a3595579cc`), colonnes du CSV à vérifier avant d'écrire la validation ;
  - téléchargement DVF du périmètre complet (4 départements × 2021-2025) ;
  - commit de cette mise à jour de `CLAUDE.md`.
- Bloquant : source de la carte RGA 2020 introuvable pour l'instant (Géorisques ne propose que la version 2026). Les modèles de `docs/method.md` utilisent la carte 2020 comme exposition connue du marché : à trancher avant le jour 2 (autre source, ou révision de la méthode).
- Reprise : test communes, connecteur GASPAR, recherche de la carte 2020.
- Points ouverts :
  - vérifier sur Légifrance le décret n° 2024-405 du 29 avril 2024 (RGA dans l'état des risques au 1er janvier 2025) ;
  - installer une fois l'extension DuckDB `spatial` à la main ;
  - créer le dépôt GitHub et faire le premier push (après confirmation) ;
  - clé API Anthropic avant les agents (bonus).
