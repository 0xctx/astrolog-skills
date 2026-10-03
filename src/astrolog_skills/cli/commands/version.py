"""`astro version`."""

import typer
from rich.console import Console

from astrolog_skills import __version__
from astrolog_skills.cli.app import out
from astrolog_skills.ui import rgb


def register(app: typer.Typer) -> None:
    @app.command("version", help="Show the astrolog-skills version.")
    def version(ctx: typer.Context) -> None:
        def render(c: Console) -> None:
            c.print(f"[{rgb('accent')}]✦[/] astrolog-skills [bold]{__version__}[/]")

        out(ctx).emit({"version": __version__}, render)
