"""The chart view: twelve sign boxes around a centre panel.

The rising sign sits at left-middle and signs run counter-clockwise, so the top row is the Midheaven side, as on
a wheel. Each box header shows the sign and the house cusps that begin in it (exact for whole-sign houses).
"""

from __future__ import annotations

from astrolog_skills.engine.zodiac import MODES, SIGNS, sign_index
from astrolog_skills.render.canvas import Canvas
from astrolog_skills.render.theme import ELEMENTS, Theme, mix
from astrolog_skills.render.views.common import ViewData, degree_text, short_name, symbol

ROWS = 6  # rows inside each sign box (header + 5)
# whole-sign house number → (row, column) in the 4×4 ring; 1st house at left-middle, counter-clockwise
RING = {
    1: (2, 0),
    2: (3, 0),
    3: (3, 1),
    4: (3, 2),
    5: (3, 3),
    6: (2, 3),
    7: (1, 3),
    8: (0, 3),
    9: (0, 2),
    10: (0, 1),
    11: (0, 0),
    12: (1, 0),
}


def _cusps_in_sign(cusps: list[float], sign: int) -> str:
    return "·".join(str(i + 1) for i, c in enumerate(cusps) if sign_index(c) == sign)


def draw(v: ViewData, theme: Theme, width: int = 80) -> Canvas:
    t, ui = theme, theme.ui
    box_w = (width - 5) // 4
    height = 4 * ROWS + 5
    total_w = 4 * box_w + 5
    cv = Canvas(total_w, height, ui["page"])
    chart = v.chart
    rising = sign_index(chart.angles.get("asc", 0.0))
    transiting = {id(p) for p in v.transit.points} if v.transit else set()
    points = sorted([*chart.points, *(v.transit.points if v.transit else [])], key=lambda p: p.lon % 30)

    for house, (r, c) in RING.items():
        sign = (rising + house - 1) % 12
        el = t.element(sign)
        x0, y0 = 1 + c * (box_w + 1), 1 + r * (ROWS + 1)
        cv.fill(x0, y0, box_w, ROWS, t.shade, fg=el["texture"], bg=el["body_bg"])
        cv.fill(x0, y0, box_w, 1, " ", bg=el["header_bg"])
        cv.put(x0 + 1, y0, SIGNS[sign].upper(), fg=el["header_text"], bg=el["header_bg"], bold=True)
        label = _cusps_in_sign(chart.cusps, sign) if chart.cusps else ""
        if label:
            cv.put(x0 + box_w - 1 - len(label), y0, label, fg=el["header_text"], bg=el["header_bg"])
        here = [p for p in points if sign_index(p.lon) == sign]
        shown = here if len(here) <= ROWS - 1 else here[: ROWS - 2]
        for k, p in enumerate(shown):
            y = y0 + 1 + k
            cv.put(x0, y, " " * box_w, bg=el["body_bg"])
            name = f"{symbol(p.key, p.glyph, t)} {short_name(p.key, p.name)}"
            # columns: name 1..w-10 · ℞ at w-9 · a space · degrees w-7..w-2 · one blank before the frame
            is_transit = id(p) in transiting  # transiting planets in the label colour, not bold
            name_fg = ui["label"] if is_transit else ui["white"]
            cv.put(x0 + 1, y, name[: box_w - 10], fg=name_fg, bg=el["body_bg"], bold=not is_transit)
            if p.retrograde and p.key not in ("north_node", "south_node"):
                cv.put(x0 + box_w - 9, y, "℞", fg=ui["retro"], bg=el["body_bg"], bold=True)
            deg_fg = ui["label"] if is_transit else el["accent"]
            cv.put(x0 + box_w - 7, y, degree_text(p.lon), fg=deg_fg, bg=el["body_bg"], bold=True)
        if len(here) > len(shown):
            y = y0 + ROWS - 1
            cv.put(x0, y, " " * box_w, bg=el["body_bg"])
            cv.put(x0 + 1, y, f"+{len(here) - len(shown)} more", fg=el["accent"], bg=el["body_bg"])

    _frame(cv, box_w, ui["frame"], ui["page"])
    _centre(cv, v, theme, box_w)
    return cv


def _frame(cv: Canvas, w: int, fg: tuple[int, int, int], bg: tuple[int, int, int]) -> None:
    xs = [k * (w + 1) for k in range(5)]
    ys = [k * (ROWS + 1) for k in range(5)]
    for y in range(ys[4] + 1):
        for x in xs:
            if not (x == xs[2] and ys[1] < y < ys[3]):
                cv.put(x, y, "║", fg, bg, True)
    for y in ys:
        for k in range(4):
            if not (y == ys[2] and k in (1, 2)):
                cv.put(xs[k] + 1, y, "═" * w, fg, bg, True)
    special = {(0, 0): "╔", (4, 0): "╗", (0, 4): "╚", (4, 4): "╝", (2, 1): "╩", (2, 3): "╦", (1, 2): "╣", (3, 2): "╠"}
    for i in range(5):
        for j in range(5):
            if (i, j) == (2, 2):
                continue
            ch = special.get((i, j)) or (
                "╦" if j == 0 else "╩" if j == 4 else "╠" if i == 0 else "╣" if i == 4 else "╬"
            )
            cv.put(xs[i], ys[j], ch, fg, bg, True)


