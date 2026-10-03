from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

from astrolog_skills.analysis.doctrine import parse_doctrine
from astrolog_skills.analysis.doctrine.explain import attach_notes, build_study, study_contacts, study_items
from astrolog_skills.engine import profile as P
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.moment import Moment
from astrolog_skills.export import notes as reading_notes
from astrolog_skills.packs import loader
from astrolog_skills.paths import data_dir
from tests.conftest import run_cli

FIXTURE = Path(__file__).parent / "fixtures" / "doctrine_pack.toml"
D = parse_doctrine(tomllib.loads(FIXTURE.read_text()), "t")
EINSTEIN = Moment("1879-03-14", "11:30", "LMT", 48.4, 10.0, "Albert Einstein")
GLOSSARY_MD = "# T\n\n## Glossary\n- **Of the sect** — works for the native. (p. 1)\n"


@pytest.fixture
def study(fake_astrolog: Path) -> dict:  # type: ignore[type-arg]
    assert D is not None
    return build_study(cast(EINSTEIN, P.load("default")), D, {}, years=40)


def test_every_item_has_a_unique_key(study: dict) -> None:  # type: ignore[type-arg]
    keys = [i["note_key"] for i in study_items(study)]
    assert len(keys) == len(set(keys)) and all(i.get("note_label") for i in study_items(study))
    assert "sect" in keys and "planet:moon" in keys and "lot:fortune" in keys and "place:10" in keys
    assert any(k.startswith("condition:") for k in keys) and any(k.startswith("releasing:spirit:1:") for k in keys)


def test_contacts_on_a_date(study: dict) -> None:  # type: ignore[type-arg]
    listed = study_contacts(study, "1905-06-30")
    keys = {c["key"]: c for c in listed}
    timed = [k for k in keys if k.startswith(("profection:", "releasing:"))]
    assert "profection:asc:26" in keys and "profection:asc:27" in keys  # this year and the next (the forecast)
    assert all(keys[k]["required"] for k in timed if not k.startswith(("profection:sect_light", "profection:contrary")))
    assert not keys["profection:sect_light:26"]["required"] and keys["profection:asc:27"]["forecast"]
    level2 = [k for k in timed if k.startswith("releasing:") and k.split(":")[2] == "2"]
    assert level2 and all(keys[k]["forecast"] for k in level2)
    assert all("1905-06-30" < k.split(":")[3] < "1907-07-01" or keys[k]["label"] for k in level2)
    assert keys["planet:sun"]["required"] and not keys["finding:sun:of_sect"]["required"]
    assert keys["place:10"]["required"] and not keys["place:11"]["required"]


def test_attach_notes_and_check(study: dict) -> None:  # type: ignore[type-arg]
    notes = {"planet:moon": "The Moon is helped.", "profection:asc:3": "An early year.", "nope": "x"}
    assert attach_notes(study, notes) == 2
    moon = next(p for p in study["planets"] if p["key"] == "moon")
    assert moon["note"] == "The Moon is helped."
    every = {i["note_key"] for i in study_items(study)}
    report = reading_notes.check(notes, study_contacts(study, "1905-06-30"), also_valid=every)
    assert report["unknown_keys"] == ["nope"]  # an off-date profection key is valid, not unknown
    assert report["study_with_notes"] == 1 and {"key": "sect", "label": "The chart's sect"} in report["missing_study"]


def _pack_with_doctrine() -> Path:
    pack = loader.user_dir() / "doctrine-test"
    pack.mkdir(parents=True)
    (pack / "method.toml").write_text(FIXTURE.read_text())
    (pack / "meanings.md").write_text(GLOSSARY_MD)
    return pack


