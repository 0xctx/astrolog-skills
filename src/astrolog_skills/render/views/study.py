"""Doctrine and time-lord views: a planet-by-planet condition sheet, the lots, and the time lords on a date. All
drawn from the study (analysis/doctrine/explain.py), so they say exactly what the HTML page says."""

from __future__ import annotations

from datetime import date
from typing import Any

from astrolog_skills.engine.zodiac import SIGNS
from astrolog_skills.render.canvas import RGB, Canvas
from astrolog_skills.render.theme import Theme
from astrolog_skills.render.views.common import ViewData, symbol
from astrolog_skills.render.views.panels import _panel

Span = tuple[str, RGB, bool]
GOOD, BAD = (127, 220, 149), (255, 122, 133)


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _wrap(spans: list[Span], width: int, indent: int) -> list[list[Span]]:
    """Flow coloured spans into lines of `width` cells; continuation lines start `indent` cells in."""
    lines: list[list[Span]] = [[]]
    used = 0
    for text, fg, bold in spans:
        if text and not text.strip():  # a pure indent span
            lines[-1].append((text, fg, bold))
            used += len(text)
            continue
        for word in text.split(" "):
            if not word:
                continue
            glue = used and lines[-1] and not lines[-1][-1][0].endswith(" ")
            piece = (" " if glue else "") + word
            if used + len(piece) > width and lines[-1]:
                lines.append([(" " * indent, fg, False)])
                used = indent
                piece = word
            lines[-1].append((piece, fg, bold))
            used += len(piece)
    return lines


def _sheet(theme: Theme, width: int, title: str, rows: list[list[Span]], note: str = "") -> Canvas:
    ui, bg = theme.ui, theme.ui["center_bg"]
    body = rows + (_wrap([(note, ui["dim"], False)], width - 6, 0) if note else [])
    cv = _panel(theme, width, len(body) + 3, title)
    for y, row in enumerate(body):
        x = 3
        for text, fg, bold in row:
            cv.put(x, 2 + y, text[: max(0, width - 3 - x)], fg, bg, bold)
            x += len(text)
    return cv


def _missing(theme: Theme, width: int, title: str) -> Canvas:
    return _sheet(
        theme,
        min(width, 76),
        title,
        [[("this pack has no doctrine rules — try --pack hellenistic", theme.ui["dim"], False)]],
    )


