# Méthode

Question : le marché immobilier applique-t-il une décote aux maisons situées en zone
d'exposition forte au retrait-gonflement des argiles (RGA) ?

Tous les seuils et les URL sont dans `config/perimetre.toml`.

## 1. Périmètre et période

- Départements 31, 47, 77, 82 (environ 1 600 communes).
- Ventes DVF de 2021 à 2025, par année civile complète.
- Pourquoi 2021 : la carte d'exposition 2020 est publique sur Géorisques et encadre
  les obligations de la loi ELAN depuis le 1er octobre 2020. Elle était donc disponible
  pour le marché pendant toute la période étudiée. Commencer en 2021 évite de mélanger,
  dans une même année, des ventes antérieures et postérieures à son entrée en vigueur.
- **2025, année de réforme** : selon une source secondaire, le décret n° 2024-405 du
  29 avril 2024 ajoute l'exposition RGA à l'état des risques remis à l'acheteur à
  partir du 1er janvier 2025 (l'état des risques est remis dès la première visite
  depuis 2023). *Référence à vérifier sur Légifrance.* L'information n'est donc plus
  seulement disponible : elle est remise à l'acheteur. Voir la variante « réforme 2025 »
  (section 5).

## 2. Ventes DVF (fichiers DVF géolocalisés d'Etalab)

- `nature_mutation = 'Vente'` uniquement.
- **Vente simple** : la mutation compte exactement une maison et aucun autre local
  (appartement, local industriel ou commercial) ; les dépendances sont tolérées.
- **Dédoublonnage** : DVF répète une mutation en autant de lignes que de combinaisons
  local × parcelle × nature de culture. La surface de terrain est la somme des couples
  (parcelle, nature de culture, nature de culture spéciale) distincts, jamais la somme
  brute des lignes. La nature de culture spéciale fait partie de la clé car deux
  subdivisions de la même parcelle et de la même culture ont des surfaces distinctes.
- **Une maison ou plusieurs** : les maisons d'une mutation sont comptées par
  (parcelle, surface bâtie, nombre de pièces) distincts. Une mutation à plusieurs
  dispositions (`numero_disposition` > 1) est exclue.
- **Valeur foncière** : répétée sur chaque ligne d'une mutation, elle est prise une seule
  fois par mutation, jamais sommée.
- **Terrain** : les ventes dont la surface de terrain dépasse `terrain_max_m2`
  (10 000 m²) sont exclues, avant le calcul des quantiles de prix.
- **Motifs d'exclusion** : chaque mutation est comptée pour le premier motif rencontré
  (ordre : nature, dispositions, valeur absente, aucune maison, autre local, plusieurs
  maisons, sans coordonnées, bornes de surface, valeur minimale, plafond de terrain,
  quantiles de prix).
- **Prix au m²** = valeur foncière / surface réelle bâtie.
- **Valeurs aberrantes** : bornes absolues (surface bâtie entre 20 et 400 m²,
  valeur foncière ≥ 15 000 €), puis exclusion des 1 % les plus bas et les plus hauts
  du prix au m², par département et par année.
- Ventes sans coordonnées : exclues, avec leur nombre consigné.

## 3. Exposition RGA

- Point de la vente (centroïde de la parcelle, WGS84) reprojeté en Lambert-93
  (EPSG:2154), puis jointure point dans polygone avec DuckDB `spatial`.
- Classes : **faible**, **moyen**, **fort** ; une vente hors de tout polygone est
  classée **hors zone argileuse**.
- **Carte 2020** : exposition connue du marché, utilisée dans les modèles.
- **Carte 2026** : sert à repérer les **bascules** (vente non classée « fort » en 2020
  et « fort » en 2026). Source : Géorisques, dépôt manuel.
- Les deux cartes codent l'exposition dans la colonne `niveau` : 1 = faible, 2 = moyen,
  3 = fort. Aucun polygone de niveau 0 : une vente hors de tout polygone est « hors zone
  argileuse » (0). Les deux cartes sont lues comme EPSG:2154.
