from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrolog_skills.cli import app, register_all
from tests.conftest import run_cli

TRUECOLOR = "\x1b[38;2;"


def test_help_lists_commands() -> None:
    res = run_cli("--help")
    assert res.returncode == 0
    for name in ("doctor", "config", "astrolog", "version"):
        assert name in res.stdout


def test_every_command_module_registers() -> None:
    modules = register_all()
    assert {"astrolog", "config", "doctor", "version"} <= set(modules)
    names = {c.name for c in app.registered_commands} | {g.name for g in app.registered_groups}
    assert {"doctor", "version", "config", "astrolog"} <= names


def test_rich_is_truecolor_even_when_piped() -> None:
    res = run_cli("version")
    assert TRUECOLOR in res.stdout


def test_plain_has_no_ansi() -> None:
    res = run_cli("--plain", "version")
    assert "\x1b" not in res.stdout and "0.1.0" in res.stdout


def test_no_color_env_means_plain() -> None:
    res = run_cli("version", env={"NO_COLOR": "1"})
    assert "\x1b" not in res.stdout


def test_json_is_one_clean_document(fake_astrolog: Path) -> None:
    for args in (["version"], ["config", "show"], ["doctor"]):
        res = run_cli("--json", *args)
        assert res.returncode == 0, res.stderr
        assert "\x1b" not in res.stdout
        json.loads(res.stdout)


def test_doctor_rich_output_under_budget(fake_astrolog: Path) -> None:
    res = run_cli("doctor")
    assert res.returncode == 0
    assert "first light" in res.stdout and "All good" in res.stdout
    assert len(res.stdout) < 30_000


def test_doctor_fails_with_exit_1_and_fixes() -> None:
    res = run_cli("--plain", "doctor")
    assert res.returncode == 1
    assert "astro astrolog install" in " ".join(res.stdout.split())  # fixes may wrap across lines


def test_error_path_json() -> None:
    res = run_cli("--json", "config", "set", "nope", "1")
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["ok"] is False and "display.width" in data["fix"]


def test_error_path_rich() -> None:
    res = run_cli("config", "set", "display.width", "banana")
    assert res.returncode == 1 and "✗" in res.stdout


def test_config_display_orbs() -> None:
    assert run_cli("config", "set", "display.orbs", "natal").returncode == 0
    assert "natal" in run_cli("--json", "config", "get", "display.orbs").stdout
    bad = run_cli("--json", "config", "set", "display.orbs", "sideways")
    assert bad.returncode == 1 and "harmonic" in json.loads(bad.stdout)["error"]


def test_config_set_location_cli() -> None:
    res = run_cli("--json", "config", "set", "location", "48N24 10E00", "--name", "Ulm")
    assert res.returncode == 0
    assert json.loads(res.stdout)["location"] == {"name": "Ulm", "lat": 48.4, "lon": 10.0}


def test_install_preview_downloads_nothing(fake_astrolog: Path) -> None:
    res = run_cli("--json", "astrolog", "install")
    data = json.loads(res.stdout)
    assert res.returncode == 0 and data["preview"] is True
    assert data["url"].startswith("https://github.com/CruiserOne/Astrolog/")
    assert not (Path(data["prefix"]) / "astrolog").exists()


def test_astrolog_info(fake_astrolog: Path) -> None:
    data = json.loads(run_cli("--json", "astrolog", "info").stdout)
    assert data["version"] == "8.00" and data["ephemeris"] == "swiss" and data["source"] == "env"


def test_astrolog_info_missing() -> None:
    res = run_cli("--json", "astrolog", "info")
    assert res.returncode == 1 and json.loads(res.stdout)["fix"] == "astro astrolog install"


EINSTEIN_ARGS = ["--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00", "--name", "Einstein"]


