"""Self-contained interactive HTML charts: one file, everything inline, no network requests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from astrolog_skills import __version__
from astrolog_skills.analysis.aspects import find_aspects
from astrolog_skills.analysis.aspects_registry import BY_KEY
from astrolog_skills.charts.store import slug
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.errors import AstroError
from astrolog_skills.packs.loader import Pack
from astrolog_skills.paths import data_dir, plugin_root
from astrolog_skills.render.theme import Theme

PARTS = ("template.html", "style.css", "core.js", "app.js")


def builtin_dir() -> Path:
    return plugin_root() / "presets"


def user_dir() -> Path:
    return data_dir() / "presets"


def list_presets() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for base in (builtin_dir(), user_dir()):
        if base.is_dir():
            for d in sorted(base.iterdir()):
                if (d / "template.html").is_file():
                    found[d.name] = d
    return found


def parse_harmonics(spec: str, highest: int) -> list[int]:
    """'7', '1-12', '1,5,7,11' or a mix like '1-12,16,20' → sorted harmonics, each 1..highest."""
    found: set[int] = set()
    for part in (p.strip() for p in spec.split(",")):
        try:
            lo, _, hi = part.partition("-")
            first, last = int(lo), int(hi or lo)
        except ValueError as err:
            raise AstroError(
                f"'{spec}' isn't a list of harmonics.", fix="e.g. --harmonics 7, 1-12 or 1,5,7,11"
            ) from err
        if not 1 <= first <= last <= highest:
            raise AstroError(
                f"Harmonics must run from 1 to {highest}, low to high; '{part}' doesn't.",
                fix="e.g. --harmonics 360, 1-12 or 1,5,7,11",
            )
        found.update(range(first, last + 1))
    if len(found) > 360:
        raise AstroError("That's more than 360 harmonics for one page.", fix="pick a smaller range")
    return sorted(found)


def harmonics_label(harmonics: list[int]) -> str:
    """[7] → '7', [1..12] → '1-12', [1, 5, 7] → '1_5_7' (for file names)."""
    if len(harmonics) > 1 and harmonics == list(range(harmonics[0], harmonics[-1] + 1)):
        return f"{harmonics[0]}-{harmonics[-1]}"
    return "_".join(map(str, harmonics))


def payload(
    chart: ChartModel,
    pack: Pack,
    theme: Theme,
    harmonics: int | list[int] = 1,
    natal_orbs: bool = False,
    midpoints: str | None = None,
) -> dict[str, Any]:
    """Everything the page needs; the browser recomputes harmonics from these longitudes and rules. One harmonic
    makes a single chart; several make a page that steps through exactly those, with the strongest harmonics (midpoint
    structures against random charts) under the slider. `midpoints` picks the method the lists open with."""
    m = pack.method
    shown = [harmonics] if isinstance(harmonics, int) else sorted(set(harmonics))
    strongest = None
    if len(shown) > 1:
        from astrolog_skills.analysis.midpoints import rank_harmonics

        strongest = rank_harmonics(chart, m, shown).to_dict()
    return {
        "chart": chart.to_dict(),
        "pack": {
            "name": pack.name,
            "label": pack.label,
            "aspects": [
                {
                    "key": a.key,
                    "name": a.name,
                    "angle": a.angle,
                    "orb": m.orb_for(a),
                    "family": a.family,
                    "glyph": a.glyph,
                    "harmonic": a.harmonic,
                }
                for a in m.aspect_types
            ],
            "harmonic_chart": [
                {
                    "key": k,
                    "name": BY_KEY[k].name,
                    "angle": BY_KEY[k].angle,
                    "orb": orb,
                    "family": BY_KEY[k].family,
                    "glyph": BY_KEY[k].glyph,
                    "harmonic": BY_KEY[k].harmonic,
                }
                for k, orb in m.harmonic_chart_orbs.items()
            ],
            "patterns": {
                "orb": m.pattern_orb,
                "min_size": m.pattern_min_size,
                "strong_size": m.pattern_strong_size,
                "bodies": list(m.pattern_bodies),
                "weights": {
                    f"{x}|{y}": m.weight(x, y)
                    for i, x in enumerate(m.pattern_bodies)
                    for y in m.pattern_bodies[i + 1 :]
                },
            },
            "harmonic_range": list(m.harmonic_range),
            "midpoints": {
                "aspects": [
                    {
                        "key": k,
                        "name": BY_KEY[k].name,
                        "angle": BY_KEY[k].angle,
                        "family": BY_KEY[k].family,
                        "glyph": BY_KEY[k].glyph,
                        "harmonic": BY_KEY[k].harmonic,
                    }
                    for k in m.midpoint_aspects
                ],
                "orb": m.midpoint_orb,
                "new_orb": m.midpoint_new_orb,
                "method": midpoints or m.midpoint_method,
                "highest": m.harmonic_max,
            },
        },
        "display": {"orbs": "natal" if natal_orbs else "harmonic"},
        "aspects": [a.to_dict() for a in find_aspects(chart, m)],
        "theme": {"ui": theme.ui, "elements": theme.elements, "aspects": theme.aspects},
        "harmonic": shown[0],
        "harmonics": shown,
        "strongest": strongest,
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "toolkit": __version__,
    }


def _json_for_html(data: dict[str, Any]) -> str:
    """JSON safe inside <script type="application/json">: no '</' can close the tag early."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def render(data: dict[str, Any], preset: str = "default") -> str:
    folder = list_presets().get(preset)
    if folder is None:
        raise AstroError(f"No HTML preset called '{preset}'.", fix="available: " + ", ".join(list_presets()))
    parts = {}
    for name in PARTS:
        path = folder / name
        if not path.is_file():
            raise AstroError(f"Preset '{preset}' is missing {name}.", fix=f"add it to {folder}")
        parts[name] = path.read_text(encoding="utf-8")
    title = f"{data['chart']['name'] or 'Chart'} · astrolog-skills"
    html = parts["template.html"]
    for placeholder, value in (
        ("/*@STYLE@*/", parts["style.css"]),
        ("/*@CORE@*/", parts["core.js"]),
        ("/*@APP@*/", parts["app.js"]),
        ("@DATA@", _json_for_html(data)),
        ("@TITLE@", title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")),
    ):
        if placeholder not in html:
            raise AstroError(f"Preset '{preset}' template has no {placeholder} placeholder.")
        html = html.replace(placeholder, value)
    return html


def export_path(chart: ChartModel, harmonics: list[int]) -> Path:
    who = slug(chart.name) if chart.name else "chart"
    suffix = "" if harmonics == [1] else f"-h{harmonics_label(harmonics)}"
    return data_dir() / "exports" / f"{who}{suffix}.html"


def write(html: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path
