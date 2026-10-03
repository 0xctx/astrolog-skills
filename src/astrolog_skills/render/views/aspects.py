"""Aspects two ways: per-planet trees (aspects, then midpoints — midpoint-tree style) and the grid."""

from __future__ import annotations

from astrolog_skills.analysis.aspects import ANGLE_KEYS, ANGLE_NAMES
from astrolog_skills.analysis.aspects_registry import BY_KEY, AspectType
from astrolog_skills.engine.zodiac import SIGNS, sign_index
from astrolog_skills.errors import AstroError
from astrolog_skills.render.canvas import Canvas
from astrolog_skills.render.theme import Theme, mix
from astrolog_skills.render.views.common import ViewData, degree_text, element_index, short_name, symbol

FAMILY_ORDER = ("conjunction", "hard", "soft", "green", "pink", "quintile", "septile", "novile", "decile")


def _cell_text(sym: str, orb: float) -> str:
    return f"{sym}{orb:.0f}°" if orb >= 1 else f"{sym}{orb * 60:.0f}′"


def _orb_text(orb: float) -> str:
    minutes = int(orb * 60 + 1e-7)
    return f"{minutes // 60}°{minutes % 60:02d}′"


Row = tuple[str, tuple[int, int, int], str, bool, float, float]  # symbol, colour, text, midpoint?, orb, strength
Tree = tuple[str, list[Row]]  # heading, rows


def draw_trees(v: ViewData, theme: Theme, width: int = 80) -> Canvas:
    """A tree per body, midpoint-tree style: its aspects to single planets first, then the midpoints it sits
    on or aspects, each tightest first. In a harmonic chart, orbs show as measured there (or ÷ H: display.orbs)."""
    return _draw(v, theme, width, _trees(v, theme))


def tree_pages(v: ViewData, theme: Theme, width: int, limit: int) -> list[Canvas]:
    """The trees split into pages whose ANSI output each stays within `limit` characters (Claude Code's `!` cap);
    a page holds whole rows of trees, and a row that is too long on its own still gets a page."""
    trees = _trees(v, theme)
    cols = _layout(width)[1]
    rows_of_trees = [trees[i : i + cols] for i in range(0, len(trees), cols)]
    groups: list[list[Tree]] = []
    for block in rows_of_trees:
        if groups and len(_draw(v, theme, width, groups[-1] + block).render()) <= limit:
            groups[-1] += block
        else:
            groups.append(list(block))
    if len(groups) == 1:
        return [_draw(v, theme, width, groups[0])]
    return [_draw(v, theme, width, g, f"page {i} of {len(groups)}") for i, g in enumerate(groups, 1)]


def _layout(width: int) -> tuple[int, int, int, int, int]:
    """(page width, columns, margin, column pitch, name width) — a tree is 29 wide: a 3-wide symbol ("Ses" in letters),
    a 16-wide name ("Mercury/Jupiter"), one space and the orb; spare width goes to the gap between the two columns."""
    w = min(width, 78)
    name_w, tree_w = 16, 29
    cols = 2 if w >= 2 * tree_w + 12 else 1
    margin = 4 if cols == 2 else 2
    return w, cols, margin, tree_w + (w - 2 - 2 * margin - cols * tree_w), name_w


