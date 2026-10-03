from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from astrolog_skills.errors import AstroError
from astrolog_skills.sources import extract, index, library
from tests.conftest import run_cli
from tests.fakes.mini_pdf import write_pdf

pytestmark = pytest.mark.skipif(shutil.which("pdftotext") is None, reason="poppler (pdftotext) not installed")

BODY = ["sect day night chart benefic malefic"] * 6  # 36 words: enough for a text layer


def book(tmp_path: Path) -> Path:
    """8 pages: title, contents, five body pages printed 1–5 (PDF offset 2), then an index."""
    pages = [
        ["A Test Book", "by Nobody"],
        ["Contents", "Planets ...... 1", "Sect ...... 2", "Lots ...... 3", "Timing ...... 4", "Index ...... 6"],
        ["1\tCHAPTER 1: PLANETS", *BODY, "The planets wander."],
        ["SECT\t2", *BODY, "Sect divides day charts from night charts.", "under the beams"],
        ["3\tCHAPTER 2: LOTS", *BODY, "The Lot of Fortune marks the body."],
        ["TIMING\t4", *BODY, "Profections move one sign a year."],
        ["5\tCHAPTER 3: RELEASING", *BODY, "Releasing counts sign periods."],
        ["Index", "sect 2", "lots 3", "under the beams 2"],
    ]
    return write_pdf(tmp_path / "Test Book.pdf", pages)


def test_extract_printed_pages_and_matter(tmp_path: Path) -> None:
    pages = extract.extract_pages(book(tmp_path))
    assert len(pages) == 8 and extract.has_text_layer(pages)
    pmap = extract.printed_pages(pages)
    assert pmap.offset == 2
    assert pmap.printed == [None, None, 1, 2, 3, 4, 5, 6]
    assert pmap.confirmed[2:7] == [True] * 5
    flags = extract.matter_flags(pages, pmap)
    assert flags[0] == "front" and flags[1] == "contents" and flags[7] == "back" and flags[2:7] == [""] * 5


def test_text_files_and_no_text_layer(tmp_path: Path) -> None:
    one = tmp_path / "notes.txt"
    one.write_text("just one page of notes")
    assert extract.extract_pages(one) == ["just one page of notes"]
    two = tmp_path / "paged.txt"
    two.write_text("first\fsecond")
    assert extract.extract_pages(two) == ["first", "second"]
    scan = write_pdf(tmp_path / "scan.pdf", [[], [], []])
    assert not extract.has_text_layer(extract.extract_pages(scan))
    with pytest.raises(AstroError) as err:
        library.add("hellenistic", scan)
    assert "scan" in str(err.value) and err.value.fix and "ocrmypdf" in err.value.fix  # the install line
    assert not (library.sources_dir("hellenistic") / "scan.pdf").exists()  # rejected files aren't copied in
    with pytest.raises(AstroError):
        extract.extract_pages(tmp_path / "x.docx")


def test_index_search_ranks_body_above_contents_and_index(tmp_path: Path) -> None:
    added = library.add("hellenistic", book(tmp_path))
    assert added.id == "test-book" and added.pages == 8 and added.offset == 2
    assert added.matter == {"front": 1, "contents": 1, "back": 1}
    hits = index.search(added.index, '"under the beams"')
    assert hits[0].printed == 2 and hits[0].matter == "" and hits[-1].matter == "back"
    assert index.search(added.index, "Fortune body")[0].printed == 3
    assert index.search(added.index, "sect OR lots") == []  # OR is a word unless --raw
    assert {h.printed for h in index.search(added.index, "Fortune OR Profections", raw=True)} == {3, 4}
    with pytest.raises(AstroError):
        index.search(added.index, '"unclosed', raw=True)
    with pytest.raises(AstroError):
        index.fts_query('  ""  ')
    pdf_page, printed, text, _ = index.page(added.index, 4)
    assert (pdf_page, printed) == (6, 4) and "Profections" in text
    assert index.page(added.index, 1, pdf=True)[1] is None
    with pytest.raises(AstroError):
        index.page(added.index, 99)


def test_sources_toml_kept_and_readd_replaces(tmp_path: Path) -> None:
    pdf = book(tmp_path)
    toml = library.pack_dir("hellenistic") / "sources.toml"
    library.pack_dir("hellenistic").mkdir(parents=True)
    toml.write_text('[[source]]\nid = "other"\ntitle = "Another text"\ncovers = "lots"\n')
    assert not library.add("hellenistic", pdf).replaced
    assert library.add("hellenistic", pdf).replaced  # again: rebuilt and reported, not duplicated
    entries = library.read_toml("hellenistic")
    assert [e["id"] for e in entries] == ["other", "test-book"]
    assert entries[1]["file"] == "sources/test-book.pdf" and entries[1]["pages"] == 8
    assert (library.sources_dir("hellenistic") / "test-book.pdf").is_file()
    listed = {s["id"]: s for s in library.list_sources("hellenistic")}
    assert listed["test-book"]["indexed"] and listed["test-book"]["offset"] == 2 and not listed["other"]["indexed"]
    assert library.resolve("hellenistic", None) == "test-book"
    with pytest.raises(AstroError):
        library.resolve("hellenistic", "missing")
    with pytest.raises(AstroError):
        library.pack_dir("///")


def test_cli_add_search_page_render(tmp_path: Path) -> None:
    pdf = book(tmp_path)
    added = json.loads(run_cli("--json", "sources", "add", "hellenistic", str(pdf)).stdout)
    assert added["pages"] == 8 and added["printed_offset"] == 2
    found = json.loads(run_cli("--json", "sources", "search", "hellenistic", "releasing").stdout)
    assert found["hits"][0]["printed"] == 5
    page = json.loads(run_cli("--json", "sources", "page", "hellenistic", "3").stdout)
    assert page["pdf_page"] == 5 and "Fortune" in page["text"]
    if shutil.which("pdftoppm"):
        image = json.loads(run_cli("--json", "sources", "render", "hellenistic", "2").stdout)
        assert Path(image["image"]).is_file() and image["pdf_page"] == 4
    listed = json.loads(run_cli("--json", "sources", "list", "hellenistic").stdout)
    assert listed["sources"][0]["id"] == "test-book"
    missing = run_cli("--json", "sources", "search", "empty-pack", "sect")
    assert missing.returncode == 1


def test_poppler_hint_per_os() -> None:
    assert extract.poppler_hint('ID="fedora"') == "sudo dnf install poppler-utils"
    assert extract.poppler_hint("ID=ubuntu\nID_LIKE=debian") == "sudo apt install poppler-utils"
    assert "pacman" in extract.poppler_hint("ID=arch")