def doctrine(v: ViewData, theme: Theme, width: int = 80) -> Canvas:
    """Each planet: position, place and sect; its good and bad testimony; who bonifies or maltreats it and how."""
    s = v.study
    w = max(60, min(width, 120))
    if not s:
        return _missing(theme, w, "DOCTRINE")
    ui = theme.ui
    inner = w - 6
    glyphs = {pt.key: pt.glyph for pt in v.natal.points}
    rows: list[list[Span]] = []
    sect = s["sect"]
    head: list[Span] = [
        (("Day chart" if sect["day"] else "Night chart") + f" · {s['rising']} rising", ui["title"], True)
    ]
    for x in sect["spectrum"]:
        head.append(
            (
                f" · {x['name']} {x['role']}",
                GOOD if x["role"].startswith("most helpful") else BAD if x["role"] == "most difficult" else ui["dim"],
                False,
            )
        )
    rows += _wrap(head, inner, 2)
    for p in s["planets"]:
        rows.append([])
        el = theme.element(int(p["lon"] // 30))
        line: list[Span] = [
            (f"{symbol(p['key'], glyphs.get(p['key'], ''), theme)} {p['name']:<8}", el["accent"], True),
            (f" {p['pos']:<17} {ordinal(p['place'])} place", ui["text"], False),
        ]
        rows += _wrap(line, inner, 2)
        if p.get("note"):
            rows += _wrap([("  ▸ ", ui["title"], True), (p["note"], ui["text"], False)], inner, 4)
        chips: list[Span] = []
        for i, t in enumerate(p["tokens"]):
            colour = GOOD if t["tone"] == "good" else BAD if t["tone"] == "bad" else ui["dim"]
            chips.append((t["label"].lower() + ("," if i < len(p["tokens"]) - 1 else ""), colour, t["tone"] != ""))
        rows += _wrap([("  ", ui["dim"], False), *chips], inner, 2)
        for c in p["conditions"]:
            mark, colour = ("+", GOOD) if c["effect"] == "bonify" else ("−", BAD)
            how = " · ".join(
                x
                for x in (
                    c["label"].lower(),
                    c["aspect"],
                    f"{c['distance']:.2f}° {'applying' if c['applying'] else 'separating'}"
                    if c["distance"] is not None
                    else "",
                )
                if x
            )
            spans: list[Span] = [
                (
                    f"  {mark} {'bonified' if c['effect'] == 'bonify' else 'maltreated'} by {' and '.join(c['actors'])}",
                    colour,
                    True,
                ),
                (f" · {how}" + (" · reception" if c["reception"] else ""), ui["dim"], False),
            ]
            rows += _wrap(spans, inner, 6)
    cites = " · ".join(f"{k} {v_}" for k, v_ in s.get("cites", {}).items() if "." not in k)
    return _sheet(theme, w, "DOCTRINE · " + v.pack.label.upper(), rows, cites)


def lots(v: ViewData, theme: Theme, width: int = 80) -> Canvas:
    s = v.study
    w = max(60, min(width, 120))
    if not s:
        return _missing(theme, w, "LOTS")
    ui = theme.ui
    rows: list[list[Span]] = []
    for lot in s["lots"]:
        lord = f" · lord {lot['lord_name']} in {ordinal(lot['lord_place'])}" if lot["lord"] else ""
        spans: list[Span] = [
            (f"{lot['title']:<11}", ui["white"], True),
            (f" {lot['pos']:<17} {ordinal(lot['place'])}{lord}", ui["text"], False),
            (f"  +{len(lot['good'])}", GOOD, True),
            (f" −{len(lot['bad'])}", BAD, True),
        ]
        rows += _wrap(spans, w - 6, 13)
        detail = [(", ".join(lot["good"][:3]), GOOD, False)] if lot["good"] else []
        if lot["bad"]:
            detail.append(((" · " if detail else "") + ", ".join(lot["bad"][:3]), BAD, False))
        if detail:
            rows += _wrap([(" " * 12, ui["dim"], False), *detail], w - 6, 13)
    return _sheet(
        theme, w, "LOTS · " + v.pack.label.upper(), rows, "the full checklist per lot: --json or the HTML page"
    )


def _when(v: ViewData) -> str:
    if v.transit is not None and v.transit.moment.get("date"):
        return str(v.transit.moment["date"])
    return date.today().isoformat()


def timelords(v: ViewData, theme: Theme, width: int = 80) -> Canvas:
    """The time lords on a date (the --transits date, or today): profection years, releasing periods, what's next."""
    s = v.study
    w = max(60, min(width, 120))
    if not s:
        return _missing(theme, w, "TIME LORDS")
    ui = theme.ui
    day = _when(v)
    rows: list[list[Span]] = []
    if not s.get("birth", "") <= day < s.get("end", "9999"):
        rows += _wrap([
            (f"{day} is outside the years worked out for this chart ({s['birth'][:4]}–{s['end'][:4]}).", ui["text"], False),
            (" Pick a date with --transits YYYY-MM-DD.", ui["dim"], False),
        ], w - 6, 4)  # fmt: skip
    years = [y for y in s.get("profections", []) if y["begins"] <= day < y["ends"]]
    for y in years:
        start = {"asc": "", "sect_light": " from the sect light", "contrary_light": " from the other light"}.get(
            y["start"], f" from {y['start']}"
        )
        planets = ", ".join(x.title() for x in y["planets_in_sign"])
        rows += _wrap([
            (f"Profection{start}:", ui["label"], True),
            (f" age {y['age']} · {ordinal(y['place'])} place {y['sign']} · lord {y['lord'].title()} in {ordinal(y['lord_place'])}", ui["text"], False),
            (f" · {planets} in the sign" if planets else "", ui["text"], False),
            (f" · to {y['ends']}", ui["dim"], False),
        ], w - 6, 4)  # fmt: skip
    upcoming: list[tuple[str, list[Span]]] = []
    for lot, rel in s.get("releasing", {}).items():
        if not any(p["begins"] <= day < p["ends"] or p["begins"] > day for p in rel["periods"]):
            continue  # nothing current or ahead from this lot on this date
        rows.append([])
        rows.append(
            [(f"Releasing from {lot.title()}" + (" (moved on one sign)" if rel["shifted"] else ""), ui["label"], True)]
        )
        for p in rel["periods"]:
            if p["begins"] <= day < p["ends"]:
                rows += _wrap(_period(p, theme, "  "), w - 6, 6)
            elif p["begins"] > day and (p["peak"] or p["loosing"]) and len(upcoming) < 40:
                upcoming.append((p["begins"], [(f"  {lot.title():<8}", ui["dim"], False), *_period(p, theme, "")]))
    if upcoming:
        rows.append([])
        rows.append([("Next peaks and loosings", ui["label"], True)])
        for _, spans in sorted(upcoming, key=lambda x: x[0])[:6]:
            rows += _wrap(spans, w - 6, 6)
    if s.get("lords"):
        L = s["lords"]
        rows.append([])
        lords = " → ".join(
            f"{x['planet'].title()} ({ordinal(x['place'])}{', ' + x['quality'] if x['quality'] else ''})"
            for x in L["lords"]
        )
        change = " or ".join(str(c["year_of_life"]) for c in L["changeover"])
        rows += _wrap(
            [
                ("Sect light lords:", ui["label"], True),
                (f" {lords}" + (f" · second from year {change}" if change else ""), ui["text"], False),
            ],
            w - 6,
            4,
        )
    return _sheet(theme, w, f"TIME LORDS · {day}", rows)


def _period(p: dict[str, Any], theme: Theme, pad: str) -> list[Span]:
    ui = theme.ui
    el = theme.element(SIGNS.index(p["sign"]) if p["sign"] in SIGNS else 0)
    spans: list[Span] = [
        (f"{pad}L{p['level']} {p['sign']:<11}", el["accent"], True),
        (f" {p['begins']} → {p['ends']} · {ordinal(p['from_fortune'])} from Fortune", ui["text"], False),
    ]
    if p["peak"]:
        spans.append((f" · peak {p['peak']}", ui["title"], True))
    if p["loosing"]:
        spans.append((" · loosing of the bond", BAD, True))
    if p["completion"]:
        spans.append((" · completion", ui["label"], False))
    if p["in_sign"]:
        spans.append((" · " + ", ".join(x.title() for x in p["in_sign"]) + " in it", ui["dim"], False))
    if p["benefic_angle"]:
        spans.append((" · benefic's angle", GOOD, False))
    if p["malefic_angle"]:
        spans.append((" · malefic's angle", BAD, False))
    return spans


def life(v: ViewData, theme: Theme, width: int = 80) -> Canvas:
    """The life: the reading's overview, each topic with its verdict and testimonies, and the chapters."""
    s = v.study
    w = max(60, min(width, 120))
    if not s:
        return _missing(theme, w, "LIFE")
    if not s.get("topics"):
        return _sheet(theme, w, "LIFE", [[("this pack defines no [topics]", theme.ui["dim"], False)]])
    ui = theme.ui
    rows: list[list[Span]] = []
    if s["life"].get("note"):
        rows += _wrap([(s["life"]["note"], ui["text"], False)], w - 6, 0)
        rows.append([])
    for t in s["topics"]:
        colour = GOOD if t["tone"] == "favourable" else BAD if t["tone"] == "difficult" else ui["label"]
        rows += _wrap([(t["label"], ui["white"], True), (f"  {t['verdict']}", colour, True)], w - 6, 2)
        if t.get("note"):
            rows += _wrap([("  ▸ ", ui["title"], True), (t["note"], ui["text"], False)], w - 6, 4)
        parts: list[Span] = [("  ", ui["dim"], False)]
        for i, c in enumerate(t["components"]):
            tone = GOOD if c["lean"] == "good" else BAD if c["lean"] == "bad" else ui["dim"]
            parts.append(
                (
                    c["title"] + f" +{len(c['good'])}/−{len(c['bad'])}" + ("," if i < len(t["components"]) - 1 else ""),
                    tone,
                    False,
                )
            )
        rows += _wrap(parts, w - 6, 2)
        rows.append([])
    for lot, rel in s.get("releasing", {}).items():
        rows.append([(f"Chapters of the life · {lot.title()}", ui["label"], True)])
        for p in rel["periods"]:
            if p["level"] != 1 or p["begins"] >= s["end"]:
                continue
            spans: list[Span] = [
                (
                    f"  {p['begins'][:4]}–{p['ends'][:4]} {p['sign']:<11}",
                    theme.element(SIGNS.index(p["sign"]))["accent"],
                    True,
                )
            ]
            if p["peak"]:
                spans.append((f" peak {p['peak']}", ui["title"], True))
            if p.get("note"):
                spans.append((f" {p['note']}", ui["text"], False))
            rows += _wrap(spans, w - 6, 20)
    return _sheet(theme, w, "LIFE · " + v.pack.label.upper(), rows)