def test_cast_json(fake_astrolog: Path) -> None:
    res = run_cli("--json", "cast", *EINSTEIN_ARGS)
    assert res.returncode == 0, res.stdout
    data = json.loads(res.stdout)
    assert data["schema"] == 1 and data["name"] == "Einstein" and len(data["cusps"]) == 12
    assert data["moment"]["utc"].startswith("1879-03-14T10:50")


def test_cast_rich_and_plain(fake_astrolog: Path) -> None:
    assert "Pisces" in run_cli("--plain", "cast", *EINSTEIN_ARGS).stdout
    assert TRUECOLOR in run_cli("cast", *EINSTEIN_ARGS).stdout


def test_cast_missing_options_explains() -> None:
    res = run_cli("--json", "cast", "--date", "1879-03-14")
    assert res.returncode == 1 and "--time" in json.loads(res.stdout)["error"]


def test_cast_with_profile(fake_astrolog: Path) -> None:
    data = json.loads(run_cli("--json", "cast", *EINSTEIN_ARGS, "--profile", "vedic-lahiri").stdout)
    assert data["profile"]["zodiac"] == "sidereal" and data["profile"]["houses"] == "Whole Sign"


def test_profile_commands() -> None:
    listing = json.loads(run_cli("--json", "profile", "list").stdout)
    assert listing["active"] == "default" and {p["name"] for p in listing["profiles"]} >= {"default", "vedic-lahiri"}
    assert json.loads(run_cli("--json", "profile", "use", "whole-sign").stdout)["active"] == "whole-sign"
    shown = json.loads(run_cli("--json", "profile", "show").stdout)
    assert shown["name"] == "whole-sign" and "-R0" in shown["pins"]
    made = json.loads(run_cli("--json", "profile", "new", "mine", "--from", "vedic-lahiri").stdout)
    assert Path(made["path"]).exists()
    assert run_cli("--json", "profile", "use", "nope").returncode == 1


def test_raw_passthrough(fake_astrolog: Path) -> None:
    res = run_cli("raw", *EINSTEIN_ARGS[:-2], "--", "-v", "-c", "Koch")
    assert res.returncode == 0 and res.stdout.startswith("FAKE ASTROLOG")
    assert res.stdout.rstrip().endswith("-v -c Koch") and "10:00:00E" in res.stdout
    data = json.loads(run_cli("--json", "raw", "--", "-Hc").stdout)
    assert "Astrolog version" in data["stdout"] and data["argv"][-1] == "-Hc"


def test_place_command(atlas: Path) -> None:
    data = json.loads(run_cli("--json", "place", "Ulm").stdout)
    assert {p["label"] for p in data["places"]} == {"Ulm, Germany", "Ulm, Montana, United States"}


def test_chart_add_list_show_rm(atlas: Path) -> None:
    add = json.loads(
        run_cli(
            "--json",
            "chart",
            "add",
            "Einstein",
            "--date",
            "1879-03-14",
            "--time",
            "11:30",
            "--place",
            "Ulm, Germany",
            "--rating",
            "AA",
            "--tag",
            "physics",
        ).stdout
    )
    assert add["chart"]["tz"] == "Europe/Berlin" and add["chart"]["tags"] == ["physics"]
    assert [c["name"] for c in json.loads(run_cli("--json", "chart", "list").stdout)["charts"]] == ["Einstein"]
    shown = json.loads(run_cli("--json", "chart", "show", "einstein").stdout)
    assert shown["record"]["rating"] == "AA" and shown["points"][0]["key"] == "sun"
    assert json.loads(run_cli("--json", "cast", "--chart", "Einstein").stdout)["name"] == "Einstein"
    assert run_cli("--json", "chart", "rm", "Einstein").returncode == 0
    assert run_cli("--json", "chart", "show", "Einstein").returncode == 1


def test_cast_with_place(atlas: Path) -> None:
    data = json.loads(run_cli("--json", "cast", "--date", "2000-06-01", "--time", "12:00", "--place", "Paris").stdout)
    assert data["moment"]["tz"] == "Europe/Paris" and data["moment"]["utc"].startswith("2000-06-01T10:00")


