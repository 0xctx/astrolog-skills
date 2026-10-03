"""Outline a source from its contents pages: chapters and sections with printed page ranges, figures and tables."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict, dataclass, field
from typing import Any

from astrolog_skills.sources import index, library

_ENTRY = re.compile(r"^\s*(?:(\d{1,3}(?:\.\d{1,3})?)\s+)?(\S.*?)\s+(\d{1,4})\s*$")
_LIST_HEADING = re.compile(r"\b(figures?|tables?|illustrations?|charts?|plates?)\b", re.I)
_BACK = re.compile(
    r"^(conclusion|epilogue|afterword|appendix|timeline|glossary|abbreviations|bibliography|index|notes)\b", re.I
)
_SKIP = re.compile(r"\bcontents\b|^list of\b", re.I)


@dataclass
class Entry:
    title: str
    start: int
    end: int = 0
    number: str = ""

    @property
    def pages(self) -> int:
        return self.end - self.start + 1


@dataclass
class Chapter(Entry):
    sections: list[Entry] = field(default_factory=list)


@dataclass
class Outline:
    source: str
    first: int  # first and last printed body pages
    last: int
    chapters: list[Chapter]
    back: list[Entry]
    figures: list[Entry]
    tables: list[Entry]
    kind: str = "pages"  # pages | sections (numbers are § sections, chapters are lessons or top headings)

    def to_dict(self) -> dict[str, Any]:
        def entry(e: Entry) -> dict[str, Any]:
            d = {k: v for k, v in asdict(e).items() if k != "sections"}
            d["pages"] = e.pages
            if isinstance(e, Chapter):
                d["sections"] = [entry(s) for s in e.sections]
            return d

        return {
            "source": self.source,
            "kind": self.kind,
            "body_pages": [self.first, self.last],
            "chapters": [entry(c) for c in self.chapters],
            "back": [entry(e) for e in self.back],
            "figures": [entry(e) for e in self.figures],
            "tables": [entry(e) for e in self.tables],
        }


def _contents_pages(db: sqlite3.Connection) -> list[str]:
    return [str(r[0]) for r in db.execute("SELECT body FROM pages WHERE matter = 'contents' ORDER BY pdf_page")]


def parse_contents(pages: list[str], last_page: int) -> tuple[list[Chapter], list[Entry], list[Entry], list[Entry]]:
    """Contents text → (chapters with sections, back matter, figures, tables)."""
    chapters: list[Chapter] = []
    back: list[Entry] = []
    figures: list[Entry] = []
    tables: list[Entry] = []
    mode = "contents"
    for page in pages:
        for line in page.splitlines():
            text = line.strip()
            if not text:
                continue
            if not re.search(r"\d\s*$", text):  # a heading or running head, not an entry
                if re.search(r"\bcontents\b", text, re.I):
                    mode = "contents"
                elif m := _LIST_HEADING.search(text):
                    # a combined "figures and tables" list starts with its figures
                    mode = "tables" if m[1].lower().startswith("table") and "figure" not in text.lower() else "figures"
                continue
            m = _ENTRY.match(line)
            if not m or _SKIP.search(m[2]):
                continue
            number, title, start = m[1] or "", m[2].strip().rstrip(" .·…").strip(), int(m[3])
            if mode in ("figures", "tables") or "." in number:
                (tables if mode == "tables" else figures).append(Entry(title, start, number=number))
            elif _BACK.match(title):
                back.append(Entry(title, start))
            elif number or (title.upper() == title and any(c.isalpha() for c in title)):
                chapters.append(Chapter(title, start, number=number))
            elif chapters:
                chapters[-1].sections.append(Entry(title, start))
    _close([*chapters, *back], last_page)
    for c in chapters:
        _close(c.sections, c.end)
    return chapters, back, figures, tables


def _close(entries: list[Any], last: int) -> None:
    """Each entry ends where the next begins."""
    for e, nxt in zip(entries, [*entries[1:], None], strict=False):
        e.end = max(e.start, (nxt.start - 1) if nxt is not None else last)


def _section_outline(sid: str, rows: list[tuple[int, str]]) -> Outline:
    """Notes and transcripts: a chapter per lesson or top heading, its sections by timestamp or subheading."""
    chapters: list[Chapter] = []
    for n, label in rows:
        head, sep, rest = label.partition(" › ") if " › " in label else label.rpartition(", ")
        if not sep:  # a plain timestamp or "part N" belongs to the whole source; a lone heading is its own chapter
            plain = re.fullmatch(r"(\d{1,2}:)?\d{1,2}:\d{2}|part \d+|start", label)
            head = sid if plain else label
        if not chapters or chapters[-1].title != head:
            chapters.append(Chapter(head, n, n))
        chapters[-1].end = n
        chapters[-1].sections.append(Entry(rest if sep else label, n, n, number=f"§ {n}"))
    first, last = (rows[0][0], rows[-1][0]) if rows else (0, 0)
    return Outline(sid, first, last, chapters, [], [], [], kind="sections")


def outline(pack: str, source_id: str | None = None) -> Outline:
    sid = library.resolve(pack, source_id)
    if index.meta(library.index_path(pack, sid)).get("kind") == "sections":
        with sqlite3.connect(library.index_path(pack, sid)) as db:
            found = db.execute("SELECT printed, label FROM pages ORDER BY printed")
            rows = [(int(n), str(lb or "")) for n, lb in found]
        return _section_outline(sid, rows)
    with sqlite3.connect(library.index_path(pack, sid)) as db:
        first, last = db.execute("SELECT MIN(printed), MAX(printed) FROM pages WHERE matter = ''").fetchone()
        (final,) = db.execute("SELECT MAX(printed) FROM pages").fetchone()
        contents = _contents_pages(db)
    chapters, back, figures, tables = parse_contents(contents, int(final or 0))
    return Outline(sid, int(first or 0), int(last or 0), chapters, back, figures, tables)
