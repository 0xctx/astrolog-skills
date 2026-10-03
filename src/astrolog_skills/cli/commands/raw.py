"""`astro raw -- <switches>` — any Astrolog feature, with your profile (and optional chart) applied."""

from __future__ import annotations

import sys

import typer

from astrolog_skills.cli.app import out
from astrolog_skills.cli.birth import moment_from_options
from astrolog_skills.engine.raw import raw
from astrolog_skills.packs.settings import chart_profile


def register(app: typer.Typer) -> None:
    @app.command(
        "raw",
        help="Run Astrolog directly: astro raw [chart options] -- <astrolog switches>. Your profile's settings "
        "are applied first; your switches come last and win.",
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )
    def raw_cmd(
        ctx: typer.Context,
        date: str = typer.Option(None, "--date", help="Local date, YYYY-MM-DD."),
        time: str = typer.Option(None, "--time", help="Local clock time, HH:MM[:SS]."),
        chart: str = typer.Option(None, "--chart", help="A saved chart."),
        place: str = typer.Option(None, "--place", help='Birthplace, e.g. "Ulm, Germany".'),
        tz: str = typer.Option(None, "--tz", help="IANA zone, offset, UTC, or LMT."),
        at: str = typer.Option(None, "--at", help='Coordinates, e.g. "48N24 10E00".'),
        lat: float = typer.Option(None, "--lat"),
        lon: float = typer.Option(None, "--lon"),
        profile: str = typer.Option(None, "--profile", help="Settings profile (default: the active one)."),
    ) -> None:
        has_chart = any(v is not None for v in (chart, date, time, place, tz, at, lat, lon))
        moment = (
            moment_from_options(chart=chart, date=date, time=time, tz=tz, place=place, at=at, lat=lat, lon=lon)[0]
            if has_chart
            else None
        )
        switches = [a for a in ctx.args if a != "--"]
        argv, done = raw(switches, moment, chart_profile(profile))
        o = out(ctx)
        if o.is_json:
            o.emit({"argv": argv, "returncode": done.returncode, "stdout": done.stdout, "stderr": done.stderr})
        else:
            sys.stdout.write(done.stdout)
            if done.stderr.strip():
                sys.stderr.write(done.stderr)
        if done.returncode:
            raise typer.Exit(done.returncode)
