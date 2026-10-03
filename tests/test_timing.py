from __future__ import annotations

import json
import tomllib
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from astrolog_skills.analysis.doctrine import parse_doctrine
from astrolog_skills.analysis.doctrine.rules import SEVEN, SIGN_KEYS
from astrolog_skills.analysis.timing.ascension import ascensional_times
from astrolog_skills.analysis.timing.profections import age_on, anniversary, profection
from astrolog_skills.analysis.timing.releasing import Releaser, current
from astrolog_skills.analysis.timing.sect_light import sect_light_lords
from astrolog_skills.analysis.timing.transits import time_lord_transits
from astrolog_skills.engine.model import ChartModel, Point
from astrolog_skills.engine.objects import BY_KEY
from astrolog_skills.errors import AstroError
from tests.conftest import run_cli

FIXTURE = Path(__file__).parent / "fixtures" / "doctrine_pack.toml"
D = parse_doctrine(tomllib.loads(FIXTURE.read_text()), "t")
assert D is not None and D.releasing is not None


def chart(asc: float = 100.0, **lons: float) -> ChartModel:
    park = {"sun": 345.0, "moon": 255.0, "mercury": 3.0, "venus": 17.0, "mars": 297.0, "jupiter": 327.0, "saturn": 4.0}
    pts = [Point(k, BY_KEY[k].name, BY_KEY[k].glyph, lons.get(k, park[k]), 0.0, 0.5) for k in SEVEN]
    return ChartModel("t", {}, {}, pts, [], {"asc": asc, "mc": (asc + 270) % 360})


# ── profections ───────────────────────────────────────────────────────────────


def test_birthdays_and_ages() -> None:
    assert anniversary(date(2000, 2, 29), 1) == date(2001, 2, 28) and anniversary(date(2000, 2, 29), 4) == date(
        2004, 2, 29
    )
    assert age_on(date(1990, 6, 15), date(2020, 6, 14)) == 29 and age_on(date(1990, 6, 15), date(2020, 6, 15)) == 30


def test_profection_years() -> None:
    c = chart(asc=100)  # Cancer rising
    first = profection(c, D, date(1879, 3, 14), 0)
    assert (first.sign, first.place, first.lord, first.begins) == ("Cancer", 1, "moon", "1879-03-14")
    y13 = profection(c, D, date(1879, 3, 14), 13)
    assert (y13.sign, y13.place, y13.lord, y13.ends) == ("Leo", 2, "sun", "1893-03-14")
    assert profection(c, D, date(1879, 3, 14), 21).sign == "Aries"  # the tenth place at 21, 33, 45 …
    # planets in the profected sign (Mercury and Saturn in Aries) are activated
    assert profection(c, D, date(1879, 3, 14), 9).planets_in_sign == ["mercury", "venus", "saturn"]


def test_profection_starting_points() -> None:
    c = chart(asc=100)  # the Sun at 345 is above the horizon: a day chart
    assert profection(c, D, date(2000, 1, 1), 0, "sect_light").sign == "Pisces"
    assert profection(c, D, date(2000, 1, 1), 0, "contrary_light").sign == "Sagittarius"
    assert profection(c, D, date(2000, 1, 1), 1, "place:10").sign == "Taurus"
    assert profection(c, D, date(2000, 1, 1), 0, "lot:fortune").sign
    with pytest.raises(AstroError):
        profection(c, D, date(2000, 1, 1), 0, "lot:nowhere")


# ── the sect light's lords ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("lat", "row"),
    [  # a published table of ascensional times: Aries, Taurus, Gemini, Cancer, Leo, Virgo
        (0, (27.91, 29.90, 32.18, 32.18, 29.90, 27.91)),
        (30, (21.18, 24.40, 29.91, 34.44, 35.40, 34.63)),
        (48, (14.88, 18.88, 27.44, 36.91, 40.92, 40.93)),
    ],
)
def test_ascensional_times_match_the_table(lat: float, row: tuple[float, ...]) -> None:
    times = ascensional_times(lat)
    assert [times[s] for s in SIGN_KEYS[:6]] == pytest.approx(list(row), abs=0.02)
    assert times["pisces"] == pytest.approx(times["aries"], abs=0.01)  # signs of equal declination rise alike
    assert sum(times.values()) == pytest.approx(360, abs=0.05)
    with pytest.raises(AstroError):
        ascensional_times(70)


def test_sect_light_lords_and_changeover() -> None:
    day = sect_light_lords(chart(asc=100), D, 48.4)  # Sun in Pisces by day: Venus, Mars, the Moon
    assert day.light == "sun" and [x.planet for x in day.lords] == ["venus", "mars", "moon"]
    assert [x.quality for x in day.lords] == ["good", "good", "bad"]  # places 10, 7, 6
    by = {c["method"]: c for c in day.changeover}
    assert by["minor_years"]["years"] == 15 and by["minor_years"]["ages"] == [14, 15]  # Mars: 15
    assert by["ascensional_time"]["years"] == ascensional_times(48.4)["capricorn"]
    night = sect_light_lords(chart(asc=100, sun=150), D, 48.4)  # Sun below: the Moon in Sagittarius by night
    assert night.light == "moon" and [x.planet for x in night.lords] == ["jupiter", "sun", "saturn"]


