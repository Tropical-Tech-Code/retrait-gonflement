# Retrait-Gonflement

**Statut : en construction**

Le marché immobilier applique-t-il une décote aux maisons situées en zone
d'exposition forte au retrait-gonflement des argiles ? Résultat global : la
« prime de risque implicite ». Carte par commune : l'écart de prix observé entre la zone
forte et le reste de la commune.

## Le signal étudié

À compléter.

## Sources de données

- Demandes de valeurs foncières géolocalisées (DVF, Etalab)
- Cartes d'exposition au retrait-gonflement des argiles (Géorisques / BRGM)
- Arrêtés de catastrophe naturelle sécheresse (GASPAR, Géorisques)
- Contours des communes (API Géo, issus d'ADMIN EXPRESS de l'IGN)

### Récupération des données

DVF et les contours des communes se téléchargent par commande :

```
uv run python -m retrait_gonflement.data.dvf --departement 82 --annee 2024
uv run python -m retrait_gonflement.data.communes --departement 82
```

Les cartes d'exposition RGA n'ont pas d'URL stable (formulaire Géorisques) : elles se
déposent à la main.

1. Sur Géorisques, télécharger pour chaque département étudié (31, 47, 77, 82) le
   Shapefile en Lambert 93 de la carte d'exposition.
2. Déposer chaque archive `.zip` telle quelle (sans la renommer ni la décompresser) dans
   `data/raw/rga/2026/` pour la carte 2026, par exemple `AleaRG_2025_31_L93.zip`, ou dans
   `data/raw/rga/2020/` pour la carte 2020.
3. Vérifier le dépôt : `uv run python -m retrait_gonflement.data.rga --millesime 2026`.
   La commande signale les départements manquants et les archives incomplètes
   (il faut les 5 fichiers `.shp`, `.shx`, `.dbf`, `.prj`, `.cpg`).

## Démo

Lien et capture ou GIF : à compléter.

## Méthodologie et limites

À compléter.

## Installation

À compléter.
