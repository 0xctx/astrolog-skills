"""Notes and course transcripts as sources: cut into sections (timestamps and lessons, headings, parts), searched,
found by label, and checked by the pack builder like a book's printed pages. Synthetic texts only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from astrolog_skills.errors import AstroError
from astrolog_skills.packs import draft, verify
from astrolog_skills.sources import extract, index, library
from tests.conftest import run_cli


def words(n: int, word: str = "talk") -> str:
    return " ".join([word] * n)


TRANSCRIPT = f"""Lesson 1: Sect
00:00 Welcome to the first class.
00:30 {words(210)}
02:10 The day team is led by the Sun with Jupiter and Saturn, and that is the core of sect.
03:00 {words(30)}
Lesson 2: Lots
00:00 Today the lots, starting with Fortune.
00:40 {words(205, "count")}
05:15 Fortune is counted from the Sun to the Moon by day and the reverse by night.
"""

SRT = """1
00:00:01,000 --> 00:00:04,000
Welcome back to the course.

2
00:41:10,500 --> 00:41:14,000
Profections move one sign each year from the rising sign.
"""

VTT = """WEBVTT

00:00:01.000 --> 00:00:04.000
Hello and welcome.

01:02:03.000 --> 01:02:07.000
Releasing from Spirit shows the career chapters.
"""

NOTES = """# Hellenistic notes

## Profections
### Annual
Each year the rising sign moves on by one sign; the lord of that sign is the lord of the year.

### Monthly
Not covered in class.

