"""Source → citable units: a book's pages (with its printed page numbers and front/back matter), or the sections of a
transcript or notes file (by timestamp and lesson, by heading, or in parts).

PDFs go through poppler's `pdftotext -layout` (one form feed per page); text with form feeds is paged the same way.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from astrolog_skills import packages
from astrolog_skills.errors import AstroError

TEXT_SUFFIXES = (".txt", ".md", ".text", ".srt", ".vtt")
SECTION_WORDS = 200  # a timestamped section runs until it has at least this many words (about a minute and a half)
PART_WORDS = 400  # plain text without timestamps or headings: parts of about this size, cut at paragraph breaks
_STAMP = re.compile(r"^\s*[\[(]?((?:\d{1,2}:)?\d{1,2}:\d{2})(?:[.,]\d{1,3})?[\])]?(?:\s*(?:-->|–|-)\s*[\d:.,]+)?\s*")
_CUE_NUMBER = re.compile(r"^\s*\d+\s*$")
_LESSON = re.compile(r"^\s*#*\s*((?:lesson|module|class|session|week|part|episode|lecture|unit)\s+\d+)\b.{0,60}$", re.I)
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_NUMBER_LINE = re.compile(r"^\s*(\d{1,4})\s*$")
_NUMBER_EDGE = re.compile(r"^\s*(\d{1,4})\s{2,}\S.{0,70}$|^.{0,70}\S\s{2,}(\d{1,4})\s*$")
_TOC_LINE = re.compile(r"^\s*\S.*\s(\d{1,4})\s*$")
_BACK_HEADINGS = re.compile(r"^\s*(bibliography|index|glossary|notes|references|abbreviations)\s*$", re.I)


def poppler_hint(os_release: str | None = None) -> str:
    """The one command that installs poppler (pdftotext, pdftoppm) on this OS."""
    return packages.hint(
        {"*": "poppler-utils", "pacman": "poppler", "zypper": "poppler-tools"},
        mac="brew install poppler",
        windows="install poppler for Windows and put its bin folder on PATH",
        otherwise="install poppler (it provides pdftotext and pdftoppm) with your package manager",
        os_release=os_release,
    )


def ocr_hint(os_release: str | None = None) -> str:
    """The command that installs ocrmypdf (with tesseract) on this OS."""
    return packages.hint(
        {"*": "ocrmypdf"},
        mac="brew install ocrmypdf",
        windows="pip install ocrmypdf (and install Tesseract for Windows)",
        otherwise="install ocrmypdf (it brings tesseract) with your package manager, or: pip install ocrmypdf",
        os_release=os_release,
    )


def ocr(source: Path, target: Path) -> None:
    """Give a scanned PDF a text layer (ocrmypdf + tesseract), written to `target`."""
    binary = shutil.which("ocrmypdf")
    if binary is None:
        raise AstroError(
            f"{source.name} has no text layer (it looks like a scan), and ocrmypdf isn't installed to read it.",
            fix=ocr_hint(),
        )
    done = subprocess.run(
        [binary, "--skip-text", "--quiet", str(source), str(target)], capture_output=True, text=True, check=False
    )
    if done.returncode != 0 or not target.is_file():
        raise AstroError(f"OCR failed on {source.name}: {done.stderr.strip()[:200]}", fix="check the PDF opens")


def _run(tool: str, args: list[str]) -> str:
    binary = shutil.which(tool)
    if binary is None:
        raise AstroError(f"{tool} isn't installed — it's needed to read PDF sources.", fix=poppler_hint())
    done = subprocess.run([binary, *args], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise AstroError(f"{tool} couldn't read the file: {done.stderr.strip()[:200]}", fix="check the file opens")
    return done.stdout


def pdf_info(path: Path) -> dict[str, str]:
    """pdfinfo's key: value pairs (Title, Author, Pages, …)."""
    info: dict[str, str] = {}
    for line in _run("pdfinfo", [str(path)]).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            info[key.strip()] = value.strip()
    return info


def extract_pages(path: Path) -> list[str]:
    """The text of each page, in order."""
    if path.suffix.lower() in TEXT_SUFFIXES:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text.split("\f") if "\f" in text else [text]
    if path.suffix.lower() != ".pdf":
        raise AstroError(f"Can't read {path.name}: sources are PDF or text files.", fix="convert it to PDF or .txt")
    pages = _run("pdftotext", ["-layout", str(path), "-"]).split("\f")
    if pages and not pages[-1].strip():
        pages.pop()  # pdftotext ends with a form feed
    return pages


@dataclass
class Units:
    """A source cut into citable units: "pages" (printed page numbers) or "sections" (numbered, with labels)."""

    kind: str  # pages | sections
    how: str  # pdf | form feeds | timestamps | headings | parts
    texts: list[str]
    labels: list[str]  # "" for pages


