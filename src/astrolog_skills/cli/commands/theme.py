"""`astro theme …` — terminal colour themes."""

from __future__ import annotations

from typing import Any

import typer
from rich.console import Console
from rich.markup import escape

from astrolog_skills import config
from astrolog_skills.cli.app import out
from astrolog_skills.render import theme as themes
from astrolog_skills.ui import rgb


def register(app: typer.Typer) -> None:
    theme_app = typer.Typer(help="Terminal colour themes.", no_args_is_help=True)
    app.add_typer(theme_app, name="theme")

    @theme_app.command("list", help="List themes (yours replace built-ins with the same name).")
    def list_(ctx: typer.Context) -> None:
        active = str(config.get("display.theme"))
        mine = str(themes.user_dir())
        rows: list[dict[str, Any]] = [
            {"name": n, "label": themes.load(n).label, "active": n == active, "user": str(p).startswith(mine)}
            for n, p in themes.list_themes().items()
        ]

        def render(c: Console) -> None:
            for r in rows:
                mark = f"[bold {rgb('ok')}]●[/]" if r["active"] else " "
                c.print(
                    f" {mark} [bold]{r['name']:<16}[/] {escape(r['label'])}"
                    + ("  [dim](yours)[/]" if r["user"] else "")
                )

        out(ctx).emit({"active": active, "themes": rows}, render)

    @theme_app.command("copy", help="Copy a theme to edit its colours.")
    def copy(ctx: typer.Context, name: str, as_: str = typer.Option(None, "--as", help="New name.")) -> None:
        target = themes.copy_to_user(name, as_)
        message = f"[{rgb('ok')}]✓[/] copied to {escape(str(target))} — then: astro view --theme {target.stem}"
        out(ctx).emit({"ok": True, "path": str(target)}, lambda c: c.print(message))

    @theme_app.command("use", help="Make a theme the default.")
    def use(ctx: typer.Context, name: str) -> None:
        themes.load(name)
        config.set_value("display.theme", name)
        out(ctx).emit(
            {"ok": True, "active": name}, lambda c: c.print(f"[{rgb('ok')}]✓[/] now using theme [bold]{name}[/]")
        )
