"""`astro aspects` and `astro patterns` — the analysis engine, driven by a tradition pack."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markup import escape

from astrolog_skills.analysis.aspects import ANGLE_NAMES, find_aspects
from astrolog_skills.analysis.aspects_registry import BY_KEY
from astrolog_skills.analysis.patterns import harmonic_profile, score_harmonic
from astrolog_skills.cli.app import out
from astrolog_skills.cli.birth import moment_from_options
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.objects import BY_KEY as OBJECTS
from astrolog_skills.engine.profile import Profile
from astrolog_skills.errors import AstroError
from astrolog_skills.packs.settings import resolve
from astrolog_skills.ui import rgb

CHART_OPTS = {
    "chart": typer.Option(None, "--chart", help="A saved chart."),
    "date": typer.Option(None, "--date", help="Local date, YYYY-MM-DD."),
    "time": typer.Option(None, "--time", help="Local clock time, HH:MM[:SS]."),
    "place": typer.Option(None, "--place", help='Birthplace, e.g. "Ulm, Germany".'),
    "tz": typer.Option(None, "--tz", help="IANA zone, offset, UTC or LMT."),
    "at": typer.Option(None, "--at", help='Coordinates, e.g. "48N24 10E00".'),
}


def name_of(key: str) -> str:
    return OBJECTS[key].name if key in OBJECTS else ANGLE_NAMES.get(key, key)


def _chart(
    chart: str | None,
    date: str | None,
    time: str | None,
    place: str | None,
    tz: str | None,
    at: str | None,
    prof: Profile,
) -> ChartModel:
    moment, _ = moment_from_options(chart=chart, date=date, time=time, place=place, tz=tz, at=at)
    return cast(moment, prof)


def _range(text: str) -> tuple[int, int]:
    try:
        low, _, high = text.partition("-")
        lo, hi = int(low), int(high or low)
    except ValueError as err:
        raise AstroError(f"'{text}' isn't a harmonic range.", fix="e.g. --range 1-32") from err
    if not 1 <= lo <= hi <= 1000:
        raise AstroError("Harmonic range must be within 1–1000, low to high.")
    return lo, hi


def register(app: typer.Typer) -> None:
    @app.command("aspects", help="Aspects in a chart (or a harmonic chart) by your tradition pack's rules.")
    def aspects_cmd(
        ctx: typer.Context,
        chart: str = CHART_OPTS["chart"],
        date: str = CHART_OPTS["date"],
        time: str = CHART_OPTS["time"],
        place: str = CHART_OPTS["place"],
        tz: str = CHART_OPTS["tz"],
        at: str = CHART_OPTS["at"],
        pack: str = typer.Option(None, "--pack", help="Tradition pack (default: your profile's)."),
        profile: str = typer.Option(None, "--profile", help="Settings profile."),
        harmonic: int = typer.Option(1, "--harmonic", "-H", help="Aspects inside harmonic chart H."),
    ) -> None:
        prof, p = resolve(profile, pack)
        model = _chart(chart, date, time, place, tz, at, prof)
        found = find_aspects(model, p.method, harmonic)
        data = {"chart": model.name, "pack": p.name, "harmonic": harmonic, "aspects": [a.to_dict() for a in found]}

        def render(c: Console) -> None:
            c.print(
                f"[bold]{escape(model.name or 'Chart')}[/] · {escape(p.label)} · H{harmonic} · {len(found)} aspects"
            )
            for a in found:
                t = BY_KEY[a.aspect]
                move = "" if a.applying is None else (" applying" if a.applying else " separating")
                c.print(
                    f"  {name_of(a.a):<12} {t.glyph:<2} {t.name:<15} {name_of(a.b):<12} orb {a.orb:5.2f}°  "
                    f"[{rgb('dim')}]{a.strength:.0%}{move}[/]"
                )

        out(ctx).emit(data, render)

    @app.command(
        "patterns", help="Vibrational patterns (3+ bodies conjunct in a harmonic chart) and the pack's pattern scores."
    )
    def patterns_cmd(
        ctx: typer.Context,
        chart: str = CHART_OPTS["chart"],
        date: str = CHART_OPTS["date"],
        time: str = CHART_OPTS["time"],
        place: str = CHART_OPTS["place"],
        tz: str = CHART_OPTS["tz"],
        at: str = CHART_OPTS["at"],
        pack: str = typer.Option(None, "--pack", help="Tradition pack (default: your profile's)."),
        profile: str = typer.Option(None, "--profile", help="Settings profile."),
        harmonic: int = typer.Option(None, "--harmonic", "-H", help="One harmonic."),
        range_: str = typer.Option(None, "--range", help="Harmonic range, e.g. 1-32 (default: the pack's)."),
        top: int = typer.Option(0, "--top", help="Only the N strongest harmonics."),
    ) -> None:
        prof, p = resolve(profile, pack)
        model = _chart(chart, date, time, place, tz, at, prof)
        lons = {pt.key: pt.lon for pt in model.points}
        if harmonic:
            scores = [score_harmonic(lons, harmonic, p.method)]
        else:
            lo, hi = _range(range_) if range_ else p.method.harmonic_range
            scores = harmonic_profile(lons, p.method, lo, hi)
        if top:
            scores = sorted(scores, key=lambda s: (-s.score1, -s.score2))[:top]
        data = {
            "chart": model.name,
            "pack": p.name,
            "orb": p.method.pattern_orb,
            "harmonics": [s.to_dict() for s in scores],
        }

        def render(c: Console) -> None:
            title = f"[bold]{escape(model.name or 'Chart')}[/] · {escape(p.label)}"
            c.print(f"{title} · patterns within {p.method.pattern_orb:g}° in the harmonic chart")
            for s in scores:
                if not s.patterns and not top:
                    continue
                c.print(
                    f"  [bold {rgb('accent')}]H{s.harmonic:<3}[/] 4-body patterns {s.score1} · weighted {s.score2:.1f}"
                )
                for pat in s.patterns:
                    names = " · ".join(name_of(b) for b in pat.bodies)
                    c.print(
                        f"       {names}  [{rgb('dim')}]span {pat.span:.2f}° ({pat.span / s.harmonic:.2f}° natal)[/]"
                    )

        out(ctx).emit(data, render)
