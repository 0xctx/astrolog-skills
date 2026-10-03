"""Objective checks on a drafted (or live) pack: every claim's words are on its cited page, every cited rule has
evidence, the pack's own wording doesn't copy the source, and the rule tables pass their invariants."""

from __future__ import annotations

import contextlib
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from astrolog_skills.analysis.doctrine.rules import Problem, check_doctrine
from astrolog_skills.analysis.method import merge, parse
from astrolog_skills.errors import AstroError
from astrolog_skills.packs import draft, loader
from astrolog_skills.packs.crosscheck import lots_against_astrolog
from astrolog_skills.sources import index, library

MAX_GAP = 8  # words a quote may skip between its own words (figure labels, running heads, notes)
NEIGHBOURS = 3  # pages either side searched before the whole source
VERBATIM = 12  # this many words in a row shared with a cited page = copied wording
QUOTE_MAX = 25  # longer evidence quotes draw a warning (keep them to a phrase)
QUOTE_MIN = 4  # fewer words could be found almost anywhere
_PAGES = re.compile(r"(\d{1,4})\s*[-–]\s*(\d{1,4})|(\d{1,4})")
_CITE_IN_TEXT = re.compile(r"(\bpp?\.|§)\s*([\d,\s–-]+\d)")  # "p. 488", "pp. 12-14", "§ 12"
_WORD = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower().replace("’", "'"))


def page_numbers(text: str) -> set[int]:
    """'p. 512, 518-520' → {512, 518, 519, 520}."""
    out: set[int] = set()
    for a, b, single in _PAGES.findall(text):
        if single:
            out.add(int(single))
        elif int(b) >= int(a) and int(b) - int(a) < 200:
            out.update(range(int(a), int(b) + 1))
    return out


def contains(quote: list[str], page: list[str], max_gap: int = MAX_GAP) -> bool:
    """The quote's words appear in order, each within `max_gap` words of the last; a word may also be split in two
    on the page (a hyphen at a line break)."""

    def at(k: int, word: str) -> int:
        if k < len(page) and page[k] == word:
            return 1
        if k + 1 < len(page) and page[k] + page[k + 1] == word:
            return 2
        return 0

    if not quote:
        return False
    for start in range(len(page)):
        step = at(start, quote[0])
        if not step:
            continue
        pos, ok = start + step, True
        for word in quote[1:]:
            for skip in range(max_gap + 1):
                step = at(pos + skip, word)
                if step:
                    pos += skip + step
                    break
            else:
                ok = False
                break
        if ok:
            return True
    return False


@dataclass
class Claim:
    rule: str
    page: str
    quote: str
    source: str = ""
    n: int = 0


@dataclass
class Report:
    target: str  # "draft" | "live"
    claims: int = 0
    found: int = 0
    problems: list[Problem] = field(default_factory=list)
    crosschecked: list[str] = field(default_factory=list)  # lots that matched Astrolog's own parts
    backing: dict[str, list[str]] = field(default_factory=dict)  # rule → the sources whose evidence was found

    @property
    def errors(self) -> int:
        return sum(1 for p in self.problems if p.level == "error")

    def to_dict(self) -> dict[str, Any]:
        warnings = len(self.problems) - self.errors
        return {
            "ok": self.errors == 0,
            "target": self.target,
            "claims": self.claims,
            "found": self.found,
            "errors": self.errors,
            "warnings": warnings,
            "astrolog_checked": self.crosschecked,
            "problems": [p.to_dict() for p in self.problems],
            "backing": self.backing,
            "several_sources": sorted(r for r, s in self.backing.items() if len(s) > 1),
        }


class _Source:
    """Printed pages of one source, tokenised on demand."""

    def __init__(self, pack: str, source_id: str) -> None:
        self.id = source_id
        self.db = library.index_path(pack, source_id)
        self._cache: dict[int, list[str] | None] = {}
        self._text: dict[int, str] = {}
        self.kind = index.meta(self.db).get("kind", "pages") if self.db.is_file() else "pages"

    def cite(self, page: int | str) -> str:
        """ "p. 488" or "§ 12" — a claim's page as written when it already says which."""
        text = str(page).strip()
        return (
            text if text[:1] in ("§", "p") else library.cite(self.kind, int(text) if text.isdigit() else None) or text
        )

    def words(self, printed: int) -> list[str] | None:
        if printed not in self._cache:
            try:
                self._text[printed] = index.page(self.db, printed)[2]
                self._cache[printed] = tokens(self._text[printed])
            except AstroError:
                self._cache[printed] = None
        return self._cache[printed]

    def prose(self, printed: int) -> list[str]:
        """The page's words without short lines (figure labels, running heads), so copied sentences read through."""
        if self.words(printed) is None:
            return []
        lines = self._text[printed].splitlines()
        return tokens("\n".join(ln for ln in lines if len(ln.split()) >= 4))

    def all_printed(self) -> list[int]:
        import sqlite3

        with sqlite3.connect(self.db) as db:
            return [int(r[0]) for r in db.execute("SELECT printed FROM pages WHERE printed IS NOT NULL ORDER BY 1")]


