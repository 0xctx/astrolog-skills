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
SCORE = {"new": "z_new", "old": "z_old", "aspects": "aspects"}
METHOD = {
    "new": "midpoint structures, new method",
    "old": "midpoint structures, old method",
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


def _dm(deg: float) -> str:
    d, m = int(deg), round((deg - int(deg)) * 60)
    if m == 60:
        d, m = d + 1, 0
    return f"{d}°{m:02d}′"


def _sigma(z: float) -> str:
    colour = rgb("ok") if z >= 2 else rgb("warn") if z >= 1 else rgb("dim")
    return f"[{colour}]{z:+.1f}σ[/]"


def _bars(c: Console, rows: list[dict[str, Any]], by: str, top: set[int]) -> None:
    """One bar per harmonic: its score above chance (or the aspect score), the strongest ones bright."""
    if len(rows) > 76:
        return
    wide = len(rows) <= 38
    values = [max(float(r[SCORE[by]]), 0.0) for r in rows]
    peak = max(values) or 1.0
    line, labels = "  ", "  "
    step = 2 if wide else 1
    free = 0  # the next column a label may start in, so neighbouring labels never run together
    for i, (r, v) in enumerate(zip(rows, values, strict=True)):
        block = BLOCKS[min(int(v / peak * (len(BLOCKS) - 1) + 0.5), len(BLOCKS) - 1)] if v > 0 else "·"
        colour = rgb("gold") if r["harmonic"] in top else rgb("accent") if v > 0 else rgb("dim")
        line += f"[{colour}]{block}[/]" + (" " if wide else "")
        n = str(r["harmonic"])
        col = i * step
        wanted = r["harmonic"] in top or r["harmonic"] % 8 == 0 or i == 0
        if wanted and col >= free:
            labels += " " * (col - (len(labels) - 2)) + n
            free = col + len(n) + 1
    c.print(line)
    c.print(f"[{rgb('dim')}]{labels.rstrip()}[/]")


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
    c.print()
    for r in best:
        score = f"aspects {r['aspects']:.1f}" if by == "aspects" else _sigma(r[SCORE[by]])
        rest = f"midpoints {r['new']:.2f} (typical {r['chance_new']:.2f}) · old {_sigma(r['z_old'])}"
        if by == "old":
            rest = f"midpoints {r['old']:.2f} (typical {r['chance_old']:.2f}) · new {_sigma(r['z_new'])}"
        aspects = f" · aspects {r['aspects']:.1f}" if by != "aspects" else f" · new {_sigma(r['z_new'])}"
        c.print(f"  [bold {rgb('gold')}]H{r['harmonic']:<3}[/] {score}  {rest}{aspects}", soft_wrap=True)
        structs = r["old_structures"] if by == "old" else r["new_structures"]
        if structs:
            c.print("       " + " · ".join(_structure(s) for s in structs), soft_wrap=True)
    if data["structures"]:
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
        f" · rank by --by new|old|aspects[/]",
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
