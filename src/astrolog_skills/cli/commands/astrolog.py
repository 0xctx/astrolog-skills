"""`astro astrolog …` — install and inspect the Astrolog program itself."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel

from astrolog_skills.astrolog import install, locate
from astrolog_skills.cli.app import out
from astrolog_skills.errors import AstroError
from astrolog_skills.ui import rgb


def _render_plan(c: Console, p: install.InstallPlan) -> None:
    how = (
        "compile the official source (headless, no X11)"
        if p.method == "source-build"
        else "unpack the official Windows CLI"
    )
    c.print()
    c.rule(f"[bold {rgb('accent')}]✦ install Astrolog {p.version} ✦[/]", style=rgb("dim"))
    c.print()
    c.print(f"  [bold]From[/]     {escape(p.url)}")
    c.print(f"  [bold]Checksum[/] [{rgb('dim')}]sha256 {p.sha256[:16]}… (verified before anything is built)[/]")
    c.print(f"  [bold]How[/]      {how}")
    c.print(
        f"  [bold]Into[/]     {escape(str(p.prefix))}" + (f"  [{rgb('warn')}](already exists)[/]" if p.exists else "")
    )
    for tool, path in p.prerequisites.items():
        mark = (
            f"[{rgb('ok')}]✓[/] {escape(path)}" if path else f"[{rgb('bad')}]✗ missing[/] → `{install.compiler_hint()}`"
        )
        c.print(f"  [bold]{tool.capitalize():<9}[/]{mark}")
    c.print()
    c.print(f"  [{rgb('dim')}]Nothing has been downloaded. Nothing outside that folder is touched.[/]")
    flag = " --force" if p.exists else ""
    c.print(f"  Run [bold {rgb('accent')}]astro astrolog install --yes{flag}[/] to go ahead.")
    c.print()


def register(app: typer.Typer) -> None:
    ast_app = typer.Typer(help="Install or inspect the Astrolog program.", no_args_is_help=True)
    app.add_typer(ast_app, name="astrolog")

    @ast_app.command("install", help="Build Astrolog from its official source (preview unless --yes).")
    def install_cmd(
        ctx: typer.Context,
        version: str = typer.Option(install.DEFAULT_VERSION, "--version", help="Astrolog release to install."),
        prefix: Path | None = typer.Option(
            None, "--prefix", help="Install folder (default ~/.astrolog-skills/astrolog)."
        ),
        force: bool = typer.Option(False, "--force", help="Replace an existing install at the prefix."),
        yes: bool = typer.Option(False, "--yes", help="Actually download, build and install."),
    ) -> None:
        o = out(ctx)
        p = install.plan(version, prefix, force)
        if not yes:
            o.emit({"ok": True, "preview": True, **p.to_dict()}, lambda c: _render_plan(c, p))
            return
        result = install.execute(p, progress=lambda msg: o.status(f"[{rgb('dim')}]  … {escape(msg)}[/]"))

        def done(c: Console) -> None:
            c.print()
            c.print(
                Panel(
                    f"[bold]Astrolog {result['version']}[/] installed in [bold]{result['seconds']}s[/]\n"
                    f"[{rgb('dim')}]{escape(result['path'])}[/]\n"
                    f"ephemeris: [bold]{result['ephemeris']}[/] · calculations verified ✓\n\n"
                    f"Next: [bold {rgb('accent')}]astro doctor[/]",
                    title=f"[bold {rgb('gold')}]✦ Astrolog is ready ✦[/]",
                    border_style=rgb("ok"),
                    padding=(1, 2),
                    expand=False,
                )
            )

        o.emit(result, done)

    @ast_app.command("info", help="Show which Astrolog is used, its version and data files.")
    def info(ctx: typer.Context) -> None:
        found = locate.find()
        if not found:
            raise AstroError("Astrolog isn't installed or configured.", fix="astro astrolog install")
        v = locate.version_text(locate.version(found.path))
        eph = locate.ephemeris(found.path)
        docs = found.path.parent / "astrolog.htm"
        data = {
            "path": str(found.path),
            "source": found.source,
            "version": v,
            "ephemeris": eph.mode,
            "ephemeris_dir": str(eph.directory),
            "docs": str(docs) if docs.exists() else None,
        }

        def render(c: Console) -> None:
            for key, value in data.items():
                c.print(f"  [{rgb('accent')}]{key:<14}[/] {escape(str(value))}")

        out(ctx).emit(data, render)
