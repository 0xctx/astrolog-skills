"""`astro export html` — one self-contained, interactive HTML chart."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markup import escape

from astrolog_skills import config
from astrolog_skills.analysis.doctrine.explain import attach_notes, without_citations
from astrolog_skills.charts import store
from astrolog_skills.charts.store import slug
from astrolog_skills.cli.app import out
from astrolog_skills.cli.birth import moment_from_options
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.errors import AstroError
from astrolog_skills.export import html
from astrolog_skills.export import notes as reading_notes
from astrolog_skills.packs.settings import citations, resolve, with_midpoints
from astrolog_skills.paths import data_dir
from astrolog_skills.render import theme as themes
from astrolog_skills.ui import rgb


def _reading(path: str | None, model: ChartModel, pack: str) -> dict[str, str] | None:
    """The reading to show in the page: the file named, or the newest one saved for this chart and pack."""
    from pathlib import Path

    if path:
        file = Path(path).expanduser()
        if not file.is_file():
            raise AstroError(f"No reading at {file}.", fix="give the path of a saved Markdown reading")
    else:
        who = slug(model.name) if model.name else "chart"
        found = sorted((data_dir() / "exports").glob(f"{who}-{pack}-*.md"))
        if not found:
            return None
        file = found[-1]
    return {"name": file.name, "text": file.read_text(encoding="utf-8")}


def register(app: typer.Typer) -> None:
    export_app = typer.Typer(help="Export charts: interactive HTML.", no_args_is_help=True)
    app.add_typer(export_app, name="export")

    @export_app.command("html", help="Write one self-contained interactive HTML chart (works offline; can be emailed).")
    def html_cmd(
        ctx: typer.Context,
        chart: str = typer.Option(None, "--chart", help="A saved chart."),
        date: str = typer.Option(None, "--date"),
        time: str = typer.Option(None, "--time"),
        place: str = typer.Option(None, "--place"),
        tz: str = typer.Option(None, "--tz"),
        at: str = typer.Option(None, "--at"),
        name: str = typer.Option("", "--name"),
        now: bool = typer.Option(False, "--now"),
        harmonic: int = typer.Option(None, "--harmonic", "-H", help="Just one harmonic chart, e.g. 7."),
        harmonics: str = typer.Option(
            None,
            "--harmonics",
            help="Harmonics to step through: 1-12, 1,5,7,11 or 1-12,16 (default: the pack's range).",
        ),
        pack: str = typer.Option(None, "--pack", help="Tradition pack (default: your profile's)."),
        profile: str = typer.Option(None, "--profile"),
        theme: str = typer.Option(None, "--theme", help="Colour theme (default: display.theme)."),
        preset: str = typer.Option("default", "--preset", help="HTML design (yours in ~/.astrolog-skills/presets)."),
        out_: str = typer.Option(None, "--out", help="Where to write it (default: ~/.astrolog-skills/exports/)."),
        interp: bool = typer.Option(
            False, "--interp", help="Add the reading's interpretation to each hover (off: the aspect title only)."
        ),
        notes: str = typer.Option(None, "--notes", help="A notes file other than the saved one (implies --interp)."),
        reading: str = typer.Option(
            None, "--reading", help="A written reading (Markdown) for the Reading tab (default: the newest saved one)."
        ),
        midpoints: str = typer.Option(
            None, "--midpoints", help="Midpoint lists by the old or new method (default: the pack's)."
        ),
    ) -> None:
        from pathlib import Path

        moment, _ = moment_from_options(
            chart=chart, date=date, time=time, place=place, tz=tz, at=at, name=name, now=now
        )
        prof, tradition = resolve(profile, pack)
        tradition = with_midpoints(tradition, midpoints)
        model = cast(moment, prof)
        # the page's title line shows the place by name when we know it (a saved chart or --place)
        model.moment["place"] = store.load(chart).place if chart else (place or "")
        th = themes.load(theme or str(config.get("display.theme")))
        natal_orbs = config.get("display.orbs") == "natal"
        if harmonic is not None and harmonics:
            raise AstroError("Use --harmonic (one chart) or --harmonics (several), not both.")
        highest = 10_000  # any harmonic is just longitude × H; the pack's harmonics.max is for research sweeps
        if harmonics:
            chosen = html.parse_harmonics(harmonics, highest)
        elif harmonic is not None:
            chosen = html.parse_harmonics(str(harmonic), highest)
        else:
            lo, hi = tradition.method.harmonic_range
            chosen = list(range(lo, hi + 1))
        interp = interp or bool(notes)  # naming a notes file means you want the notes shown
        notes_file = Path(notes).expanduser() if notes else reading_notes.notes_path(model, tradition.name)
        if notes and not notes_file.is_file():
            raise AstroError(f"No notes file at {notes_file}.")
        written = reading_notes.load(notes_file) if interp and notes_file.is_file() else {}
        data = html.payload(model, tradition, th, chosen, natal_orbs)
        data["notes"] = written
        data["interp"] = interp
        from astrolog_skills.cli.commands.doctrine import study_for

        data["study"] = study_for(moment, model, tradition, prof)
        if data["study"] is not None and notes_file.is_file():
            # the doctrine panels show the reading's interpretation whenever it exists; aspect rows keep --interp
            attach_notes(data["study"], reading_notes.load(notes_file))
        if data["study"] is not None and not citations():
            data["study"] = without_citations(data["study"])
        data["reading"] = _reading(reading, model, tradition.name)
        data["reading_on"] = reading_notes.reading_date(notes_file) if notes_file.is_file() else None
        target = Path(out_).expanduser() if out_ else html.export_path(model, chosen)
        path = html.write(html.render(data, preset), target)
        size = path.stat().st_size
        # a high harmonic magnifies birth-time error: how far does one minute move the Moon?
        moon = next((p for p in model.points if p.key == "moon"), None)
        drift = abs(moon.speed) * max(chosen) / 1440 if moon else 0.0
        warnings = (
            [
                f"at H{max(chosen)} one minute of birth time moves the Moon about {drift:.1f}°"
                " — only as exact as the time"
            ]
            if drift >= 1
            else []
        )

        def render(c: Console) -> None:
            c.print(
                f"[{rgb('ok')}]✓[/] wrote [bold]{escape(str(path))}[/] ({size / 1024:.0f} KB, works offline)",
                soft_wrap=True,
            )
            c.print(
                f'  [{rgb("dim")}]open it in a browser — e.g. xdg-open / open / start "{escape(str(path))}"[/]',
                soft_wrap=True,
            )
            if written:
                c.print(f"  [{rgb('dim')}]with {len(written)} interpretations on hover[/]", soft_wrap=True)
            elif interp:
                tip = "no reading notes for this chart and pack yet — ask Claude for a reading with notes"
                c.print(f"  [{rgb('dim')}]{tip}[/]", soft_wrap=True)
            for note in warnings:
                c.print(f"  [{rgb('warn')}]{escape(note)}[/]", soft_wrap=True)

        data_out = {
            "ok": True,
            "path": str(path),
            "bytes": size,
            "preset": preset,
            "harmonics": chosen,
            "notes": warnings,
            "reading_notes": len(written),
        }
        out(ctx).emit(data_out, render)
