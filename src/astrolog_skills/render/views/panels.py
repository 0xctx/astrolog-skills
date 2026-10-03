"""Smaller views: element/mode balance, planet patterns, and a positions table."""

from __future__ import annotations

from typing import Any

from astrolog_skills.engine.zodiac import ELEMENTS, MODES, SIGNS, sign_index
from astrolog_skills.render.canvas import Canvas
from astrolog_skills.render.theme import Theme, mix
from astrolog_skills.render.views.common import ViewData, degree_text, short_name, symbol


def _panel(theme: Theme, width: int, height: int, title: str) -> Canvas:
    ui = theme.ui
    cv = Canvas(width, height, ui["page"])
    cv.fill(1, 1, width - 2, height - 2, " ", bg=ui["center_bg"])
    cv.box(0, 0, width, height, ui["frame"], ui["page"])
    cv.center(0, 0, width, f" {title} ", ui["frame_text"], ui["frame"], True)
    return cv


def balance(v: ViewData, theme: Theme, width: int = 80) -> Canvas:
    """Elements and modes, counting the pack's pattern bodies (ten planets by default)."""
    ui, bg = theme.ui, theme.ui["center_bg"]
    pts = [p for p in v.chart.points if p.key in v.pack.method.pattern_bodies]
    w = min(width, 64)
    cv = _panel(theme, w, 8, "BALANCE")
    col2 = w // 2 + 1
    for k, name in enumerate(ELEMENTS):
        who = [p for p in pts if sign_index(p.lon) % 4 == k]
        cv.put(3, 2 + k, f"{name.capitalize():<6}", ui["text"], bg)
        cv.put(10, 2 + k, "■" * len(who), theme.element(k)["header_bg"], bg, True)
        cv.put(19, 2 + k, str(len(who)), ui["text"], bg, True)  # the count, as the modes show it
        cv.put(22, 2 + k, " ".join(symbol(p.key, p.glyph, theme) for p in who)[: col2 - 24], ui["dim"], bg)
    for k, name in enumerate(MODES):
        who = [p for p in pts if sign_index(p.lon) % 3 == k]
        cv.put(col2, 2 + k, f"{name.capitalize():<9}", ui["text"], bg)
        cv.put(col2 + 9, 2 + k, "■" * len(who), ui["label"], bg, True)
        cv.put(col2 + 20, 2 + k, str(len(who)), ui["text"], bg, True)
    return cv


def patterns(v: ViewData, theme: Theme, width: int = 80) -> Canvas:
    ui, bg = theme.ui, theme.ui["center_bg"]
    m, h = v.pack.method, v.harmonic
    pats = v.patterns.patterns
    w = min(width, 76)
    cv = _panel(theme, w, max(1, len(pats)) + 7, f"PLANET GROUPS · H{h} · {v.pack.label}")
    natal_orb = m.pattern_orb / h
    rule = f"{m.pattern_min_size}+ planets all within {m.pattern_orb:g}° in the H{h} chart ({natal_orb:.3g}° natal)"
    scores = f"{m.pattern_strong_size}-planet patterns: {v.patterns.score1}   weighted score: {v.patterns.score2:.1f}"
    cv.put(3, 2, rule, ui["label"], bg)
    cv.put(3, 3, scores, ui["dim"], bg)
    names = {p.key: p for p in v.natal.points}
    if not pats:
        cv.put(3, 5, "none", ui["dim"], bg)
    for k, pat in enumerate(pats):
        colour = mix(ui["dim"], ui["title"], pat.strength)
        label = " · ".join(short_name(b, names[b].name) for b in pat.bodies)
        cv.put(3, 5 + k, label[: w - 20], colour, bg, pat.strength > 0.5)
        span = f"{pat.span / h:.2f}° natal" if v.natal_orbs or h == 1 else f"{pat.span:.1f}° in H{h}"
        cv.put(w - 3 - len(span), 5 + k, span, colour, bg)
    return cv


def positions(v: ViewData, theme: Theme, width: int = 80) -> Canvas:
    ui, bg = theme.ui, theme.ui["center_bg"]
    rows = v.chart.points
    w = min(width, 64)
    cv = _panel(theme, w, len(rows) + 5, "POSITIONS" + (f" · H{v.harmonic}" if v.harmonic > 1 else ""))
    cv.put(3, 2, "body", ui["label"], bg, True)
    cv.put(20, 2, "position", ui["label"], bg, True)
    cv.put(44, 2, "house   speed", ui["label"], bg, True)
    for k, p in enumerate(rows):
        el = theme.element(sign_index(p.lon))
        y = 3 + k
        cv.put(3, y, f"{symbol(p.key, p.glyph, theme)} {short_name(p.key, p.name)}", ui["white"], bg, True)
        cv.put(20, y, f"{degree_text(p.lon)} {SIGNS[sign_index(p.lon)]}", el["accent"], bg, True)
        if p.retrograde and p.key not in ("north_node", "south_node"):
            cv.put(38, y, "℞", ui["retro"], bg, True)
        cv.put(44, y, f"{p.house or '':>5} {p.speed:+8.3f}", ui["dim"], bg)
    return cv


def transits(v: ViewData, theme: Theme, width: int = 80) -> Canvas:
    """Transit-to-natal aspects, tightest first (needs a transit chart)."""
    from astrolog_skills.analysis.aspects_registry import BY_KEY

    ui, bg = theme.ui, theme.ui["center_bg"]
    rows = (v.transit_aspects or [])[:40]
    w = min(width, 76)
    when = v.transit.moment.get("date", "") if v.transit else ""
    cv = _panel(theme, w, max(1, len(rows)) + 4, f"TRANSITS {when}".strip())
    natal = {p.key: p for p in v.natal.points}
    moving = {p.key: p for p in v.transit.points} if v.transit else {}
    if not rows:
        cv.put(3, 2, "none within the transit orbs" if v.transit else "add --transits to see them", ui["dim"], bg)

    def label(key: str, pool: dict[str, Any]) -> str:
        p = pool.get(key)
        if p is None:
            return {"asc": "AC Ascendant", "mc": "MC Midheaven"}.get(key, key)
        return f"{symbol(key, p.glyph, theme)} {short_name(key, p.name)}"

    for k, a in enumerate(rows):
        asp = BY_KEY[a.aspect]
        colour = mix(ui["dim"], theme.aspects[asp.family], 0.35 + 0.65 * a.strength)
        y = 2 + k
        cv.put(3, y, label(a.transit, moving)[:15], ui["label"], bg, True)
        cv.put(19, y, f"{asp.glyph if theme.glyphs else asp.letters} {asp.name}"[:17], colour, bg, a.strength > 0.5)
        cv.put(37, y, label(a.natal, natal)[:15], ui["white"], bg, True)
        cv.put(53, y, f"{a.orb:4.2f}° {'applying' if a.applying else 'separating'}"[: w - 56], ui["dim"], bg)
    return cv