def test_set_commands(fake_astrolog: Path) -> None:
    adb = str(Path(__file__).parent / "fixtures" / "adb_sample.xml")
    made = json.loads(
        run_cli("--json", "set", "create", "music", "--adb", adb, "--category", "Vocation : Entertain/Music").stdout
    )
    assert made["count"] == 2
    shown = json.loads(run_cli("--json", "set", "show", "music").stdout)
    assert shown["count"] == 2 and shown["genders"] == {"m": 2}
    assert [s["name"] for s in json.loads(run_cli("--json", "set", "list").stdout)["sets"]] == ["music"]
    assert run_cli("--json", "set", "create", "x", "--adb", adb, "--csv", adb).returncode == 1  # two sources
    assert run_cli("--json", "set", "rm", "music").returncode == 0


def test_data_categories(fake_astrolog: Path) -> None:
    adb = str(Path(__file__).parent / "fixtures" / "adb_sample.xml")
    data = json.loads(run_cli("--json", "data", "categories", adb, "--grep", "physics").stdout)
    assert data["categories"] == [["Vocation : Science : Physics", 1]]


@pytest.mark.network
def test_fetch_sample_downloads_the_free_adb_sample() -> None:
    res = run_cli("--json", "data", "fetch-sample")
    data = json.loads(res.stdout)
    assert res.returncode == 0 and data["stats"]["usable"] > 5000 and "Astrodienst" in data["notice"]


def test_packs_cli() -> None:
    listing = json.loads(run_cli("--json", "packs", "list").stdout)
    assert listing["active"] == "psychological" and {p["name"] for p in listing["packs"]} >= {"vibrational"}
    shown = json.loads(run_cli("--json", "packs", "show", "vibrational").stdout)
    assert shown["aspects"]["quintile"] == 3.2 and shown["files"]["REVIEW.md"]
    made = json.loads(run_cli("--json", "packs", "copy", "vibrational", "--as", "mine").stdout)
    assert Path(made["path"], "method.toml").exists()


def test_patterns_and_aspects_cli(fake_astrolog: Path) -> None:
    einstein = ["--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00"]
    pat = json.loads(run_cli("--json", "patterns", *einstein, "--pack", "vibrational", "-H", "1").stdout)
    assert pat["harmonics"][0]["patterns"][0]["bodies"] == ["sun", "mercury", "saturn"]
    ranged = json.loads(
        run_cli("--json", "patterns", *einstein, "--pack", "vibrational", "--range", "1-12", "--top", "3").stdout
    )
    assert len(ranged["harmonics"]) == 3
    asp = json.loads(run_cli("--json", "aspects", *einstein).stdout)
    assert asp["pack"] == "psychological" and asp["aspects"][0]["strength"] <= 1
    assert run_cli("--json", "patterns", *einstein, "--range", "nope").returncode == 1


def test_view_command(fake_astrolog: Path) -> None:
    einstein = ["--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00"]
    rich = run_cli("view", *einstein)
    assert rich.returncode == 0 and TRUECOLOR in rich.stdout and len(rich.stdout) < 30_000
    plain = run_cli("--plain", "view", *einstein, "--show", "chart,positions")
    assert "\x1b" not in plain.stdout and "POSITIONS" in plain.stdout
    data = json.loads(
        run_cli("--json", "view", *einstein, "--show", "aspects", "-H", "5", "--pack", "vibrational").stdout
    )
    assert data["views"] == ["aspects"] and data["harmonic"] == 5 and "patterns" in data
    assert run_cli("view", *einstein, "--show", "wheel").returncode == 1
    letters = run_cli("--plain", "view", *einstein, "--letters")
    assert "☉" not in letters.stdout and "Su Sun" in letters.stdout


