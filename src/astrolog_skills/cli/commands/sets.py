"""`astro set …` — research chart sets from saved charts, CSV files or Astro-Databank exports."""

from __future__ import annotations

from collections import Counter
from typing import Any

import typer
from rich.console import Console
from rich.markup import escape

from astrolog_skills.charts import sets
from astrolog_skills.cli.app import out
from astrolog_skills.engine.zodiac import format_position
from astrolog_skills.errors import AstroError
from astrolog_skills.packs.settings import chart_profile
from astrolog_skills.ui import rgb


def _split(values: list[str]) -> list[str]:
    return [v.strip() for item in values for v in item.split(",") if v.strip()]


def register(app: typer.Typer) -> None:
    set_app = typer.Typer(help="Research chart sets (saved charts, CSV, Astro-Databank).", no_args_is_help=True)
    app.add_typer(set_app, name="set")

    @set_app.command("create", help="Define a set from one source plus filters.")
    def create(
        ctx: typer.Context,
        name: str,
        adb: str = typer.Option(None, "--adb", help="Astro-Databank XML export (your licensed copy or a free sample)."),
        csv: str = typer.Option(None, "--csv", help="CSV file: name,date,time,tz,lat,lon,place,rating,tags."),
        chart: list[str] = typer.Option([], "--chart", help="Saved charts (repeatable or comma-separated)."),
        rating: list[str] = typer.Option([], "--rating", help="Rodden ratings to keep, e.g. AA,A."),
        category: list[str] = typer.Option(
            [], "--category", help='ADB category prefix, e.g. "Vocation : Entertain/Music".'
        ),
        exclude_category: list[str] = typer.Option([], "--exclude-category", help="Category prefix to drop."),
        gender: str = typer.Option("", "--gender", help="m or f."),
        datatype: list[str] = typer.Option([], "--datatype", help='ADB data type, e.g. "Public Figure".'),
        include_research: bool = typer.Option(False, "--include-research", help="Keep anonymous research groups."),
        description: str = typer.Option("", "--description"),
        replace: bool = typer.Option(False, "--replace", help="Overwrite an existing set."),
    ) -> None:
        sources = [k for k, v in (("adb", adb), ("csv", csv), ("charts", chart)) if v]
        if len(sources) != 1:
            raise AstroError("Give exactly one source.", fix="--adb FILE, --csv FILE, or --chart NAME (repeatable)")
        filt = sets.SetFilter(
            ratings=_split(rating),
            categories=category,
            exclude_categories=exclude_category,
            gender=gender.lower(),
            datatypes=datatype,
            exclude_research=not include_research,
        )
        s = sets.create(
            name,
            sources[0],
            path=adb or csv or "",
            charts=_split(chart),
            description=description,
            filter_=filt,
            overwrite=replace,
        )
        kept, stats = sets.records(s)

        def render(c: Console) -> None:
            c.print(
                f"[{rgb('ok')}]✓[/] set [bold]{s.name}[/]: [bold]{len(kept)}[/] charts "
                f"[{rgb('dim')}]({', '.join(f'{k} {v}' for k, v in stats.items())})[/]"
            )

        out(ctx).emit({"ok": True, "name": s.name, "count": len(kept), "stats": stats}, render)

    @set_app.command("list", help="List chart sets.")
    def list_(ctx: typer.Context) -> None:
        rows = [{"name": s.name, "kind": s.kind, "description": s.description} for s in sets.list_sets()]

        def render(c: Console) -> None:
            if not rows:
                c.print(f"[{rgb('dim')}]No sets yet — create one with `astro set create`.[/]")
            for r in rows:
                c.print(f"  [bold]{r['name']:<24}[/] {r['kind']:<7} {escape(r['description'])}")

        out(ctx).emit({"sets": rows}, render)

    @set_app.command("show", help="Summarise a set: size, ratings, genders, most common categories.")
    def show(ctx: typer.Context, name: str, top: int = typer.Option(8, "--top", help="Categories to list.")) -> None:
        s = sets.load(name)
        kept, stats = sets.records(s)
        ratings = Counter(r.rating or "?" for r in kept)
        genders = Counter(r.gender or "?" for r in kept)
        cats = Counter(c for r in kept for c in set(r.categories)).most_common(top)
        data = {
            "name": s.name,
            "kind": s.kind,
            "path": s.path,
            "filter": s.filter.__dict__,
            "count": len(kept),
            "stats": stats,
            "ratings": dict(ratings),
            "genders": dict(genders),
            "categories": cats,
            "sample": [r.name for r in kept[:5]],
        }

        def render(c: Console) -> None:
            c.print(f"[bold {rgb('accent')}]{s.name}[/] — {len(kept)} charts from {s.kind}")
            c.print(f"  ratings  {dict(ratings)}\n  genders  {dict(genders)}")
            for cat, n in cats:
                c.print(f"  [{rgb('dim')}]{n:>5}[/] {escape(cat)}")

        out(ctx).emit(data, render)

    @set_app.command("cast", help="Calculate every chart in a set (one fast Astrolog run).")
    def cast_cmd(
        ctx: typer.Context,
        name: str,
        profile: str = typer.Option(None, "--profile", help="Settings profile (default: the active one)."),
        limit: int = typer.Option(None, "--limit", help="Only the first N charts."),
    ) -> None:
        pairs = sets.cast_set(sets.load(name), chart_profile(profile), limit)
        rows: list[dict[str, Any]] = [
            {
                "id": r.id,
                "name": r.name,
                "utc": r.utc.isoformat(),
                "rating": r.rating,
                "points": {k: v["lon"] for k, v in chart.points.items()},
                "angles": chart.angles,
            }
            for r, chart in pairs
        ]

        def render(c: Console) -> None:
            c.print(f"[{rgb('ok')}]✓[/] cast [bold]{len(rows)}[/] charts")
            for row in rows[:10]:
                sun, moon = row["points"].get("sun"), row["points"].get("moon")
                c.print(
                    f"  {escape(row['name'])[:30]:<30} ☉ {format_position(sun) if sun is not None else '—':<16} "
                    f"☽ {format_position(moon) if moon is not None else '—'}"
                )
            if len(rows) > 10:
                c.print(f"  [{rgb('dim')}]… and {len(rows) - 10} more (use --json for all)[/]")

        out(ctx).emit({"count": len(rows), "charts": rows}, render)

    @set_app.command("rm", help="Delete a set definition (the source file is left alone).")
    def rm(ctx: typer.Context, name: str) -> None:
        sets.remove(name)
        out(ctx).emit({"ok": True}, lambda c: c.print(f"[{rgb('ok')}]✓[/] removed set {escape(name)}"))
