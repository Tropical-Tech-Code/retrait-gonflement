import io
import zipfile

import pandas as pd
import pytest

from retrait_gonflement.data import catnat
from retrait_gonflement.data.commun import ErreurDonnees

CONFIG = {
    "sources": {"gaspar": {"table": "catnat_gaspar_*.csv", "libelle_risque": "Sécheresse"}},
}
ENTETE = "id_gaspar;code_commune;lib_risque_jo;date_debut;date_fin;date_signature_arrete"


def archive(chemin, lignes: list[str]):
    with zipfile.ZipFile(chemin, "w") as z:
        z.writestr("autre_table.csv", "a;b\n1;2\n")
        z.writestr("catnat_gaspar_2026-10-05.csv", "\n".join([ENTETE, *lignes]) + "\n")
    return chemin


LIGNES = [
    # 31001 : un événement de 2022 en deux arrêtés (reconnaissance + modificatif) = 1 événement
    "1;31001;Sécheresse;2022-05-01;2022-09-30;2023-01-10",
    "2;31001;Sécheresse;2022-05-01;2022-09-30;2023-03-01",
    "3;31001;Sécheresse;2018-04-01;2018-09-30;2019-01-10",
    "4;31001;Sécheresse;2010-04-01;2010-09-30;2011-01-10",       # avant 2015 : dans le total seulement
    "5;31001;Mouvement de Terrain;2022-06-01;2022-06-05;2022-07-01",  # autre libellé : écarté
    "6;31002;Sécheresse;2015-01-01;2015-03-31;2015-06-01",       # début le 1er janvier 2015 : compte
    "7;31002;Sécheresse;2014-12-31;2015-02-01;2015-06-01",       # début la veille : ne compte pas
    "8;31002;Sécheresse;2022-05-01;2022-09-30;2023-01-10",
    "9;31999;Sécheresse;2020-05-01;2020-09-30;2021-01-10",       # code absent des contours (dép. 31)
    "10;99001;Sécheresse;2020-05-01;2020-09-30;2021-01-10",      # hors périmètre
]


@pytest.fixture
def arrets(tmp_path):
    return catnat.lire_secheresse(archive(tmp_path / "gaspar.zip", LIGNES), CONFIG)


def test_lecture_garde_le_libelle_retenu_seulement(arrets):
    assert len(arrets) == 9  # 10 lignes, moins « Mouvement de Terrain »
    assert set(arrets.columns) == {"code_commune", "date_debut", "date_fin"}
    assert arrets["date_debut"].dtype.kind == "M"


def test_evenements_distincts(arrets):
    evt = catnat.evenements(arrets)
    assert len(evt) == 8  # les deux arrêtés du même événement ne comptent qu'une fois
    assert (evt["code_commune"] == "31001").sum() == 3


def test_comptage_depuis_2015_sur_date_debut(arrets):
    compte = catnat.compter_par_commune(catnat.evenements(arrets), 2015)
    assert compte.loc["31001", ["catnat_total", "catnat_depuis_2015"]].tolist() == [3, 2]
    assert compte.loc["31002", ["catnat_total", "catnat_depuis_2015"]].tolist() == [3, 2]
    assert compte.loc["31001", "catnat_dernier"] == pd.Timestamp("2022-09-30")


def test_fusions_rapprochent_et_dedoublonnent(arrets):
    # 31999 (ancienne commune) devient 31001 : son événement s'ajoute, s'il n'existe pas déjà
    evt = catnat.evenements(arrets, {"31999": "31001"})
    compte = catnat.compter_par_commune(evt, 2015)
    assert compte.loc["31001", "catnat_total"] == 4 and "31999" not in compte.index
    # même événement sous l'ancien et le nouveau code : compté une fois
    doublon = pd.concat([arrets, arrets.iloc[[0]].assign(code_commune="31999")], ignore_index=True)
    avec_doublon = catnat.compter_par_commune(catnat.evenements(doublon, {"31999": "31001"}), 2015)
    assert avec_doublon.loc["31001", "catnat_total"] == 4  # inchangé par le doublon


def test_codes_non_rapproches_du_perimetre(arrets):
    evt = catnat.evenements(arrets)
    bilan = catnat.rapprocher(evt, {"31001", "31002"}, ["31", "47"])
    # 31999 est dans le périmètre sans contour ; 99001 est hors périmètre et n'est pas compté
    assert bilan == {"n_codes_perimetre": 3, "n_codes_non_rapproches": 1, "n_evenements_non_rapproches": 1}
    apres = catnat.rapprocher(catnat.evenements(arrets, {"31999": "31001"}), {"31001", "31002"}, ["31"])
    assert apres["n_codes_non_rapproches"] == 0


def test_charger_fusions(tmp_path):
    assert catnat.charger_fusions(tmp_path / "absent.csv") == {}
    chemin = tmp_path / "fusions.csv"
    chemin.write_text("ancien_code,nouveau_code\n31999,31001\n", encoding="utf-8")
    assert catnat.charger_fusions(chemin) == {"31999": "31001"}
    chemin.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ErreurDonnees, match="ancien_code"):
        catnat.charger_fusions(chemin)


def test_format_de_date_inattendu_refuse(tmp_path):
    chemin = archive(tmp_path / "gaspar.zip", ["1;31001;Sécheresse;01/05/2022;30/09/2022;2023-01-10"])
    with pytest.raises(ErreurDonnees, match="AAAA-MM-JJ"):
        catnat.lire_secheresse(chemin, CONFIG)


def test_archive_illisible(tmp_path):
    (tmp_path / "x.zip").write_bytes(b"pas un zip")
    with pytest.raises(ErreurDonnees):
        catnat.lire_secheresse(tmp_path / "x.zip", CONFIG)


def test_horodatage_accepte(tmp_path):
    chemin = archive(tmp_path / "gaspar.zip", ["1;31001;Sécheresse;2022-05-01 00:00:00;2022-09-30 00:00:00;2023-01-10"])
    arrets = catnat.lire_secheresse(chemin, CONFIG)
    assert arrets["date_debut"].iloc[0] == pd.Timestamp("2022-05-01")
