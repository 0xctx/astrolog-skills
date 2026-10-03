"""`astro doctor` — health check with a first-light card."""

from __future__ import annotations

from typing import Any

import typer
from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from astrolog_skills import doctor
from astrolog_skills.cli.app import out
from astrolog_skills.ui import rgb

ICONS = {
    "ok": ("✓", "ok"),
    "warn": ("!", "warn"),
    "fail": ("✗", "bad"),
    "info": ("·", "dim"),
    "skip": ("–", "dim"),
}


def first_light_panel(fl: dict[str, Any]) -> Panel:
    def body(glyph: str, label: str, part: dict[str, Any], extra: str = "") -> Text:
        line = Text()
        line.append(f" {glyph} ", style=f"bold {rgb(part['element'])}")
        line.append(f"{label:<7}", style=f"bold {rgb('text')}")
        line.append(part["text"], style=f"bold {rgb(part['element'])}")
        if extra:
            line.append(f"  · {extra}", style=rgb("dim"))
        return line

    moon = fl["moon"]
    lines: list[Text] = [
        body("☉", "Sun", fl["sun"]),
        body("☽", "Moon", moon, f"{moon['phase'].lower()} · {round(moon['illumination'] * 100)}% lit"),
    ]
    if fl.get("rising"):
        lines.append(body("↑", "Rising", fl["rising"]))
    else:
        lines.append(Text.from_markup(f"[{rgb('dim')}] ↑ Rising set your location to see it:[/]"))
        lines.append(Text.from_markup(f'[{rgb("accent")}]   astro config set location "48N24 10E00" --name Ulm[/]'))
    lines.append(Text(""))
    lines.append(
        Text.from_markup(f" [italic {rgb('dim')}]Try: “show my chart” — or ask Claude anything about the sky.[/]")
    )
    return Panel(
        Group(*lines),
        title=f"[bold {rgb('gold')}]✦ first light ✦[/]",
        subtitle=f"[{rgb('dim')}]{fl['time_utc']}[/]",
        border_style=rgb("accent"),
        padding=(1, 2),
        expand=False,
    )


def render(c: Console, report: doctor.DoctorReport) -> None:
    c.print()
    c.rule(f"[bold {rgb('accent')}]✦ astrolog-skills doctor ✦[/]", style=rgb("dim"))
    c.print()
    # A grid keeps wrapped details and fixes indented under their own check.
    grid = Table.grid(padding=(0, 1))
    grid.add_column(width=1)  # margin
    grid.add_column(width=1)  # icon
    grid.add_column(width=16, no_wrap=True)  # title
    grid.add_column(ratio=1, overflow="fold")  # detail / fix
    for r in report.checks:
        icon, colour = ICONS[r.status]
        title_style = "bold" if r.status != "skip" else rgb("dim")
        grid.add_row(
            "", f"[bold {rgb(colour)}]{icon}[/]", f"[{title_style}]{r.title}[/]", f"[{rgb('dim')}]{escape(r.detail)}[/]"
        )
        if r.fix:
            grid.add_row("", "", "", f"[{rgb('accent')}]→[/] {escape(r.fix)}")
    c.print(grid)
    c.print()
    problems = sum(r.status == "fail" for r in report.checks)
    if report.ok:
        c.print(f"  [bold {rgb('ok')}]All good — the sky is yours.[/]")
    else:
        word = "problem" if problems == 1 else "problems"
        c.print(f"  [bold {rgb('bad')}]{problems} {word}[/] — follow the [{rgb('accent')}]→[/] fixes above.")
    if report.first_light:
        c.print()
        c.print(first_light_panel(report.first_light))
    c.print()


def register(app: typer.Typer) -> None:
    @app.command("doctor", help="Check that everything works — and see the sky right now.")
    def doctor_cmd(
        ctx: typer.Context,
        no_first_light: bool = typer.Option(False, "--no-first-light", help="Skip the current-sky card."),
    ) -> None:
        report = doctor.run_all(with_first_light=not no_first_light)
        out(ctx).emit(report.to_dict(), lambda c: render(c, report))
        if not report.ok:
            raise typer.Exit(1)
