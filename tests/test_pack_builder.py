from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrolog_skills.errors import AstroError
from astrolog_skills.packs import draft
from astrolog_skills.packs.build import outline, parse_contents
from astrolog_skills.packs.verify import contains, page_numbers, tokens, verify
from astrolog_skills.sources import library
from tests.conftest import run_cli
from tests.fakes.mini_pdf import write_pdf

FILL = ["planets signs places aspects lots"] * 7  # 35 words: a text layer

SECT_LINES = [
    "Day charts and night charts divide the planets into two teams.",
    "The diurnal team is led by the Sun with Jupiter",
    "Figure 7.1",  # a figure label interleaved with the sentence
    "and Saturn, and the nocturnal team by the Moon.",
]
LOT_LINES = ["The Lot of Fortune counts from the Sun to the Moon by day", "and from the Moon to the Sun by night."]


def mini_book(tmp_path: Path) -> Path:
    """Title, contents (indented, with dot leaders and a tables list), five body pages printed 1–5, an index."""
    pages = [
        ["A Mini Source"],
        [
            "TABLE OF CONTENTS",
            "1   PLANETS ........ 1",
            "      Sect ........ 2",
            "      Lots ........ 3",
            "2   SIGNS ........ 4",
            "      Bounds ........ 4",
            "      Index ........ 6",
            "TABLES",
            "4.1   The Bounds ........ 4",
        ],
        ["1\tPLANETS", *FILL, "The seven planets wander through the signs."],
        ["SECT\t2", *FILL, *SECT_LINES],
        ["3\tLOTS", *FILL, *LOT_LINES],
        ["BOUNDS\t4", *FILL, "Aries: Jupiter 6, Venus 12, Mercury 20, Mars 25, Saturn 30."],
        ["5\tSIGNS", *FILL, "Each sign has thirty degrees."],
        ["Index", "sect 2", "lots 3"],
    ]
    return write_pdf(tmp_path / "Mini.pdf", pages)


