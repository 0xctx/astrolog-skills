"""`astro doctrine` — a chart read through the pack's doctrine: sect, dignities, solar phase and places."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from astrolog_skills.analysis.doctrine.engine import NatalDoctrine, analyse
from astrolog_skills.analysis.doctrine.explain import build_study
from astrolog_skills.cli.app import out
from astrolog_skills.cli.birth import moment_from_options
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.moment import Moment
from astrolog_skills.engine.profile import Profile
from astrolog_skills.engine.zodiac import format_position
from astrolog_skills.errors import AstroError
from astrolog_skills.packs import meanings
from astrolog_skills.packs.loader import Pack
from astrolog_skills.packs.settings import citations, resolve
from astrolog_skills.ui import rgb


def study_for(moment: Moment, model: ChartModel, tradition: Pack, prof: Profile) -> dict[str, Any] | None:
    """The study (findings, reasons, glossary, time lords) for views and the HTML page; None without doctrine."""
    doctrine = tradition.method.doctrine
    if doctrine is None:
        return None
    later = None
    if doctrine.phase and doctrine.phase.heliacal_days:
        later = cast(later_moment(moment, doctrine.phase.heliacal_days), prof)
    glossary = meanings.load_glossary(tradition.file("meanings.md"))
    return build_study(model, doctrine, glossary, later)


def later_moment(moment: Moment, days: int) -> Moment:
    assert moment.utc is not None
    u = moment.utc + timedelta(days=days)
    return Moment(u.date().isoformat(), u.strftime("%H:%M:%S"), "UTC", moment.lat, moment.lon, moment.name)


SECTIONS = ("planets", "testimony", "conditions", "lots", "places")


def _words(token: str) -> str:
    return token.replace("_", " ")


def _render(r: NatalDoctrine, pack: str, show: list[str]) -> Callable[[Console], None]:
    dim = rgb("dim")

    def planets(c: Console) -> None:
        t = Table(box=None, pad_edge=False, header_style=dim)
        for col in ("planet", "position", "place", "sect", "dignities", "phase"):
            t.add_column(col)
        for p in r.planets:
            sect = ""
            if p.sect and p.sect.sect:
                sect = f"{p.sect.sect}, {'of' if p.sect.of_sect else 'contrary to'} sect"
                joys = [
                    w for w, on in (("hemisphere", p.sect.rejoices_hemisphere), ("sign", p.sect.rejoices_sign)) if on
                ]
                if joys:
                    sect += "; rejoices by " + " and ".join(joys)
            place = f"{p.place.place} · " + ", ".join(p.place.labels())
            t.add_row(
                p.key.title(),
                format_position(p.lon),
                place,
                sect,
                ", ".join(p.dignities.labels()) if p.dignities else "",
                ", ".join(p.phase.labels()) if p.phase else "",
            )
        c.print(t)

    def testimony(c: Console) -> None:
        if not any(t.good or t.bad for t in r.testimony.values()):
            c.print(f"[{dim}]testimony: the pack's [scoring] names no good or bad findings[/]")
            return
        c.print("[bold]Testimony[/]")
        for key, t in r.testimony.items():
            score = f" · score {t.score:g}" if t.score is not None else ""
            c.print(f"  {key.title():<8} {plus_minus(t.good, t.bad)}{score}", soft_wrap=True)

    def conditions(c: Console) -> None:
        if not r.conditions:
            c.print(f"[{dim}]conditions: none found[/]")
            return
        c.print("[bold]Bonification and maltreatment[/]")
        for x in sorted(r.conditions, key=lambda x: (x.target, x.effect, x.condition)):
            colour = rgb("ok") if x.effect == "bonify" else rgb("bad")
            verb = "bonified" if x.effect == "bonify" else "maltreated"
            how = [_words(x.condition)]
            if x.aspect:
                how.append(x.aspect)
            if x.distance is not None:
                how.append(f"{x.distance:.2f}° {'applying' if x.applying else 'separating'}")
            sect = "" if x.actor_of_sect is None else " (of sect)" if x.actor_of_sect else " (contrary to sect)"
            extra = " · reception" if x.reception else ""
            actor = " and ".join(a.title() for a in x.actor.split("+"))
            c.print(
                f"  {x.target.title():<8} [{colour}]{verb}[/] by {actor}{sect} · {', '.join(how)}{extra}",
                soft_wrap=True,
            )

    def plus_minus(good: list[str], bad: list[str]) -> str:
        g = ", ".join(_words(x) for x in good) or "—"
        b = ", ".join(_words(x) for x in bad) or "—"
        return f"[{rgb('ok')}]+{len(good)}[/] {g}  [{rgb('bad')}]−{len(bad)}[/] {b}"

    def lots(c: Console) -> None:
        if not r.lots:
            return
        c.print("[bold]Lots[/]")
        for name, lot in r.lots.items():
            tp = r.lot_topics[name]
            lord = f" · lord {tp.lord.title()} in {tp.lord_place}" if tp.lord else ""
            fallback = " (fallback formula)" if lot.fallback else ""
            judged = r.lot_testimony.get(name)
            verdict = f"  {plus_minus(judged.good, judged.bad)}" if judged and (judged.good or judged.bad) else ""
            c.print(
                f"  {name.title():<11} {format_position(lot.lon)} · place {lot.place}{lord}{fallback}{verdict}",
                soft_wrap=True,
            )

    def places_(c: Console) -> None:
        t = Table(box=None, pad_edge=False, header_style=dim)
        for col in ("place", "sign", "lord", "lord in", "lord's condition"):
            t.add_column(col)
        for tp in r.places:
            mark = [
                x for x in tp.checklist if x.startswith("lord_") and x.endswith(("bonified", "maltreated", "beams"))
            ]
            mark = [x for x in mark if not x.startswith("lord_not_")]
            t.add_row(
                tp.name.removeprefix("place "),
                tp.sign,
                tp.lord.title(),
                str(tp.lord_place or ""),
                ", ".join(_words(x.removeprefix("lord_")) for x in mark),
            )
        c.print(t)

    parts = {"planets": planets, "testimony": testimony, "conditions": conditions, "lots": lots, "places": places_}

    def render(c: Console) -> None:
        head = "Day chart" if r.day else "Night chart"
        if r.sect:
            head += f" · sect light {r.sect.light.title()}"
            if r.sect.benefic:
                head += f" · benefic of sect {r.sect.benefic.title()}"
            if r.sect.malefic:
                head += f" · malefic of sect {r.sect.malefic.title()}"
        c.print(f"[bold]{escape(r.chart)}[/] · {escape(pack)} · {head} · {r.asc_place_sign} rising")
        for name in show:
            parts[name](c)
        main = {k: v for k, v in r.cites.items() if "." not in k} if citations() else {}
        if main:
            c.print(f"[{dim}]" + " · ".join(f"{k} {escape(v)}" for k, v in main.items()) + " · all pages: --json[/]")
        for n in r.notes:
            c.print(f"[{rgb('warn')}]note[/] {escape(n)}")

    return render


def register(app: typer.Typer) -> None:
    @app.command(
        "doctrine", help="A chart by the pack's doctrine: sect, dignities, phase, places, conditions, lots, rulers."
    )
    def doctrine_cmd(
        ctx: typer.Context,
        chart: str = typer.Option(..., "--chart", help="A saved chart."),
        pack: str = typer.Option(None, "--pack", help="Tradition pack with doctrine rules (default: your profile's)."),
        profile: str = typer.Option(None, "--profile"),
        show: str = typer.Option(
            "planets,testimony,conditions,lots", "--show", help="Sections: " + ", ".join(SECTIONS) + " (or all)."
        ),
    ) -> None:
        chosen = list(SECTIONS) if show.strip() == "all" else [x.strip() for x in show.split(",") if x.strip()]
        unknown = [x for x in chosen if x not in SECTIONS]
        if unknown:
            raise AstroError(f"Unknown section(s): {', '.join(unknown)}.", fix="choose from " + ", ".join(SECTIONS))
        moment, _ = moment_from_options(chart=chart)
        prof, tradition = resolve(profile, pack)
        doctrine = tradition.method.doctrine
        if doctrine is None:
            raise AstroError(
                f"Pack '{tradition.name}' has no doctrine rules (sect, dignities, phase, places).",
                fix="use a pack that has them, e.g. --pack hellenistic, or build one from your sources",
            )
        model = cast(moment, prof)
        later = None
        if doctrine.phase and doctrine.phase.heliacal_days:
            later = cast(later_moment(moment, doctrine.phase.heliacal_days), prof)
        result = analyse(model, doctrine, later)
        data = {"pack": tradition.name, **result.to_dict()}
        out(ctx).emit(data, _render(result, tradition.name, chosen))
