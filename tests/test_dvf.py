import gzip
from pathlib import Path

import httpx
import pytest

from retrait_gonflement.data import dvf

FIXTURE = Path(__file__).parent / "fixtures" / "dvf_exemple.csv"

CONFIG = {
    "perimetre": {"departements": ["31", "47"], "annee_debut": 2023, "annee_fin": 2024},
    "sources": {"dvf": {"url": "https://exemple.test/{annee}/{departement}.csv.gz"}},
}


def csv_gz(texte: str | None = None) -> bytes:
    return gzip.compress((texte or FIXTURE.read_text(encoding="utf-8")).encode("utf-8"))


def client_simule(contenu: bytes, appels: list | None = None) -> httpx.Client:
    def repondre(requete: httpx.Request) -> httpx.Response:
        if appels is not None:
            appels.append(str(requete.url))
        return httpx.Response(200, content=contenu)

    return httpx.Client(transport=httpx.MockTransport(repondre))


def test_charger_config_reelle():
    config = dvf.charger_config()
    assert config["perimetre"]["departements"] == ["31", "47", "77", "82"]
    assert config["estimation"]["seuil_pas_de_decote"] == -0.03
    assert "{annee}" in config["sources"]["dvf"]["url"]


def test_construire_url():
    assert dvf.construire_url(CONFIG, 2023, "31") == "https://exemple.test/2023/31.csv.gz"


def test_url_vide_refusee():
    config = {**CONFIG, "sources": {"dvf": {"url": ""}}}
    with pytest.raises(dvf.ErreurDonnees):
        dvf.construire_url(config, 2023, "31")


def test_fixture_contient_les_cas_attendus():
    lignes = FIXTURE.read_text(encoding="utf-8").splitlines()[1:]
    assert 18 <= len(lignes) <= 25
    texte = "\n".join(lignes)
    for motif in ("Appartement", "Echange", "Local industriel", "Dépendance"):
        assert motif in texte


def test_valider_colonnes_ok():
    dvf.valider_colonnes(csv_gz())


def test_valider_colonnes_manquantes():
    with pytest.raises(dvf.ErreurDonnees, match="latitude"):
        dvf.valider_colonnes(csv_gz("id_mutation,valeur_fonciere\n1,100\n"))


def test_valider_fichier_non_gzip():
    with pytest.raises(dvf.ErreurDonnees):
        dvf.valider_colonnes(b"pas un gzip")


def test_telecharger_ecrit_un_fichier_par_annee_et_departement(tmp_path):
    appels: list[str] = []
    ecrits = dvf.telecharger_dvf(CONFIG, client_simule(csv_gz(), appels), tmp_path)
    assert len(appels) == 4
    assert sorted(p.name for p in ecrits) == [
        "dvf_2023_31.csv.gz", "dvf_2023_47.csv.gz",
        "dvf_2024_31.csv.gz", "dvf_2024_47.csv.gz",
    ]
    assert not list(tmp_path.glob("*.tmp"))


def test_telecharger_ne_retelecharge_pas(tmp_path):
    dvf.telecharger_dvf(CONFIG, client_simule(csv_gz()), tmp_path)
    appels: list[str] = []
    assert dvf.telecharger_dvf(CONFIG, client_simule(csv_gz(), appels), tmp_path) == []
    assert appels == []


def test_telecharger_refuse_colonnes_manquantes_sans_ecrire(tmp_path):
    with pytest.raises(dvf.ErreurDonnees):
        dvf.telecharger_dvf(CONFIG, client_simule(csv_gz("a,b\n1,2\n")), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_resumer_fichier_ne_montre_pas_le_contenu(tmp_path):
    chemin = tmp_path / "dvf_2023_31.csv.gz"
    chemin.write_bytes(csv_gz())
    resume = dvf.resumer_fichier(chemin)
    assert "20 lignes" in resume and "Mo" in resume
    assert "Exemplville" not in resume


def test_telecharger_erreur_http(tmp_path):
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    with pytest.raises(httpx.HTTPStatusError):
        dvf.telecharger_dvf(CONFIG, client, tmp_path)
