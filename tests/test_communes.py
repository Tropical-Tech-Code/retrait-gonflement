import json
from pathlib import Path

import httpx
import pytest

from retrait_gonflement.data import communes
from retrait_gonflement.data.commun import ErreurDonnees

FIXTURE = Path(__file__).parent / "fixtures" / "communes_exemple.geojson"

CONFIG = {
    "perimetre": {"departements": ["31", "47"]},
    "sources": {"communes": {"url": "https://exemple.test/{departement}.geojson"}},
}


def client_simule(contenu: bytes, appels: list | None = None) -> httpx.Client:
    def repondre(requete: httpx.Request) -> httpx.Response:
        if appels is not None:
            appels.append(str(requete.url))
        return httpx.Response(200, content=contenu)

    return httpx.Client(transport=httpx.MockTransport(repondre))


def test_url_reelle_de_la_config():
    url = communes.construire_url(communes.charger_config(), "82")
    assert "/departements/82/communes" in url


def test_url_vide_refusee():
    with pytest.raises(ErreurDonnees):
        communes.construire_url({"sources": {"communes": {"url": ""}}}, "31")


def test_valider_fixture():
    assert communes.valider_geojson(FIXTURE.read_bytes()) == 2


@pytest.mark.parametrize(
    "contenu",
    [
        b"pas du json",
        b'{"type": "Feature"}',
        b'{"type": "FeatureCollection", "features": []}',
        b'{"type": "FeatureCollection", "features": [{"properties": {"code": "1"}, "geometry": {}}]}',
        b'{"type": "FeatureCollection", "features": [{"properties": {"code": "1", "nom": "A"}, "geometry": null}]}',
    ],
)
def test_valider_geojson_invalide(contenu):
    with pytest.raises(ErreurDonnees):
        communes.valider_geojson(contenu)


def test_telecharger_un_fichier_par_departement(tmp_path):
    appels: list[str] = []
    ecrits = communes.telecharger_communes(CONFIG, client_simule(FIXTURE.read_bytes(), appels), tmp_path)
    assert sorted(p.name for p in ecrits) == ["communes_31.geojson", "communes_47.geojson"]
    assert len(appels) == 2
    assert json.loads(ecrits[0].read_bytes())["type"] == "FeatureCollection"


def test_telecharger_ne_retelecharge_pas(tmp_path):
    communes.telecharger_communes(CONFIG, client_simule(FIXTURE.read_bytes()), tmp_path)
    appels: list[str] = []
    assert communes.telecharger_communes(CONFIG, client_simule(FIXTURE.read_bytes(), appels), tmp_path) == []
    assert appels == []


def test_telecharger_refuse_contenu_invalide_sans_ecrire(tmp_path):
    with pytest.raises(ErreurDonnees):
        communes.telecharger_communes(CONFIG, client_simule(b"{}"), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_resumer_fichier_ne_montre_pas_le_contenu():
    resume = communes.resumer_fichier(FIXTURE)
    assert "2 communes" in resume
    assert "Exemplville" not in resume
