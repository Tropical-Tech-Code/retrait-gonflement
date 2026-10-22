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


def base_ventes_rga():
    """10 ventes : dép. 31 (4 ventes) et 77 (6 ventes), niveaux 2020 et 2026 simulés."""
    con = duckdb.connect()
    con.execute("CREATE TABLE ventes_rga (code_departement VARCHAR, rga_2020 INTEGER, rga_2026 INTEGER)")
    lignes = [("31", 3, 3), ("31", 3, 2), ("31", 2, 2), ("31", 0, 0)]
    lignes += [("77", 3, 3), ("77", 3, 3), ("77", 2, 3), ("77", 2, 2), ("77", 1, 1), ("77", 2, 1)]
    con.executemany("INSERT INTO ventes_rga VALUES (?, ?, ?)", lignes)
    return con


def test_repartition_zones_par_departement():
    zones = metadonnees.repartition_zones(base_ventes_rga())
    assert set(zones) == {"31", "77"}
    assert zones["31"]["n_ventes"] == 4
    assert (zones["31"]["part_0"], zones["31"]["part_1"], zones["31"]["part_2"], zones["31"]["part_3"]) == (0.25, 0, 0.25, 0.5)
    assert zones["77"]["n_ventes"] == 6
    assert zones["77"]["part_3"] == 2 / 6 and zones["77"]["part_2"] == 3 / 6 and zones["77"]["part_1"] == 1 / 6
    for z in zones.values():
        assert abs(sum(z[f"part_{n}"] for n in range(4)) - 1) < 1e-12


def test_changements_carte_2026_dans_les_deux_sens():
    c = metadonnees.changements_carte_2026(base_ventes_rga())
    assert c["n_ventes"] == 10
    assert c["n_vers_plus_fort"] == 1       # 2 -> 3 en 77
    assert c["n_vers_moins_fort"] == 2      # 3 -> 2 en 31, 2 -> 1 en 77
    assert c["n_change"] == 3
    assert c["part_change"] == 0.3


def test_changements_carte_2026_sans_vente():
    con = duckdb.connect()
    con.execute("CREATE TABLE ventes_rga (code_departement VARCHAR, rga_2020 INTEGER, rga_2026 INTEGER)")
    c = metadonnees.changements_carte_2026(con)
    assert c["n_ventes"] == 0 and c["part_change"] is None


def test_main_ecrit_zones_et_carte_2026_si_la_table_existe(tmp_path, capsys):
    base = tmp_path / "travail.duckdb"
    con = duckdb.connect(str(base))
    con.execute("CREATE TABLE mutations_dvf (n_lignes INTEGER, annee INTEGER, motif VARCHAR)")
    con.execute("INSERT INTO mutations_dvf VALUES (1, 2021, NULL)")
    con.execute("CREATE TABLE ventes_rga (code_departement VARCHAR, rga_2020 INTEGER, rga_2026 INTEGER)")
    con.execute("INSERT INTO ventes_rga VALUES ('31', 3, 3), ('31', 2, 3)")
    con.close()
    resume = tmp_path / "resume_global.json"
    resume.write_text("{}", encoding="utf-8")
    metadonnees.main(["--base", str(base), "--resume", str(resume), "--raw", str(tmp_path / "raw")])
    contenu = json.loads(resume.read_text(encoding="utf-8"))
    assert contenu["zones_rga"]["31"]["part_3"] == 0.5
    assert contenu["carte_2026"]["n_change"] == 1 and contenu["carte_2026"]["n_vers_plus_fort"] == 1
    assert "Carte 2026 contre 2020" in capsys.readouterr().out


def test_main_sans_table_ventes_rga_ne_touche_pas_aux_cles_existantes(tmp_path, capsys):
    base = tmp_path / "travail.duckdb"
    con = duckdb.connect(str(base))
    con.execute("CREATE TABLE mutations_dvf (n_lignes INTEGER, annee INTEGER, motif VARCHAR)")
    con.close()
    resume = tmp_path / "resume_global.json"
    resume.write_text(json.dumps({"zones_rga": {"31": {}}}), encoding="utf-8")
    metadonnees.main(["--base", str(base), "--resume", str(resume), "--raw", str(tmp_path / "raw")])
    assert json.loads(resume.read_text(encoding="utf-8"))["zones_rga"] == {"31": {}}
    assert "ventes_rga absente" in capsys.readouterr().out


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
