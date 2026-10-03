"""`astro config …` — view and change settings in ~/.astrolog-skills/config.toml."""

from __future__ import annotations

import typer
from rich.console import Console

from astrolog_skills import config
from astrolog_skills.cli.app import out
from astrolog_skills.paths import config_path
from astrolog_skills.ui import rgb


def _show(c: Console, cfg: dict[str, object], prefix: str = "") -> None:
    for key, value in cfg.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            _show(c, value, f"{name}.")
        else:
            shown = "[dim](not set)[/]" if value in (None, "") else f"[bold]{value}[/]"
            c.print(f"  [{rgb('accent')}]{name:<26}[/] {shown}")


def register(app: typer.Typer) -> None:
    cfg_app = typer.Typer(help="View and change settings.", no_args_is_help=True)
    app.add_typer(cfg_app, name="config")

    @cfg_app.command("show", help="Show all settings.")
    def show(ctx: typer.Context) -> None:
        cfg = config.load()

        def render(c: Console) -> None:
            c.print(f"[dim]{config_path()}[/]")
            _show(c, cfg)

        out(ctx).emit(cfg, render)

    @cfg_app.command("path", help="Print where the config file lives.")
    def path(ctx: typer.Context) -> None:
        out(ctx).emit({"path": str(config_path())}, lambda c: c.print(str(config_path())))

    @cfg_app.command("get", help="Print one setting, e.g. display.width.")
    def get(ctx: typer.Context, key: str) -> None:
        value = config.get(key)
        out(ctx).emit({"key": key, "value": value}, lambda c: c.print(str(value)))

    @cfg_app.command(
        "set",
        help='Change a setting. For your location: [bold]astro config set location "48N24 10E00" --name Ulm[/]',
    )
    def set_(
        ctx: typer.Context,
        key: str,
        value: str,
        name: str = typer.Option("", "--name", help="Place name (location only)."),
    ) -> None:
        if key == "location":
            cfg = config.set_location(value, name)
            loc = cfg["defaults"]["location"]
            label = f" ({loc['name']})" if loc["name"] else ""
            out(ctx).emit(
                {"ok": True, "location": loc},
                lambda c: c.print(
                    f"[{rgb('ok')}]✓[/] location set to [bold]{loc['lat']:.4f}, {loc['lon']:.4f}[/]{label}"
                ),
            )
            return
        config.set_value(key, value)
        new = config.get(key)
        out(ctx).emit(
            {"ok": True, "key": key, "value": new},
            lambda c: c.print(f"[{rgb('ok')}]✓[/] {key} = [bold]{new}[/]"),
        )