def test_theme_cli() -> None:
    assert json.loads(run_cli("--json", "theme", "list").stdout)["active"] == "default"
    assert json.loads(run_cli("--json", "theme", "copy", "default", "--as", "mine").stdout)["ok"]
    assert json.loads(run_cli("--json", "theme", "use", "mine").stdout)["active"] == "mine"
    assert run_cli("--json", "theme", "use", "nope").returncode == 1


def test_research_and_harmonics_cli(fake_astrolog: Path, tmp_path: Path) -> None:
    rows = ["name,date,time,tz,lat,lon"] + [
        f"P{i},{1950 + i}-0{1 + i % 9}-1{i % 9},0{i % 10}:30,UTC,48.4,10.0" for i in range(30)
    ]
    csv_file = tmp_path / "s.csv"
    csv_file.write_text("\n".join(rows) + "\n")
    assert run_cli("--json", "set", "create", "demo", "--csv", str(csv_file)).returncode == 0
    res = run_cli("--json", "research", "sweep", "demo", "--range", "1-6", "--shuffles", "4", "--top", "3")
    data = json.loads(res.stdout)
    assert res.returncode == 0, res.stderr
    assert data["count"] == 30 and data["run"] and all(len(v) == 6 for v in data["measures"].values())
    assert json.loads(run_cli("--json", "research", "list").stdout)["runs"][0]["id"] == data["run"]
    assert "observed" in run_cli("--plain", "research", "show", data["run"]).stdout
    einstein = ["--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00"]
    data = json.loads(run_cli("--json", "harmonics", *einstein, "--top", "4").stdout)
    z = {h["harmonic"]: h["z_new"] for h in data["harmonics"]}
    assert len(data["ranked"]) == 4 and z[data["ranked"][0]] >= z[data["ranked"][-1]] and len(data["harmonics"]) == 32


def test_report_data(fake_astrolog: Path) -> None:
    einstein = [
        "--date",
        "1879-03-14",
        "--time",
        "11:30",
        "--tz",
        "LMT",
        "--at",
        "48N24 10E00",
        "--name",
        "Albert Einstein",
    ]
    data = json.loads(
        run_cli("--json", "report-data", *einstein, "--pack", "psychological", "--pack", "vibrational").stdout
    )
    assert [p["name"] for p in data["packs"]] == ["psychological", "vibrational"]
    vib = data["packs"][1]
    assert set(vib["files"]) >= {"process.md", "meanings.md", "REVIEW.md"} and vib["strongest_harmonics"]
    assert data["export_path"].endswith(".md") and "albert-einstein-psychological-vibrational" in data["export_path"]
    assert data["balance"]["elements"]["water"] == ["sun"]
    assert json.loads(run_cli("--json", "report-data", *einstein).stdout)["packs"][0]["name"] == "psychological"


def test_export_html_cli(fake_astrolog: Path, tmp_path: Path) -> None:
    einstein = ["--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00", "--name", "Einstein"]
    data = json.loads(run_cli("--json", "export", "html", *einstein, "-H", "5").stdout)
    assert data["ok"] and data["path"].endswith("einstein-h5.html") and Path(data["path"]).exists()
    out = tmp_path / "x.html"
    assert json.loads(run_cli("--json", "export", "html", *einstein, "--out", str(out)).stdout)["path"] == str(out)
    assert run_cli("--json", "export", "html", *einstein, "--preset", "nope").returncode == 1


def test_transits_cli_and_view(fake_astrolog: Path) -> None:
    einstein = ["--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00"]
    data = json.loads(run_cli("--json", "transits", *einstein, "--on", "2026-01-01", "--days", "10").stdout)
    assert data["when"]["date"] == "2026-01-01" and isinstance(data["transits"], list) and "window" in data
    assert run_cli("--json", "transits", *einstein, "--on", "soon").returncode == 1
    assert run_cli("--json", "transits", *einstein, "--days", "999").returncode == 1
    shown = run_cli("--plain", "view", *einstein, "--transits", "2026-01-01")
    assert shown.returncode == 0 and "TRANSITS 2026-01-01" in shown.stdout and "in blue" in shown.stdout
