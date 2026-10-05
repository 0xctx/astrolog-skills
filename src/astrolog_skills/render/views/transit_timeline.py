"""Terminal transit timeline: under a header per transiting planet, one row per transit across the days it is in
orb, brightest on its exact days (●), then the patterns transits form in harmonic charts."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from rich.console import Console
from rich.markup import escape

from astrolog_skills import config
from astrolog_skills.analysis.aspects_registry import BY_KEY
from astrolog_skills.render.theme import load as theme_load
from astrolog_skills.render.theme import mix
from astrolog_skills.ui import rgb

ROWS = 60  # the terminal list; --json has every passage
LABEL = 30


def point_name(key: str) -> str:
    from astrolog_skills.cli.commands.analysis import name_of

    return "/".join(name_of(k) for k in key.split("/"))


def _axis(start: date, days: int, cols: int) -> str:
    """Month names over the columns where each month begins."""
    line = [" "] * cols
    prev = start.month
    for col in range(1, cols):
        d = start + timedelta(days=col * days / cols)
        if d.month != prev and col + 3 <= cols:
            line[col : col + 3] = list(d.strftime("%b"))
        prev = d.month
    return "".join(line)


def render(c: Console, tl: dict[str, Any], width: int) -> None:
    start, days = date.fromisoformat(tl["start"]), tl["days"]
    cols = max(20, min(days + 1, width - LABEL - 18, 64))  # room for two exact dates

    def col(iso: str) -> int:
        return int(min(cols - 1, max(0, int((date.fromisoformat(iso) - start).days / max(days, 1) * cols))))

    rows = tl["passages"]
    th = theme_load(str(config.get("display.theme")))
    dim = th.ui["dim"]
    end = start + timedelta(days=days)
    c.print(f"\n[bold]Next {days} days[/] [{rgb('dim')}]{start} → {end} · ━ in orb · ● exact[/]")
    c.print(f"[{rgb('dim')}]{' ' * LABEL}{_axis(start, days, cols)}[/]")
    mover = None
    for r in rows[:ROWS]:
        if r["transit"] != mover:  # a header per transiting planet, slowest first
            mover = r["transit"]
            c.print(f"[bold {rgb('water')}]{escape(point_name(mover))}[/]")
        asp = BY_KEY[r["aspect"]]
        hue = th.aspects.get(asp.family, th.ui["label"])
        mid = "/" in r["natal"]
        label = f"    {asp.glyph} {point_name(r['natal'])}"
        a, b, peak = col(r["enters"]), col(r["leaves"]), col(r["peak"])
        exact = {col(hit) for hit in r["exact"]}
        peaks = exact or {peak}
        cells = []
        for k in range(cols):
            if not a <= k <= b:
                cells.append(" ")
                continue
            near = 1 - min(abs(k - e) for e in peaks) / max(b - a, 1)  # brightest on each exact (or tightest) day
            glow = (0.25 + 0.75 * near * r["strength"]) * (0.7 if mid else 1.0)
            r_, g_, b_ = mix(dim, hue, glow)
            cells.append(f"[rgb({r_},{g_},{b_})]{'●' if k in exact else '━'}[/]")
        when = " " + ", ".join(h[5:] for h in r["exact"]) if r["exact"] else ""
        name = f"[{rgb('dim')}]{escape(label)}[/]" if mid else escape(label)
        pad = " " * max(0, LABEL - len(label))
        c.print(f"{name}{pad}{''.join(cells)}[{rgb('dim')}]{when}[/]")
    if len(rows) > ROWS:
        more = len(rows) - ROWS
        c.print(f"  [{rgb('dim')}]… {more} more: narrow with --transiting, --aspects h7 or --no-midpoints[/]")
    if not rows:
        c.print(f"  [{rgb('dim')}]nothing within the pack's orbs[/]")
    pats, hs = tl["patterns"], tl["harmonics"]
    if not hs:
        return  # the tradition doesn't read patterns
    span = f"H{hs[0]}–{hs[-1]}" if hs == list(range(hs[0], hs[-1] + 1)) else ", ".join(f"H{h}" for h in hs)
    c.print(f"\n[bold]Harmonic patterns with transits[/] [{rgb('dim')}]{span} · strongest first[/]")
    for p in pats[:12]:
        moving = ", ".join(point_name(k) for k in p["transits"])
        natal = ", ".join(point_name(k) for k in p["natal"])
        dates = p["starts"] if p["starts"] == p["ends"] else f"{p['starts']} → {p['ends']}"
        c.print(
            f"  [{rgb('gold')}]H{p['harmonic']:<3}[/] [bold]{p['strength']:.2f}[/]  {escape(moving)} "
            f"[{rgb('dim')}]with natal[/] {escape(natal)}",
            soft_wrap=True,
        )
        c.print(
            f"       [{rgb('dim')}]{dates} · tightest {p['peak']} · "
            f"astro view --harmonic {p['harmonic']} --transits {p['peak']}[/]",
            soft_wrap=True,
        )
    if not pats:
        c.print(f"  [{rgb('dim')}]none in the window[/]")
