"""A pack's private library: `~/.astrolog-skills/traditions/<pack>/sources/`, its index files and `sources.toml`.

Source files and their extracted text stay in the user's data folder — never in the plugin or the repository.
"""

from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import tomli_w

from astrolog_skills.charts.store import slug
from astrolog_skills.errors import AstroError
from astrolog_skills.packs.loader import user_dir
from astrolog_skills.sources import extract, index

HEADER = "# Sources for this pack. The texts stay in sources/ on this computer and are never shared.\n\n"


def pack_dir(pack: str) -> Path:
    name = slug(pack)
    if not name:
        raise AstroError(f"'{pack}' isn't a usable pack name.", fix="use letters, digits and dashes, e.g. hellenistic")
    return user_dir() / name


def sources_dir(pack: str) -> Path:
    return pack_dir(pack) / "sources"


def index_path(pack: str, source_id: str) -> Path:
    return sources_dir(pack) / ".index" / f"{source_id}.sqlite"


def read_toml(pack: str) -> list[dict[str, Any]]:
    path = pack_dir(pack) / "sources.toml"
    if not path.is_file():
        return []
    try:
        with open(path, "rb") as f:
            return list(tomllib.load(f).get("source", []))
    except tomllib.TOMLDecodeError as err:
        raise AstroError(f"Can't read {path}: {err}", fix=f"fix {path}") from err


def write_toml(pack: str, entries: list[dict[str, Any]]) -> Path:
    path = pack_dir(pack) / "sources.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER + tomli_w.dumps({"source": entries}), encoding="utf-8")
    return path


@dataclass
class Added:
    id: str
    file: Path
    pages: int  # pages, or sections
    offset: int
    matter: dict[str, int]
    index: Path
    replaced: bool = False  # a source with the same id was already there (rebuilt from this file)
    kind: str = "pages"  # pages | sections
    how: str = "pdf"  # pdf | form feeds | timestamps | headings | parts
    ocr: bool = False  # the text came from OCR (a scanned PDF)


def add(pack: str, file: Path, origin: dict[str, str] | None = None) -> Added:
    """Copy (unless already there), extract, index, and record the source in the pack's sources.toml. A scanned PDF is
    read by OCR first when ocrmypdf is installed. `origin` records where a fetched page came from (url, fetched)."""
    file = file.expanduser()
    if not file.is_file():
        raise AstroError(f"No file at {file}.")
    target_dir = sources_dir(pack)
    target_dir.mkdir(parents=True, exist_ok=True)
    source_id = slug(file.stem) or "source"
    # read the original first: a file that can't be used is never copied into the pack
    found = extract.units(file)
    pages = found.texts
    if found.kind == "sections" and not any(t.split() for t in pages):
        raise AstroError(f"{file.name} has no text in it.")
    target = file if file.resolve().parent == target_dir.resolve() else target_dir / f"{source_id}{file.suffix.lower()}"
    ocred = False
    if found.kind == "pages" and not extract.has_text_layer(pages):
        if file.suffix.lower() != ".pdf":
            raise AstroError(f"{file.name} has almost no text in it.")
        scratch = target_dir / f".{source_id}.ocr.pdf"
        extract.ocr(file, scratch)  # raises with the install line when ocrmypdf is missing
        scratch.replace(target)
        file, ocred = target, True
        found = extract.units(target)
        pages = found.texts
        if not extract.has_text_layer(pages):
            raise AstroError(f"OCR found almost no text in {file.name}.", fix="check the scan's quality")
    replaced = any(e.get("id") == source_id for e in read_toml(pack))
    if target != file:
        shutil.copyfile(file, target)
    if found.kind == "pages":
        page_map = extract.printed_pages(pages)
        flags = extract.matter_flags(pages, page_map)
    else:  # sections are numbered 1..N, with no front or back matter
        page_map = extract.PageMap(0, list(range(1, len(pages) + 1)), [True] * len(pages))
        flags = [""] * len(pages)
    info = extract.pdf_info(target) if target.suffix.lower() == ".pdf" else {}
    db = index_path(pack, source_id)
    index.build(
        db,
        pages,
        page_map.printed,
        flags,
        {"id": source_id, "file": target.name, "offset": str(page_map.offset), "kind": found.kind, "how": found.how},
        found.labels,
    )
    entries = [e for e in read_toml(pack) if e.get("id") != source_id]
    previous = next((e for e in read_toml(pack) if e.get("id") == source_id), {})
    entry = {
        "id": source_id,
        "file": f"sources/{target.name}",
        "title": previous.get("title") or info.get("Title", ""),
        "author": previous.get("author") or info.get("Author", ""),
        "pages": len(pages),
        "units": found.how if found.kind == "sections" else "pages",
        "added": date.today().isoformat(),
        **({"ocr": True} if ocred else {}),
        **(origin or {}),
        "covers": previous.get("covers", ""),
    }
    write_toml(pack, [*entries, {k: v for k, v in entry.items() if v != "" or k == "covers"}])
    counts = {name: flags.count(name) for name in ("front", "contents", "back")}
    return Added(source_id, target, len(pages), page_map.offset, counts, db, replaced, found.kind, found.how, ocred)


def set_title(pack: str, source_id: str, title: str) -> None:
    """Fill in a source's title (e.g. a fetched page's) unless the user has set one."""
    entries = read_toml(pack)
    for e in entries:
        if e.get("id") == source_id and not e.get("title"):
            e["title"] = title
    write_toml(pack, entries)


def list_sources(pack: str) -> list[dict[str, Any]]:
    out = []
    for entry in read_toml(pack):
        sid = str(entry.get("id", ""))
        db = index_path(pack, sid)
        row = {**entry, "indexed": db.is_file()}
        if db.is_file():
            info = index.meta(db)
            row["offset"] = int(info.get("offset", "0"))
            row["kind"] = info.get("kind", "pages")
        out.append(row)
    return out


def cite(kind: str, number: int | None) -> str:
    """How a unit is cited: "p. 488" for a book's printed page, "§ 12" for a transcript's or notes' section."""
    if number is None:
        return ""
    return f"§ {number}" if kind == "sections" else f"p. {number}"


def resolve(pack: str, source_id: str | None) -> str:
    """The source to use: the one named, or the pack's only indexed source."""
    ids = [str(s["id"]) for s in list_sources(pack) if s.get("indexed")]
    if source_id:
        if source_id not in ids:
            raise AstroError(
                f"No indexed source '{source_id}' in pack '{pack}'.", fix="indexed: " + (", ".join(ids) or "none")
            )
        return source_id
    if len(ids) == 1:
        return ids[0]
    if not ids:
        raise AstroError(f"Pack '{pack}' has no indexed sources.", fix=f"astro sources add {pack} <file>")
    raise AstroError(f"Pack '{pack}' has several sources.", fix="choose one with --source: " + ", ".join(ids))
