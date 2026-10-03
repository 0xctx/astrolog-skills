"""`astro timing …` — time lords by the pack's rules: profections, the sect light's lords, transits, releasing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import typer
from rich.console import Console
from rich.markup import escape

from astrolog_skills.analysis.doctrine.rules import Doctrine
from astrolog_skills.analysis.timing.profections import age_on, anniversary, profection
from astrolog_skills.analysis.timing.releasing import Period, current, releaser
from astrolog_skills.analysis.timing.sect_light import sect_light_lords
from astrolog_skills.analysis.timing.transits import daily, time_lord_transits
from astrolog_skills.cli.app import out
from astrolog_skills.cli.birth import moment_from_options
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.moment import Moment
from astrolog_skills.engine.profile import Profile
from astrolog_skills.errors import AstroError
from astrolog_skills.packs.settings import citations, resolve
from astrolog_skills.ui import rgb

CHART = typer.Option(..., "--chart", help="A saved chart.")
PACK = typer.Option(None, "--pack", help="Tradition pack with [timing] rules (default: your profile's).")


@dataclass
class Setup:
    moment: Moment
    natal: ChartModel
    doctrine: Doctrine
    pack: str
    profile: Profile

    @property
    def birth(self) -> date:
        return date.fromisoformat(self.moment.date)

    @property
    def birth_utc(self) -> datetime:
        assert self.moment.utc is not None
        return self.moment.utc.replace(tzinfo=None)


def _setup(chart: str, pack: str | None, profile: str | None) -> Setup:
    moment, _ = moment_from_options(chart=chart)
    prof, tradition = resolve(profile, pack)
    if tradition.method.doctrine is None:
        raise AstroError(
            f"Pack '{tradition.name}' has no timing rules.", fix="use a pack with [timing], e.g. --pack hellenistic"
        )
    return Setup(moment, cast(moment, prof), tradition.method.doctrine, tradition.name, prof)


def _date(text: str | None, default: date) -> date:
    if not text or text == "now":
        return default
    try:
        return date.fromisoformat(text)
    except ValueError as err:
        raise AstroError(f"'{text}' isn't a date.", fix="use YYYY-MM-DD") from err


def _period_line(p: Period) -> str:
    flags = []
    if p.peak:
        flags.append(f"[{rgb('ok')}]peak {p.peak}[/]")
    if p.loosing:
        flags.append(f"[{rgb('warn')}]loosing of the bond[/]")
    if p.completion:
        flags.append("completion")
    if p.benefic_angle:
        flags.append("benefic's angle")
    if p.malefic_angle:
        flags.append(f"[{rgb('bad')}]malefic's angle[/]")
    planets = ", ".join(x.title() for x in p.in_sign)
    extra = f" · in it: {planets}" if planets else ""
    pad = "  " * (p.level - 1)
    return (
        f"{pad}L{p.level} {p.sign:<11} {p.begins} → {p.ends} · {p.from_fortune} from Fortune ({p.triad})"
        f"{extra}{' · ' + ' · '.join(flags) if flags else ''}"
    )


def register(app: typer.Typer) -> None:
    timing_app = typer.Typer(help="Time lords by the pack's rules.", no_args_is_help=True)
    app.add_typer(timing_app, name="timing")

    @timing_app.command("profections", help="The profection year(s): sign, place, lord, activated planets.")
    def profections_cmd(
        ctx: typer.Context,
        chart: str = CHART,
        pack: str = PACK,
        profile: str = typer.Option(None, "--profile"),
        on: str = typer.Option(None, "--on", help="Date YYYY-MM-DD (default today)."),
        age: int = typer.Option(None, "--age", help="Age in years instead of a date."),
        years: int = typer.Option(1, "--years", help="How many years from there (up to 120)."),
    ) -> None:
        s = _setup(chart, pack, profile)
        if not 1 <= years <= 120:
            raise AstroError("--years must be 1–120.")
        first = age if age is not None else age_on(s.birth, _date(on, date.today()))
        starts = s.doctrine.profections.starts if s.doctrine.profections else ("asc",)
        rows = [
            profection(s.natal, s.doctrine, s.birth, a, start).to_dict()
            for a in range(first, first + years)
            for start in starts
        ]
        cite = s.doctrine.profections.cite if s.doctrine.profections else ""

        def render(c: Console) -> None:
            for r in rows:
                planets = ", ".join(x.title() for x in r["planets_in_sign"])
                lord = f"lord {r['lord'].title()} in {r['lord_place']}" if r["lord"] else ""
                c.print(
                    f"age {r['age']:>3} · from {r['start']:<14} {r['begins']} → {r['ends']} · {r['sign']:<11} "
                    f"place {r['place']:>2} · {lord}{' · in it: ' + planets if planets else ''}",
                    soft_wrap=True,
                )
            if cite and citations():
                c.print(f"[{rgb('dim')}]profections {escape(cite)}[/]")

        out(ctx).emit({"pack": s.pack, "cite": cite, "years": rows}, render)

    @timing_app.command("lords", help="The triplicity lords of the sect light and when the second takes over.")
    def lords_cmd(
        ctx: typer.Context, chart: str = CHART, pack: str = PACK, profile: str = typer.Option(None, "--profile")
    ) -> None:
        s = _setup(chart, pack, profile)
        report = sect_light_lords(s.natal, s.doctrine, s.moment.lat)

        def render(c: Console) -> None:
            c.print(f"Sect light {report.light.title()} in {report.sign}")
            for lord in report.lords:
                q = f" · {lord.quality}" if lord.quality else ""
                where = f"{lord.sign:<11} place {lord.place:>2} ({lord.angularity})"
                c.print(f"  {lord.role:<12} {lord.planet.title():<8} {where}{q}")
            for cand in report.changeover:
                method = str(cand["method"]).replace("_", " ")
                c.print(
                    f"  changeover by {method}: {cand['years']:g} → year {cand['year_of_life']} "
                    f"(age {cand['ages'][0]}–{cand['ages'][1]})"
                )
            if report.cite and citations():
                c.print(f"[{rgb('dim')}]{escape(report.cite)}[/]")

        out(ctx).emit({"pack": s.pack, **report.to_dict()}, render)

    @timing_app.command("transits", help="Transits that involve the time lords, day by day.")
    def transits_cmd(
        ctx: typer.Context,
        chart: str = CHART,
        pack: str = PACK,
        profile: str = typer.Option(None, "--profile"),
        start: str = typer.Option(None, "--from", help="First day YYYY-MM-DD (default today)."),
        days: int = typer.Option(365, "--days", help="How many days (up to 730)."),
    ) -> None:
        if not 1 <= days <= 730:
            raise AstroError("--days must be 1–730.")
        s = _setup(chart, pack, profile)
        first = _date(start, date.today()) - timedelta(days=1)
        positions = daily(s.profile, first, days, s.moment.lat, s.moment.lon)
        events = time_lord_transits(s.natal, s.doctrine, s.birth, positions)

        def render(c: Console) -> None:
            for e in events:
                what = f"enters {e.sign}" if e.kind == "ingress" else f"{e.aspect} natal {e.target.title()}"
                rx = " (retrograde)" if e.retrograde else ""
                c.print(f"{e.date}  {e.planet.title():<8} {what}{rx} · {', '.join(e.why)}", soft_wrap=True)
            if not events:
                c.print("no time-lord transits in this window")

        out(ctx).emit({"pack": s.pack, "events": [e.to_dict() for e in events]}, render)

    @timing_app.command("releasing", help="Zodiacal releasing periods from a lot.")
    def releasing_cmd(
        ctx: typer.Context,
        chart: str = CHART,
        pack: str = PACK,
        profile: str = typer.Option(None, "--profile"),
        lot: str = typer.Option(
            "spirit", "--lot", help="Lot to release from (spirit, fortune, or one the pack lists)."
        ),
        on: str = typer.Option(None, "--on", help="Show the periods running on this date (default today)."),
        start: str = typer.Option(None, "--from", help="List periods from this date instead."),
        end: str = typer.Option(None, "--to", help="… up to this date."),
        level: int = typer.Option(2, "--level", help="Deepest level to list (1–4)."),
    ) -> None:
        if not 1 <= level <= 4:
            raise AstroError("--level must be 1–4.")
        s = _setup(chart, pack, profile)
        r = releaser(s.natal, s.doctrine, s.birth_utc, lot)
        if start or end:
            since = datetime.combine(_date(start, s.birth), datetime.min.time())
            until = datetime.combine(_date(end, date.today()), datetime.min.time())
            rows = [p for p in r.periods(until, level, since) if p.begins < until.date().isoformat()]
            mode = "range"
        else:
            day = _date(on, date.today())
            until = datetime.combine(day + timedelta(days=1), datetime.min.time())
            rows = current(r.periods(until, level, datetime.combine(day, datetime.min.time())), day.isoformat())
            mode = "current"
        data = {
            "pack": s.pack,
            "lot": lot,
            "start_sign": rows[0].sign if rows and mode == "current" else None,
            "shifted": r.shifted,
            "mode": mode,
            "periods": [p.to_dict() for p in rows],
            "cite": s.doctrine.releasing.cite if s.doctrine.releasing else "",
        }

        def render(c: Console) -> None:
            note = " (moved on one sign: Spirit shares Fortune's sign)" if r.shifted else ""
            c.print(f"Releasing from {lot.title()}{note}")
            for p in rows:
                c.print(_period_line(p), soft_wrap=True)

        out(ctx).emit(data, render)

    @timing_app.command("search", help="Find dates: peak, loosing, completion (releasing) or place:N (profections).")
    def search_cmd(
        ctx: typer.Context,
        chart: str = CHART,
        what: str = typer.Option(..., "--what", help="peak, loosing, completion, or place:10 for profection years."),
        pack: str = PACK,
        profile: str = typer.Option(None, "--profile"),
        lot: str = typer.Option("spirit", "--lot"),
        start: str = typer.Option(None, "--from", help="From YYYY-MM-DD (default today)."),
        end: str = typer.Option(None, "--to", help="To YYYY-MM-DD (default 30 years on)."),
        level: int = typer.Option(2, "--level", help="Deepest releasing level to search (1–4)."),
    ) -> None:
        s = _setup(chart, pack, profile)
        a = _date(start, date.today())
        b = _date(end, anniversary(a, 30))
        hits: list[dict[str, object]] = []
        if what.startswith("place:"):
            place = int(what[6:])
            for age in range(max(0, age_on(s.birth, a)), age_on(s.birth, b) + 1):
                year = profection(s.natal, s.doctrine, s.birth, age)
                if year.place == place:
                    hits.append(year.to_dict())
        elif what in ("peak", "loosing", "completion"):
            r = releaser(s.natal, s.doctrine, s.birth_utc, lot)
            since = datetime.combine(a, datetime.min.time())
            until = datetime.combine(b, datetime.min.time())
            for p in r.periods(until, level, since):
                flag = p.peak if what == "peak" else p.loosing if what == "loosing" else p.completion
                if flag and a.isoformat() <= p.begins < b.isoformat():
                    hits.append(p.to_dict())
        else:
            raise AstroError(f"Can't search for '{what}'.", fix="peak, loosing, completion, or place:N")

        def render(c: Console) -> None:
            for h in hits:
                if "level" in h:
                    c.print(_period_line(Period(**h)), soft_wrap=True)  # type: ignore[arg-type]
                else:
                    c.print(
                        f"age {h['age']} · {h['begins']} → {h['ends']} · {h['sign']} · lord {str(h['lord']).title()}"
                    )
            if not hits:
                c.print("nothing found in this range")

        out(ctx).emit({"pack": s.pack, "what": what, "from": a.isoformat(), "to": b.isoformat(), "hits": hits}, render)