def _centre(cv: Canvas, v: ViewData, theme: Theme, w: int) -> None:
    ui = theme.ui
    x, y, cw, ch = w + 2, ROWS + 2, 2 * w + 1, 2 * ROWS + 1
    bg = ui["center_bg"]
    cv.fill(x, y, cw, ch, " ", bg=bg)
    natal, m = v.natal, v.natal.moment
    cv.center(x, y, cw, (natal.name or "Chart").upper(), ui["title"], bg, True)
    when = f"{m.get('date', '')} {m.get('time', '')} {m.get('tz', '')}".strip()
    cv.center(x, y + 1, cw, when, ui["text"], bg)
    where = m.get("place") or ""
    if not where and "lat" in m:
        ns, ew = ("N" if m["lat"] >= 0 else "S"), ("E" if m["lon"] >= 0 else "W")
        where = f"{abs(m['lat']):.2f}{ns} {abs(m['lon']):.2f}{ew}"
    subtitle = f"HARMONIC {v.harmonic}" if v.harmonic > 1 else natal.profile.get("houses", "")
    line = f"{where} · {subtitle}" if where else subtitle
    if v.transit is not None:  # the place is in the title area already; the key matters more here
        line = f"transits {v.transit.moment.get('date', '')} in blue"
    cv.center(x, y + 2, cw, line, ui["label"] if v.transit is not None else ui["dim"], bg)

    lons = [p.lon for p in v.chart.points if p.key in v.pack.method.pattern_bodies]
    elems = [sum(1 for lon in lons if sign_index(lon) % 4 == k) for k in range(4)]
    modes = [sum(1 for lon in lons if sign_index(lon) % 3 == k) for k in range(3)]
    col2 = x + cw // 2 + 1
    cv.put(x + 2, y + 4, "ELEMENTS", ui["label"], bg, True)
    cv.put(col2, y + 4, "MODES", ui["label"], bg, True)
    bar_w = max(4, cw // 2 - 12)
    mode_w = x + cw - col2 - 13  # label 9 + gap + 2-digit count + margin
    # one block per planet; when a count won't fit, both columns shrink by the same factor so equal counts look equal
    scale = min(1.0, bar_w / max(max(elems), 1), mode_w / max(max(modes), 1))

    def bar(n: int) -> str:
        return "■" * (max(1, round(n * scale)) if n else 0)

    for k, name in enumerate(ELEMENTS):
        cv.put(x + 2, y + 5 + k, f"{name.capitalize():<6}", ui["text"], bg)
        cv.put(x + 8, y + 5 + k, bar(elems[k]), theme.element(k)["header_bg"], bg, True)
        cv.put(x + 9 + bar_w, y + 5 + k, str(elems[k]), ui["text"], bg, True)
    for k, name in enumerate(MODES):
        cv.put(col2, y + 5 + k, f"{name.capitalize():<9}", ui["text"], bg)
        cv.put(col2 + 9, y + 5 + k, bar(modes[k]), ui["label"], bg, True)
        cv.put(col2 + 10 + mode_w, y + 5 + k, str(modes[k]), ui["text"], bg, True)

    pm = v.pack.method
    shown_orb = pm.pattern_orb / v.orb_scale
    with_transits = v.transit_patterns is not None
    title = "GROUPS WITH TRANSITS" if with_transits else "PLANET GROUPS"
    cv.put(x + 2, y + 10, f"{title} · within {shown_orb:.3g}°"[: cw - 4], ui["label"], bg, True)
    pats = v.transit_patterns if v.transit_patterns is not None else v.patterns.patterns
    if not pats:
        none = "none (a transit with 2+ natal planets)" if with_transits else "none (3+ planets all this close)"
        cv.put(x + 2, y + 11, none, ui["dim"], bg)
    names = {p.key: p for p in [*(v.transit.points if v.transit else []), *v.natal.points]}

    def short(b: str) -> str:  # "t:saturn" → "tSat"
        key = b.removeprefix("t:")
        return ("t" if b.startswith("t:") else "") + short_name(key, names[key].name)[:3]

    for k, pat in enumerate(pats[: ch - 11]):
        colour = mix(ui["dim"], ui["title"], pat.strength)
        label = "-".join(short(b) for b in pat.bodies)
        cv.put(x + 2, y + 11 + k, label[: cw - 12], colour, bg, pat.strength > 0.5)
        span = f"{pat.span / v.orb_scale:5.2f}°"
        cv.put(x + cw - 2 - len(span), y + 11 + k, span, colour, bg, pat.strength > 0.5)