- Le niveau d'une vente est le plus haut niveau parmi les polygones de son département
  qui contiennent le point (cas d'un point exactement sur une limite).
- Robustesse : réestimation en excluant les ventes à moins de 50 m d'une limite de
  zone (la carte est établie au 1/50 000). Limite de zone = limite du polygone qui
  contient la vente ; pour une vente hors zone argileuse, présence d'un polygone du
  département à moins de 50 m. Définition approchée : la limite entre deux polygones de
  même niveau compte aussi.

## 4. Comptage préalable, avant d'écrire le modèle

Dès les données disponibles : nombre de ventes par commune et par classe, nombre de
**communes mixtes** (ventes en zone « fort » et dans les autres zones : faible, moyen ou hors zone argileuse) et nombre
de communes qui passeraient les seuils de la section 6. Si ce nombre est trop faible,
les seuils ou le périmètre sont revus avant d'aller plus loin.

## 5. Modèle global (trois catégories)

```
log(prix/m²) = β_moyen · moyen + β_fort · fort
             + log(surface bâtie) + log(1 + terrain) + terrain_nul
             + indicatrices du nombre de pièces (1 à 6 et plus)
             + effet fixe commune × trimestre
```

- **Référence : « faible » ou « hors zone argileuse ».**
- L'effet fixe commune × trimestre compare des maisons vendues dans la même commune,
  le même trimestre.
- Erreurs standard groupées par commune ; estimation avec `pyfixest`.
- Lecture : décote en % = exp(β) − 1.
- **Contraste « fort − moyen »** : écart de log-prix β_fort − β_moyen, et son effet
  exp(β_fort − β_moyen) − 1. Variance = V(β_fort) + V(β_moyen) − 2 Cov(β_fort, β_moyen),
  lue dans la matrice de variance groupée par commune ; IC à 95 % et p-valeur par la loi
  de Student (nombre de communes − 1). C'est la décote annoncée, le chiffre phare de
  l'app : l'écart entre deux zones exposées (voir les limites). Calculé pour le modèle
  principal et chaque variante qui contient « moyen » et « fort ».
- **Modèle « fort contre tout le reste »** : une seule indicatrice « fort », référence =
  niveaux 0, 1 et 2, même spécification. C'est la définition de la prime par commune
  (section 6) : le résultat global est ainsi comparable aux primes communales.
- **Test placebo** : même modèle avec en plus l'indicatrice « bascule » (section 3).
  Une décote sur ces ventes signifierait que le marché perçoit le risque sans la
  carte officielle, ou que la zone est corrélée à autre chose. Résultat dans
  `resume_global.json` uniquement, marqué « indicatif, faible puissance (861 ventes,
  8 communes) » : la carte 2026 fait basculer vers « fort » 861 ventes, dans
  8 communes (3 en 31, 5 en 77, aucune en 47 et 82) ; elle reclasse aussi des ventes vers le
  bas (3 → 2 : 378 en 31, 187 en 77). Au total, la carte 2026 change le niveau de 1 474
  ventes sur 82 525 (1,79 %, soit environ 2 %) : 894 vers un niveau plus fort, 580 vers un
  niveau moins fort (clé `carte_2026` de `resume_global.json`). **L'IC repose sur 8 communes** : les erreurs
  groupées par commune sont peu fiables avec si peu de groupes. Le signe du coefficient
  est positif, ce qui suggère une hétérogénéité de quartiers au sein des communes ; les
  écarts ne sont pas causaux. Ces deux avertissements figurent dans le JSON.
- **Variante « réforme 2025 »** : même modèle avec en plus le terme
  `β_fort_2025 · fort × (vente en 2025)`. β_fort y mesure la décote de 2021 à 2024 et
  β_fort_2025 l'écart en 2025 : un β_fort_2025 négatif signifierait que la décote se
  creuse quand l'information est remise à l'acheteur. L'effet fixe commune × trimestre
  absorbe déjà le niveau général des prix en 2025 ; le terme ne capte que l'évolution
  de l'écart « fort ». Résultat publié dans `resume_global.json` uniquement, jamais par
  commune, et présenté comme un **indice** : une seule année après la réforme.
  Le modèle principal, sans ce terme, reste la référence pour la décote globale.

## 6. Prime par commune

- **Comparaison : « fort » contre tout le reste** (niveaux 0, 1 et 2 : hors zone
  argileuse, faible, moyen), pour garder assez de ventes dans la zone de référence de
  chaque commune. Ce reste est très majoritairement « moyen » (voir les limites).
- Même modèle avec un terme `fort × commune` : les contrôles sont estimés sur
  l'ensemble des ventes, chaque commune a son propre coefficient.
- **Spécification** : celle du modèle « fort contre tout le reste » (section 5), en une
  seule régression : un terme « fort » propre à chaque commune estimable, un terme commun
  pour les ventes « fort » des autres communes, mêmes contrôles et mêmes effets fixes
  commune × trimestre. La prime de la commune = exp(β) − 1 de son terme.
- **Erreurs groupées par section cadastrale** (10 premiers caractères de `id_parcelle` :
  commune, préfixe, section) et non par commune : une prime communale ne repose que sur
  les ventes d'une commune, un groupement par commune n'aurait qu'un seul groupe. Chaque
  prime est un coefficient propre à sa commune ; son erreur ne dépend donc que des
  sections de cette commune. IC par la loi de Student à (sections de la commune − 1)
  degrés de liberté.
- **Repli HC1** : une commune qui compte moins de `min_sections_groupement` sections
  (10, dans la config) reçoit des erreurs robustes à l'hétéroscédasticité HC1 (sans
  groupement), avec (ventes de la commune − 1) degrés de liberté. Ces erreurs ignorent la
  corrélation entre ventes voisines et sont donc plus optimistes : le nombre de communes
  concernées est consigné dans `resume_global.json` (`erreurs`) et la colonne `erreurs`
  du fichier des primes indique `sections` ou `hc1`.
