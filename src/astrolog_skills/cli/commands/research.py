"""`astro harmonics` (one chart) and `astro research …` (chart sets): harmonic strength and sweeps."""

from __future__ import annotations

from typing import Any

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from astrolog_skills.cli.app import out
from astrolog_skills.cli.birth import moment_from_options
from astrolog_skills.cli.commands.analysis import _range
from astrolog_skills.engine.cast import cast
from astrolog_skills.errors import AstroError
from astrolog_skills.packs import loader
from astrolog_skills.packs.settings import chart_profile
from astrolog_skills.research import runs, sweep
from astrolog_skills.ui import rgb


def _significance(p: float) -> str:
    return "notable" if p <= 0.05 else "suggestive" if p <= 0.2 else "chance"


def render_sweep(c: Console, result: dict[str, Any], top: int) -> None:
    from astrolog_skills.research.sweep import LABELS

    if "measures" not in result:
        raise AstroError("This run was saved by an earlier version.", fix="run the sweep again")
    params = result["params"]
    c.print(
        f"\n[bold {rgb('gold')}]{escape(result['set_name'])}[/] — {result['count']} charts · H{params['range'][0]}–"
        f"{params['range'][1]} · {escape(params['pack'])} · baseline: {params['shuffles']} control groups"
    )
    summary = []
    for measure, stats in result["measures"].items():
        c.print(f"\n[bold {rgb('water')}]{LABELS[measure]}[/]")
        table = Table(box=None, padding=(0, 1), header_style=rgb("dim"))
        for col in ("H", "observed", "expected", "ratio", "z", "adjusted p", "", "strongest in this set"):
            table.add_column(
                col, justify="right" if col in ("H", "observed", "expected", "ratio", "z", "adjusted p") else "left"
            )
        for s in sorted(stats, key=lambda s: -s["z"])[:top]:
            verdict = _significance(s["p_family"])
            colour = rgb("ok") if verdict == "notable" else rgb("warn") if verdict == "suggestive" else rgb("dim")
            names = ", ".join(escape(t["name"]) for t in s["top"][:3])
            table.add_row(
                f"[bold]{s['harmonic']}[/]",
                f"{s['observed']:.3f}",
                f"{s['expected']:.3f}",
                f"{s['ratio']:.3f}",
                f"{s['z']:+.2f}",
                f"{s['p_family']:.3f}",
                f"[{colour}]{verdict}[/]",
                names,
            )
        c.print(table)
        notable = [s["harmonic"] for s in stats if s["p_family"] <= 0.05]
        summary.append(f"{measure}: " + (", ".join(f"H{h}" for h in sorted(notable)) if notable else "none notable"))
    if len(result["measures"]) > 1:
        c.print(f"\n[bold]Which measure separates this set from chance?[/] {' · '.join(summary)}")
    c.print(
        f"[{rgb('dim')}]expected = the same measure on control charts built from this set's own dates, times and"
        " places; adjusted p accounts for testing every harmonic in the range. Exploratory — look closer, don't"
        " conclude.[/]\n"
    )


