import json

import pandas as pd
import pytest

import donnees
from conftest import resume_test

LECTEURS = {
    "communes.parquet": donnees.lire_communes,
    "carres.geojson": lambda d: donnees.lire_geojson(d, "carres.geojson", "code_insee"),
    "resume_global.json": donnees.lire_resume,
}


def test_lecture_des_trois_fichiers(dossier_processed, monkeypatch):
    monkeypatch.setenv(donnees.VARIABLE_DOSSIER, str(dossier_processed))
    tout = donnees.charger_tout()
    assert len(tout.communes) == 6
    assert len(tout.carres["features"]) == 6
    assert tout.resume["n_communes_estimables"] == 4


def test_l_app_ne_lit_ni_contours_ni_departements(dossier_processed, monkeypatch):
    # ces fichiers existent dans data/processed/ (produits par le pipeline) mais l'app ne les ouvre pas
    for nom in ("contours.geojson", "departements.geojson"):
        assert not (dossier_processed / nom).exists()
    lus = []
    ouvrir = donnees.Path.read_text

    def espion(self, *args, **kwargs):
        lus.append(self.name)
        return ouvrir(self, *args, **kwargs)

    monkeypatch.setattr(donnees.Path, "read_text", espion)
    donnees.lire_geojson(dossier_processed, "carres.geojson", "code_insee")
    donnees.lire_resume(dossier_processed)
    assert not {"contours.geojson", "departements.geojson"} & set(lus)
    source = (donnees.RACINE / "app").rglob("*.py")
    assert not [p.name for p in source if "departements.geojson" in p.read_text(encoding="utf-8")
                or "contours.geojson" in p.read_text(encoding="utf-8")]


def test_dossier_par_defaut_est_data_processed(monkeypatch):
    monkeypatch.delenv(donnees.VARIABLE_DOSSIER, raising=False)
    assert donnees.dossier() == donnees.RACINE / "data" / "processed"


def test_colonne_manquante_nommee(dossier_processed):
    communes = pd.read_parquet(dossier_processed / "communes.parquet").drop(columns=["quadrant", "prime"])
    communes.to_parquet(dossier_processed / "communes.parquet", index=False)
    with pytest.raises(donnees.ErreurDonneesApp) as e:
        donnees.lire_communes(dossier_processed)
    assert "communes.parquet" in str(e.value)
    assert "prime" in str(e.value) and "quadrant" in str(e.value)


@pytest.mark.parametrize("nom", list(LECTEURS))
def test_fichier_obligatoire_absent(dossier_processed, nom):
    (dossier_processed / nom).unlink()
    with pytest.raises(donnees.ErreurDonneesApp, match=f"Fichier manquant : data/processed/{nom}"):
        LECTEURS[nom](dossier_processed)


def test_carres_sans_code_insee(dossier_processed):
    geojson = json.loads((dossier_processed / "carres.geojson").read_text(encoding="utf-8"))
    geojson["features"][0]["properties"] = {}
    (dossier_processed / "carres.geojson").write_text(json.dumps(geojson), encoding="utf-8")
    with pytest.raises(donnees.ErreurDonneesApp, match="code_insee"):
        donnees.lire_geojson(dossier_processed, "carres.geojson", "code_insee")


def test_resume_sans_etiquettes_des_departements(dossier_processed):
    resume = resume_test()
    del resume["carres"]["etiquettes"]
    (dossier_processed / "resume_global.json").write_text(json.dumps(resume), encoding="utf-8")
    with pytest.raises(donnees.ErreurDonneesApp, match="carres.etiquettes"):
        donnees.lire_resume(dossier_processed)


def test_resume_cle_manquante(dossier_processed):
    resume = resume_test()
    del resume["mediane_sinistralite"]
    del resume["modeles_globaux"]["principal"]["contraste_fort_moins_moyen"]
    (dossier_processed / "resume_global.json").write_text(json.dumps(resume), encoding="utf-8")
    with pytest.raises(donnees.ErreurDonneesApp) as e:
        donnees.lire_resume(dossier_processed)
    assert "mediane_sinistralite" in str(e.value)
    assert "contraste_fort_moins_moyen" in str(e.value)


def test_json_illisible(dossier_processed):
    (dossier_processed / "resume_global.json").write_text("{pas du json", encoding="utf-8")
    with pytest.raises(donnees.ErreurDonneesApp, match="illisible"):
        donnees.lire_resume(dossier_processed)