- Prime publiée seulement si la commune compte au moins **15 ventes « fort »**,
  **15 ventes de référence** (niveaux 0, 1 et 2) et **50 ventes au total**, avec un IC à 95 %.
- Sinon : commune « non estimable », avec son motif (pas de ventes dans les deux
  zones, ou effectifs insuffisants).
- **Statut de décote** (communes estimables), à partir de l'IC à 95 % de la prime :
  - **décote** : IC entièrement sous 0 ;
  - **pas de décote** : borne basse de l'IC au-dessus du seuil `seuil_pas_de_decote`
    (−3 % par défaut, dans la config) : une décote éventuelle serait au plus faible ;
  - **indéterminé** : tout le reste (IC trop large pour conclure).

  « Pas de décote » n'est pas « IC contient 0 » : une commune peu informative (IC de
  −20 % à +10 %) est indéterminée, pas classée sans décote.
- **Sinistralité** : comparée à la médiane de `catnat_depuis_2015` parmi les communes
  estimables. « Supérieure à la médiane » = strictement au-dessus.
- **Quadrants** (communes « décote » ou « pas de décote » seulement ; les indéterminées
  sont comptées à part) :

| | Décote | Pas de décote |
|---|---|---|
| **Sinistralité supérieure à la médiane** | Risque intégré | Angle mort |
| **Sinistralité inférieure ou égale à la médiane** | Décote à expliquer | Cohérent |

**Définitions à reprendre à l'identique partout (app, simulateur, README) :**

| Résultat | Zone comparée | Référence |
|---|---|---|
| Décote globale « moyen » | moyen | faible ou hors zone argileuse |
| Décote globale « fort » | fort | faible ou hors zone argileuse |
| Décote globale « fort − moyen » (chiffre phare) | fort | moyen |
| Global « fort contre tout le reste » (comparable aux primes) | fort | hors zone, faible ou moyen |
| Prime par commune | fort | tout le reste : faible, moyen ou hors zone argileuse |