def register(app: typer.Typer) -> None:
    @app.command(
        "harmonics",
        help="Which harmonics are strongest in one chart: a scan of its harmonics ranked by midpoint structures"
        " (--by new|old|aspects), with the other measures alongside. --harmonic H for one harmonic in detail.",
    )
    def harmonics_cmd(
        ctx: typer.Context,
        chart: str = typer.Option(None, "--chart", help="A saved chart."),
        date: str = typer.Option(None, "--date"),
        time: str = typer.Option(None, "--time"),
        place: str = typer.Option(None, "--place"),
        tz: str = typer.Option(None, "--tz"),
        at: str = typer.Option(None, "--at"),
        pack: str = typer.Option("vibrational", "--pack", help="Tradition pack (default: vibrational)."),
        profile: str = typer.Option(None, "--profile"),
        harmonics: str = typer.Option(None, "--harmonics", help="Harmonics: 1-32, 1,5,7,18 … (default: the pack's)."),
        harmonic: int = typer.Option(None, "--harmonic", "-H", help="One harmonic in detail."),
        by: str = typer.Option("new", "--by", help="Rank by: new (midpoints, new method), old, or aspects."),
        top: int = typer.Option(8, "--top", help="How many harmonics to list."),
        orb_base: float = typer.Option(None, "--orb-base", help="New method's conjunction orb: 3 (default) or 4."),
    ) -> None:
        from astrolog_skills.analysis.midpoints import rank_harmonics
        from astrolog_skills.export.html import parse_harmonics
        from astrolog_skills.render.views.strongest import render_detail, render_ranking

        if by not in ("new", "old", "aspects"):
            raise AstroError(f"--by must be new, old or aspects, not '{by}'.")
        if orb_base is not None and not 1 <= orb_base <= 6:
            raise AstroError("--orb-base must be between 1 and 6 degrees (3 or 4 are the usual choices).")
        moment, _ = moment_from_options(chart=chart, date=date, time=time, place=place, tz=tz, at=at)
        p = loader.load(pack)
        model = cast(moment, chart_profile(profile, p))
        lo, hi = p.method.harmonic_range
        chosen = parse_harmonics(harmonics, 10_000) if harmonics else list(range(lo, hi + 1))
        if harmonic is not None:
            chosen = sorted({*chosen, harmonic})
        ranking = rank_harmonics(model, p.method, chosen, orb_base)
        data: dict[str, Any] = {"chart": model.name, "pack": p.name, "by": by, **ranking.to_dict()}
        data["ranked"] = [h.harmonic for h in ranking.ranked(by)][:top]
        if harmonic is not None:
            from astrolog_skills.analysis.aspects import find_aspects
            from astrolog_skills.analysis.midpoints import midpoint_contacts

            planets = set(ranking.bodies)

            def mids(how: str) -> list[dict[str, Any]]:
                found = midpoint_contacts(model, p.method, harmonic, how, orb_base)
                rows = [c for f, cs in found.items() if f in planets for c in cs if {c.a, c.b} <= planets]
                return [c.to_dict() for c in sorted(rows, key=lambda c: -c.strength)[:12]]

            aspects = [a for a in find_aspects(model, p.method, harmonic) if {a.a, a.b} <= planets]
            data["detail"] = {
                "harmonic": harmonic,
                "aspects": [a.to_dict() for a in sorted(aspects, key=lambda a: a.orb)[:12]],
                "midpoints": {"new": mids("new"), "old": mids("old")},
            }

        def render(c: Console) -> None:
            if harmonic is not None:
                render_detail(c, data, model.name or "Chart")
            else:
                render_ranking(c, data, model.name or "Chart", top)

        out(ctx).emit(data, render)

    research_app = typer.Typer(
        help="Research across chart sets: harmonic sweeps (midpoint structures, aspects) against control charts.",
        no_args_is_help=True,
    )
    app.add_typer(research_app, name="research")

    @research_app.command(
        "sweep",
        help="Measure every chart in a set in every harmonic — midpoint structures (new and old methods) and two-planet"
        " aspects — and compare with control charts.",
    )
    def sweep_cmd(
        ctx: typer.Context,
        set_name: str = typer.Argument(..., help="A chart set (astro set list)."),
        range_: str = typer.Option("1-32", "--range", help="Harmonics, e.g. 1-180."),
        pack: str = typer.Option("vibrational", "--pack"),
        profile: str = typer.Option("vibrational", "--profile", help="Needs all ten planets."),
        control: str = typer.Option(None, "--control", help="Also report another set's means (e.g. everyone)."),
        shuffles: int = typer.Option(20, "--shuffles", help="Control groups for the baseline (more = finer p)."),
        seed: int = typer.Option(1, "--seed", help="Random seed (same seed = same result)."),
        top: int = typer.Option(10, "--top", help="Harmonics to list per measure."),
        measures: str = typer.Option(
            "new,old,aspects",
            "--measures",
            help="What to measure: new (midpoint structures, new method), old (old method), aspects (pair score).",
        ),
        save: bool = typer.Option(True, "--save/--no-save", help="Save the run to ~/.astrolog-skills/research."),
    ) -> None:
        lo, hi = _range(range_)
        chosen = tuple(m.strip() for m in measures.split(",") if m.strip())
        p = loader.load(pack)
        o = out(ctx)
        o.status(f"[{rgb('dim')}]casting the set and {shuffles} control groups…[/]")
        result = sweep.sweep(
            set_name,
            chart_profile(profile, p),
            p,
            lo,
            hi,
            shuffles=shuffles,
            seed=seed,
            control=control,
            top=top,
            measures=chosen,
        )
        data = result.to_dict()
        if save:
            data["run"] = runs.save(result, p).stem

        def render(c: Console) -> None:
            render_sweep(c, data, top)
            if save:
                c.print(f"[{rgb('dim')}]saved as {data['run']} — astro research show {data['run']}[/]")

        o.emit(data, render)

    @research_app.command("list", help="Saved research runs.")
    def list_(ctx: typer.Context) -> None:
        rows = runs.list_runs()

        def render(c: Console) -> None:
            for r in rows or [{"id": "(none yet)", "set": "", "count": "", "range": ["", ""], "pack": ""}]:
                span = f"H{r['range'][0]}–{r['range'][1]}"
                c.print(f"  [bold]{r['id']}[/]  {escape(str(r['set']))} {r['count']} charts {span} {r['pack']}")

        out(ctx).emit({"runs": rows}, render)

    @research_app.command("show", help="Show a saved run.")
    def show(ctx: typer.Context, run_id: str, top: int = typer.Option(10, "--top")) -> None:
        data = runs.load(run_id)
        out(ctx).emit(data, lambda c: render_sweep(c, data["result"], top))