def _trees(v: ViewData, theme: Theme) -> list[Tree]:
    from astrolog_skills.analysis.midpoints import SKIP, midpoint_contacts

    ui, h, m = theme.ui, v.harmonic, v.pack.method
    names = {p.key: p for p in v.natal.points}
    shown = {p.key: p for p in v.chart.points}

    def name(key: str, short: bool = False) -> str:
        if key in ANGLE_KEYS:
            return symbol(key, "", theme) if short else ANGLE_NAMES[key]
        return short_name(key, names[key].name)

    def glyph(key: str) -> str:
        return symbol(key, "" if key in ANGLE_KEYS else names[key].glyph, theme)

    mids = midpoint_contacts(v.natal, m, h)
    trees: list[Tree] = []
    for key in [p.key for p in v.chart.points if p.key not in SKIP] + [k for k in ANGLE_KEYS if k in v.chart.angles]:
        rows: list[Row] = []
        for a in sorted((a for a in v.aspects if key in (a.a, a.b)), key=lambda a: a.orb):
            other = a.b if a.a == key else a.a
            if other in SKIP:
                continue
            asp = BY_KEY[a.aspect]
            colour = mix(ui["dim"], theme.aspects[asp.family], 0.35 + 0.65 * a.strength)
            rows.append(
                (
                    asp.glyph if theme.glyphs else asp.letters,
                    colour,
                    name(other),
                    False,
                    a.orb / v.orb_scale,
                    a.strength,
                )
            )
        for c in mids.get(key, []):
            asp = BY_KEY[c.aspect]
            colour = mix(ui["dim"], theme.aspects[asp.family], 0.35 + 0.65 * c.strength)
            pair = f"{name(c.a, True)}/{name(c.b, True)}"
            rows.append(
                (asp.glyph if theme.glyphs else asp.letters, colour, pair, True, c.orb / v.orb_scale, c.strength)
            )
        pos = shown[key].lon if key in shown else v.chart.angles[key]
        head = f"{glyph(key)} {name(key).upper()}  {degree_text(pos).strip()} {SIGNS[sign_index(pos)]}"
        trees.append((head, rows))
    return trees


def _draw(v: ViewData, theme: Theme, width: int, trees: list[Tree], page: str = "") -> Canvas:
    ui, bg, h, m = theme.ui, theme.ui["center_bg"], v.harmonic, v.pack.method
    w, cols, margin, col_w, name_w = _layout(width)
    blocks = [trees[i : i + cols] for i in range(0, len(trees), cols)]
    heights = [max(len(t[1]) for t in blk) + 2 for blk in blocks]
    cv = Canvas(w, 5 + (h > 1) + sum(heights), ui["page"])
    cv.fill(1, 1, w - 2, cv.height - 2, " ", bg=bg)
    cv.box(0, 0, w, cv.height, ui["frame"], ui["page"])
    title = (
        ("ASPECTS & MIDPOINTS" if m.midpoint_aspects else "ASPECTS")
        + f" · {v.pack.label}"
        + (f" · H{h}" if h > 1 else "")
        + (f" · {page}" if page else "")
    )
    cv.center(0, 0, w, f" {title} "[: w - 2], ui["frame_text"], ui["frame"], True)
    conj = "☌" if theme.glyphs else "conj"
    from astrolog_skills.analysis.midpoints import shown_method

    if shown_method(m, h) == "new":
        orbs = f"new method {conj} {_orb_text(m.midpoint_new_orb / v.orb_scale)}"
    else:
        orbs = f"{conj}{'☍' if theme.glyphs else '/opp'} {_orb_text(m.midpoint_orb / v.orb_scale)}"
    rule = (
        f"planets, then midpoints · {orbs}, others in proportion"
        if m.midpoint_aspects
        else "aspects to other planets · tightest first"
    )
    cv.put(3, 2, rule[: w - 5], ui["dim"], bg)
    if h > 1:
        cv.put(3, 3, v.orb_note()[: w - 5], ui["dim"], bg)
    y = 4 + (h > 1)
    for blk, height in zip(blocks, heights, strict=True):
        for col, (head, rows) in enumerate(blk):
            x = 1 + margin + col * col_w
            cv.put(x, y, head[: min(col_w - 2, w - 2 - x)], ui["title"], bg, True)  # headings may use the gap
            if not rows:
                cv.put(x + 2, y + 1, "no contacts", ui["dim"], bg)
            for k, (sym, colour, text, is_mid, orb, strength) in enumerate(rows):
                yy = y + 1 + k
                cv.put(x + 2, yy, f"{sym:<3}"[:3], colour, bg, strength > 0.5)
                # the orb shares the name's colour: one colour change fewer per entry keeps big charts within `!`
                fg = ui["label"] if is_mid else ui["white"]
                cv.put(x + 6, yy, f"{text[:name_w]:<{name_w}} {_orb_text(orb):>6}", fg, bg, not is_mid)
        y += height
    return cv


