"""Short meanings from a pack's `meanings.md`, for quick definitions (e.g. the HTML chart's hover notes).

Reads the pack's own wording, never invents it. Recognised forms:
- bullets `- **Sun ☉** — text` (planets/points, aspects; `**Semisquare ∠ / Sesquiquadrate ⚼**` names two aspects)
- bullets `- **H7** — text [source]` (harmonics)
- run-on lists `Sun — text · Moon — text` in a section about planets
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from astrolog_skills.analysis.aspects_registry import BY_KEY as ASPECTS
from astrolog_skills.engine.objects import OBJECTS

BULLET = re.compile(r"^\s*[-*]\s+\*\*(.+?)\*\*\s*[—–-]\s*(.+?)\s*$")
HARMONIC = re.compile(r"^H(\d+)$")
EXTRA_NAMES = {"ascendant": "asc", "midheaven": "mc", "north node": "north_node", "south node": "south_node"}


def _names(label: str) -> list[str]:
    """'Quintile Q' → ['quintile q', 'quintile']: glyphs dropped, then a trailing letter-symbol like Q, bQ or Vx."""
    words = re.sub(r"[^\w\s-]", "", label).lower().split()
    return [" ".join(words[:n]) for n in range(len(words), 0, -1)]


def _body_key(label: str) -> str | None:
    for name in _names(label):
        if name in EXTRA_NAMES:
            return EXTRA_NAMES[name]
        for o in OBJECTS:
            if o.name.lower() == name or o.key == name.replace(" ", "_"):
                return o.key
    return None


def _aspect_keys(label: str) -> list[str]:
    keys = []
    for part in label.split("/"):
        for name in _names(part):
            found = [a.key for a in ASPECTS.values() if a.name.lower() == name]
            if found:
                keys += found
                break
    return keys


GLOSSARY = re.compile(r"^##\s+Glossary\b", re.I | re.M)
_PAGES_AT_END = re.compile(r"\s*\((pp?\.\s*[^)]*)\)\s*$")


def slug(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", term.lower()).strip("_")


def _split_glossary(text: str) -> tuple[str, str]:
    """(the meanings, the glossary section) — the glossary runs to the next level-2 heading."""
    m = GLOSSARY.search(text)
    if not m:
        return text, ""
    rest = text[m.end() :]
    nxt = re.search(r"^##\s", rest, re.M)
    glossary = rest[: nxt.start()] if nxt else rest
    return text[: m.start()] + (rest[nxt.start() :] if nxt else ""), glossary


def glossary(text: str) -> dict[str, dict[str, str]]:
    """`## Glossary` bullets (`- **Term** — what it means (p. 12-14)`) → slug → {title, text, pages}."""
    out: dict[str, dict[str, str]] = {}
    lines = _split_glossary(text)[1].splitlines()
    for i, line in enumerate(lines):
        m = BULLET.match(line)
        if not m:
            continue
        title, body = m.group(1).strip(), m.group(2)
        for more in lines[i + 1 :]:
            if not more.startswith("  ") or BULLET.match(more):
                break
            body += " " + more.strip()
        pages = ""
        if pm := _PAGES_AT_END.search(body):
            pages, body = pm.group(1), body[: pm.start()]
        out[slug(title)] = {"title": title, "text": body.strip(), "pages": pages}
    return out


def parse(text: str) -> dict[str, Any]:
    text = _split_glossary(text)[0]
    bodies: dict[str, str] = {}
    aspects: dict[str, str] = {}
    harmonics: dict[str, str] = {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = BULLET.match(line)
        if m:
            label, body = m.group(1).strip(), m.group(2)
            # a bullet may continue on indented lines
            for more in lines[i + 1 :]:
                if not more.startswith("  ") or BULLET.match(more):
                    break
                body += " " + more.strip()
            if hm := HARMONIC.match(label):
                harmonics[hm.group(1)] = body
            elif keys := _aspect_keys(label):
                for k in keys:
                    aspects[k] = body
            elif "," in label and all(_body_key(part) for part in label.split(",")):
                # several bodies in one bullet: pair them with the ;-separated clauses when the counts match
                named = [b for part in label.split(",") if (b := _body_key(part)) is not None]
                clauses = [c.strip().rstrip(".") for c in body.split(";")]
                each = clauses if len(clauses) == len(named) else [body] * len(named)
                for body_key, clause in zip(named, each, strict=True):
                    bodies[body_key] = clause
            elif key := _body_key(label):
                bodies[key] = body
        elif " · " in line and " — " in line and not line.lstrip().startswith("-"):
            for item in line.split(" · "):
                name, sep, body = item.partition(" — ")
                key = _body_key(name) if sep else None
                if key and key not in bodies:
                    bodies[key] = body.strip().rstrip("·").strip()
    return {"bodies": bodies, "aspects": aspects, "harmonics": harmonics}


def load_glossary(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None or not path.is_file():
        return {}
    return glossary(path.read_text(encoding="utf-8"))


def load(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {"bodies": {}, "aspects": {}, "harmonics": {}}
    return parse(path.read_text(encoding="utf-8"))