Le simulateur n'utilise que la prime par commune (référence « tout le reste ») :
il ne s'applique donc qu'aux communes estimables.

## 7. CatNat sécheresse (GASPAR)

Par commune : nombre d'arrêtés de reconnaissance pour la sécheresse (mouvements de
terrain différentiels consécutifs à la sécheresse et à la réhydratation des sols),
nombre depuis 2015, date du dernier arrêté. Codes INSEE harmonisés sur le même
millésime du code officiel géographique que DVF et les contours.

- **Libellé retenu : « Sécheresse » uniquement.** « Mouvement de Terrain » est écarté : il
  reste stable (35 à 165 arrêtés par an) et ne suit pas les épisodes de sécheresse (35 en
  2022, contre 7 279 pour « Sécheresse »).
- **Événement** = triplet distinct (code commune, `date_debut`, `date_fin`) : plusieurs
  arrêtés (reconnaissance, modificatif) pour le même événement comptent une fois.
  `catnat_depuis_2015` compte les événements dont `date_debut` est le 1er janvier 2015 ou
  après ; `catnat_total` tous les événements ; `catnat_dernier` est la date de fin du
  dernier événement.
- **Rapprochement des codes** : les codes GASPAR sont comparés à ceux des contours. Un
  fichier optionnel `config/fusions_communes.csv` (`ancien_code`, `nouveau_code`)
  rapproche les communes fusionnées avant le comptage. Le nombre de codes du périmètre
  non rapprochés est consigné dans `resume_global.json` (`catnat.codes_perimetre`).
- **Seuil de sinistralité** = médiane de `catnat_depuis_2015` parmi les communes
  estimables ; « supérieure » = strictement au-dessus. Une commune sans arrêté compte 0.
  Observé : médiane = 2 arrêtés ; les arrêtés étant des nombres entiers, « sinistralité
  supérieure à la médiane » signifie **3 arrêtés ou plus depuis 2015**, et c'est le
  libellé affiché dans l'app.
- **Quadrants** : calculés par le pipeline pour les communes « décote » et « pas de
  décote ». Une commune non estimable ou « indéterminée » n'a pas de quadrant.

## 8. Sorties

`data/processed/resume_global.json` contient notamment :
- sous `modeles_globaux` : `principal`, `fort_contre_reste`, `sans_limite`,
  `placebo_bascule` et `reforme_2025` ; pour chacun, les coefficients (β, erreur
  standard, IC à 95 %, effet exp(β) − 1 en fraction, p-valeur), le nombre de ventes et de
  communes utilisées, et le contraste `contraste_fort_moins_moyen` quand il existe ;
- β_moyen, β_fort et β_bascule, avec IC à 95 % et effectifs ;
- β_fort_2025 (variante « réforme 2025 »), avec IC à 95 % et nombre de ventes « fort »
  en 2025, marqué comme indice ;
- la période et le nombre de ventes après chaque étape de nettoyage ;
- `n_communes_estimables` ;
- `n_significatives_decote` et `n_significatives_prime` (IC qui ne contient pas 0) ;
- `n_attendu_hasard` = 0,05 × `n_communes_estimables` (environ la moitié dans
  chaque sens), pour comparer avec le nombre observé ;
- `n_decote`, `n_pas_de_decote`, `n_indetermine` (statut de décote) et le nombre de
  communes par quadrant ;
- `mediane_sinistralite` et `seuil_pas_de_decote`.

## 9. Limites

- **Corrélation, pas causalité** : la géologie suit le relief (plateaux, vallées,
  coteaux), qui joue aussi sur le prix au sein d'une même commune.
- **Tests multiples** : chaque commune estimable est un test à 95 %. Même sans aucun
  effet réel, environ 5 % des communes testées paraîtraient significatives par hasard,
  soit jusqu'à 80 communes si les 1 600 étaient estimables. Une commune isolée
  significative n'est donc pas une preuve ; le nombre observé est comparé au nombre
  attendu par hasard dans `resume_global.json`.
