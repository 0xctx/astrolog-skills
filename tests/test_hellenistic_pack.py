"""The built-in Hellenistic pack: a complete sample of the tradition's doctrine with no page citations, that a user's
own cited pack (built from their sources) starts from and then replaces."""

from __future__ import annotations

import json
import re
from pathlib import Path

from astrolog_skills.analysis.doctrine.rules import check_doctrine
from astrolog_skills.packs import draft, loader, verify
from astrolog_skills.sources import library
from tests.conftest import run_cli

PACK = loader.builtin_dir() / "hellenistic"


def test_complete_and_clean() -> None:
    p = loader.load("hellenistic")
    d = p.method.doctrine
    assert d is not None and not d.cited and not p.user
    assert d.summary()["sections"] == [
        "sect", "dignities", "phase", "places", "profections", "releasing", "transits", "periods", "sect_light",
        "scoring", "lots", "conditions", "topics",
    ]  # fmt: skip
    assert len(d.lots) == 17 and len(d.conditions) == 8 and len(d.topics) == 11  # with Marriage and containment
    assert d.configs is not None and (d.configs.assembly, d.configs.void_range) == (15, 30)
    assert check_doctrine(d) == []  # no citation warnings for a sample marked cited = false
    chart = p.method.chart
    assert chart is not None and (chart.zodiac, chart.houses, chart.node) == ("tropical", "whole-sign", "mean")


def test_no_page_references() -> None:
    for f in sorted(PACK.iterdir()):
        if f.is_file():
            text = f.read_text()
            assert not re.search(r"\bpp?\.\s*\d", text), f.name
            assert not re.search(r"(?m)^\s*cite\s*=", text), f.name


def test_reads_a_chart(fake_astrolog: Path) -> None:
    add = ("chart", "add", "Ein", "--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00")
    assert run_cli(*add).returncode == 0
    done = run_cli("--json", "report-data", "--chart", "Ein", "--pack", "hellenistic", "--on", "1905-06-30")
    assert done.returncode == 0, done.stderr
    data = json.loads(done.stdout)["packs"][0]
    assert data["study"]["topics"] and data["timing"]["profections"] and "sources" not in data
    assert data["settings"]["houses"] == "Whole Sign"


def test_your_cited_pack_starts_from_it(tmp_path: Path) -> None:
    notes = tmp_path / "notes.md"
    notes.write_text("# Notes\n\n## Sect\nThe day team is led by the Sun.\n\n## Lots\nFortune from the Sun.\n")
    library.add("hellenistic", notes)
    assert not loader.load("hellenistic").user  # sources alone don't replace the built-in pack
    started = draft.start("hellenistic")
    assert started.copied == ["method.toml", "meanings.md", "process.md", "REVIEW.md"]
    assert (started.path / "method.toml").read_text() == (PACK / "method.toml").read_text()
    report = verify.verify("hellenistic")
    assert any("uncited" in p.message for p in report.problems)
    assert draft.apply("hellenistic").files and loader.load("hellenistic").user  # now yours replaces it