# ── releasing: published dated tables (start sign + birth date only) ─────────


def run(
    start: str, born: date, until: date, fortune: str = "aries", levels: int = 2
) -> list[tuple[int, str, str, bool, bool]]:
    assert D is not None and D.releasing is not None
    r = Releaser(
        D.releasing, "spirit", SIGN_KEYS.index(start), datetime.combine(born, datetime.min.time()),
        SIGN_KEYS.index(fortune), {}, {}, "", "",
    )  # fmt: skip
    return [
        (p.level, p.sign, p.begins, p.loosing, p.completion)
        for p in r.periods(datetime.combine(until, datetime.min.time()), levels)
    ]


def test_releasing_dates_with_a_loosing_of_the_bond() -> None:
    rows = run("virgo", date(1944, 5, 14), date(1974, 1, 1))
    starts = {(lv, s): b for lv, s, b, *_ in rows}
    l2 = [(s, b) for lv, s, b, *_ in rows if lv == 2]
    assert l2[:12] == [
        ("Virgo", "1944-05-14"), ("Libra", "1946-01-04"), ("Scorpio", "1946-09-01"), ("Sagittarius", "1947-11-25"),
        ("Capricorn", "1948-11-19"), ("Aquarius", "1951-02-07"), ("Pisces", "1953-07-26"), ("Aries", "1954-07-21"),
        ("Taurus", "1955-10-14"), ("Gemini", "1956-06-10"), ("Cancer", "1958-01-31"), ("Leo", "1960-02-20"),
    ]  # fmt: skip
    loosing = [r for r in rows if r[3]]
    assert loosing == [(2, "Pisces", "1961-09-12", True, False)]  # jumps from Virgo to its opposite
    assert starts[(1, "Libra")] == "1964-01-30" and starts[(1, "Scorpio")] == "1971-12-19"


def test_releasing_other_tables() -> None:
    gore = run("scorpio", date(1948, 3, 31), date(1964, 1, 1))
    l2 = [b for lv, s, b, *_ in gore if lv == 2]
    assert l2[1:4] == ["1949-06-24", "1950-06-19", "1952-09-06"]
    assert (1, "Sagittarius", "1963-01-12", False, False) in gore
    arnold = run("sagittarius", date(1947, 7, 30), date(2005, 1, 1), fortune="aquarius")
    assert (1, "Capricorn", "1959-05-28", False, False) in arnold and (
        1,
        "Aquarius",
        "1986-01-06",
        False,
        False,
    ) in arnold
    assert (2, "Cancer", "1976-09-25", True, False) in arnold  # Capricorn's loosing
    assert (2, "Capricorn", "1984-11-12", False, True) in arnold  # back to Capricorn: a completion
    assert (2, "Leo", "2003-05-07", True, False) in arnold  # Aquarius's loosing


def test_releasing_levels_and_flags() -> None:
    assert D is not None and D.releasing is not None
    born = datetime(2000, 1, 1)
    # Fortune in Aries: Capricorn is the 10th from it (peak 2 in the pack's ranking), Taurus the 2nd (an end)
    r = Releaser(D.releasing, "spirit", 9, born, 0, {"saturn": 6, "mars": 9}, {"capricorn": "saturn"}, "", "mars")
    first = r.periods(born + timedelta(days=10), 4)
    assert [p.level for p in first[:4]] == [1, 2, 3, 4]  # level 4 Capricorn: 27 × 5 hours
    l1 = first[0]
    assert (l1.sign, l1.lord, l1.from_fortune, l1.peak, l1.triad) == ("Capricorn", "saturn", 10, 2, "angle")
    assert l1.in_sign == ["mars"] and l1.superior_square == ["saturn"] and l1.malefic_angle
    lengths = [(datetime.fromisoformat(p.ends) - datetime.fromisoformat(p.begins)).days for p in first]
    assert lengths[1] == 27 * 30  # 27 months of 30 days
    on = current(r.periods(datetime(2001, 1, 2), 2), "2001-01-01")
    assert [p.level for p in on] == [1, 2]


def test_spirit_moves_on_from_fortune_s_sign() -> None:
    from astrolog_skills.analysis.timing.releasing import releaser

    # Sun and Moon together make Fortune and Spirit fall on the Ascendant's sign
    c = chart(asc=100, sun=200, moon=200)
    r = releaser(c, D, datetime(2000, 1, 1), "spirit")
    assert r.shifted and r.start_sign == (r.fortune_sign + 1) % 12
    no_shift = replace(D, releasing=replace(D.releasing, same_sign_shift=False))
    assert not releaser(c, no_shift, datetime(2000, 1, 1), "spirit").shifted


# ── time-lord transits ────────────────────────────────────────────────────────


