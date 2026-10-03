"""A source's search index: SQLite FTS5 over its units (a book's printed pages, or a transcript's or notes' numbered
sections with their labels), ranked by BM25."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from astrolog_skills.errors import AstroError

MATTER_PENALTY = 1000.0  # moves contents, front and back matter below every body page


@dataclass
class Hit:
    printed: int | None  # the printed page, or the section number
    pdf_page: int
    matter: str
    snippet: str
    score: float
    label: str = ""  # a section's timestamp, lesson or heading

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build(
    db_path: Path,
    pages: list[str],
    printed: list[int | None],
    matter: list[str],
    meta: dict[str, str],
    labels: list[str] | None = None,
) -> None:
    labels = labels or [""] * len(pages)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    with sqlite3.connect(tmp) as db:
        db.execute(
            "CREATE VIRTUAL TABLE pages USING fts5(pdf_page UNINDEXED, printed UNINDEXED, matter UNINDEXED,"
            " label UNINDEXED, body,"
            " tokenize='porter unicode61')"
        )
        db.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        db.executemany(
            "INSERT INTO pages VALUES (?, ?, ?, ?, ?)",
            [
                (i, p, m, lb, text)
                for i, (text, p, m, lb) in enumerate(zip(pages, printed, matter, labels, strict=True), 1)
            ],
        )
        db.executemany("INSERT INTO meta VALUES (?, ?)", [*meta.items(), ("built", date.today().isoformat())])
    tmp.replace(db_path)


def _open(db_path: Path) -> sqlite3.Connection:
    if not db_path.is_file():
        raise AstroError(f"This source isn't indexed yet ({db_path.name}).", fix="astro sources add <pack> <file>")
    return sqlite3.connect(db_path)


def meta(db_path: Path) -> dict[str, str]:
    with _open(db_path) as db:
        return dict(db.execute("SELECT key, value FROM meta").fetchall())


def fts_query(text: str) -> str:
    """Plain words → every word required; "quoted phrases" kept. FTS operators are only honoured with --raw."""
    phrases = re.findall(r'"([^"]+)"', text)
    words = re.sub(r'"[^"]*"', " ", text).split()
    terms = [f'"{p.strip()}"' for p in phrases if p.strip()]
    terms += ['"' + w.replace('"', "") + '"' for w in words if w.replace('"', "")]
    if not terms:
        raise AstroError("Nothing to search for.", fix='e.g. astro sources search <pack> "under the beams"')
    return " AND ".join(terms)


def search(db_path: Path, query: str, limit: int = 10, raw: bool = False) -> list[Hit]:
    match = query if raw else fts_query(query)
    sql = (
        "SELECT printed, pdf_page, matter, snippet(pages, 4, '[', ']', '…', 16), label, "
        "bm25(pages) + CASE WHEN matter = '' THEN 0 ELSE ? END AS score "
        "FROM pages WHERE pages MATCH ? ORDER BY score LIMIT ?"
    )
    try:
        with _open(db_path) as db:
            rows = db.execute(sql, (MATTER_PENALTY, match, limit)).fetchall()
    except sqlite3.OperationalError as err:
        raise AstroError(f"Search syntax problem: {err}.", fix="drop --raw, or quote phrases") from err
    return [
        Hit(int(p) if p is not None else None, int(pdf), m, " ".join(sn.split()), round(float(s), 3), lb or "")
        for p, pdf, m, sn, lb, s in rows
    ]


def page(db_path: Path, number: int, pdf: bool = False) -> tuple[int, int | None, str, str]:
    """(pdf page, printed page or section, text, label) for a printed page or section number (a PDF page with pdf)."""
    column = "pdf_page" if pdf else "printed"
    with _open(db_path) as db:
        row = db.execute(f"SELECT pdf_page, printed, body, label FROM pages WHERE {column} = ?", (number,)).fetchone()
    if row is None:
        raise AstroError(f"No {'PDF page' if pdf else 'page or section'} {number} in this source.")
    return int(row[0]), int(row[1]) if row[1] is not None else None, str(row[2]), str(row[3] or "")


def _seconds(stamp: str) -> int | None:
    parts = stamp.strip().split(":")
    if not 2 <= len(parts) <= 3 or not all(p.isdigit() for p in parts):
        return None
    total = 0
    for p in parts:
        total = total * 60 + int(p)
    return total


def find(db_path: Path, ref: str) -> int:
    """A section number from a label: a timestamp ("41:10") finds the section running at that time (within a lesson,
    "lesson 3, 41:10"); other text matches a label, ignoring case."""
    with _open(db_path) as db:
        rows = [
            (int(n), str(lb or ""))
            for n, lb in db.execute("SELECT printed, label FROM pages WHERE printed IS NOT NULL ORDER BY printed")
        ]
    want = ref.strip().lower()
    lesson, _, stamp = want.rpartition(",")
    at = _seconds(stamp)
    if at is not None:
        best = None
        for n, label in rows:
            lb_lesson, _, lb_stamp = label.lower().rpartition(",")
            start = _seconds(lb_stamp)
            if start is not None and lb_lesson.strip() == lesson.strip() and start <= at:
                best = n
        if best is not None:
            return best
    for n, label in rows:
        if want and want in label.lower():
            return n
    raise AstroError(f"No section matching '{ref}'.", fix="astro sources search … shows each section's label")