def test_report_data_notes_and_export(fake_astrolog: Path, tmp_path: Path) -> None:
    _pack_with_doctrine()
    add = ("chart", "add", "Ein", "--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00")
    assert run_cli(*add).returncode == 0
    base = ("--chart", "Ein", "--pack", "doctrine-test")
    rd = json.loads(run_cli("--json", "report-data", *base, "--on", "1905-06-30").stdout)
    pack = rd["packs"][0]
    assert pack["study"]["planets"] and pack["timing"]["on"] == "1905-06-30"
    assert pack["timing"]["profections"] and set(pack["timing"]["releasing"]) == {"fortune", "spirit"}
    assert "sources" not in pack and pack["notes_attached"] == 0
    # notes keys include the study, with the date's timeline
    keys = json.loads(run_cli("--json", "notes", "keys", *base, "--on", "1905-06-30").stdout)
    study_keys = [c["key"] for c in keys["contacts"] if c["kind"] == "study"]
    assert "planet:moon" in study_keys and "profection:asc:26" in study_keys
    path = Path(keys["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "contacts": {
                    "planet:moon": "A helped Moon.",
                    "sect": "A day chart.",
                    "releasing:spirit:1:1879-03-14": "First chapter.",
                }
            }
        )
    )
    check = json.loads(run_cli("--json", "notes", "check", *base, "--on", "1905-06-30").stdout)
    assert check["unknown_keys"] == [] and check["study_with_notes"] == 3 and check["missing_study"]
    rd2 = json.loads(run_cli("--json", "report-data", *base, "--on", "1905-06-30").stdout)
    assert rd2["packs"][0]["notes_attached"] == 3
    # the newest saved reading goes into the page's Reading tab; notes reach the study without --interp
    exports = data_dir() / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    (exports / "ein-doctrine-test-2026-01-01.md").write_text("# Old\n")
    (exports / "ein-doctrine-test-2026-09-30.md").write_text("# Einstein\n\nA **day** chart (p. 1).\n")
    out = tmp_path / "ein.html"
    done = run_cli("export", "html", *base, "--harmonic", "1", "--out", str(out))
    assert done.returncode == 0, done.stderr
    data = json.loads(re.search(r'id="chart-data">(.*?)</script>', out.read_text(), re.S).group(1))  # type: ignore[union-attr]
    assert data["reading"]["name"].endswith("2026-09-30.md") and "**day**" in data["reading"]["text"]
    assert next(p for p in data["study"]["planets"] if p["key"] == "moon")["note"] == "A helped Moon."
    assert data["interp"] is False  # aspect rows still need --interp
    bad = run_cli(
        "export", "html", *base, "--harmonic", "1", "--reading", str(tmp_path / "missing.md"), "--out", str(out)
    )
    assert bad.returncode != 0
    shown = run_cli("view", *base, "--show", "doctrine")
    assert "A helped Moon." in shown.stdout


def test_topics_testimonies_and_verdicts(study: dict) -> None:  # type: ignore[type-arg]
    topics = {t["name"]: t for t in study["topics"]}
    assert set(topics) == {"career", "partnership", "body"}
    body = topics["body"]
    kinds = [c["kind"] for c in body["components"]]
    assert kinds == ["planet", "place", "place", "lot"]  # the Moon; the 1st and 6th places; Fortune
    assert all(c["lean"] in ("good", "bad", "mixed") and c["why"] for c in body["components"])
    assert body["tone"] in ("favourable", "difficult", "mixed") and "rule of three" in body["why"]
    ups = sum(c["lean"] == "good" for c in body["components"])
    downs = sum(c["lean"] == "bad" for c in body["components"])
    expected = "favourable" if ups > downs else "difficult" if downs > ups else "mixed"
    assert body["tone"] == expected
    keys = {c["key"]: c for c in study_contacts(study, "1905-06-30")}
    assert keys["life"]["required"] and keys["topic:career"]["required"]
    chapters = [k for k in keys if k.startswith("releasing:") and k.split(":")[2] == "1"]
    assert len(chapters) >= 4 and all(keys[k]["required"] for k in chapters)  # every chapter of the life


def test_topics_rules() -> None:
    from astrolog_skills.analysis.doctrine.rules import check_doctrine
    from astrolog_skills.errors import AstroError

    raw = tomllib.loads(FIXTURE.read_text())
    raw["topics"]["career"]["lots"] = ["nowhere"]
    d = parse_doctrine(raw, "t")
    assert d is not None and any(p.where == "topics.career.lots" for p in check_doctrine(d))
    raw["topics"]["career"]["places"] = [13]
    with pytest.raises(AstroError):
        parse_doctrine(raw, "t")


def test_life_view_and_reading_date(fake_astrolog: Path, tmp_path: Path) -> None:
    _pack_with_doctrine()
    add = ("chart", "add", "Ein", "--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00")
    assert run_cli(*add).returncode == 0
    base = ("--chart", "Ein", "--pack", "doctrine-test")
    path = Path(json.loads(run_cli("--json", "notes", "keys", *base).stdout)["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"on": "1905-06-30", "contacts": {"life": "A life of work.", "topic:career": "Visible work."}})
    )
    shown = run_cli("view", *base, "--show", "life")
    assert shown.returncode == 0 and "A life of work." in shown.stdout and "Visible work." in shown.stdout
    out = tmp_path / "e.html"
    assert run_cli("export", "html", *base, "--harmonic", "1", "--out", str(out)).returncode == 0
    data = json.loads(re.search(r'id="chart-data">(.*?)</script>', out.read_text(), re.S).group(1))  # type: ignore[union-attr]
    assert data["reading_on"] == "1905-06-30" and data["study"]["life"]["note"] == "A life of work."
    assert next(t for t in data["study"]["topics"] if t["name"] == "career")["note"] == "Visible work."


def test_configurations_table(study: dict) -> None:  # type: ignore[type-arg]
    rows = {(c["a"], c["b"]): c for c in study["configurations"]}
    assert len(rows) == 36  # every pair of the seven planets and the two angles
    for c in rows.values():
        if c["aspect"] is None:
            assert "distance" not in c  # aversion: no configuration to measure
        else:
            assert 0 <= c["distance"] <= 180 and c["overcomes"] in ("", c["a"], c["b"])
    assert all(
        k in ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "asc", "mc")
        for pair in rows
        for k in pair
    )