- **Excès de communes significatives** : sur 193 communes estimables, 31 primes sont
  significatives (16 en décote, 15 en prime), contre environ 10 attendues par hasard
  (4,8 par sens). L'excès est symétrique : il ne signale pas une décote générale. Le
  diagnostic par type d'erreurs (`diagnostic_erreurs` dans `resume_global.json`) écarte
  le repli HC1 : la part de significatives est proche dans les communes à erreurs
  groupées par section (17,0 %) et en HC1 (14,8 %), et les IC sont plus larges en HC1
  (25,7 contre 21,3 points). Interprétation retenue : une hétérogénéité de quartiers au
  sein des communes (au-delà du niveau commune × trimestre), cohérente avec le placebo.
  Les primes communales sont donc des **écarts de prix observés entre la zone forte et le
  reste de la commune**, jamais l'effet de l'argile.
- **Les décotes se trouvent surtout dans les communes peu sinistrées** : parmi les
  communes classées en quadrant, 14 sont en « décote à expliquer » (décote, sinistralité
  inférieure ou égale à la médiane) contre 2 en « risque intégré » (décote, sinistralité
  supérieure) ; côté « pas de décote », 18 « cohérent » et 9 « angle mort ». Les écarts de
  prix ne suivent donc pas la sinistralité : cela va dans le sens de l'interprétation
  « écarts entre quartiers » plutôt que d'un prix du risque lié à l'historique de
  sécheresse.
- **Sinistralité sécheresse 2015-2023** : GASPAR ne contient aucune sécheresse reconnue
  après 2023 (délai de reconnaissance). L'indicateur couvre donc 2015-2023 et non
  jusqu'en 2025 ; dans l'app : « arrêtés sécheresse 2015-2023 ». Les épisodes récents
  (2024-2025) ne sont pas encore reconnus et n'apparaissent pas.
- Le point de la vente est le centroïde de la parcelle, et la carte est établie au
  1/50 000 : des ventes proches d'une limite de zone peuvent être mal classées.
- **Deux maisons identiques sur une même parcelle** (mêmes surface bâtie et nombre de
  pièces) sont comptées comme une seule maison, la mutation est donc conservée à tort.
  Cas rare, non mesuré.
- **La décote mesurée est un écart entre deux zones exposées** : la référence de la prime
  par commune (hors zone argileuse, faible, moyen) est très majoritairement « moyen »
  (hors zone et faible représentent moins de 8 % des ventes). La décote est donc l'écart
  entre « fort » et « moyen », deux zones déjà exposées, et non l'écart entre une zone
  exposée et une zone sans exposition.
- **La référence « hors zone + faible » est un petit groupe aux caractéristiques
  propres** (moins de 8 % des ventes, souvent des communes ou des quartiers à part). Les
  écarts « moyen » et « fort » contre cette référence peuvent donc refléter autre chose
  que l'argile ; c'est pourquoi le chiffre phare est le contraste « fort − moyen », entre
  deux groupes plus nombreux et plus proches.
- **Référence hétérogène selon les départements** : les cartes ne comptent aucun polygone
  « faible » dans le 77 et le 82 (2020 et 2026) ni dans le 47 (2026). Dans ces départements,
  la référence « faible ou hors zone argileuse » est composée uniquement de maisons hors
  zone argileuse ; elle n'a pas la même composition qu'en Haute-Garonne (31).
- Seuils minimaux de ventes : ils limitent les estimations fragiles mais ne les
  suppriment pas.
- **Réforme 2025** : une seule année après la réforme, et d'autres changements de 2025
  (taux d'intérêt, sécheresses récentes, couverture médiatique) peuvent jouer sur
  l'écart « fort ». β_fort_2025 est un indice, pas une mesure de l'effet de la réforme.
  Les ventes de fin 2025 peuvent aussi manquer dans DVF au moment du téléchargement.
- Seules les ventes simples de maisons sont étudiées ; les résultats ne s'étendent
  pas aux appartements ni aux terrains à bâtir.
