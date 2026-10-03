"""`astro place "Ulm, Germany"` — look up coordinates and time zone in Astrolog's atlas."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markup import escape

from astrolog_skills import places
from astrolog_skills.cli.app import out
from astrolog_skills.ui import rgb


def register(app: typer.Typer) -> None:
    @app.command("place", help='Find a place: coordinates and time zone. Add a country or state: "Ulm, Germany".')
    def place_cmd(
        ctx: typer.Context,
        query: str = typer.Argument(..., help='e.g. "Ulm, Germany", "Springfield, Illinois", "Zürich".'),
        limit: int = typer.Option(10, "--limit", help="How many candidates to list."),
    ) -> None:
        found = places.search(query, limit=limit)
        data = {"query": query, "places": [p.to_dict() for p in found]}

        def render(c: Console) -> None:
            if not found:
                c.print(f"[{rgb('warn')}]No place matches '{escape(query)}'.[/] Check the spelling or add the country.")
                return
            for p in found:
                ns, ew = ("N" if p.lat >= 0 else "S"), ("E" if p.lon >= 0 else "W")
                coords = f"{abs(p.lat):8.4f}{ns} {abs(p.lon):9.4f}{ew}"
                c.print(f"  [bold]{escape(p.label):<44}[/] {coords}  [{rgb('accent')}]{p.tz}[/]")

        out(ctx).emit(data, render)
