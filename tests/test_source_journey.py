"""The whole source-built tradition journey, end to end: a book → a verified pack → doctrine and timing → reading data
and notes → the study page. Synthetic book and fake Astrolog, so it runs everywhere."""

from __future__ import annotations

import json
import re
from pathlib import Path

from astrolog_skills.packs import loader
from astrolog_skills.paths import data_dir
from tests.conftest import run_cli
from tests.test_pack_builder import mini_book

FIXTURE = Path(__file__).parent / "fixtures" / "doctrine_pack.toml"
GLOSSARY = """# Mini

## Planets
- **Sun** — the light of the day.

## Glossary
- **Of the sect** — a planet whose team matches the chart's. (p. 2)
- **Lots** — a distance between two points projected from the Ascendant. (p. 3)
"""
EVIDENCE = """[[claim]]
rule = "sect.diurnal"
page = "2"
quote = "the diurnal team is led by the Sun with Jupiter and Saturn"

[[claim]]
rule = "lots.fortune"
page = "3"
quote = "counts from the Sun to the Moon by day"
"""


def ok(*args: str) -> dict:  # type: ignore[type-arg]
    done = run_cli("--json", *args)
    assert done.returncode == 0, f"astro {' '.join(args)}: {done.stdout}{done.stderr}"
    return json.loads(done.stdout)  # type: ignore[no-any-return]


def test_from_a_book_to_a_reading(fake_astrolog: Path, tmp_path: Path) -> None:
    # 1. the book goes into a new pack, privately
    added = ok("sources", "add", "mini", str(mini_book(tmp_path)))
    assert added["pages"] == 8 and Path(added["index"]).is_relative_to(data_dir())
    assert [c["title"] for c in ok("packs", "outline", "mini")["chapters"]] == ["PLANETS", "SIGNS"]
    # 2. Claude drafts the rules, meanings and evidence; verify checks them against the book; the user approves
    draft = Path(ok("packs", "draft", "mini")["path"])
    (draft / "method.toml").write_text(FIXTURE.read_text())
    (draft / "meanings.md").write_text(GLOSSARY)
    (draft / "evidence.toml").write_text(EVIDENCE)
    report = ok("packs", "verify", "mini")
    assert report["ok"] and report["found"] == 2
    assert ok("packs", "apply", "mini", "--yes")["applied"]
    assert (loader.user_dir() / "mini" / "method.toml").is_file()
    assert not (loader.user_dir() / "mini" / "method.toml").read_text().count("diurnal team is led")  # no book text
    # 3. a chart read by the pack's doctrine and timing
    add = ("chart", "add", "Ein", "--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00")
    assert run_cli(*add).returncode == 0
    base = ("--chart", "Ein", "--pack", "mini")
    doctrine = ok("doctrine", *base)
    assert len(doctrine["planets"]) == 7 and doctrine["conditions"] is not None
    assert ok("timing", "profections", *base, "--age", "26")["years"]
    assert ok("timing", "releasing", *base, "--on", "1905-06-30")["periods"]
    # 4. the reading's data, with the sources to search
    data = ok("report-data", *base, "--on", "1905-06-30")["packs"][0]
    assert data["sources"]["list"][0]["indexed"] and data["study"]["topics"] and data["timing"]["profections"]
    hits = ok("sources", "search", "mini", "Lot of Fortune")["hits"]
    assert hits and hits[0]["printed"] == 3
    # 5. notes for the study, then the page
    keys = ok("notes", "keys", *base, "--on", "1905-06-30")
    required = [c["key"] for c in keys["contacts"] if c.get("required")]
    assert "life" in required and any(k.startswith("topic:") for k in required)
    notes = {k: f"A plain note for {k}." for k in required}
    Path(keys["path"]).parent.mkdir(parents=True, exist_ok=True)
    Path(keys["path"]).write_text(json.dumps({"on": "1905-06-30", "contacts": notes}))
    assert ok("notes", "check", *base, "--on", "1905-06-30")["missing_study"] == []
    exports = data_dir() / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    (exports / "ein-mini-2026-10-01.md").write_text("# Einstein\n\nYou are built for thinking.\n")
    out = tmp_path / "ein.html"
    ok("export", "html", *base, "--harmonic", "1", "--out", str(out))
    page = json.loads(re.search(r'id="chart-data">(.*?)</script>', out.read_text(), re.S).group(1))  # type: ignore[union-attr]
    assert page["study"]["life"]["note"] == "A plain note for life." and page["reading_on"] == "1905-06-30"
    assert page["reading"]["text"].startswith("# Einstein") and page["study"]["configurations"]
    # the book itself never reaches the page
    assert "diurnal team is led" not in out.read_text()
