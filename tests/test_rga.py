import io
import zipfile

import pytest

from retrait_gonflement.data import rga
from retrait_gonflement.data.commun import ErreurDonnees

CONFIG = {
    "perimetre": {"departements": ["31", "47"]},
    "sources": {
        "rga_2020": {"fichier": ""},
        "rga_2026": {"fichier": "AleaRG_2025_{departement}_L93.zip"},
    },
}

TOUTES_EXTENSIONS = [".shp", ".shx", ".dbf", ".prj", ".cpg"]


def zip_octets(extensions: list[str] = TOUTES_EXTENSIONS, base: str = "alea") -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        for ext in extensions:
            z.writestr(base + ext, b"contenu factice")
    return tampon.getvalue()


def deposer(dossier, deps=("31", "47"), contenu=None):
    for dep in deps:
        (dossier / f"AleaRG_2025_{dep}_L93.zip").write_bytes(contenu or zip_octets())


def test_config_reelle():
    config = rga.charger_config()
    noms = rga.noms_attendus(config, "2026")
    assert noms["82"] == "AleaRG_2025_82_L93.zip"
    assert set(noms) == {"31", "47", "77", "82"}


def test_millesime_2020_sans_source():
    with pytest.raises(ErreurDonnees, match="pas encore trouvée"):
        rga.noms_attendus(rga.charger_config(), "2020")


def test_millesime_inconnu():
    with pytest.raises(ErreurDonnees):
        rga.noms_attendus(CONFIG, "1999")


def test_valider_shapefile_complet():
    assert len(rga.valider_zip_shapefile(zip_octets())) == 5


def test_valider_shapefile_sans_cpg():
    with pytest.raises(ErreurDonnees, match=r"\.cpg"):
        rga.valider_zip_shapefile(zip_octets([".shp", ".shx", ".dbf", ".prj"]))


def test_valider_non_zip():
    with pytest.raises(ErreurDonnees, match="illisible"):
        rga.valider_zip_shapefile(b"pas un zip")


def test_depot_complet(tmp_path):
    deposer(tmp_path)
    chemins = rga.verifier_depot(CONFIG, "2026", tmp_path)
    assert [c.name for c in chemins] == ["AleaRG_2025_31_L93.zip", "AleaRG_2025_47_L93.zip"]


def test_departement_manquant_message_clair(tmp_path):
    deposer(tmp_path, deps=("31",))
    with pytest.raises(ErreurDonnees) as e:
        rga.verifier_depot(CONFIG, "2026", tmp_path)
    message = str(e.value)
    assert "AleaRG_2025_47_L93.zip" in message
    assert "AleaRG_2025_31_L93.zip" not in message


def test_tous_les_departements_manquants_listes_ensemble(tmp_path):
    with pytest.raises(ErreurDonnees) as e:
        rga.verifier_depot(CONFIG, "2026", tmp_path)
    assert "31" in str(e.value) and "47" in str(e.value)


def test_fichier_invalide_nomme(tmp_path):
    deposer(tmp_path)
    (tmp_path / "AleaRG_2025_47_L93.zip").write_bytes(b"page html")
    with pytest.raises(ErreurDonnees, match="AleaRG_2025_47_L93.zip"):
        rga.verifier_depot(CONFIG, "2026", tmp_path)


def test_resumer_fichier_ne_montre_pas_le_contenu(tmp_path):
    deposer(tmp_path, deps=("31",), contenu=zip_octets(base="secret"))
    resume = rga.resumer_fichier(tmp_path / "AleaRG_2025_31_L93.zip")
    assert "5 fichiers" in resume and "Mo" in resume
    assert "secret" not in resume
