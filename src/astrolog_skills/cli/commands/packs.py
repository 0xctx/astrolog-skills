"""`astro packs …` — tradition packs: list, show, check, copy, and build from sources (outline … apply)."""

from __future__ import annotations

from typing import Any

import typer
from rich.console import Console
from rich.markup import escape

from astrolog_skills.cli.app import out
from astrolog_skills.engine import profile as profiles
from astrolog_skills.packs import loader
from astrolog_skills.ui import rgb


def _describe(s: dict[str, Any]) -> str:
    zodiac = f"sidereal ({s.get('ayanamsa')})" if s.get("zodiac") == "sidereal" else s.get("zodiac")
    parts = [zodiac] if zodiac else []
    parts += [f"{s['houses']} houses"] if s.get("houses") else []
    parts += [f"{s['node']} node"] if s.get("node") else []
    parts += ["objects: " + ", ".join(s["points"])] if s.get("points") else []
    return " · ".join(parts)


def register(app: typer.Typer) -> None:
    packs_app = typer.Typer(
        help="Tradition packs: calculation rules + meanings for a school of astrology.", no_args_is_help=True
    )
    app.add_typer(packs_app, name="packs")

    @packs_app.command("list", help="List tradition packs (yours replace built-ins with the same name).")
    def list_(ctx: typer.Context) -> None:
        active = profiles.active().pack
        rows = []
        for name in loader.list_packs():
            p = loader.load(name)
            rows.append(
                {
                    "name": name,
                    "label": p.label,
                    "user": p.user,
                    "active": name == active,
                    "orb_rule": p.method.orb_rule,
                    "aspects": len(p.method.aspects),
                }
            )

        def render(c: Console) -> None:
            for r in rows:
                mark = f"[bold {rgb('ok')}]●[/]" if r["active"] else " "
                origin = f"[{rgb('gold')}]yours[/]" if r["user"] else f"[{rgb('dim')}]built-in[/]"
                c.print(
                    f" {mark} [bold]{r['name']:<16}[/] {escape(str(r['label'])):<38} {r['aspects']} aspects · "
                    f"{r['orb_rule']} orbs  {origin}"
                )

        out(ctx).emit({"active": active, "packs": rows}, render)

    @packs_app.command("show", help="Show a pack's rules: aspects and orbs, harmonics, patterns, files.")
    def show(ctx: typer.Context, name: str = typer.Argument(None, help="Pack (default: your profile's pack).")) -> None:
        p = loader.load(name or profiles.active().pack)
        data = p.to_dict()

        def render(c: Console) -> None:
            c.print(f"[bold {rgb('accent')}]{escape(p.label)}[/]  [{rgb('dim')}]{escape(str(p.directory))}[/]")
            orbs = "  ".join(f"{k} {v:g}°" for k, v in data["aspects"].items())
            c.print(f"  aspects   {orbs}")
            pat = data["patterns"]
            c.print(
                f"  patterns  {pat['min_size']}+ bodies within {pat['orb']:g}° (harmonic chart); "
                f"{pat['strong_size']}-body patterns scored"
            )
            c.print(f"  harmonics {data['harmonic_range'][0]}–{data['harmonic_range'][1]}")
            if data["doctrine"]:
                c.print(f"  doctrine  {', '.join(data['doctrine']['sections'])}")
            if p.method.chart:
                hint = f"[{rgb('dim')}]astro packs settings[/]"
                c.print(f"  chart     {escape(_describe(p.method.chart.to_dict()))}  {hint}")
            present = [n for n, ok in data["files"].items() if ok]
            c.print(f"  files     method.toml, {', '.join(present)}")
            for s in data["sources"]:
                c.print(f"  [{rgb('dim')}]source: {escape(s.get('author', ''))} — {escape(s.get('title', ''))}[/]")

        out(ctx).emit(data, render)

    @packs_app.command(
        "settings",
        help="The chart settings a pack uses (zodiac, houses, node, objects): its own, your saved adjustments and"
        " the result. Options save adjustments; --reset forgets them.",
    )
    def settings_(
        ctx: typer.Context,
        name: str = typer.Argument(..., help="Pack."),
        houses: str = typer.Option(None, "--houses", help="House system, e.g. placidus."),
        zodiac: str = typer.Option(None, "--zodiac", help="tropical, or an ayanamsa (lahiri, fagan-bradley…)."),
        node: str = typer.Option(None, "--node", help="true or mean."),
        points: str = typer.Option(None, "--points", help="A list replaces the objects; +ceres adds, -pluto drops."),
        reset: bool = typer.Option(False, "--reset", help="Forget your saved adjustments for this pack."),
    ) -> None:
        from astrolog_skills.engine.profile import chart_settings
        from astrolog_skills.packs import settings

        p = loader.load(name)
        if reset:
            settings.save(p.name, None)
        elif any((houses, zodiac, node, points)):
            own = settings.saved(p.name).to_dict()
            new = chart_settings(zodiac, houses, node, points, where="astro packs settings")
            merged = {**own, **new.to_dict()}
            if new.points:  # +/- build on what you saved before
                plain = [t for t in new.points if t[:1] not in "+-"]
                merged["points"] = list(new.points) if plain else [*own.get("points", []), *new.points]
            if new.zodiac == "tropical":
                merged.pop("ayanamsa", None)
            before = settings.saved(p.name)
            settings.save(p.name, settings.saved_from(merged, p.name))
            try:
                settings.chart_profile(None, p)  # nothing broken is kept
            except Exception:
                settings.save(p.name, before)
                raise
        result = settings.chart_profile(None, p)
        data: dict[str, Any] = {
            "pack": p.name,
            "pack_settings": {**p.method.chart.to_dict(), "cite": p.method.chart.cite} if p.method.chart else None,
            "your_settings": settings.saved(p.name).to_dict() or None,
            "result": result.to_dict(),
            "summary": result.summary(),
        }

        def render(c: Console) -> None:
            c.print(f"[bold {rgb('accent')}]{escape(p.label)}[/] — chart settings")
            c.print(f"  the pack     {escape(_describe(data['pack_settings'] or {}) or 'none (your profile decides)')}")
            c.print(f"  yours        {escape(_describe(data['your_settings'] or {}) or 'no adjustments')}")
            c.print(f"  [bold]in use[/]       {escape(result.summary())} · {len(result.objects)} objects")
            c.print(f"               [{rgb('dim')}]{escape(', '.join(result.objects))}[/]")
            c.print(
                f"  [{rgb('dim')}]try once: astro --houses placidus … · keep: astro packs settings {p.name} --houses …"
                " · undo: --reset[/]"
            )

        out(ctx).emit(data, render)

    @packs_app.command("check", help="Check packs: citations, tables and lot formulas (all packs if none named).")
    def check(ctx: typer.Context, name: str = typer.Argument(None, help="Pack to check (default: all).")) -> None:
        from astrolog_skills.analysis.doctrine import check_doctrine

        names = [name] if name else list(loader.list_packs())
        results: list[dict[str, Any]] = []
        for pack_name in names:
            method = loader.load(pack_name).method
            problems = check_doctrine(method.doctrine) if method.doctrine else []
            results.append({"pack": pack_name, "problems": [p.to_dict() for p in problems]})
        errors = sum(1 for r in results for p in r["problems"] if p["level"] == "error")

        def render(c: Console) -> None:
            for r in results:
                if not r["problems"]:
                    c.print(f"[{rgb('ok')}]✓[/] {escape(r['pack'])}")
                    continue
                c.print(f"[bold]{escape(r['pack'])}[/]")
                for p in r["problems"]:
                    mark = f"[{rgb('bad')}]✗[/]" if p["level"] == "error" else f"[{rgb('warn')}]![/]"
                    c.print(f"  {mark} {escape(p['where'])}: {escape(p['message'])}", soft_wrap=True)
                    if p["fix"]:
                        c.print(f"    [{rgb('dim')}]→ {escape(p['fix'])}[/]", soft_wrap=True)

        out(ctx).emit({"ok": errors == 0, "errors": errors, "packs": results}, render)
        if errors:
            raise typer.Exit(1)

    @packs_app.command(
        "outline",
        help="A source's chapters, sections, figures and tables with printed pages (notes and transcripts: lessons or"
        " headings with their § sections).",
    )
    def outline_cmd(
        ctx: typer.Context,
        pack: str,
        source: str = typer.Option(None, "--source", help="Source id (default: the pack's only source)."),
    ) -> None:
        from astrolog_skills.packs.build import outline

        result = outline(pack, source)
        data = result.to_dict()

        def render(c: Console) -> None:
            if result.kind == "sections":
                c.print(f"[bold]{escape(result.source)}[/] · sections § {result.first}–{result.last}")
                for ch in result.chapters:
                    c.print(f"  {escape(ch.title)}  [{rgb('dim')}]§ {ch.start}–{ch.end}[/]")
                return
            c.print(f"[bold]{escape(result.source)}[/] · body pp. {result.first}–{result.last}")
            for ch in result.chapters:
                c.print(f"  {ch.number:>3} {escape(ch.title.title())}  [{rgb('dim')}]pp. {ch.start}–{ch.end}[/]")
            if result.tables:
                tables = ", ".join(f"{t.number} {t.title} (p. {t.start})" for t in result.tables)
                c.print(f"  [{rgb('dim')}]tables: {escape(tables)}[/]", soft_wrap=True)
            c.print(f"  [{rgb('dim')}]sections and figures: --json[/]")

        out(ctx).emit(data, render)

    @packs_app.command("draft", help="Start a draft of a pack (copies its files, or skeletons for a new pack).")
    def draft_cmd(ctx: typer.Context, pack: str) -> None:
        from astrolog_skills.packs import draft

        started = draft.start(pack)
        data = {
            "ok": True,
            "path": str(started.path),
            "copied": started.copied,
            "created": started.created,
            "hand_edits": started.hand_edits,
        }

        def render(c: Console) -> None:
            c.print(f"[{rgb('ok')}]✓[/] draft at [bold]{escape(str(started.path))}[/]")
            if started.hand_edits:
                c.print(f"  [{rgb('dim')}]includes {started.hand_edits} line(s) you edited since the last apply[/]")

        out(ctx).emit(data, render)

    @packs_app.command("discard", help="Delete a pack's draft.")
    def discard_cmd(ctx: typer.Context, pack: str) -> None:
        from astrolog_skills.packs import draft

        gone = draft.discard(pack)
        out(ctx).emit({"ok": True, "path": str(gone)}, lambda c: c.print(f"[{rgb('ok')}]✓[/] draft removed"))

    @packs_app.command("verify", help="Check a draft against its sources: evidence, citations, wording, tables.")
    def verify_cmd(
        ctx: typer.Context,
        pack: str,
        live: bool = typer.Option(False, "--live", help="Check the live pack instead of its draft."),
    ) -> None:
        from astrolog_skills.packs.verify import verify

        report = verify(pack, live)
        data = report.to_dict()

        def render(c: Console) -> None:
            mark = f"[{rgb('ok')}]✓[/]" if report.errors == 0 else f"[{rgb('bad')}]✗[/]"
            c.print(f"{mark} {escape(pack)} ({report.target}) · evidence found {report.found}/{report.claims}")
            for p in report.problems:
                sign = f"[{rgb('bad')}]✗[/]" if p.level == "error" else f"[{rgb('warn')}]![/]"
                c.print(f"  {sign} {escape(p.where)}: {escape(p.message)}", soft_wrap=True)
                if p.fix:
                    c.print(f"    [{rgb('dim')}]→ {escape(p.fix)}[/]", soft_wrap=True)

        out(ctx).emit(data, render)
        if report.errors:
            raise typer.Exit(1)

    @packs_app.command("diff", help="What the draft would change in the live pack.")
    def diff_cmd(ctx: typer.Context, pack: str) -> None:
        from astrolog_skills.packs import draft

        diffs = draft.diff(pack)
        data = {"files": [d.__dict__ for d in diffs]}

        def render(c: Console) -> None:
            for d in diffs:
                c.print(f"[bold]{d.name}[/] {d.status} (+{d.added} −{d.removed})")
                for line in d.edits_changed:
                    c.print(f"  [{rgb('warn')}]⚠ changes your own edit:[/] {escape(line.strip())}", soft_wrap=True)
                if d.diff:
                    c.print(escape(d.diff), soft_wrap=True, highlight=False)

        out(ctx).emit(data, render)

    @packs_app.command("apply", help="Apply a verified draft to the live pack (needs --yes after the user approves).")
    def apply_cmd(
        ctx: typer.Context,
        pack: str,
        yes: bool = typer.Option(False, "--yes", help="The user has seen the diff and approved it."),
    ) -> None:
        from astrolog_skills.errors import AstroError
        from astrolog_skills.packs import draft
        from astrolog_skills.packs.verify import verify

        report = verify(pack)
        if report.errors:
            raise AstroError(
                f"The draft has {report.errors} problem(s); nothing was applied.", fix=f"astro packs verify {pack}"
            )
        if not yes:
            pending = [{"file": d.name, "status": d.status} for d in draft.diff(pack) if d.status != "same"]
            out(ctx).emit(
                {"ok": False, "applied": [], "pending": pending, "next": f"astro packs apply {pack} --yes"},
                lambda c: c.print(f"Not applied. Show the diff, get approval, then: astro packs apply {pack} --yes"),
            )
            return
        done = draft.apply(pack)
        data = {"ok": True, "applied": done.files, "backup": str(done.backup) if done.backup else None}
        out(ctx).emit(data, lambda c: c.print(f"[{rgb('ok')}]✓[/] applied {', '.join(done.files) or 'nothing'}"))

    @packs_app.command("copy", help="Copy a pack into your folder to edit it (same name replaces the built-in).")
    def copy(
        ctx: typer.Context,
        name: str,
        as_: str = typer.Option(None, "--as", help="Save your copy under a new name."),
    ) -> None:
        target = loader.copy_to_user(name, as_)
        out(ctx).emit(
            {"ok": True, "path": str(target)},
            lambda c: c.print(f"[{rgb('ok')}]✓[/] copied to [bold]{escape(str(target))}[/] — edit its files"),
        )