def draw(v: ViewData, theme: Theme, width: int = 80) -> Canvas:
    t, ui = theme, theme.ui
    bodies: list[tuple[str, str, float]] = [(p.key, symbol(p.key, p.glyph, t), p.lon) for p in v.chart.points]
    bodies += [(k, symbol(k, "", t), v.chart.angles[k]) for k in ANGLE_KEYS if k in v.chart.angles]
    n = len(bodies)
    cell = min(6, (width - 4) // n)  # 5-wide cells hold "⚼50′"; the frame adds 4 columns
    if cell < 5:
        raise AstroError(
            f"{n} bodies don't fit an aspect grid {width} columns wide.",
            fix="use --width 120, or a profile with fewer objects",
        )
    grid_w = cell * n + 4
    by_pair = {frozenset((a.a, a.b)): a for a in v.aspects}
    used = sorted({BY_KEY[a.aspect] for a in v.aspects}, key=lambda x: (FAMILY_ORDER.index(x.family), x.angle))
    key_rows = _key_lines(used, t, grid_w - 4)
    height = n + 5 + len(key_rows)
    cv = Canvas(grid_w, height, ui["page"])
    cv.fill(1, 1, grid_w - 2, height - 2, " ", bg=ui["grid_bg"])
    cv.box(0, 0, grid_w, height, ui["frame"], ui["page"])
    title = f" ASPECTS · {v.pack.label} " + (f"· H{v.harmonic} " if v.harmonic > 1 else "")
    cv.center(0, 0, grid_w, title, ui["frame_text"], ui["frame"], True)

    ox, oy = 2, 2
    for r, (kr, sr, lr) in enumerate(bodies):
        for c in range(r + 1):
            x, y = ox + c * cell, oy + r
            if c == r:
                el = t.element(element_index(lr))
                cv.put(x, y, f"{sr:^{cell}}", el["header_text"], el["header_bg"], True)
                continue
            base = ui["cell_a"] if (r + c) % 2 else ui["cell_b"]
            cv.put(x, y, " " * cell, bg=base)
            a = by_pair.get(frozenset((kr, bodies[c][0])))
            if a is None:
                continue
            asp = BY_KEY[a.aspect]
            fam = t.aspects[asp.family]
            k = a.strength  # 1 exact → 0 at the edge of the orb
            fg = mix(mix(base, fam, 0.5), ui["white"] if k > 0.85 else fam, k)
            bg = mix(base, fam, 0.35 * k * k)
            sym = asp.glyph if t.glyphs else asp.letters
            cv.put(x, y, _cell_text(sym, a.orb).center(cell)[:cell], fg, bg, k > 0.5)

    y = oy + n + 1
    for line in key_rows:
        xx = ox + 1
        for text, colour, bold in line:
            cv.put(xx, y, text, colour, ui["grid_bg"], bold)
            xx += len(text)
        y += 1
    return cv


def _key_lines(used: list[AspectType], theme: Theme, width: int) -> list[list[tuple[str, tuple[int, int, int], bool]]]:
    """Legend: symbol + name + angle for each aspect shown, wrapped to the grid width; then a strength note."""
    ui = theme.ui
    lines: list[list[tuple[str, tuple[int, int, int], bool]]] = [[]]
    length = 0
    for asp in used:
        sym = asp.glyph if theme.glyphs else asp.letters
        piece = [(sym, theme.aspects[asp.family], True), (f" {asp.name} {asp.angle:g}°  ", ui["dim"], False)]
        size = sum(len(p[0]) for p in piece)
        if length + size > width and lines[-1]:
            lines.append([])
            length = 0
        lines[-1].extend(piece)
        length += size
    if not used:
        lines = [[("no aspects within the pack's orbs", ui["dim"], False)]]
    lines.append([("brighter = tighter orb = stronger", ui["white"], True)])
    return lines
