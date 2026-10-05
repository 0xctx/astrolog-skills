"""`astro report-data` — everything a written reading needs, in one JSON bundle."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import typer
from rich.console import Console

from astrolog_skills.analysis.aspects import find_aspects
from astrolog_skills.analysis.doctrine.explain import attach_notes, without_citations
from astrolog_skills.analysis.midpoints import rank_harmonics
from astrolog_skills.analysis.patterns import score_harmonic
from astrolog_skills.analysis.timing.transits import daily, time_lord_transits
from astrolog_skills.charts.store import slug
from astrolog_skills.cli.app import out
from astrolog_skills.cli.birth import moment_from_options
from astrolog_skills.cli.commands.analysis import _range
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.moment import Moment
from astrolog_skills.engine.profile import Profile
from astrolog_skills.engine.zodiac import ELEMENTS, MODES, sign_index
from astrolog_skills.errors import AstroError
from astrolog_skills.export import notes as reading_notes
from astrolog_skills.export.notes import notes_path
from astrolog_skills.packs.loader import Pack
from astrolog_skills.packs.settings import citations, resolve
from astrolog_skills.paths import data_dir
from astrolog_skills.sources import library


def _doctrine_parts(
    moment: Moment, model: ChartModel, pack: Pack, prof: Profile, on: str | None, transits_days: int
) -> dict[str, Any]:
    """For packs with doctrine: the study (with any notes already written), the time lords on a date, and the
    pack's sources with how to search them."""
    from astrolog_skills.cli.commands.doctrine import study_for

    out: dict[str, Any] = {}
    sources = library.list_sources(pack.name) if (pack.directory / "sources.toml").is_file() else []
    if sources:
        out["sources"] = {
            "list": [{k: s.get(k) for k in ("id", "title", "author", "pages", "indexed", "covers")} for s in sources],
            "search": f'astro --json sources search {pack.name} "words or phrase"',
            "page": f"astro --json sources page {pack.name} N",
        }
    study = study_for(moment, model, pack, prof)
    if study is None:
        return out
    path = notes_path(model, pack.name)
    attached = attach_notes(study, reading_notes.load(path)) if path.is_file() else 0
    day = on or date.today().isoformat()
    try:
        date.fromisoformat(day)
    except ValueError as err:
        raise AstroError(f"'{day}' isn't a date.", fix="use YYYY-MM-DD") from err
    upcoming = []
    for lot, rel in study.get("releasing", {}).items():
        for r in rel["periods"]:
            if day <= r["begins"] and (r["peak"] or r["loosing"]) and r["begins"][:4] <= str(int(day[:4]) + 10):
                upcoming.append({"lot": lot, **r})
    timing: dict[str, Any] = {
        "on": day,
        "profections": [y for y in study.get("profections", []) if y["begins"] <= day < y["ends"]],
        "releasing": {
            lot: [r for r in rel["periods"] if r["begins"] <= day < r["ends"]]
            for lot, rel in study.get("releasing", {}).items()
        },
        "upcoming": sorted(upcoming, key=lambda r: r["begins"])[:20],
    }
    if transits_days:
        if not 1 <= transits_days <= 730:
            raise AstroError("--transits-days must be 1–730.")
        doctrine = pack.method.doctrine
        assert doctrine is not None
        first = date.fromisoformat(day) - timedelta(days=1)
        positions = daily(prof, first, transits_days, moment.lat, moment.lon)
        timing["transits"] = [
            e.to_dict() for e in time_lord_transits(model, doctrine, date.fromisoformat(moment.date), positions)
        ]
    out |= {"study": study if citations() else without_citations(study), "timing": timing, "notes_attached": attached}
    return out


def register(app: typer.Typer) -> None:
    @app.command("report-data", help="All the data for a written reading (JSON): chart, aspects, patterns, pack files.")
    def report_data(
        ctx: typer.Context,
        chart: str = typer.Option(None, "--chart", help="A saved chart."),
        date_: str = typer.Option(None, "--date"),
        time: str = typer.Option(None, "--time"),
        place: str = typer.Option(None, "--place"),
        tz: str = typer.Option(None, "--tz"),
        at: str = typer.Option(None, "--at"),
        name: str = typer.Option("", "--name"),
        pack: list[str] = typer.Option([], "--pack", help="Tradition pack(s); repeat to blend (default: profile's)."),
        profile: str = typer.Option(None, "--profile"),
        harmonics: str = typer.Option("1-32", "--harmonics", help="Harmonic range for the profile of scores."),
        on: str = typer.Option(None, "--on", help="Date for the time lords (YYYY-MM-DD, default today)."),
        transits_days: int = typer.Option(
            0, "--transits-days", help="Also list the time lords' transits for N days from --on (up to 730)."
        ),
    ) -> None:
        moment, notes = moment_from_options(chart=chart, date=date_, time=time, place=place, tz=tz, at=at, name=name)
        lo, hi = _range(harmonics)
        packs: list[dict[str, Any]] = []
        models: dict[Profile, ChartModel] = {}  # one cast per distinct set of chart settings
        first: ChartModel | None = None
        names: list[str | None] = list(pack) or [None]
        for pack_name in names:
            prof, p = resolve(profile, pack_name)
            model = models.get(prof) or models.setdefault(prof, cast(moment, prof))
            first = first or model
            lons = {pt.key: pt.lon for pt in model.points}
            ranking = rank_harmonics(model, p.method, list(range(lo, hi + 1)))
            packs.append(
                {
                    "name": p.name,
                    "label": p.label,
                    "files": {
                        n: str(f)
                        for n in ("process.md", "meanings.md", "sources.toml", "REVIEW.md")
                        if (f := p.file(n))
                    },
                    "aspects": [a.to_dict() for a in find_aspects(model, p.method)],
                    "natal_patterns": score_harmonic(lons, 1, p.method).to_dict(),
                    "strongest_harmonics": {
                        "by": ranking.default_by(),  # new, or groups beyond the new method's reach
                        "measures": "z_new / z_old: midpoint structures, new and old method; z_groups: planet groups;"
                        " each vs a typical chart in that harmonic; aspects: the pack's pair score",
                        "harmonics": [h.to_dict() for h in ranking.ranked(ranking.default_by())[:8]],
                        "structures": ranking.structures[:10],
                    },
                    "notes_path": str(notes_path(model, p.name)),
                    "settings": prof.to_dict(),
                    **_doctrine_parts(moment, model, p, prof, on, transits_days),
                }
            )
        model = first or cast(moment, resolve(profile, None)[0])
        bodies = [
            pt
            for pt in model.points
            if pt.key in {"sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"}
        ]
        balance = {
            "elements": {e: [pt.key for pt in bodies if sign_index(pt.lon) % 4 == i] for i, e in enumerate(ELEMENTS)},
            "modes": {m: [pt.key for pt in bodies if sign_index(pt.lon) % 3 == i] for i, m in enumerate(MODES)},
        }
        who = slug(model.name) if model.name else "chart"
        export = data_dir() / "exports" / f"{who}-{'-'.join(p['name'] for p in packs)}-{date.today().isoformat()}.md"
        data = {
            "chart": model.to_dict(),
            "balance": balance,
            "packs": packs,
            "notes": notes,
            "export_path": str(export),
            "citations": citations(),
        }

        def render(c: Console) -> None:
            c.print("report-data is meant to be read as JSON: astro --json report-data …")

        out(ctx).emit(data, render)