def _files(pack: str, live: bool) -> tuple[Path, Path]:
    """(folder with the pack files, evidence file)."""
    if live:
        return library.pack_dir(pack), draft.evidence_live(pack)
    folder = draft.draft_dir(pack)
    if not folder.is_dir():
        raise AstroError(f"Pack '{pack}' has no draft to verify.", fix=f"astro packs draft {pack}, or use --live")
    return folder, folder / draft.EVIDENCE


def _claims(path: Path, report: Report) -> list[Claim]:
    if not path.is_file():
        return []
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as err:
        report.problems.append(Problem("error", path.name, f"can't read it: {err}"))
        return []
    out = []
    for n, c in enumerate(raw.get("claim", []), start=1):
        if not isinstance(c, dict) or not all(isinstance(c.get(k), str | int) for k in ("rule", "page", "quote")):
            report.problems.append(Problem("error", f"evidence #{n}", "needs rule, page and quote"))
            continue
        out.append(Claim(str(c["rule"]), str(c["page"]), str(c["quote"]), str(c.get("source", "")), n))
    return out


def _method_raw(folder: Path, report: Report) -> dict[str, Any] | None:
    path = folder / "method.toml"
    if not path.is_file():
        return None
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as err:
        report.problems.append(Problem("error", "method.toml", f"isn't valid TOML: {err}"))
        return None
    return raw


def _rule_cite(raw: dict[str, Any], rule: str) -> tuple[bool, str]:
    """(the rule exists, the cite of its nearest table)."""
    node: Any = raw
    cite = str(raw.get("cite", ""))
    for part in rule.split("."):
        if not isinstance(node, dict) or part not in node:
            return False, ""
        node = node[part]
        if isinstance(node, dict) and "cite" in node:
            cite = str(node["cite"])
    return True, cite


_SEGMENT_SOURCE = re.compile(r"^\s*([a-z0-9][a-z0-9_-]*)\s+(?=(?:pp?\.|§|\d))", re.I)


def cite_pages(cite: str) -> dict[str, set[int]]:
    """A rule's cite by source: "book p. 525; course § 12" → {"book": {525}, "course": {12}}. Segments without a
    source name ("p. 525") go under "" and count for any source."""
    out: dict[str, set[int]] = {}
    for segment in cite.split(";"):
        m = _SEGMENT_SOURCE.match(segment)
        source = m.group(1).lower() if m and m.group(1).lower() not in ("p", "pp") else ""
        out.setdefault(source, set()).update(page_numbers(segment[m.end() :] if source and m else segment))
    return out


