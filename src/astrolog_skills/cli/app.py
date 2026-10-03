"""The `astro` Typer app and its global options."""

from __future__ import annotations

import typer

from astrolog_skills.ui import Output, make_output

app = typer.Typer(
    name="astro",
    no_args_is_help=True,
    rich_markup_mode="rich",
    add_completion=False,
    pretty_exceptions_enable=False,
    help="✦ astrolog-skills — Astrolog in plain English. Run [bold]astro doctor[/] to begin.",
)


@app.callback()
def _global(
    ctx: typer.Context,
    plain: bool = typer.Option(False, "--plain", help="No colour — for reading by Claude or piping."),
    as_json: bool = typer.Option(False, "--json", help="One JSON document on stdout, nothing else."),
    width: int | None = typer.Option(None, "--width", help="Output width in columns (default from config)."),
    houses: str | None = typer.Option(None, "--houses", help="House system for this command, e.g. placidus."),
    zodiac: str | None = typer.Option(None, "--zodiac", help="tropical, or an ayanamsa (lahiri, fagan-bradley…)."),
    node: str | None = typer.Option(None, "--node", help="true or mean."),
    points: str | None = typer.Option(
        None, "--points", help="Objects: a list replaces them; +ceres adds, -pluto drops (comma-separated)."
    ),
    cite: bool = typer.Option(False, "--cite", help="Readings and pages cite the sources' page numbers."),
) -> None:
    if width is None and not as_json and not plain:  # config width shapes colour views; plain is for reading
        from astrolog_skills import config

        try:
            width = int(config.get("display.width"))
        except Exception:
            width = None
    ctx.obj = make_output(plain=plain, as_json=as_json, width=width)

    from astrolog_skills.engine.profile import chart_settings
    from astrolog_skills.packs import settings

    settings.set_flags(chart_settings(zodiac, houses, node, points, where="--houses/--zodiac/--node/--points"), cite)


def out(ctx: typer.Context) -> Output:
    """The Output configured by the global options (falls back to rich when called directly)."""
    obj = ctx.find_root().obj
    return obj if isinstance(obj, Output) else make_output()