## Releasing
Peaks come in the tenth from Fortune.
"""


def test_transcript_by_time_and_lesson(tmp_path: Path) -> None:
    f = tmp_path / "course.txt"
    f.write_text(TRANSCRIPT)
    u = extract.units(f)
    assert (u.kind, u.how) == ("sections", "timestamps")
    assert u.labels == ["Lesson 1, 00:00", "Lesson 1, 02:10", "Lesson 2, 00:00", "Lesson 2, 05:15"]
    assert "day team is led by the Sun" in u.texts[1] and "00:" not in u.texts[1]  # timestamps stripped
    assert all(len(t.split()) >= extract.SECTION_WORDS for t in u.texts[:1])


def test_captions(tmp_path: Path) -> None:
    srt = tmp_path / "lesson-3.srt"
    srt.write_text(SRT)
    u = extract.units(srt)
    assert u.how == "timestamps" and u.labels == ["00:00:01"]  # short cues gather into one section
    assert "Profections move one sign" in u.texts[0] and "-->" not in u.texts[0] and "\n2\n" not in u.texts[0]
    vtt = tmp_path / "lesson-4.vtt"
    vtt.write_text(VTT)
    v = extract.units(vtt)
    assert v.labels == ["00:00:01"] and "WEBVTT" not in v.texts[0] and "Releasing from Spirit" in v.texts[0]


def test_notes_by_heading(tmp_path: Path) -> None:
    f = tmp_path / "notes.md"
    f.write_text(NOTES)
    u = extract.units(f)
    assert u.how == "headings"
    assert u.labels == [
        "Hellenistic notes › Profections › Annual",
        "Hellenistic notes › Profections › Monthly",
        "Hellenistic notes › Releasing",
    ]  # a heading with no text of its own (Profections) doesn't make an empty section


def test_plain_text_in_parts_and_pages_unchanged(tmp_path: Path) -> None:
    f = tmp_path / "plain.txt"
    f.write_text("\n\n".join(words(150, f"w{i}") for i in range(6)))
    u = extract.units(f)
    assert u.how == "parts" and u.labels == ["part 1", "part 2"]
    paged = tmp_path / "paged.txt"
    paged.write_text("first\fsecond")
    assert extract.units(paged).kind == "pages"
    with pytest.raises(AstroError, match="caption"):
        extract.units(tmp_path / "x.docx")


def test_add_search_and_find(tmp_path: Path) -> None:
    f = tmp_path / "course.txt"
    f.write_text(TRANSCRIPT)
    added = library.add("mini", f)
    assert (added.kind, added.how, added.pages) == ("sections", "timestamps", 4)
    hit = index.search(added.index, "day team")[0]
    assert (hit.printed, hit.label) == (2, "Lesson 1, 02:10")
    assert index.find(added.index, "lesson 1, 2:40") == 2  # the section running at that time
    assert index.find(added.index, "lesson 2, 06:00") == 4
    assert index.find(added.index, "Lesson 2") == 3
    with pytest.raises(AstroError):
        index.find(added.index, "lesson 9")
    entry = library.list_sources("mini")[0]
    assert entry["kind"] == "sections" and entry["units"] == "timestamps"
    with pytest.raises(AstroError, match="no text"):
        empty = tmp_path / "empty.md"
        empty.write_text("   \n")
        library.add("mini", empty)


def test_cli_cites_sections(tmp_path: Path) -> None:
    f = tmp_path / "notes.md"
    f.write_text(NOTES)
    assert run_cli("sources", "add", "mini", str(f)).returncode == 0
    found = json.loads(run_cli("--json", "sources", "search", "mini", "lord of the year").stdout)
    assert found["hits"][0]["kind"] == "sections" and found["hits"][0]["source"] == "notes"
    assert found["hits"][0]["cite"] == "§ 1" and found["hits"][0]["where"].endswith("Profections › Annual")
    page = json.loads(run_cli("--json", "sources", "page", "mini", "releasing").stdout)
    assert page["printed"] == 3 and page["cite"] == "§ 3" and "tenth from Fortune" in page["text"]
    assert json.loads(run_cli("--json", "sources", "page", "mini", "2").stdout)["label"].endswith("Monthly")
    assert run_cli("sources", "render", "mini", "1").returncode != 0  # only PDF pages render


def test_verify_checks_section_claims(tmp_path: Path) -> None:
    f = tmp_path / "course.txt"
    f.write_text(TRANSCRIPT)
    library.add("mini", f)
    folder = draft.start("mini").path
    (folder / "method.toml").write_text(
        'label = "Mini"\n[aspects]\nset = ["conjunction"]\n[orbs]\nconjunction = 8\n'
        '[sect]\ncite = "§ 2"\nday_rule = "sun_above_horizon"\ndiurnal = ["sun", "jupiter", "saturn"]\n'
        'nocturnal = ["moon", "venus", "mars"]\nmercury = "morning_evening"\n'
    )
    (folder / "evidence.toml").write_text(
        '[[claim]]\nrule = "sect"\npage = "§ 2"\nquote = "the day team is led by the Sun with Jupiter and Saturn"\n'
    )
    report = verify.verify("mini")
    assert report.found == 1, [p.message for p in report.problems]
    (folder / "evidence.toml").write_text(
        '[[claim]]\nrule = "sect"\npage = "§ 4"\nquote = "the day team is led by the Sun with Jupiter and Saturn"\n'
    )
    report = verify.verify("mini")
    messages = [p.message for p in report.problems]
    assert any("wrong citation: the words are on § 2, not § 4" in m for m in messages), messages
    # the pack's own prose citing a section is checked for copied wording too
    (folder / "evidence.toml").write_text(
        '[[claim]]\nrule = "sect"\npage = "§ 2"\nquote = "the day team is led by the Sun with Jupiter and Saturn"\n'
    )
    (folder / "meanings.md").write_text(
        "# Mini\n\n## Sect\n- **Sect** — The day team is led by the Sun with Jupiter and Saturn, and that is the core"
        " of sect. (§ 2)\n"
    )
    messages = [p.message for p in verify.verify("mini").problems]
    assert any("copies the source's wording (§ 2)" in m for m in messages), messages


def test_outline_by_lesson_and_heading(tmp_path: Path) -> None:
    from astrolog_skills.packs.build import outline

    course = tmp_path / "course.txt"
    course.write_text(TRANSCRIPT)
    library.add("mini", course)
    o = outline("mini").to_dict()
    assert o["kind"] == "sections" and [c["title"] for c in o["chapters"]] == ["Lesson 1", "Lesson 2"]
    assert [s["title"] for s in o["chapters"][1]["sections"]] == ["00:00", "05:15"]
    notes = tmp_path / "notes.md"
    notes.write_text(NOTES)
    library.add("other", notes)
    chapters = outline("other").to_dict()["chapters"]
    assert [c["title"] for c in chapters] == ["Hellenistic notes"]
    assert chapters[0]["sections"][0]["title"] == "Profections › Annual"


def test_a_second_source_joins_the_pack(tmp_path: Path) -> None:
    """Add a course to a pack that already has notes: search covers both, and the next draft starts from the live
    pack so the new source extends it."""
    notes = tmp_path / "notes.md"
    notes.write_text(NOTES)
    course = tmp_path / "course.txt"
    course.write_text(TRANSCRIPT)
    library.add("mini", notes)
    folder = draft.start("mini").path
    (folder / "method.toml").write_text('label = "Mini"\n[aspects]\nset = ["conjunction"]\n[orbs]\nconjunction = 8\n')
    draft.apply("mini")
    library.add("mini", course)
    both = json.loads(run_cli("--json", "sources", "search", "mini", "Fortune").stdout)
    assert both["sources"] == ["notes", "course"] and {h["source"] for h in both["hits"]} == {"notes", "course"}
    one = json.loads(run_cli("--json", "sources", "search", "mini", "Fortune", "--source", "course").stdout)
    assert {h["source"] for h in one["hits"]} == {"course"}
    again = draft.start("mini")
    assert "method.toml" in again.copied and 'label = "Mini"' in (again.path / "method.toml").read_text()
