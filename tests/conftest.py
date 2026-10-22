"""Petites données construites dans les tests, au format de data/processed/ (aucune donnée réelle)."""

import json

import pandas as pd
import pytest

IC95 = "ic95_effet"


def coefficient(effet, bas, haut, p=0.5):
    return {"effet": effet, IC95: [bas, haut], "p_valeur": p, "n_ventes_terme": 100}


def resume_test() -> dict:
    return {
        "periode": [2021, 2025],
        "date_generation": "2026-10-16",
        "modeles_globaux": {
            "principal": {
                "n_ventes": 280,
                "coefficients": {
                    "moyen": coefficient(-0.0338, -0.0671, 0.0008),
                    "fort": coefficient(-0.0250, -0.0509, 0.0016),
                },
                "contraste_fort_moins_moyen": coefficient(0.0091, -0.0289, 0.0486),
            },
            "fort_contre_reste": {"coefficients": {"fort": coefficient(0.0070, -0.0297, 0.0451)}},
            "sans_limite": {"contraste_fort_moins_moyen": coefficient(0.0137, -0.0350, 0.0640)},
            "reforme_2025": {"statut": "indice : une seule année après la réforme"},
            "placebo_bascule": {
                "statut": "indicatif, faible puissance (853 ventes, 8 communes)",
                "coefficients": {"bascule": coefficient(0.0356, 0.0167, 0.0548, 0.0003)},
                "avertissements": ["l'IC repose sur 8 communes", "le signe positif suggère des quartiers"],
            },
        },
        "n_communes_estimables": 4,
        "n_significatives_decote": 1,
        "n_significatives_prime": 1,
        "n_attendu_hasard": 0.2,
        "n_attendu_par_sens": 0.1,
        "n_decote": 1,
        "n_pas_de_decote": 1,
        "n_indetermine": 2,
        "seuil_pas_de_decote": -0.03,
        "seuil_prix_median": 5,
        "mediane_sinistralite": 2.0,
        "n_par_quadrant": {"Risque intégré": 1, "Angle mort": 1, "Décote à expliquer": 0, "Cohérent": 0},
        "primes_communes": {
            "seuils": {"min_ventes_fort": 15, "min_ventes_reference": 15, "min_ventes_total": 50},
            "par_departement": {"31": {}, "47": {}, "77": {}, "82": {}},
        },
        "catnat": {"libelle": "Sécheresse", "periode": "2015-2023", "annee_debut_max": 2023},
        "carres": {
            "marge_cases": 1.3,
            "zones": {"sud_ouest": {"departements": ["31", "47", "82"], "maille_km": 3.0,
                                    "largeur_carre_px": 13.0, "emprise": [0.5, 42.9, 2.5, 43.3]},
                      "seine_et_marne": {"departements": ["77"], "maille_km": 3.0,
                                         "largeur_carre_px": 26.0, "emprise": [1.8, 42.9, 2.6, 43.3]}},
            "etiquettes": {"31": {"lon": 1.4, "lat": 43.05}, "77": {"lon": 2.2, "lat": 43.05}},
        },
        "nettoyage": {"n_mutations": 1000, "n_ventes_retenues": 300, "etapes": []},
        "sources": {"note_date": "Date de téléchargement.", "liste": [
            {"cle": "dvf", "nom": "DVF géolocalisées (Etalab)", "millesime": "ventes 2021-2025",
             "date_telechargement": "2026-10-15"},
            {"cle": "rga_2020", "nom": "Carte RGA 2020 (Géorisques / BRGM)", "millesime": "2020",
             "date_telechargement": "2026-10-16"},
            {"cle": "rga_2026", "nom": "Carte RGA 2026 (Géorisques / BRGM)", "millesime": "2026",
             "date_telechargement": "2026-10-15"},
            {"cle": "gaspar", "nom": "GASPAR (Géorisques)", "millesime": "catnat_gaspar_2026-10-05.csv",
             "date_telechargement": "2026-10-16"},
            {"cle": "communes", "nom": "Contours des communes (API Géo)", "millesime": "version de l'API Géo",
             "date_telechargement": None},
        ]},
        "zones_rga": {
            "31": {"n_ventes": 100, "part_0": 0.02, "part_1": 0.004, "part_2": 0.5, "part_3": 0.476},
            "77": {"n_ventes": 200, "part_0": 0.07, "part_1": 0.004, "part_2": 0.4, "part_3": 0.526},
        },
        "carte_2026": {"n_ventes": 1000, "n_change": 18, "n_vers_plus_fort": 10, "n_vers_moins_fort": 8,
                       "part_change": 0.018},
    }


