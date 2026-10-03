"""`astro profile …` — the settings (zodiac, ayanamsa, houses, points) every calculation uses."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.markup import escape

from astrolog_skills import config
from astrolog_skills.cli.app import out
from astrolog_skills.engine import profile as profiles
from astrolog_skills.ui import rgb


def register(app: typer.Typer) -> None:
    prof_app = typer.Typer(help="Settings profiles: zodiac, ayanamsa, house system, points.", no_args_is_help=True)
    app.add_typer(prof_app, name="profile")

    @prof_app.command("list", help="List profiles (yours replace built-ins with the same name).")
    def list_(ctx: typer.Context) -> None:
        current = profiles.active_name()
        rows = []
        for name, path in profiles.list_profiles().items():
            p = profiles.load(name)
            rows.append(
                {
                    "name": name,
                    "active": name == current,
                    "summary": p.summary(),
                    "description": p.description,
                    "user": str(path).startswith(str(profiles.user_dir())),
                    "path": str(path),
                }
            )

        def render(c: Console) -> None:
            for r in rows:
                mark = f"[bold {rgb('ok')}]●[/]" if r["active"] else " "
                origin = f"[{rgb('gold')}]yours[/]" if r["user"] else f"[{rgb('dim')}]built-in[/]"
                c.print(f" {mark} [bold]{r['name']:<16}[/] {r['summary']}  {origin}")
                if r["description"]:
                    c.print(f"   [{rgb('dim')}]{' ' * 16} {escape(str(r['description']))}[/]")

        out(ctx).emit({"active": current, "profiles": rows}, render)

    @prof_app.command("show", help="Show one profile in full (default: the active one).")
    def show(ctx: typer.Context, name: str = typer.Argument(None)) -> None:
        p = profiles.load(name) if name else profiles.active()
        data = {**p.to_dict(), "pins": profiles.pins(p)}

        def render(c: Console) -> None:
            c.print(f"[bold {rgb('accent')}]{p.name}[/] — {escape(p.description)}")
            for key in ("zodiac", "ayanamsa", "houses", "node", "pack", "theme"):
                if data.get(key) is not None:
                    c.print(f"  [{rgb('dim')}]{key:<9}[/] {data[key]}")
            c.print(f"  [{rgb('dim')}]objects  [/] {', '.join(data['objects'])}")
            c.print(f"  [{rgb('dim')}]file     [/] {escape(p.source)}")

        out(ctx).emit(data, render)

    @prof_app.command("use", help="Make a profile the default for everything.")
    def use(ctx: typer.Context, name: str) -> None:
        p = profiles.load(name)
        config.set_value("defaults.profile", name)
        out(ctx).emit(
            {"ok": True, "active": name, "summary": p.summary()},
            lambda c: c.print(f"[{rgb('ok')}]✓[/] now using [bold]{name}[/] — {p.summary()}"),
        )

    @prof_app.command("new", help="Copy a profile into your folder so you can edit it.")
    def new(
        ctx: typer.Context, name: str, from_: str = typer.Option("default", "--from", help="Profile to copy.")
    ) -> None:
        path = profiles.create(name, from_)
        out(ctx).emit(
            {"ok": True, "name": name, "path": str(path)},
            lambda c: c.print(f"[{rgb('ok')}]✓[/] created [bold]{name}[/] — edit it at {escape(str(path))}"),
        )