def test_time_lord_transits() -> None:
    c = chart(asc=100)  # Cancer rising; at age 0 the year is Cancer, its lord the Moon
    birth = date(2000, 1, 1)
    others = {
        "sun": (280.0, 1.0),
        "moon": (10.0, 13.0),
        "mercury": (270.0, 1.2),
        "venus": (300.0, 1.2),
        "jupiter": (40.0, 0.1),
        "saturn": (50.0, 0.05),
    }
    days = [
        (date(2000, 6, 1), {**others, "mars": (89.6, 0.6)}),
        (date(2000, 6, 2), {**others, "mars": (90.2, 0.6)}),  # Mars enters Cancer, the profected sign
    ]
    events = time_lord_transits(c, D, birth, days)
    ingress = [e for e in events if e.kind == "ingress"]
    assert [(e.planet, e.sign, e.why) for e in ingress] == [("mars", "Cancer", ["into the profected sign"])]
    # the lord of the year (the Moon) is ignored for exact hits (too fast) but Saturn as a planet in the sign counts
    lord_year = date(2009, 6, 1)  # age 9: Aries, with Mercury, Venus and Saturn natally there
    near = {**others, "mars": (200.0, 0.6), "saturn": (2.9, 0.05)}
    after = {**near, "saturn": (3.1, 0.05)}
    hits = time_lord_transits(c, D, birth, [(lord_year, near), (lord_year + timedelta(days=1), after)])
    exact = [(e.planet, e.target, e.aspect) for e in hits if e.kind == "exact"]
    assert ("saturn", "mercury", "conjunction") in exact
    assert not [e for e in hits if e.planet == "jupiter"]


# ── command ───────────────────────────────────────────────────────────────────


def test_timing_cli(fake_astrolog: Path) -> None:
    from astrolog_skills.packs import loader

    pack = loader.user_dir() / "doctrine-test"
    pack.mkdir(parents=True)
    (pack / "method.toml").write_text(FIXTURE.read_text())
    add = ("chart", "add", "Ein", "--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00")
    assert run_cli(*add).returncode == 0
    base = ("--chart", "Ein", "--pack", "doctrine-test")
    years = json.loads(run_cli("--json", "timing", "profections", *base, "--age", "26", "--years", "2").stdout)
    assert len(years["years"]) == 6 and years["years"][0]["begins"] == "1905-03-14"
    lords = json.loads(run_cli("--json", "timing", "lords", *base).stdout)
    assert len(lords["lords"]) == 3 and lords["changeover"]
    rel = json.loads(
        run_cli("--json", "timing", "releasing", *base, "--from", "1879-03-14", "--to", "1900-01-01").stdout
    )
    assert rel["periods"][0]["begins"] == "1879-03-14" and rel["mode"] == "range"
    now = json.loads(run_cli("--json", "timing", "releasing", *base, "--on", "1905-06-30").stdout)
    assert [p["level"] for p in now["periods"]] == [1, 2]
    found = json.loads(
        run_cli(
            "--json", "timing", "search", *base, "--what", "place:10", "--from", "1900-01-01", "--to", "1930-01-01"
        ).stdout
    )
    assert [h["age"] for h in found["hits"]] == [21, 33, 45]
    bad = run_cli("timing", "search", *base, "--what", "eclipse")
    assert bad.returncode != 0
    shown = run_cli("timing", "transits", *base, "--from", "1905-01-01", "--days", "20")
    assert shown.returncode == 0, shown.stderr


@pytest.mark.parametrize(
    ("age", "place"),
    # published profection examples: an age and the place it activates
    [(25, 2), (38, 3), (51, 4), (28, 5), (29, 6), (18, 7), (55, 8), (20, 9), (46, 11), (47, 12), (27, 4), (23, 12)],
)
def test_the_source_s_profection_examples(age: int, place: int) -> None:
    assert profection(chart(asc=100), D, date(1950, 1, 1), age).place == place


def test_no_duplicate_hits_and_no_monthly_moon() -> None:
    c = chart(asc=100)  # at age 9 the year is Aries; Saturn (natally in Aries) is activated
    birth = date(2000, 1, 1)
    base = {
        "sun": (280.0, 1.0),
        "mercury": (270.0, 1.2),
        "venus": (300.0, 1.2),
        "mars": (200.0, 0.6),
        "jupiter": (40.0, 0.1),
    }
    natal_mc = c.angles["mc"]
    before = {**base, "moon": (359.5, 13.0), "saturn": ((natal_mc + 180 - 0.1) % 360, 0.05)}
    after = {**base, "moon": (12.0, 13.0), "saturn": ((natal_mc + 180 + 0.1) % 360, 0.05)}
    events = time_lord_transits(c, D, birth, [(date(2009, 6, 1), before), (date(2009, 6, 2), after)])
    hits = [(e.planet, e.target, e.aspect) for e in events if e.kind == "exact" and e.target == "mc"]
    assert hits.count(("saturn", "mc", "opposition")) == 1
    assert not [e for e in events if e.planet == "moon" and e.kind == "ingress"]
