"""`astro notes …` — reading notes: plain-language snippets per contact, shown on hover in the HTML chart."""

from __future__ import annotations

from datetime import date
from typing import Any

import typer
from rich.console import Console
from rich.markup import escape

from astrolog_skills.analysis.doctrine.explain import study_contacts, study_items
from astrolog_skills.cli.app import out
from astrolog_skills.cli.birth import moment_from_options
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.export import html
from astrolog_skills.export import notes as reading_notes
from astrolog_skills.packs import meanings
from astrolog_skills.packs.loader import Pack
from astrolog_skills.packs.settings import resolve
from astrolog_skills.ui import rgb


def register(app: typer.Typer) -> None:
    notes_app = typer.Typer(help="Reading notes for the HTML chart's hover snippets.", no_args_is_help=True)
    app.add_typer(notes_app, name="notes")

    def _setup(
        chart: str, pack: str | None, profile: str | None, harmonics: str
    ) -> tuple[ChartModel, Pack, list[int], dict[str, Any] | None]:
        from astrolog_skills.cli.commands.doctrine import study_for

        moment, _ = moment_from_options(chart=chart)
        prof, tradition = resolve(profile, pack)
        model = cast(moment, prof)
        chosen = html.parse_harmonics(harmonics, 10_000)
        return model, tradition, chosen, study_for(moment, model, tradition, prof)

    def _study_keys(study: dict[str, Any] | None, on: str | None) -> tuple[list[dict[str, Any]], set[str]]:
        """(the study keys to list, every study key that exists)"""
        if study is None:
            return [], set()
        listed = study_contacts(study, on or date.today().isoformat())
        return listed, {i["note_key"] for i in study_items(study)}

    @notes_app.command("keys", help="Every contact at these harmonics, with its note key and a plain label (JSON).")
    def keys_cmd(
        ctx: typer.Context,
        chart: str = typer.Option(..., "--chart", help="A saved chart."),
        pack: str = typer.Option(None, "--pack", help="Tradition pack (default: your profile's)."),
        profile: str = typer.Option(None, "--profile"),
        harmonics: str = typer.Option("1", "--harmonics", help="The harmonics you'll export, e.g. 1,5,7,11."),
        on: str = typer.Option(None, "--on", help="Date for the timeline keys (profection years, releasing periods)."),
    ) -> None:
        model, tradition, chosen, study = _setup(chart, pack, profile, harmonics)
        found = reading_notes.contacts(model, tradition.method, chosen) + _study_keys(study, on)[0]
        path = reading_notes.notes_path(model, tradition.name)
        data = {"path": str(path), "chart": model.name, "pack": tradition.name, "harmonics": chosen, "contacts": found}

        def render(c: Console) -> None:
            c.print(f"{len(found)} contacts · write notes to [bold]{escape(str(path))}[/] (use --json for the list)")

        out(ctx).emit(data, render)

    @notes_app.command("check", help="How complete a notes file is: written, missing tight contacts, unknown keys.")
    def check_cmd(
        ctx: typer.Context,
        chart: str = typer.Option(..., "--chart", help="A saved chart."),
        pack: str = typer.Option(None, "--pack", help="Tradition pack (default: your profile's)."),
        profile: str = typer.Option(None, "--profile"),
        harmonics: str = typer.Option("1", "--harmonics", help="The harmonics you'll export, e.g. 1,5,7,11."),
        on: str = typer.Option(None, "--on", help="Date for the timeline keys (profection years, releasing periods)."),
    ) -> None:
        model, tradition, chosen, study = _setup(chart, pack, profile, harmonics)
        path = reading_notes.notes_path(model, tradition.name)
        defined = set(meanings.load(tradition.file("meanings.md"))["bodies"])
        listed, every = _study_keys(study, on)
        known = reading_notes.contacts(model, tradition.method, chosen) + listed
        report = reading_notes.check(reading_notes.load(path), known, defined, also_valid=every)
        data = {"path": str(path), **report}

        def render(c: Console) -> None:
            aspects, mids = len(report["missing_tight_aspects"]), len(report["missing_tight_midpoints"])
            gaps = f"{aspects} tight aspects, {mids} tight midpoints"
            c.print(f"[{rgb('ok')}]{report['written']}[/] notes · without one: {gaps}")
            if report["no_meanings_in_pack"]:
                c.print(
                    f"  [{rgb('dim')}]{report['no_meanings_in_pack']} more involve bodies the pack gives no meaning[/]"
                )
            if report["missing_study"]:
                c.print(
                    f"  [{rgb('warn')}]{len(report['missing_study'])} doctrine items without a note[/] (see --json)"
                )
            for k in report["unknown_keys"]:
                c.print(f"  [{rgb('warn')}]unknown key[/] {escape(k)}")
            for k in report["too_long"]:
                c.print(f"  [{rgb('warn')}]too long[/] {escape(k)}")

        out(ctx).emit(data, render)
