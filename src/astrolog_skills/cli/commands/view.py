"""`astro view` — the chart (and optional aspect list or grid, balance, patterns, positions) in colour."""

from __future__ import annotations

import sys

import typer
from rich.console import Console

from astrolog_skills import config
from astrolog_skills.analysis.doctrine.explain import attach_notes, without_citations
from astrolog_skills.analysis.midpoints import midpoint_contacts
from astrolog_skills.cli.app import out
from astrolog_skills.cli.birth import moment_from_options
from astrolog_skills.cli.commands.transits import transit_moment
from astrolog_skills.engine.cast import cast
from astrolog_skills.export import notes as reading_notes
from astrolog_skills.export.notes import notes_path
from astrolog_skills.packs.settings import citations, resolve, with_midpoints
from astrolog_skills.render import compose
from astrolog_skills.render import theme as themes
from astrolog_skills.render.views.common import ViewData
from astrolog_skills.ui import rgb


def register(app: typer.Typer) -> None:
    @app.command("view", help="See a chart in colour. --show chart,aspects,grid,balance,patterns,positions (or all).")
    def view_cmd(
        ctx: typer.Context,
        chart: str = typer.Option(None, "--chart", help="A saved chart."),
        date: str = typer.Option(None, "--date", help="Local date, YYYY-MM-DD."),
        time: str = typer.Option(None, "--time", help="Local clock time, HH:MM[:SS]."),
        place: str = typer.Option(None, "--place", help='Birthplace, e.g. "Ulm, Germany".'),
        tz: str = typer.Option(None, "--tz", help="IANA zone, offset, UTC or LMT."),
        at: str = typer.Option(None, "--at", help='Coordinates, e.g. "48N24 10E00".'),
        name: str = typer.Option("", "--name", help="Name to show."),
        now: bool = typer.Option(False, "--now", help="The sky right now."),
        show: str = typer.Option(
            "chart",
            "--show",
            help="Views: chart, aspects, grid, balance, patterns, positions or all; aspects:2 = its page 2.",
        ),
        harmonic: int = typer.Option(1, "--harmonic", "-H", help="Show harmonic chart H."),
        pack: str = typer.Option(None, "--pack", help="Tradition pack (default: your profile's)."),
        profile: str = typer.Option(None, "--profile", help="Settings profile (default: the active one)."),
        theme: str = typer.Option(None, "--theme", help="Terminal theme (default: display.theme)."),
        letters: bool = typer.Option(False, "--letters", help="Letters instead of astrology symbols."),
        transits: str = typer.Option(None, "--transits", help="Add transits for a date (YYYY-MM-DD) or 'now'."),
        midpoints: str = typer.Option(
            None, "--midpoints", help="Midpoint lists by the old or new method (default: the pack's)."
        ),
    ) -> None:
        o = out(ctx)
        moment, notes = moment_from_options(
            chart=chart, date=date, time=time, place=place, tz=tz, at=at, name=name, now=now
        )
        prof, tradition = resolve(profile, pack)
        tradition = with_midpoints(tradition, midpoints)
        model = cast(moment, prof)
        transit_chart = cast(transit_moment(transits, model), prof) if transits else None
        natal_orbs = config.get("display.orbs") == "natal"
        data = ViewData.build(model, tradition, harmonic, transit_chart, natal_orbs)
        if transits and "transits" not in show:
            show = f"{show},transits"
        names = compose.parse_views(show)
        if any(n.partition(":")[0] in compose.STUDY_VIEWS for n in names):
            from astrolog_skills.cli.commands.doctrine import study_for

            data.study = study_for(moment, model, data.pack, prof)
            notes_file = notes_path(model, data.pack.name)
            if data.study is not None and notes_file.is_file():
                attach_notes(data.study, reading_notes.load(notes_file))
            if data.study is not None and not citations():
                data.study = without_citations(data.study)
        if o.is_json:
            o.emit(
                {
                    "chart": model.to_dict(),
                    "harmonic": harmonic,
                    "pack": data.pack.name,
                    "views": names,
                    "aspects": [a.to_dict() for a in data.aspects],
                    "patterns": data.patterns.to_dict(),
                    "midpoints": {
                        k: [c.to_dict() for c in v]
                        for k, v in midpoint_contacts(data.natal, data.pack.method, harmonic).items()
                        if v
                    },
                    "notes": notes,
                }
            )
            return
        th = themes.load(theme or str(config.get("display.theme")))
        if letters or not config.get("display.glyphs"):
            th = th.with_letters()
        width = max(80, min(int(ctx.find_root().params.get("width") or config.get("display.width")), 160))
        if o.mode == "plain":
            o.console.print(compose.compose(data, th, names, width).plain(), markup=False, highlight=False)
            return
        if sys.stdout.isatty():  # a real terminal scrolls: no need to split anything
            sys.stdout.write(compose.compose(data, th, names, width).render() + "\n")
            return
        # Claude Code's `!` cuts output off near 30,000 characters: show what fits, then say how to see the rest
        text, left_out = compose.render_within_budget(data, th, names, width)
        sys.stdout.write(text + "\n")
        if left_out:
            c: Console = o.console
            again = f"--show {','.join(left_out)}"
            c.print(f"[{rgb('dim')}]… more to see — run the same command with [bold]{again}[/bold][/]", soft_wrap=True)
