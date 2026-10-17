import json
import os
import zipfile
from datetime import date, datetime

import duckdb

from retrait_gonflement.data.commun import charger_config
from retrait_gonflement.model import metadonnees


def base_mutations():
    con = duckdb.connect()
    con.execute("CREATE TABLE mutations_dvf (n_lignes INTEGER, annee INTEGER, motif VARCHAR)")
    # 10 mutations : 2 « nature », 1 « dispositions », 1 « prix_m2 », 6 retenues (4 en 2021, 2 en 2022)
    lignes = [(1, 2021, "nature")] * 2 + [(2, 2021, "dispositions"), (1, 2022, "prix_m2")]
    lignes += [(1, 2021, None)] * 4 + [(3, 2022, None)] * 2
    con.executemany("INSERT INTO mutations_dvf VALUES (?, ?, ?)", lignes)
    return con


def test_effectifs_nettoyage_restantes_apres_chaque_motif():
    n = metadonnees.effectifs_nettoyage(base_mutations())
    assert n["n_mutations"] == 10
    assert n["n_lignes_dvf"] == 1 * 2 + 2 + 1 + 4 + 6
    assert n["n_ventes_retenues"] == 6
    par_code = {e["code"]: e for e in n["etapes"]}
    assert par_code["nature"]["exclues"] == 2 and par_code["nature"]["restantes"] == 8
    assert par_code["dispositions"]["restantes"] == 7
    assert par_code["autre_local"]["exclues"] == 0 and par_code["autre_local"]["restantes"] == 7
    assert par_code["prix_m2"]["restantes"] == 6
    assert n["ventes_retenues_par_annee"] == {"2021": 4, "2022": 2}


def test_date_fichiers_prend_le_plus_recent(tmp_path):
    ancien, recent = tmp_path / "a.csv.gz", tmp_path / "b.csv.gz"
    for f, jour in ((ancien, date(2026, 10, 14)), (recent, date(2026, 10, 16))):
        f.write_bytes(b"x")
        stamp = datetime(jour.year, jour.month, jour.day, 12).timestamp()
        os.utime(f, (stamp, stamp))
    assert metadonnees.date_fichiers([ancien, recent]) == "2026-10-16"
    assert metadonnees.date_fichiers([]) is None


def test_decrire_sources_avec_et_sans_fichiers(tmp_path):
    config = charger_config()
    (tmp_path / "dvf").mkdir()
    (tmp_path / "dvf" / "dvf_2021_31.csv.gz").write_bytes(b"x")
    (tmp_path / "gaspar").mkdir()
    with zipfile.ZipFile(tmp_path / "gaspar" / "gaspar.zip", "w") as zf:
        zf.writestr("catnat_gaspar_2025-01-01.csv", "code_commune;lib_risque_jo\n")
    sources = {s["cle"]: s for s in metadonnees.decrire_sources(config, tmp_path)}
    assert sources["dvf"]["millesime"] == "ventes 2021-2025"
    assert sources["dvf"]["date_telechargement"] is not None
    assert sources["gaspar"]["millesime"] == "catnat_gaspar_2025-01-01.csv"
    # rien déposé : date absente, pas d'erreur
    assert sources["rga_2020"]["date_telechargement"] is None
    assert sources["communes"]["date_telechargement"] is None
    assert sources["communes"]["millesime"] == "version de l'API Géo à la date de consultation"
    assert set(sources) == {"dvf", "rga_2020", "rga_2026", "gaspar", "communes"}


def test_main_complete_le_resume_sans_ecraser_les_autres_cles(tmp_path):
    base = tmp_path / "travail.duckdb"
    con = duckdb.connect(str(base))
    con.execute("CREATE TABLE mutations_dvf (n_lignes INTEGER, annee INTEGER, motif VARCHAR)")
    con.execute("INSERT INTO mutations_dvf VALUES (1, 2021, NULL), (1, 2021, 'nature')")
    con.close()
    resume = tmp_path / "resume_global.json"
    resume.write_text(json.dumps({"n_communes_estimables": 193}), encoding="utf-8")
    metadonnees.main(["--base", str(base), "--resume", str(resume), "--raw", str(tmp_path / "raw")])
    contenu = json.loads(resume.read_text(encoding="utf-8"))
    assert contenu["n_communes_estimables"] == 193
    assert contenu["nettoyage"]["n_ventes_retenues"] == 1
    assert contenu["sources"]["note_date"]
    assert len(contenu["sources"]["liste"]) == 5
