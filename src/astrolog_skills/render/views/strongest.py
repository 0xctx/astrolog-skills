"""Terminal output of `astro harmonics`: a bar per harmonic (midpoint strength above a typical chart), the strongest
harmonics with their structures, and the strongest structures each at its own vibration — or one harmonic in detail."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.markup import escape

from astrolog_skills.analysis.aspects_registry import BY_KEY as ASPECTS
from astrolog_skills.engine.objects import BY_KEY as OBJECTS
from astrolog_skills.ui import rgb

BLOCKS = "▁▂▃▄▅▆▇█"
SCORE = {"new": "z_new", "old": "z_old", "groups": "z_groups", "aspects": "aspects"}
METHOD = {
    "new": "midpoint structures, new method",
    "old": "midpoint structures, old method",
    "groups": "planet groups (3+ planets together in the harmonic chart)",
    "aspects": "two-planet aspects",
}


def _name(key: str) -> str:
    o = OBJECTS.get(key)
    return o.name if o else key.title()


def _glyph(key: str) -> str:
    o = OBJECTS.get(key)
    return o.glyph if o else ""


def _structure(s: dict[str, Any], short: bool = False) -> str:
    """'☉ Sun = Venus/Pluto .97'."""
    head = f"{_glyph(s['focus'])} {_name(s['focus'])}" if not short else _name(s["focus"])
    return f"{head} = {_name(s['a'])}/{_name(s['b'])} [bold]{s['strength']:.2f}[/]"


def _group(g: dict[str, Any]) -> str:
    """'Mercury–Saturn–Neptune–Pluto 0.75 · generational'."""
    flags = []
    if g["exact_time"]:
        flags.append(f"needs the birth time within ~{g['moon_minutes']} min (the Moon)")
    if g["generational"]:
        flags.append("mostly generational (outer planets)")
    tail = f" [{rgb('dim')}]· {' · '.join(flags)}[/]" if flags else ""
    return f"{'–'.join(_name(b) for b in g['bodies'])} [bold]{g['strength']:.2f}[/]{tail}"


def _dm(deg: float) -> str:
    d, m = int(deg), round((deg - int(deg)) * 60)
    if m == 60:
        d, m = d + 1, 0
    return f"{d}°{m:02d}′"


def _sigma(z: float) -> str:
    colour = rgb("ok") if z >= 2 else rgb("warn") if z >= 1 else rgb("dim")
    return f"[{colour}]{z:+.1f}σ[/]"


def _bars(c: Console, rows: list[dict[str, Any]], by: str, top: set[int]) -> None:
    """One bar per harmonic: its score above chance (or the aspect score), the strongest ones bright. A long range
    (more than 76) is grouped: each column shows the best harmonic of its group."""
    per = -(-len(rows) // 76)  # harmonics per column
    groups = [rows[k : k + per] for k in range(0, len(rows), per)]
    best = [max(g, key=lambda r: float(r[SCORE[by]])) for g in groups]
    wide = len(groups) <= 38
    values = [max(float(r[SCORE[by]]), 0.0) for r in best]
    peak = max(values) or 1.0
    every = 8 if per == 1 else 30 if len(rows) <= 240 else 60
    line, labels = "  ", "  "
    step = 2 if wide else 1
    free = 0  # the next column a label may start in, so neighbouring labels never run together
    for i, (g, r, v) in enumerate(zip(groups, best, values, strict=True)):
        block = BLOCKS[min(int(v / peak * (len(BLOCKS) - 1) + 0.5), len(BLOCKS) - 1)] if v > 0 else "·"
        colour = rgb("gold") if r["harmonic"] in top else rgb("accent") if v > 0 else rgb("dim")
        line += f"[{colour}]{block}[/]" + (" " if wide else "")
        mark = next((x["harmonic"] for x in g if x["harmonic"] in top or x["harmonic"] % every == 0), None)
        n = str(mark if mark is not None else g[0]["harmonic"])
        col = i * step
        if (mark is not None or i == 0) and col >= free:
            labels += " " * (col - (len(labels) - 2)) + n
            free = col + len(n) + 1
    c.print(line)
    c.print(f"[{rgb('dim')}]{labels.rstrip()}[/]")


def ceiling_note(new_orb: float, highest: int) -> str | None:
    """Above 360 ÷ orb the new method has nothing left: every angle is within the orb of a conjunction in some lower
    harmonic (Dirichlet's approximation theorem), so every structure already has its own, lower, harmonic."""
    top = int(360 // new_orb)
    if highest <= top:
        return None
    return (
        f"new method: with a {new_orb:g}° orb every structure finds its own harmonic by H{top} (360 ÷ {new_orb:g}), "
        f"so the harmonics above it hold none — rank by --by old to compare them"
    )


def render_ranking(c: Console, data: dict[str, Any], chart: str, top: int) -> None:
    by, rows = data["by"], data["harmonics"]
    by_h = {r["harmonic"]: r for r in rows}
    best = [by_h[h] for h in data["ranked"][:top]]
    lo, hi = rows[0]["harmonic"], rows[-1]["harmonic"]
    span = f"H{lo}–{hi}" if len(rows) == hi - lo + 1 else ", ".join(f"H{r['harmonic']}" for r in rows)
    c.print(f"[bold]{escape(chart)}[/] · strongest harmonics {span} · {escape(data['pack'])}")
    note = "compared with a typical chart in each harmonic" if by != "aspects" else "the pack's pair score"
    c.print(f"[{rgb('dim')}]{METHOD[by]}, {note}[/]\n")
    _bars(c, rows, by, {r["harmonic"] for r in best[:3]})
    ceiling = ceiling_note(data["orbs"]["new"], hi) if by == "new" else None
    if ceiling:
        c.print(f"[{rgb('dim')}]{ceiling}[/]", soft_wrap=True)
    c.print()
    for r in best:
        score = f"aspects {r['aspects']:.1f}" if by == "aspects" else _sigma(r[SCORE[by]])
        rest = {
            "new": f"midpoints {r['new']:.2f} (typical {r['chance_new']:.2f}) · old {_sigma(r['z_old'])}",
            "old": f"midpoints {r['old']:.2f} (typical {r['chance_old']:.2f}) · new {_sigma(r['z_new'])}",
            "groups": f"groups {r['groups']:.2f} (typical {r['chance_groups']:.2f}) · new {_sigma(r['z_new'])}",
            "aspects": f"new {_sigma(r['z_new'])}",
        }[by]
        others = f" · groups {_sigma(r['z_groups'])}" if by in ("new", "old") else ""
        aspects = f" · aspects {r['aspects']:.1f}" if by != "aspects" else ""
        c.print(f"  [bold {rgb('gold')}]H{r['harmonic']:<3}[/] {score}  {rest}{others}{aspects}", soft_wrap=True)
        if by == "groups":
            for g in r["group_list"]:
                c.print(f"       {_group(g)}", soft_wrap=True)
            continue
        structs = r["old_structures"] if by == "old" else r["new_structures"]
        if structs:
            c.print("       " + " · ".join(_structure(s) for s in structs), soft_wrap=True)
    if data["structures"] and by != "groups":
        c.print(
            f"\n[bold {rgb('water')}]STRONGEST MIDPOINT STRUCTURES[/] "
            f"[{rgb('dim')}]each at its own harmonic · natal angle to the midpoint · old method[/]"
        )
        shown = data["structures"][:10]
        names = [f"{_glyph(s['focus'])} {_name(s['focus'])} = {_name(s['a'])}/{_name(s['b'])}" for s in shown]
        width = max((len(n) for n in names), default=0)
        for s, name in zip(shown, names, strict=True):
            old = " · ".join(f"{h} {v:.2f}" if v is not None else f"{h} –" for h, v in s["old"].items())
            c.print(
                f"  [bold {rgb('gold')}]H{s['harmonic']:<3}[/] {escape(name.ljust(width))}  "
                f"[bold]{s['strength']:.2f}[/]  "
                f"[{rgb('dim')}]{_dm(s['natal_angle']):>8} = {s['fraction']:<5} of the circle · old {old}[/]",
                soft_wrap=True,
            )
    c.print(
        f"\n[{rgb('dim')}]σ = how much stronger than a typical chart in that harmonic; 2σ or more is rare. "
        f"One harmonic: astro harmonics --chart NAME --harmonic {best[0]['harmonic'] if best else 1}"
        f" · rank by --by new|old|groups|aspects[/]",
        soft_wrap=True,
    )


def render_detail(c: Console, data: dict[str, Any], chart: str) -> None:
    d = data["detail"]
    h = d["harmonic"]
    row = next(r for r in data["harmonics"] if r["harmonic"] == h)
    c.print(f"[bold]{escape(chart)}[/] · [bold {rgb('gold')}]H{h}[/] · {escape(data['pack'])}")
    c.print(
        f"  midpoints {_sigma(row['z_new'])} new ({row['new']:.2f}, typical {row['chance_new']:.2f}) · "
        f"{_sigma(row['z_old'])} old · aspects {row['aspects']:.1f}\n"
    )
    if d["aspects"]:
        c.print(f"  [bold {rgb('water')}]aspects[/]")
        for a in d["aspects"][:8]:
            t = ASPECTS[a["aspect"]]
            c.print(f"    {t.glyph} {_name(a['a'])}–{_name(a['b'])} {t.name} [{rgb('dim')}]{a['orb']:.1f}°[/]")
    for how in ("new", "old"):
        c.print(f"  [bold {rgb('water')}]midpoints, {how} method[/]")
        found = d["midpoints"][how]
        if not found:
            c.print(f"    [{rgb('dim')}]none in orb[/]")
        for m in found[:8]:
            t = ASPECTS[m["aspect"]]
            own = ""
            if how == "new" and m.get("vibration") and m["vibration"] != h:
                own = f" [{rgb('dim')}](its own vibration: H{m['vibration']})[/]"
            c.print(
                f"    {t.glyph} {_name(m['focus'])} {t.name} {_name(m['a'])}/{_name(m['b'])} "
                f"[bold]{m['strength']:.2f}[/] [{rgb('dim')}]{m['orb'] * 60:.0f}′[/]{own}",
                soft_wrap=True,
            )
