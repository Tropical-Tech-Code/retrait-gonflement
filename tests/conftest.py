"""Petites données construites dans les tests, au format de data/processed/ (aucune donnée réelle)."""

import json

import pandas as pd
import pytest

IC95 = "ic95_effet"


def coefficient(effet, bas, haut):
    return {"effet": effet, IC95: [bas, haut], "p_valeur": 0.5, "n_ventes_terme": 100}


def resume_test() -> dict:
    return {
        "periode": [2021, 2025],
        "date_generation": "2026-10-16",
        "modeles_globaux": {
            "principal": {
                "coefficients": {
                    "moyen": coefficient(-0.0338, -0.0671, 0.0008),
                    "fort": coefficient(-0.0250, -0.0509, 0.0016),
                },
                "contraste_fort_moins_moyen": coefficient(0.0091, -0.0289, 0.0486),
            },
            "fort_contre_reste": {"coefficients": {"fort": coefficient(0.0070, -0.0297, 0.0451)}},
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
        "primes_communes": {"seuils": {"min_ventes_fort": 15, "min_ventes_reference": 15, "min_ventes_total": 50}},
        "catnat": {"libelle": "Sécheresse", "periode": "2015-2023"},
        "nettoyage": {"n_mutations": 1000, "n_ventes_retenues": 300, "etapes": []},
        "sources": {"note_date": "Date de téléchargement.", "liste": []},
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
        ligne("31006", "Fonsorbes", "non_estimable", motif="une_seule_zone", n_ventes=80, n_fort=80),
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
    (tmp_path / "contours.geojson").write_text(json.dumps(geojson_test(communes["code_insee"])), encoding="utf-8")
    (tmp_path / "departements.geojson").write_text(json.dumps(geojson_test(["31"])), encoding="utf-8")
    (tmp_path / "resume_global.json").write_text(json.dumps(resume_test()), encoding="utf-8")
    return tmp_path
