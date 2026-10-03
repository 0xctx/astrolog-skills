"""Reading notes: short, plain-language snippets from a written reading, keyed to each chart contact.

Claude writes them (report skill) from the pack's process.md and meanings.md; the HTML export shows them when a list
row is hovered. Keys are stable and readable:

- aspect:   `h7:sun-opposition-jupiter`     (bodies in chart order, as the aspect lists give them)
- midpoint: `h1:sun@saturn/mc-conjunction`  (the body on the midpoint @ the pair)
- study (packs with doctrine): `planet:moon`, `condition:moon:striking_with_a_ray:venus`, `lot:fortune`, `place:7`,
  `profection:asc:26`, `releasing:spirit:1:1913-09-12` … (analysis/doctrine/explain.assign_keys)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from astrolog_skills.analysis.aspects import ANGLE_NAMES, find_aspects
from astrolog_skills.analysis.aspects_registry import BY_KEY
from astrolog_skills.analysis.method import Method
from astrolog_skills.analysis.midpoints import SKIP, midpoint_contacts
from astrolog_skills.charts.store import slug
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.errors import AstroError
from astrolog_skills.paths import data_dir

LONG = 700  # characters: a note is a snippet, not the reading


def aspect_key(h: int, a: str, aspect: str, b: str) -> str:
    return f"h{h}:{a}-{aspect}-{b}"


def midpoint_key(h: int, focus: str, a: str, b: str, aspect: str) -> str:
    return f"h{h}:{focus}@{a}/{b}-{aspect}"


def notes_path(chart: ChartModel, pack: str) -> Path:
    who = slug(chart.name) if chart.name else "chart"
    return data_dir() / "notes" / f"{who}-{pack}.json"


def contacts(chart: ChartModel, method: Method, harmonics: list[int]) -> list[dict[str, Any]]:
    """Every aspect and midpoint contact the HTML lists show at these harmonics, with its key and a plain label."""
    names = {p.key: p.name for p in chart.points} | ANGLE_NAMES
    out: list[dict[str, Any]] = []
    for h in harmonics:
        where = f" (H{h})" if h > 1 else ""
        for a in find_aspects(chart, method, h):
            if SKIP[0] in (a.a, a.b):
                continue
            label = f"{names[a.a]} {BY_KEY[a.aspect].name} {names[a.b]}{where}"
            out.append(
                {
                    "key": aspect_key(h, a.a, a.aspect, a.b),
                    "harmonic": h,
                    "kind": "aspect",
                    "bodies": [a.a, a.b],
                    "label": label,
                    "orb": round(a.orb / h, 4),
                    "strength": a.strength,
                }
            )
        for focus, found in midpoint_contacts(chart, method, h).items():
            for c in found:
                label = f"{names[focus]} {BY_KEY[c.aspect].name} the {names[c.a]}/{names[c.b]} midpoint{where}"
                out.append(
                    {
                        "key": midpoint_key(h, focus, c.a, c.b, c.aspect),
                        "harmonic": h,
                        "kind": "midpoint",
                        "bodies": [focus, c.a, c.b],
                        "label": label,
                        "orb": round(c.orb / h, 4),
                        "strength": c.strength,
                    }
                )
    return out


def load(path: Path) -> dict[str, str]:
    """{key: note} from a notes file: {"chart": …, "pack": …, "contacts": {key: text}}."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise AstroError(
            f"Can't read the notes file {path} ({err}).", fix='it must be JSON: {"contacts": {…}}'
        ) from err
    found = data.get("contacts") if isinstance(data, dict) else None
    if not isinstance(found, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in found.items()):
        raise AstroError(f'{path}: expected {{"contacts": {{key: text}}}}.', fix="keys come from `astro notes keys`")
    return {k: v.strip() for k, v in found.items() if v.strip()}


def check(
    notes: dict[str, str],
    known: list[dict[str, Any]],
    defined: set[str] | None = None,
    tight: float = 0.5,
    also_valid: set[str] | None = None,
) -> dict[str, Any]:
    """Flag tight contacts (aspects and midpoints) left without a note — only those whose bodies the pack's meanings.md
    defines (`defined`), since a reading mustn't invent meanings — and required study items without one.
    `also_valid`: keys that exist but aren't listed (e.g. timeline periods away from the reading's date)."""
    keys = {c["key"] for c in known} | (also_valid or set())

    def missing(kind: str) -> tuple[list[dict[str, Any]], int]:
        tight_ones = [c for c in known if c["kind"] == kind and c["strength"] >= tight and c["key"] not in notes]
        ok = [c for c in tight_ones if defined is None or set(c["bodies"]) <= defined]
        return ok, len(tight_ones) - len(ok)

    covered, skipped_a = missing("aspect")
    mids, skipped_m = missing("midpoint")
    return {
        "written": sum(1 for k in notes if k in keys),
        "unknown_keys": sorted(k for k in notes if k not in keys),
        "missing_tight_aspects": [{"key": c["key"], "label": c["label"]} for c in covered],
        "missing_tight_midpoints": [{"key": c["key"], "label": c["label"]} for c in mids],
        "no_meanings_in_pack": skipped_a + skipped_m,
        "midpoints_with_notes": sum(1 for c in known if c["kind"] == "midpoint" and c["key"] in notes),
        "too_long": sorted(k for k, v in notes.items() if len(v) > LONG),
        "missing_study": [
            {"key": c["key"], "label": c["label"]}
            for c in known
            if c["kind"] == "study" and c.get("required") and c["key"] not in notes
        ],
        "study_with_notes": sum(1 for c in known if c["kind"] == "study" and c["key"] in notes),
    }


def reading_date(path: Path) -> str | None:
    """The date a reading was written for (`"on"` in the notes file), if it gives one."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    on = data.get("on") if isinstance(data, dict) else None
    return str(on) if isinstance(on, str) and len(on) == 10 else None
