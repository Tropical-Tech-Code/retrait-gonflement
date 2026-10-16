import io
import zipfile

import httpx
import pytest

from retrait_gonflement.data import gaspar
from retrait_gonflement.data.commun import ErreurDonnees

CONFIG = {
    "sources": {
        "gaspar": {
            "url": "https://exemple.test/gaspar.zip",
            "table": "catnat_gaspar_*.csv",
            "libelle_risque": "Sécheresse",
        }
    }
}

ENTETE = (
    "id_gaspar;code_commune;libelle_commune;num_risque_jo;lib_risque_jo;"
    "date_debut;date_fin;date_signature_arrete;date_publication_jo;date_modification"
)
LIGNES = [
    "1;31001;Exemplville;11;Sécheresse;2022-05-01;2022-09-30;2023-01-10;2023-01-20;2023-02-01",
    "2;31001;Exemplville;10;Inondations;2021-06-01;2021-06-05;2021-07-01;2021-07-10;2021-08-01",
    "3;31002;Demoville;11;Sécheresse;2018-04-01;2018-09-30;2019-01-10;2019-01-20;2019-02-01",
]


def archive(tables: dict[str, str] | None = None) -> bytes:
    """Zip factice : la table catnat plus deux autres tables, comme dans l'archive réelle."""
    if tables is None:
        tables = {"catnat_gaspar_2026-10-05.csv": "\n".join([ENTETE, *LIGNES]) + "\n"}
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        z.writestr("risq_gaspar_2026-10-05.csv", "a;b\n1;2\n")
        z.writestr("azi_gaspar_2026-10-05.csv", "a;b\n1;2\n")
        for nom, contenu in tables.items():
            z.writestr(nom, contenu)
    return tampon.getvalue()


def client_simule(contenu: bytes, appels: list | None = None) -> httpx.Client:
    def repondre(requete: httpx.Request) -> httpx.Response:
        if appels is not None:
            appels.append(str(requete.url))
        return httpx.Response(200, content=contenu)

    return httpx.Client(transport=httpx.MockTransport(repondre))


def test_config_reelle():
    source = gaspar.charger_config()["sources"]["gaspar"]
    assert source["url"].startswith("https://www.data.gouv.fr/api/1/datasets/r/")
    assert source["table"] == "catnat_gaspar_*.csv"
    assert source["libelle_risque"] == "Sécheresse"


def test_valider_archive_ok():
    assert gaspar.valider_archive(archive(), CONFIG) == ("catnat_gaspar_2026-10-05.csv", 3)


def test_table_trouvee_quelle_que_soit_la_date():
    contenu = archive({"catnat_gaspar_2027-01-15.csv": "\n".join([ENTETE, LIGNES[0]]) + "\n"})
    assert gaspar.valider_archive(contenu, CONFIG) == ("catnat_gaspar_2027-01-15.csv", 1)


def test_table_dans_un_sous_dossier():
    contenu = archive({"export/catnat_gaspar_2026-10-05.csv": ENTETE + "\n" + LIGNES[0] + "\n"})
    assert gaspar.valider_archive(contenu, CONFIG)[0] == "catnat_gaspar_2026-10-05.csv"


def test_table_absente():
    with pytest.raises(ErreurDonnees, match="introuvable"):
        gaspar.valider_archive(archive({}), CONFIG)


def test_plusieurs_tables():
    contenu = archive({"catnat_gaspar_a.csv": ENTETE + "\n", "catnat_gaspar_b.csv": ENTETE + "\n"})
    with pytest.raises(ErreurDonnees, match="plusieurs"):
        gaspar.valider_archive(contenu, CONFIG)


def test_colonne_manquante():
    entete = ENTETE.replace("lib_risque_jo", "risque")
    contenu = archive({"catnat_gaspar_2026-10-05.csv": entete + "\n"})
    with pytest.raises(ErreurDonnees, match="lib_risque_jo"):
        gaspar.valider_archive(contenu, CONFIG)


def test_mauvais_separateur():
    contenu = archive({"catnat_gaspar_2026-10-05.csv": ENTETE.replace(";", ",") + "\n"})
    with pytest.raises(ErreurDonnees, match="séparateur"):
        gaspar.valider_archive(contenu, CONFIG)


def test_non_zip():
    with pytest.raises(ErreurDonnees, match="illisible"):
        gaspar.valider_archive(b"page html", CONFIG)


def test_telecharger_ecrit_l_archive(tmp_path):
    appels: list[str] = []
    ecrits = gaspar.telecharger_gaspar(CONFIG, client_simule(archive(), appels), tmp_path)
    assert [p.name for p in ecrits] == ["gaspar.zip"]
    assert appels == ["https://exemple.test/gaspar.zip"]
    assert not list(tmp_path.glob("*.tmp"))


def test_telecharger_ne_retelecharge_pas(tmp_path):
    gaspar.telecharger_gaspar(CONFIG, client_simule(archive()), tmp_path)
    appels: list[str] = []
    assert gaspar.telecharger_gaspar(CONFIG, client_simule(archive(), appels), tmp_path) == []
    assert appels == []


def test_telecharger_ecraser(tmp_path):
    gaspar.telecharger_gaspar(CONFIG, client_simule(archive()), tmp_path)
    appels: list[str] = []
    gaspar.telecharger_gaspar(CONFIG, client_simule(archive(), appels), tmp_path, ecraser=True)
    assert len(appels) == 1


def test_telecharger_refuse_archive_invalide_sans_ecrire(tmp_path):
    with pytest.raises(ErreurDonnees):
        gaspar.telecharger_gaspar(CONFIG, client_simule(b"page html"), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_url_vide_refusee(tmp_path):
    config = {"sources": {"gaspar": {**CONFIG["sources"]["gaspar"], "url": ""}}}
    with pytest.raises(ErreurDonnees, match="URL vide"):
        gaspar.telecharger_gaspar(config, client_simule(archive()), tmp_path)


def test_resumer_fichier_sans_donnees(tmp_path):
    chemin = tmp_path / "gaspar.zip"
    chemin.write_bytes(archive())
    resume = gaspar.resumer_fichier(chemin, CONFIG)
    assert "catnat_gaspar_2026-10-05.csv" in resume and "3 arrêtés" in resume
    assert "Exemplville" not in resume
