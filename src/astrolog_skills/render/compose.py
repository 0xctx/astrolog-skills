"""Compose views into one output (the chart alone by default)."""

from __future__ import annotations

from collections.abc import Callable

from astrolog_skills.errors import AstroError
from astrolog_skills.render.canvas import Canvas, stack
from astrolog_skills.render.theme import Theme
from astrolog_skills.render.views import aspects, chart, panels, study
from astrolog_skills.render.views.common import ViewData

VIEWS: dict[str, Callable[[ViewData, Theme, int], Canvas]] = {
    "chart": chart.draw,
    "aspects": aspects.draw_trees,
    "grid": aspects.draw,
    "balance": panels.balance,
    "patterns": panels.patterns,
    "positions": panels.positions,
    "transits": panels.transits,
    "life": study.life,
    "doctrine": study.doctrine,
    "lots": study.lots,
    "timelords": study.timelords,
}
# `all` skips transits (need a date), the grid and patterns views (the trees list every aspect), and the doctrine views
# (a pack with doctrine rules: ask for them by name)
ALL_SKIPS = ("transits", "grid", "patterns", "life", "doctrine", "lots", "timelords")
STUDY_VIEWS = ("life", "doctrine", "lots", "timelords")
BUDGET = 30_000  # Claude Code truncates `!` output around here


PAGE_LIMIT = BUDGET - 1_000  # room for the other views' seams and the "more" line


def _split(name: str) -> tuple[str, int]:
    """'aspects:2' → ('aspects', 2); other views have no pages."""
    base, _, page = name.partition(":")
    return base, int(page) if page else 1


def parse_views(text: str) -> list[str]:
    names = [n.strip().lower() for n in text.split(",") if n.strip()] or ["chart"]
    if names == ["all"]:
        return [n for n in VIEWS if n not in ALL_SKIPS]
    bad = []
    for n in names:
        base, _, page = n.partition(":")
        if base not in VIEWS or (page and (base != "aspects" or not page.isdigit() or int(page) < 1)):
            bad.append(n)
    if bad:
        raise AstroError(
            f"Unknown view(s): {', '.join(bad)}.", fix="views: " + ", ".join(VIEWS) + ", or all (aspects:2 = page 2)"
        )
    return names


def _units(data: ViewData, theme: Theme, names: list[str], width: int, paged: bool) -> list[tuple[str, Canvas]]:
    """Each view as a canvas; the aspects view as its pages (from the page asked for) when output is capped."""
    out: list[tuple[str, Canvas]] = []
    for name in names:
        base, first = _split(name)
        if base != "aspects" or (not paged and first == 1):
            out.append((base, VIEWS[base](data, theme, width)))
            continue
        pages = aspects.tree_pages(data, theme, width, PAGE_LIMIT)
        if first > len(pages):
            raise AstroError(f"The aspects view has {len(pages)} page(s), not {first}.")
        last = len(pages) if paged else first
        out += [("aspects" if i == 1 else f"aspects:{i}", pages[i - 1]) for i in range(first, last + 1)]
    return out


def compose(data: ViewData, theme: Theme, names: list[str], width: int = 80) -> Canvas:
    """Every view in full (for a real terminal or --plain); 'aspects:N' draws just that page."""
    return stack([c for _, c in _units(data, theme, names, width, paged=False)], gap=1, bg=theme.ui["page"])


def render_within_budget(data: ViewData, theme: Theme, names: list[str], width: int = 80) -> tuple[str, list[str]]:
    """ANSI output of as many views (and aspect pages) as fit Claude Code's `!` limit, plus what to ask for next."""
    units = _units(data, theme, names, width, paged=True)
    shown: list[Canvas] = []
    text = ""
    for i, (_, canvas) in enumerate(units):
        candidate = stack([*shown, canvas], gap=1, bg=theme.ui["page"]).render()
        if len(candidate) > BUDGET and shown:
            rest = [label for label, _ in units[i:]]
            # later pages of the same view follow on from the first one left out
            return text, [
                r
                for j, r in enumerate(rest)
                if not (_split(r)[0] == "aspects" and j and _split(rest[j - 1])[0] == "aspects")
            ]
        shown.append(canvas)
        text = candidate
    return text, []