def _md_section(text: str, heading: str) -> str | None:
    """The text under a markdown heading (to the next heading of the same or higher level)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(#+)\s+(.*?)\s*$", line)
        if m and m[2].strip().lower() == heading.strip().lower():
            level, body = len(m[1]), []
            for nxt in lines[i + 1 :]:
                h = re.match(r"^(#+)\s", nxt)
                if h and len(h[1]) <= level:
                    break
                body.append(nxt)
            return "\n".join(body)
    return None


def _cited_tables(raw: dict[str, Any], prefix: str = "") -> list[str]:
    out = []
    for key, value in raw.items():
        if isinstance(value, dict):
            path = f"{prefix}{key}"
            if "cite" in value:
                out.append(path)
            out += _cited_tables(value, path + ".")
    return out


def verify(pack: str, live: bool = False) -> Report:
    report = Report("live" if live else "draft")
    folder, evidence = _files(pack, live)
    raw = _method_raw(folder, report)

    # 1. the rules parse and pass their own checks
    if raw is not None:
        merged = raw
        if raw.get("extends"):
            try:
                merged = merge(loader.raw_method(str(raw["extends"])), raw)
            except AstroError as err:
                report.problems.append(Problem("error", "method.toml", err.message))
        try:
            method = parse(merged, f"pack '{pack}' ({report.target})")
            if method.doctrine is not None:
                problems = check_doctrine(method.doctrine)
                report.problems += problems
                if method.doctrine.lots and not any(p.level == "error" for p in problems):
                    cross = lots_against_astrolog(method.doctrine)
                    report.crosschecked = cross.checked
                    report.problems += cross.problems
        except AstroError as err:
            report.problems.append(Problem("error", "method.toml", err.message, err.fix or ""))

    # 2. every claim: the rule exists, the page is within its cite, the words are on the page
    claims = _claims(evidence, report)
    report.claims = len(claims)
    sources: dict[str, _Source] = {}
    texts = {n: (folder / n).read_text(encoding="utf-8") for n in draft.PACK_FILES if (folder / n).is_file()}
    for c in claims:
        where = f"evidence #{c.n} ({c.rule})"
        if "#" in c.rule:
            name, heading = c.rule.split("#", 1)
            section = _md_section(texts.get(name, ""), heading)
            exists, cite = section is not None, ""
            if section is not None:
                cite = " ".join(m for _, m in _CITE_IN_TEXT.findall(section))
        else:
            exists, cite = _rule_cite(raw or {}, c.rule)
        if not exists:
            report.problems.append(Problem("error", where, "no such rule or heading in the pack"))
            continue
        pages = page_numbers(c.page)
        if not pages:
            report.problems.append(Problem("error", where, f"page {c.page!r} isn't a page number"))
            continue
        if not cite:
            report.problems.append(Problem("warn", where, "the rule has no cite", 'add cite = "p. …"'))
        else:
            by_source = cite_pages(cite)
            claim_source = c.source
            if not claim_source:
                with contextlib.suppress(AstroError):  # the pack's only source, when it has one
                    claim_source = library.resolve(pack, None)
            allowed = by_source.get("", set()) | by_source.get((claim_source or "").lower(), set())
            if not pages <= allowed:
                report.problems.append(
                    Problem("warn", where, f"{c.page} isn't in the rule's cite ({cite})", "add the page to its cite")
                )
        if len(tokens(c.quote)) < QUOTE_MIN:
            report.problems.append(Problem("error", where, "quote is too short to prove anything", "use 5–20 words"))
            continue
        if len(tokens(c.quote)) > QUOTE_MAX:
            report.problems.append(Problem("warn", where, "quote is long — a short phrase is enough"))
        try:
            sid = library.resolve(pack, c.source or None)
        except AstroError as err:
            report.problems.append(Problem("error", where, err.message, err.fix or ""))
            continue
        src = sources.setdefault(sid, _Source(pack, sid))
        quote = tokens(c.quote)
        if any(contains(quote, src.words(p) or []) for p in pages):
            report.found += 1
            backers = report.backing.setdefault(c.rule, [])
            if sid not in backers:
                backers.append(sid)
            continue
        missing = [p for p in sorted(pages) if src.words(p) is None]
        if missing:
            report.problems.append(Problem("error", where, f"{sid} has no {src.cite(missing[0])}"))
            continue
        near = [p for d in range(1, NEIGHBOURS + 1) for p in (min(pages) - d, max(pages) + d)]
        elsewhere = next((p for p in near if contains(quote, src.words(p) or [])), None)
        if elsewhere is None:
            elsewhere = next((p for p in src.all_printed() if contains(quote, src.words(p) or [])), None)
        if elsewhere is not None:
            report.problems.append(
                Problem(
                    "error", where, f"wrong citation: the words are on {src.cite(elsewhere)}, not {src.cite(c.page)}"
                )
            )
        else:
            report.problems.append(
                Problem("error", where, f"the words aren't on {src.cite(c.page)} (or anywhere in {sid})")
            )

    # your own edits since the last apply that this draft would change
    if not live:
        for d in draft.diff(pack):
            for line in d.edits_changed:
                report.problems.append(
                    Problem("warn", d.name, f"changes a line you edited by hand: {line.strip()[:90]}",
                            "keep your line in the draft, or confirm the change with the owner")
                )  # fmt: skip

    # 3. coverage: each cited table has at least one claim
    if raw is not None and raw.get("cited") is False:
        report.problems.append(
            Problem(
                "warn",
                "method.toml",
                "the pack is marked uncited (cited = false): a sample with no page citations",
                "give each rule a cite and a claim from your sources, then remove cited = false",
            )
        )
    if raw is not None:
        for path in _cited_tables(raw):
            if not any(c.rule == path or c.rule.startswith(path + ".") for c in claims):
                report.problems.append(
                    Problem("warn", path, "no evidence for this rule", "add a [[claim]] with a few words from the page")
                )

    # 4. the pack's wording is its own
    cited: dict[str, set[int]] = {}
    for c in claims:
        with contextlib.suppress(AstroError):
            cited.setdefault(library.resolve(pack, c.source or None), set()).update(page_numbers(c.page))
    # page numbers in the prose: "p." ones belong to the pack's books, "§" ones to its notes and transcripts
    in_text: dict[str, set[int]] = {"pages": set(), "sections": set()}
    for text in texts.values():
        for mark, numbers in _CITE_IN_TEXT.findall(text):
            in_text["sections" if mark == "§" else "pages"].update(page_numbers(numbers))
    for row in library.list_sources(pack):
        if row.get("indexed") and in_text.get(str(row.get("kind", "pages"))):
            cited.setdefault(str(row["id"]), set()).update(in_text[str(row.get("kind", "pages"))])
    shingles: dict[tuple[str, ...], str] = {}
    for sid, pages in cited.items():
        src = sources.setdefault(sid, _Source(pack, sid))
        for p in pages:
            words = src.prose(p)
            for i in range(len(words) - VERBATIM + 1):
                shingles.setdefault(tuple(words[i : i + VERBATIM]), src.cite(p))
    if shingles:
        for name, text in texts.items():
            if name == "REVIEW.md":
                continue
            words = tokens(text)
            hits = {
                shingles[tuple(words[i : i + VERBATIM])]
                for i in range(len(words) - VERBATIM + 1)
                if tuple(words[i : i + VERBATIM]) in shingles
            }
            if hits:
                pages_hit = ", ".join(sorted(hits))
                report.problems.append(
                    Problem(
                        "error",
                        name,
                        f"copies the source's wording ({pages_hit})",
                        "rewrite those passages in your own words",
                    )
                )
    return report