def communes_test() -> pd.DataFrame:
    """Six communes : décote (sinistrée), pas de décote (sinistrée), indéterminée,
    estimable sans arrêté, non estimable (effectifs), non estimable (une seule zone)."""
    def ligne(code, nom, statut, **kw):
        base = {
            "code_insee": code, "nom": nom, "departement": "31", "n_ventes": 100, "n_fort": 40,
            "n_moyen": 50, "n_faible": 5, "n_hors_zone": 5, "prix_m2_median": 2500.0, "statut": statut,
            "motif": None, "prime": None, "ic_bas": None, "ic_haut": None, "significatif": None,
            "statut_decote": None, "catnat_total": 0, "catnat_depuis_2015": 0, "catnat_dernier": pd.NaT,
            "sinistralite_sup_mediane": pd.NA, "quadrant": None,
        }
        return base | kw

    dernier = pd.Timestamp("2023-09-30")
    lignes = [
        ligne("31001", "Aucamville", "estimable", prime=-0.12, ic_bas=-0.20, ic_haut=-0.03, significatif="decote",
              statut_decote="decote", catnat_total=6, catnat_depuis_2015=5, catnat_dernier=dernier,
              sinistralite_sup_mediane=True, quadrant="Risque intégré"),
        ligne("31002", "Balma", "estimable", prime=0.02, ic_bas=-0.01, ic_haut=0.05, significatif="non",
              statut_decote="pas_de_decote", catnat_total=4, catnat_depuis_2015=3, catnat_dernier=dernier,
              sinistralite_sup_mediane=True, quadrant="Angle mort"),
        ligne("31003", "Cugnaux", "estimable", prime=-0.05, ic_bas=-0.20, ic_haut=0.10, significatif="non",
              statut_decote="indetermine", catnat_total=2, catnat_depuis_2015=2, catnat_dernier=dernier,
              sinistralite_sup_mediane=False),
        ligne("31004", "Daux", "estimable", prime=0.15, ic_bas=0.05, ic_haut=0.25, significatif="prime",
              statut_decote="pas_de_decote", sinistralite_sup_mediane=False, quadrant="Cohérent"),
        ligne("31005", "Escalquens", "non_estimable", motif="effectifs_insuffisants", n_ventes=30, n_fort=8,
              catnat_total=1, catnat_depuis_2015=1, catnat_dernier=dernier),
        # seule commune de la zone Seine-et-Marne (département 77) des données de test
        ligne("31006", "Fonsorbes", "non_estimable", motif="une_seule_zone", n_ventes=80, n_fort=80,
              departement="77"),
    ]
    return pd.DataFrame(lignes)


def carre(x):
    return [[[x, 43.0], [x + 0.1, 43.0], [x + 0.1, 43.1], [x, 43.1], [x, 43.0]]]


def geojson_test(codes) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"code_insee": code},
             "geometry": {"type": "Polygon", "coordinates": carre(1.0 + 0.2 * i)}}
            for i, code in enumerate(codes)
        ],
    }


@pytest.fixture
def dossier_processed(tmp_path):
    """Dossier au format de data/processed/, sous tmp_path (jamais le vrai)."""
    communes = communes_test()
    communes.to_parquet(tmp_path / "communes.parquet", index=False)
    (tmp_path / "carres.geojson").write_text(json.dumps(geojson_test(communes["code_insee"])), encoding="utf-8")
    (tmp_path / "resume_global.json").write_text(json.dumps(resume_test()), encoding="utf-8")
    return tmp_path
