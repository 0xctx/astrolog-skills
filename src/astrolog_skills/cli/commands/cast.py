"""`astro cast` — calculate a chart from birth data (saved charts arrive with `astro chart`)."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from astrolog_skills.cli.app import out
from astrolog_skills.cli.birth import moment_from_options
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.zodiac import element_of, format_position
from astrolog_skills.packs.settings import chart_profile
from astrolog_skills.ui import rgb


def render_chart(c: Console, chart: ChartModel) -> None:
    m = chart.moment
    title = chart.name or "Chart"
    c.print(
        f"\n[bold {rgb('gold')}]{escape(title)}[/]  [{rgb('dim')}]{m['date']} {m['time']} {escape(m['tz'])} "
        f"→ {m['utc'][:19].replace('T', ' ')} UT · {m['lat']:.4f}, {m['lon']:.4f}[/]"
    )
    c.print(
        f"[{rgb('dim')}]{chart.profile['name']}: {chart.profile['zodiac']}"
        f"{' · ' + chart.profile['ayanamsa'] if chart.profile.get('ayanamsa') else ''} · "
        f"{chart.profile['houses']} · {chart.profile['node']} node[/]\n"
    )
    table = Table(box=None, padding=(0, 1), show_header=True, header_style=rgb("dim"))
    for col, justify in (
        ("", "left"),
        ("", "left"),
        ("position", "left"),
        ("", "left"),
        ("house", "right"),
        ("speed", "right"),
    ):
        table.add_column(col, justify=justify)  # type: ignore[arg-type]
    for p in chart.points:
        colour = rgb(element_of(p.lon))
        table.add_row(
            f"[{colour}]{p.glyph}[/]",
            f"[bold]{p.name}[/]",
            f"[{colour}]{p.text}[/]",
            f"[{rgb('bad')}]℞[/]" if p.retrograde else "",
            str(p.house or ""),
            f"[{rgb('dim')}]{p.speed:+.4f}[/]",
        )
    c.print(table)
    a = chart.angles
    asc, mc = format_position(a["asc"], True), format_position(a["mc"], True)
    c.print(f"\n [{rgb('accent')}]ASC[/] {asc}   [{rgb('accent')}]MC[/] {mc}")
    for w in m.get("warnings", []):
        c.print(f" [{rgb('warn')}]![/] [{rgb('dim')}]{escape(w)}[/]")
    c.print()


def register(app: typer.Typer) -> None:
    @app.command("cast", help='Calculate a chart: --chart NAME, or --date --time --place "City, Country".')
    def cast_cmd(
        ctx: typer.Context,
        chart: str = typer.Option(None, "--chart", help="A saved chart (astro chart list)."),
        date: str = typer.Option(None, "--date", help="Local date, YYYY-MM-DD."),
        time: str = typer.Option(None, "--time", help="Local clock time, HH:MM or HH:MM:SS (24h)."),
        place: str = typer.Option(
            None, "--place", help='Birthplace, e.g. "Ulm, Germany" (gives coordinates and zone).'
        ),
        tz: str = typer.Option(None, "--tz", help="IANA zone (Europe/Berlin), offset (+01:00), UTC or LMT."),
        at: str = typer.Option(None, "--at", help='Coordinates, e.g. "48N24 10E00" or "48.4, 10.0".'),
        lat: float = typer.Option(None, "--lat", help="Latitude, north positive."),
        lon: float = typer.Option(None, "--lon", help="Longitude, east positive."),
        name: str = typer.Option("", "--name", help="Name for the chart."),
        profile: str = typer.Option(None, "--profile", help="Settings profile (default: the active one)."),
        now: bool = typer.Option(False, "--now", help="Chart for this moment (your location, or --place)."),
    ) -> None:
        moment, notes = moment_from_options(
            chart=chart, date=date, time=time, tz=tz, place=place, at=at, lat=lat, lon=lon, name=name, now=now
        )
        moment.warnings.extend(notes)
        chart_model = cast(moment, chart_profile(profile))
        out(ctx).emit(chart_model.to_dict(), lambda c: render_chart(c, chart_model))
