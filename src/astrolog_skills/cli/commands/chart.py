"""`astro chart …` — save charts by name and use them everywhere (`--chart NAME`)."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markup import escape

from astrolog_skills.charts import store
from astrolog_skills.cli.app import out
from astrolog_skills.cli.commands.cast import render_chart
from astrolog_skills.engine.cast import cast
from astrolog_skills.packs.settings import chart_profile
from astrolog_skills.ui import rgb


def register(app: typer.Typer) -> None:
    chart_app = typer.Typer(help="Saved charts: add, list, show, remove.", no_args_is_help=True)
    app.add_typer(chart_app, name="chart")

    @chart_app.command(
        "add", help='Save a chart: astro chart add "Anna" --date 1990-05-01 --time 14:20 --place "Paris, France".'
    )
    def add(
        ctx: typer.Context,
        name: str = typer.Argument(..., help="Name to save it under."),
        date: str = typer.Option(..., "--date", help="Local date, YYYY-MM-DD."),
        time: str = typer.Option(..., "--time", help="Local clock time, HH:MM[:SS] (24h)."),
        place: str = typer.Option(None, "--place", help='Birthplace, e.g. "Ulm, Germany".'),
        tz: str = typer.Option(None, "--tz", help="Time zone if not from the place: IANA, offset, UTC or LMT."),
        at: str = typer.Option(None, "--at", help='Coordinates instead of a place, e.g. "48N24 10E00".'),
        rating: str = typer.Option("", "--rating", help="Rodden rating: AA, A, B, C, DD, X, XX."),
        sex: str = typer.Option("", "--sex", help="male or female — only some traditional lots use it."),
        tag: list[str] = typer.Option([], "--tag", help="Tags (repeatable), e.g. --tag client --tag family."),
        source: str = typer.Option("", "--source", help="Where the birth data came from."),
        notes: str = typer.Option("", "--notes", help="Anything else worth keeping."),
        replace: bool = typer.Option(False, "--replace", help="Overwrite a chart with the same name."),
    ) -> None:
        from astrolog_skills import config

        lat = lon = None
        if at:
            lat, lon = config.parse_location(at)
        record, looked_up = store.build(
            name,
            date,
            time,
            tz=tz,
            place=place,
            lat=lat,
            lon=lon,
            rating=rating,
            tags=tag,
            source=source,
            notes=notes,
            sex=sex,
        )
        path = store.save(record, overwrite=replace)

        where = record.place or f"{record.lat:.4f}, {record.lon:.4f}"

        def render(c: Console) -> None:
            c.print(
                f"[{rgb('ok')}]✓[/] saved [bold]{escape(record.name)}[/] — {record.date} {record.time} "
                f"{escape(record.tz)} · {escape(where)}"
            )
            for note in looked_up:
                c.print(f"  [{rgb('dim')}]{escape(note)}[/]")
            c.print(f"  [{rgb('dim')}]see it: astro chart show {escape(record.name)!r}[/]")

        out(ctx).emit({"ok": True, "chart": record.to_dict(), "path": str(path), "notes": looked_up}, render)

    @chart_app.command("list", help="List saved charts.")
    def list_(ctx: typer.Context, tag: str = typer.Option(None, "--tag", help="Only charts with this tag.")) -> None:
        records = [r for r in store.list_charts() if not tag or tag in r.tags]

        def render(c: Console) -> None:
            if not records:
                c.print(f"[{rgb('dim')}]No saved charts yet — add one with `astro chart add`.[/]")
            for r in records:
                rating = f" [{rgb('gold')}]{r.rating}[/]" if r.rating else ""
                tags = f" [{rgb('dim')}]#{' #'.join(r.tags)}[/]" if r.tags else ""
                c.print(f"  [bold]{escape(r.name):<28}[/] {r.date} {r.time:<8} {escape(r.place)}{rating}{tags}")

        out(ctx).emit({"charts": [r.to_dict() for r in records]}, render)

    @chart_app.command("show", help="Calculate and show a saved chart.")
    def show(
        ctx: typer.Context,
        name: str,
        profile: str = typer.Option(None, "--profile", help="Settings profile (default: the active one)."),
    ) -> None:
        record = store.load(name)
        model = cast(record.moment(), chart_profile(profile))
        out(ctx).emit({**model.to_dict(), "record": record.to_dict()}, lambda c: render_chart(c, model))

    @chart_app.command("rm", help="Delete a saved chart.")
    def rm(ctx: typer.Context, name: str) -> None:
        path = store.remove(name)
        out(ctx).emit(
            {"ok": True, "removed": str(path)}, lambda c: c.print(f"[{rgb('ok')}]✓[/] removed {escape(name)}")
        )
