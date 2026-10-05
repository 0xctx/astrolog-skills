"""`astro transits` — the sky at a moment against a natal chart, and what perfects in the coming days."""

from __future__ import annotations

from datetime import UTC, datetime

import typer
from rich.console import Console
from rich.markup import escape

from astrolog_skills import config
from astrolog_skills.analysis.aspects_registry import BY_KEY
from astrolog_skills.analysis.transits import transit_aspects
from astrolog_skills.cli.app import out
from astrolog_skills.cli.birth import moment_from_options
from astrolog_skills.cli.commands.analysis import name_of
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.moment import Moment
from astrolog_skills.errors import AstroError
from astrolog_skills.packs.settings import resolve
from astrolog_skills.ui import rgb


def transit_moment(
    when: str, natal: ChartModel, time: str | None = None, place_at: tuple[float, float] | None = None
) -> Moment:
    """A transit moment: 'now' or YYYY-MM-DD (noon UT unless a time is given), at your location or the birthplace."""
    lat, lon = place_at or config.location() or (natal.moment["lat"], natal.moment["lon"])
    if when in ("", "now"):
        return Moment.now(lat, lon, "Transits")
    try:
        datetime.fromisoformat(when)
    except ValueError as err:
        raise AstroError(f"'{when}' isn't a date.", fix="use YYYY-MM-DD or 'now'") from err
    return Moment(when, time or "12:00", "UTC", lat, lon, "Transits")


def _names(text: str | None) -> tuple[str, ...]:
    return tuple(k.strip().lower() for k in text.split(",") if k.strip()) if text else ()


def register(app: typer.Typer) -> None:
    @app.command(
        "transits",
        help="Transits to a natal chart for a date (default now). --days N adds a timeline: every transit to the natal"
        " planets, angles and midpoints, grouped by transiting planet, and the patterns transits form in harmonic"
        " charts. Bodies, aspects and orbs are the chart's and the tradition pack's unless you choose.",
    )
    def transits_cmd(
        ctx: typer.Context,
        chart: str = typer.Option(None, "--chart", help="The natal chart (saved)."),
        date: str = typer.Option(None, "--date", help="Natal date if not saved."),
        time: str = typer.Option(None, "--time", help="Natal time if not saved."),
        place: str = typer.Option(None, "--place", help="Natal place if not saved."),
        tz: str = typer.Option(None, "--tz"),
        at: str = typer.Option(None, "--at"),
        on: str = typer.Option("now", "--on", help="Transit date YYYY-MM-DD, or now."),
        on_time: str = typer.Option(None, "--on-time", help="Transit time HH:MM (UT); default noon UT for a date."),
        days: int = typer.Option(0, "--days", help="Add a timeline of the next N days (up to 730)."),
        pack: str = typer.Option(None, "--pack", help="Tradition pack (default: your profile's)."),
        profile: str = typer.Option(None, "--profile"),
        transiting: str = typer.Option(None, "--transiting", help="Timeline: transiting bodies, e.g. saturn,ceres."),
        natal_only: str = typer.Option(None, "--natal", help="Timeline: natal points, e.g. sun,moon,asc."),
        aspects: str = typer.Option(None, "--aspects", help="Timeline: aspects, e.g. conjunction,septile or h5,h7."),
        midpoints: bool = typer.Option(
            True, "--midpoints/--no-midpoints", help="Timeline: transits to natal midpoints."
        ),
        harmonics: str = typer.Option(None, "--harmonics", help="Harmonic patterns: 1-32 … (default: the pack's)."),
        limit: int = typer.Option(400, "--limit", help="Timeline: passages in --json, slowest body first (0 = all)."),
    ) -> None:
        from astrolog_skills.analysis import transit_timeline as tt

        if not 0 <= days <= 730:
            raise AstroError("--days must be between 0 and 730.")
        prof, p = resolve(profile, pack)
        natal_moment, _ = moment_from_options(chart=chart, date=date, time=time, place=place, tz=tz, at=at)
        natal = cast(natal_moment, prof)
        moment = transit_moment(on, natal, on_time)
        sky = cast(moment, prof)
        found = transit_aspects(natal, sky, p.method)
        line = None
        if days:
            assert moment.utc is not None
            start = moment.utc.replace(hour=12, minute=0, second=0, microsecond=0) if on != "now" else datetime.now(UTC)
            sel = tt.Selection(_names(transiting), _names(natal_only), _names(aspects), midpoints)
            line = tt.build(natal, prof, p.method, start, days, moment.lat, moment.lon, sel, harmonics)
        data = {
            "natal": natal.name,
            "when": moment.to_dict(),
            "pack": p.name,
            "transits": [t.to_dict() for t in found],
            "timeline": line.to_dict(limit) if line else None,
            "sky": sky.to_dict(),
        }

        def render(c: Console) -> None:
            stamp = moment.to_dict()["utc"][:16].replace("T", " ")
            c.print(f"[bold]{escape(natal.name or 'Chart')}[/] · transits {stamp} UT · {escape(p.label)}")
            for t in found:
                asp = BY_KEY[t.aspect]
                move = "applying" if t.applying else "separating"
                c.print(
                    f"  t {name_of(t.transit):<11} {asp.glyph} {asp.name:<14} {name_of(t.natal):<11} "
                    f"orb {t.orb:4.2f}°  [{rgb('dim')}]{move}[/]"
                )
            if not found:
                c.print(f"  [{rgb('dim')}]nothing within the pack's transit orbs[/]")
            if line:
                from astrolog_skills.render.views.transit_timeline import render

                render(c, line.to_dict(), c.width)  # every passage: the view shows the first ones

        out(ctx).emit(data, render)
