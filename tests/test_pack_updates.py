"""Packs built from several sources (a cite per source; which rules more than one source backs) and rebuilds that
keep the owner's own edits."""

from __future__ import annotations

import json
from pathlib import Path

from astrolog_skills.packs import draft, verify
from astrolog_skills.packs.verify import cite_pages
from astrolog_skills.sources import library
from tests.conftest import run_cli
from tests.test_pack_builder import EVIDENCE, METHOD, mini_book

NOTES = """# Course notes

## Sect
By day the Sun leads the team of the day with Jupiter and Saturn, and the Moon leads the night.

## Lots
Fortune is counted from the Sun to the Moon by day and reversed by night.
"""


def test_cite_pages_by_source() -> None:
    assert cite_pages("book p. 525-526; course § 12") == {"book": {525, 526}, "course": {12}}
    assert cite_pages("p. 185, 190-191") == {"": {185, 190, 191}}
    assert cite_pages("§ 3; notes p. 4") == {"": {3}, "notes": {4}}


def two_sources(tmp_path: Path) -> Path:
    library.add("mini", mini_book(tmp_path))  # id "mini"
    notes = tmp_path / "course.md"
    notes.write_text(NOTES)
    library.add("mini", notes)  # id "course"
    folder = draft.start("mini").path
    (folder / "method.toml").write_text(METHOD.replace('cite = "p. 2"', 'cite = "mini p. 2; course § 1"'))
    return folder


def test_rules_backed_by_several_sources(tmp_path: Path) -> None:
    folder = two_sources(tmp_path)
    claims = EVIDENCE.replace('rule = "sect.diurnal"', 'rule = "sect.diurnal"\nsource = "mini"').replace(
        'rule = "lots.fortune"', 'rule = "lots.fortune"\nsource = "mini"'
    )
    claims += '\n[[claim]]\nrule = "sect.diurnal"\nsource = "course"\npage = "§ 1"\n'
    claims += 'quote = "the Sun leads the team of the day with Jupiter and Saturn"\n'
    (folder / "evidence.toml").write_text(claims)
    report = verify.verify("mini").to_dict()
    assert report["ok"] and report["found"] == 3, report["problems"]
    assert report["backing"]["sect.diurnal"] == ["mini", "course"] and report["several_sources"] == ["sect.diurnal"]
    assert not [p for p in report["problems"] if "isn't in the rule's cite" in p["message"]]
    # a course claim on a rule whose cite names only the book is flagged
    (folder / "method.toml").write_text(METHOD)
    report = verify.verify("mini").to_dict()
    assert any("isn't in the rule's cite" in p["message"] for p in report["problems"])


def test_a_rebuild_keeps_your_own_edits(tmp_path: Path) -> None:
    library.add("mini", mini_book(tmp_path))
    folder = draft.start("mini").path
    (folder / "method.toml").write_text(METHOD)
    (folder / "evidence.toml").write_text(EVIDENCE)
    draft.apply("mini")  # the baseline your edits are measured against
    live = library.pack_dir("mini") / "method.toml"
    live.write_text(live.read_text().replace('label = "Mini"', 'label = "Mini (my edits)"'))
    assert draft.hand_edits("mini") == {"method.toml": ['label = "Mini (my edits)"']}
    started = draft.start("mini")
    assert started.hand_edits == 1 and 'label = "Mini (my edits)"' in (started.path / "method.toml").read_text()
    assert not any(d.edits_changed for d in draft.diff("mini"))  # the draft keeps it: nothing to flag
    (started.path / "method.toml").write_text(METHOD)  # a rebuild that would undo it
    changed = {d.name: d.edits_changed for d in draft.diff("mini")}
    assert changed["method.toml"] == ['label = "Mini (my edits)"']
    messages = [p.message for p in verify.verify("mini").problems]
    assert any("changes a line you edited by hand" in m for m in messages)
    shown = run_cli("packs", "diff", "mini")
    assert "changes your own edit" in shown.stdout
    assert json.loads(run_cli("--json", "packs", "discard", "mini").stdout)["ok"]