def units(path: Path) -> Units:
    """The source's citable units, whatever kind of file it is."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return Units("pages", "pdf", (p := extract_pages(path)), [""] * len(p))
    if suffix not in TEXT_SUFFIXES:
        raise AstroError(
            f"Can't read {path.name}: sources are PDF, text, Markdown or caption (.srt, .vtt) files.",
            fix="convert it to PDF or .txt",
        )
    text = path.read_text(encoding="utf-8", errors="replace")
    if "\f" in text:
        return Units("pages", "form feeds", (p := text.split("\f")), [""] * len(p))
    lines = text.splitlines()
    if suffix in (".srt", ".vtt") or sum(1 for ln in lines if _STAMP.match(ln)) >= 3:
        return _by_time(lines)
    if sum(1 for ln in lines if _HEADING.match(ln)) >= 2:
        return _by_heading(lines)
    return _by_parts(text)


def _by_time(lines: list[str]) -> Units:
    texts: list[str] = []
    labels: list[str] = []
    lesson, label = "", ""
    body: list[str] = []

    def close() -> None:
        if any(b.strip() for b in body):
            texts.append("\n".join(body))
            labels.append(label)
        body.clear()

    for line in lines:
        cue = line.strip() in ("WEBVTT", "") or _CUE_NUMBER.match(line)
        if cue or ("-->" in line and not _STAMP.match(line)):
            continue
        marker = _LESSON.match(line)
        if marker:
            close()
            lesson, label = marker.group(1).strip().capitalize(), ""
            continue
        stamp = _STAMP.match(line)
        if stamp:
            if sum(len(b.split()) for b in body) >= SECTION_WORDS:
                close()
            if not body:
                label = f"{lesson}, {stamp.group(1)}" if lesson else stamp.group(1)
            line = line[stamp.end() :]
            if not line.strip():
                continue
        elif not body and not label:
            label = lesson or "start"
        body.append(line)
    close()
    return Units("sections", "timestamps", texts, labels)


def _by_heading(lines: list[str]) -> Units:
    texts: list[str] = []
    labels: list[str] = []
    path: list[tuple[int, str]] = []
    body: list[str] = []

    def close() -> None:
        if any(b.strip() for b in body):
            texts.append("\n".join(body))
            labels.append(" › ".join(t for _, t in path) or "start")

    for line in lines:
        h = _HEADING.match(line)
        if h:
            close()
            body = []
            level = len(h.group(1))
            path = [(lv, t) for lv, t in path if lv < level] + [(level, h.group(2).strip())]
        else:
            body.append(line)
    close()
    return Units("sections", "headings", texts, labels)


def _by_parts(text: str) -> Units:
    texts: list[str] = []
    current: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        if not para.strip():
            continue
        current.append(para)
        if sum(len(p.split()) for p in current) >= PART_WORDS:
            texts.append("\n\n".join(current))
            current = []
    if current:
        texts.append("\n\n".join(current))
    texts = texts or [text]
    return Units("sections", "parts", texts, [f"part {i}" for i in range(1, len(texts) + 1)])


def has_text_layer(pages: list[str]) -> bool:
    """True when enough pages carry real text (a scanned book without OCR has almost none)."""
    if not pages:
        return False
    wordy = sum(1 for p in pages if len(p.split()) >= 30)
    return wordy >= max(1, len(pages) // 5)


@dataclass
class PageMap:
    offset: int  # pdf page − printed page
    printed: list[int | None]  # per pdf page (1-based pdf page = index + 1); None = before printed page 1
    confirmed: list[bool]  # a number on the page itself agrees with the offset


def _candidates(page: str) -> list[int]:
    lines = [ln for ln in page.splitlines() if ln.strip()]
    found = []
    for line in lines[:3] + lines[-3:]:
        m = _NUMBER_LINE.match(line) or _NUMBER_EDGE.match(line)
        if m:
            found.append(int(next(g for g in m.groups() if g)))
    return found


def printed_pages(pages: list[str]) -> PageMap:
    """Find the offset between PDF and printed page numbers from running headers and footers."""
    votes: Counter[int] = Counter()
    per_page = []
    for i, page in enumerate(pages, start=1):
        offsets = {i - n for n in _candidates(page) if n <= i}
        per_page.append(offsets)
        votes.update(offsets)
    with_numbers = sum(1 for o in per_page if o)
    offset = 0
    if votes and with_numbers:
        best, count = votes.most_common(1)[0]
        if count >= max(2, int(0.3 * with_numbers)):
            offset = best
    printed = [(i - offset) if i - offset >= 1 else None for i in range(1, len(pages) + 1)]
    confirmed = [offset in o for o in per_page]
    return PageMap(offset, printed, confirmed)


def matter_flags(pages: list[str], page_map: PageMap) -> list[str]:
    """Per page: "front" (before printed page 1), "contents", "back" (bibliography, index…) or "" for the body."""
    flags = []
    for page, printed in zip(pages, page_map.printed, strict=True):
        lines = [ln for ln in page.splitlines() if ln.strip()]
        toc = sum(1 for ln in lines if _TOC_LINE.match(ln))
        front = printed is None or printed <= max(1, len(pages) // 50)  # contents pages come first
        if front and lines and len(lines) >= 5 and toc / len(lines) >= 0.4:
            flags.append("contents")
        elif printed is None:
            flags.append("front")
        else:
            flags.append("")
    start = int(len(pages) * 0.8)
    for i in range(start, len(pages)):
        top = [ln for ln in pages[i].splitlines() if ln.strip()][:3]
        if any(_BACK_HEADINGS.match(ln) for ln in top):
            for j in range(i, len(pages)):
                flags[j] = "back"
            break
    return flags