METHOD = """label = "Mini"
[orbs]
rule = "harmonic"

[sect]
cite = "p. 2"
diurnal = ["sun", "jupiter", "saturn"]
nocturnal = ["moon", "venus", "mars"]

[lots.fortune]
cite = "p. 3"
points = ["sun", "moon"]
reverse = true
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


@pytest.fixture
def pack(tmp_path: Path) -> str:
    library.add("mini", mini_book(tmp_path))
    started = draft.start("mini")
    assert started.created == [*draft.PACK_FILES, draft.EVIDENCE] and started.copied == []
    (started.path / "method.toml").write_text(METHOD)
    (started.path / "evidence.toml").write_text(EVIDENCE)
    return "mini"


def problems(report: object) -> list[tuple[str, str, str]]:
    return [(p.level, p.where, p.message) for p in report.problems]  # type: ignore[attr-defined]


# ── matching ──────────────────────────────────────────────────────────────────


def test_matcher_tolerates_labels_and_split_words() -> None:
    page = tokens("The diurnal team is led by the Sun with Jupiter Figure 7.1 and Saturn. Con- figurations matter.")
    assert contains(tokens("led by the Sun with Jupiter and Saturn"), page)
    assert contains(tokens("configurations matter"), page)
    assert not contains(tokens("led by the Moon"), page)
    assert not contains(tokens("Jupiter and Saturn"), tokens("Jupiter " + "x " * 9 + "and Saturn"))
    assert page_numbers("p. 512, 518-520") == {512, 518, 519, 520} and page_numbers("190–191") == {190, 191}


# ── outline ───────────────────────────────────────────────────────────────────


def test_outline_from_contents(pack: str) -> None:
    o = outline(pack)
    assert [(c.number, c.title, c.start, c.end) for c in o.chapters] == [("1", "PLANETS", 1, 3), ("2", "SIGNS", 4, 5)]
    assert [(s.title, s.start, s.end) for s in o.chapters[0].sections] == [("Sect", 2, 2), ("Lots", 3, 3)]
    assert [(e.title, e.start) for e in o.back] == [("Index", 6)]
    assert [(t.number, t.title, t.start) for t in o.tables] == [("4.1", "The Bounds", 4)]
    assert json.dumps(o.to_dict())


def test_parse_contents_figures_then_tables() -> None:
    chapters, _, figures, tables = parse_contents(
        ["LIST OF FIGURES AND TABLES", "FIGURES", "1.1   A Wheel   8", "TABLES", "8.3   The Bounds   277"], 300
    )
    assert chapters == [] and [f.title for f in figures] == ["A Wheel"] and [t.start for t in tables] == [277]


# ── verify ────────────────────────────────────────────────────────────────────


def test_verify_clean_draft(pack: str) -> None:
    report = verify(pack)
    assert report.errors == 0 and report.claims == 2 and report.found == 2, problems(report)
    assert report.to_dict()["ok"]


def test_verify_catches_a_wrong_citation(pack: str) -> None:
    ev = draft.draft_dir(pack) / "evidence.toml"
    ev.write_text(EVIDENCE.replace('page = "3"', 'page = "4"'))
    msgs = problems(verify(pack))
    assert ("error", "evidence #2 (lots.fortune)", "wrong citation: the words are on p. 3, not p. 4") in msgs
    assert any("isn't in the rule's cite" in m for _, _, m in msgs)


def test_verify_quote_not_in_source_and_unknown_rule(pack: str) -> None:
    ev = draft.draft_dir(pack) / "evidence.toml"
    ev.write_text(
        EVIDENCE + '\n[[claim]]\nrule = "sect.nocturnal"\npage = "2"\nquote = "Mars rules the night alone"\n'
        '\n[[claim]]\nrule = "lots.spirit"\npage = "3"\nquote = "and from the Moon to the Sun"\n'
        '\n[[claim]]\nrule = "sect.diurnal"\npage = "2"\nquote = "the Sun"\n'
    )
    msgs = problems(verify(pack))
    assert any(w.startswith("evidence #3") and "aren't on p. 2" in m for _, w, m in msgs)
    assert any(w.startswith("evidence #4") and "no such rule" in m for _, w, m in msgs)
    assert any(w.startswith("evidence #5") and "too short" in m for _, w, m in msgs)


def test_verify_catches_a_broken_table(pack: str) -> None:
    method = draft.draft_dir(pack) / "method.toml"
    method.write_text(
        METHOD + '\n[dignities]\ncite = "p. 4"\nbounds_scheme = "egyptian"\n[dignities.bounds.egyptian]\n'
        'aries = [["jupiter", 6], ["venus", 12], ["mercury", 20], ["mars", 25], ["saturn", 29]]\n'
    )
    msgs = problems(verify(pack))
    assert any(lvl == "error" and "dignities.bounds.egyptian" in w for lvl, w, _ in msgs)
    assert ("warn", "dignities", "no evidence for this rule") in msgs


def test_verify_catches_copied_wording(pack: str) -> None:
    meanings = draft.draft_dir(pack) / "meanings.md"
    meanings.write_text(
        "# Mini\n\n## Sect\n\n"
        "The diurnal team is led by the Sun with Jupiter and Saturn, and the nocturnal team (p. 2).\n"
    )
    msgs = problems(verify(pack))
    assert ("error", "meanings.md", "copies the source's wording (p. 2)") in msgs
    meanings.write_text(
        "# Mini\n\n## Sect\n\nBy day the Sun leads Jupiter and Saturn; the Moon leads the night (p. 2).\n"
    )
    assert not any(w == "meanings.md" for _, w, _ in problems(verify(pack)))


def test_verify_markdown_claims(pack: str) -> None:
    folder = draft.draft_dir(pack)
    (folder / "meanings.md").write_text("# Mini\n\n## Fortune\n\nThe body and its circumstances (p. 3).\n")
    (folder / "evidence.toml").write_text(
        EVIDENCE + '\n[[claim]]\nrule = "meanings.md#Fortune"\npage = "3"\nquote = "Lot of Fortune counts"\n'
    )
    report = verify(pack)
    assert report.found == 3 and report.errors == 0, problems(report)


def test_verify_bad_method_is_a_problem_not_a_crash(pack: str) -> None:
    (draft.draft_dir(pack) / "method.toml").write_text("label = 'x'\n[orbs]\nrule = 'fixed'\n")
    assert any(w == "method.toml" for _, w, _ in problems(verify(pack)))
    (draft.draft_dir(pack) / "method.toml").write_text("[[broken")
    assert any("valid TOML" in m for _, _, m in problems(verify(pack)))


# ── draft / diff / apply ──────────────────────────────────────────────────────


def test_draft_diff_apply_cycle(pack: str) -> None:
    with pytest.raises(AstroError):
        draft.start(pack)  # a draft already exists
    diffs = {d.name: d for d in draft.diff(pack)}
    assert diffs["method.toml"].status == "new" and "+[sect]" in diffs["method.toml"].diff
    first = draft.apply(pack)
    live = library.pack_dir(pack)
    assert first.backup is None and (live / "method.toml").read_text() == METHOD
    assert draft.evidence_live(pack).read_text() == EVIDENCE and not draft.draft_dir(pack).exists()
    # extend the live pack: the draft starts from it, and apply keeps the old files
    again = draft.start(pack)
    assert set(again.copied) == {*draft.PACK_FILES, draft.EVIDENCE}
    (again.path / "method.toml").write_text(METHOD.replace('label = "Mini"', 'label = "Mini 2"'))
    changed = [d for d in draft.diff(pack) if d.status == "changed"]
    assert [d.name for d in changed] == ["method.toml"] and changed[0].added == 1 and changed[0].removed == 1
    second = draft.apply(pack)
    assert second.files == ["method.toml"] and second.backup and (second.backup / "method.toml").read_text() == METHOD
    assert 'label = "Mini 2"' in (live / "method.toml").read_text()
    assert verify(pack, live=True).errors == 0


def test_cli_build_commands(tmp_path: Path) -> None:
    pdf = mini_book(tmp_path)
    assert run_cli("sources", "add", "mini", str(pdf)).returncode == 0
    shape = json.loads(run_cli("--json", "packs", "outline", "mini").stdout)
    assert [c["title"] for c in shape["chapters"]] == ["PLANETS", "SIGNS"]
    assert json.loads(run_cli("--json", "packs", "draft", "mini").stdout)["ok"]
    folder = library.pack_dir("mini") / "draft"
    (folder / "method.toml").write_text(METHOD)
    (folder / "evidence.toml").write_text(EVIDENCE.replace('page = "3"', 'page = "4"'))
    bad = run_cli("--json", "packs", "verify", "mini")
    assert bad.returncode == 1 and json.loads(bad.stdout)["errors"] >= 1
    refused = run_cli("--json", "packs", "apply", "mini", "--yes")
    assert refused.returncode == 1 and not (library.pack_dir("mini") / "method.toml").exists()
    (folder / "evidence.toml").write_text(EVIDENCE)
    assert run_cli("--json", "packs", "verify", "mini").returncode == 0
    shown = json.loads(run_cli("--json", "packs", "diff", "mini").stdout)
    assert {f["name"] for f in shown["files"]} >= {"method.toml", "evidence.toml"}
    held = json.loads(run_cli("--json", "packs", "apply", "mini").stdout)
    assert held["ok"] is False and held["pending"] and not (library.pack_dir("mini") / "method.toml").exists()
    done = json.loads(run_cli("--json", "packs", "apply", "mini", "--yes").stdout)
    assert done["ok"] and "method.toml" in done["applied"]
    assert json.loads(run_cli("--json", "packs", "show", "mini").stdout)["doctrine"]["lots"] == ["fortune"]


def test_contents_only_among_the_front_pages() -> None:
    from astrolog_skills.sources import extract

    toc = "\n".join(f"    Chapter {n}        {n * 10}" for n in range(1, 9))
    table = "\n".join(f"Aries  Jupiter  {n}" for n in range(1, 9))
    pages = ["Title page", toc] + ["\n".join(["body"] * 3 + [f"{n}"]) for n in range(1, 120)]
    pages[60] = table + "\n59"
    pmap = extract.PageMap(2, [None, None, *range(1, 120)], [False] * 121)
    flags = extract.matter_flags(pages, pmap)
    assert flags[1] == "contents" and flags[60] == ""
