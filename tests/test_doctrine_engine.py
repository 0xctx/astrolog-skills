from __future__ import annotations

import json
import os
import pwd
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from astrolog_skills.analysis.doctrine import parse_doctrine
from astrolog_skills.analysis.doctrine.dignities import decan_ruler, lords, planet_dignities, twelfth_part
from astrolog_skills.analysis.doctrine.engine import analyse
from astrolog_skills.analysis.doctrine.phase import planet_phase
from astrolog_skills.analysis.doctrine.places import planet_place, triad_angle
from astrolog_skills.analysis.doctrine.rules import Doctrine, Rejoicing
from astrolog_skills.analysis.doctrine.sect import above_horizon, chart_sect, morning_star, planet_sect
from astrolog_skills.engine.model import ChartModel, Point
from astrolog_skills.engine.objects import BY_KEY
from astrolog_skills.packs import loader
from tests.conftest import run_cli

FIXTURE = Path(__file__).parent / "fixtures" / "doctrine_pack.toml"


def doctrine() -> Doctrine:
    d = parse_doctrine(tomllib.loads(FIXTURE.read_text()), "t")
    assert d is not None
    return d


D = doctrine()
assert D.sect and D.dignities and D.phase and D.places
SECT, DIG, PHASE, PLACES = D.sect, D.dignities, D.phase, D.places


def chart(asc: float, **lons: float | tuple[float, float]) -> ChartModel:
    pts = []
    for key in ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn"):
        v = lons.get(key, 0.0)
        lon, speed = v if isinstance(v, tuple) else (v, 0.5)
        pts.append(Point(key, BY_KEY[key].name, BY_KEY[key].glyph, lon, 0.0, speed))
    return ChartModel("t", {}, {}, pts, [], {"asc": asc, "mc": (asc + 270) % 360})


# ── sect ──────────────────────────────────────────────────────────────────────


def test_day_and_night_by_the_horizon_degrees() -> None:
    assert above_horizon(200, 0) and not above_horizon(100, 0) and above_horizon(180, 0) and not above_horizon(0, 0)
    day = chart_sect(SECT, sun=200, asc=0)
    night = chart_sect(SECT, sun=100, asc=0)
    assert (day.day, day.light, day.benefic, day.malefic) == (True, "sun", "jupiter", "saturn")
    assert (night.day, night.light, night.benefic, night.malefic) == (False, "moon", "venus", "mars")


def test_mercury_sect_by_morning_or_evening() -> None:
    assert morning_star(80, 100) and not morning_star(120, 100) and morning_star(350, 10)
    early = planet_sect("mercury", 80, 100, 0, True, SECT, DIG)
    late = planet_sect("mercury", 120, 100, 0, True, SECT, DIG)
    assert (early.sect, early.of_sect, early.note) == ("diurnal", True, "morning star")
    assert (late.sect, late.of_sect, late.note) == ("nocturnal", False, "evening star")
    unresolved = planet_sect("mercury", 80, 100, 0, True, replace(SECT, mercury="configured_with"), DIG)
    assert unresolved.sect == "" and unresolved.of_sect is None and "not computed" in unresolved.note


def test_rejoicing_by_hemisphere() -> None:
    # day chart (Sun above): diurnal planets rejoice above, nocturnal ones below
    assert planet_sect("jupiter", 200, 200, 0, True, SECT, DIG).rejoices_hemisphere is True
    assert planet_sect("jupiter", 100, 200, 0, True, SECT, DIG).rejoices_hemisphere is False
    assert planet_sect("mars", 100, 200, 0, True, SECT, DIG).rejoices_hemisphere is True
    # night chart: the reverse
    assert planet_sect("jupiter", 100, 50, 0, False, SECT, DIG).rejoices_hemisphere is True
    assert planet_sect("mars", 200, 50, 0, False, SECT, DIG).rejoices_hemisphere is True
    off = replace(SECT, rejoicing=Rejoicing(by_hemisphere=False))
    assert planet_sect("mars", 200, 50, 0, False, off, DIG).rejoices_hemisphere is None


@pytest.mark.parametrize(
    ("by_sign", "jupiter_leo", "jupiter_taurus", "mars_taurus"),
    [
        ("gender", True, False, True),  # Leo masculine, Taurus feminine
        ("hemisphere", True, False, True),  # Leo in the diurnal half, Taurus in the nocturnal half
        ("domicile_lord", True, False, True),  # Leo's lord the Sun (diurnal), Taurus's lord Venus (nocturnal)
        ("none", None, None, None),
    ],
)
def test_rejoicing_by_sign(by_sign: str, jupiter_leo: bool, jupiter_taurus: bool, mars_taurus: bool) -> None:
    rules = replace(SECT, rejoicing=Rejoicing(True, by_sign))
    assert planet_sect("jupiter", 125, 200, 0, True, rules, DIG).rejoices_sign is jupiter_leo
    assert planet_sect("jupiter", 45, 200, 0, True, rules, DIG).rejoices_sign is jupiter_taurus
    assert planet_sect("mars", 45, 200, 0, True, rules, DIG).rejoices_sign is mars_taurus
    # Capricorn is feminine (earth) but in the diurnal half
    if by_sign == "hemisphere":
        assert planet_sect("jupiter", 280, 200, 0, True, rules, DIG).rejoices_sign is True


# ── dignities ─────────────────────────────────────────────────────────────────


def test_mars_dignity_details() -> None:
    aries = planet_dignities("mars", 5, DIG, True)
    assert aries.domicile and aries.decan and not aries.bounds and aries.lords.bounds == "jupiter"
    cap = planet_dignities("mars", 298, DIG, True)
    assert cap.exaltation and cap.exaltation_degree == 28 and cap.bounds and cap.lords.domicile == "saturn"
    assert planet_dignities("mars", 190, DIG, True).adversity
    assert planet_dignities("mars", 100, DIG, True).depression


def test_triplicity_sect_ruler_switches_with_sect() -> None:
    # fire: Sun (day), Jupiter (night), Saturn (participating)
    assert lords(5, DIG, day=True).triplicity == ("sun", "jupiter", "saturn")
    assert lords(5, DIG, day=False).triplicity == ("jupiter", "sun", "saturn")
    assert planet_dignities("jupiter", 5, DIG, day=False).triplicity == "sect ruler"
    assert planet_dignities("jupiter", 5, DIG, day=True).triplicity == "out-of-sect ruler"
    assert planet_dignities("saturn", 5, DIG, day=True).triplicity == "participating"


@pytest.mark.parametrize(("lon", "ruler"), [(5.999, "jupiter"), (6.0, "venus"), (29.99, "saturn"), (330, "venus")])
def test_bounds_edges(lon: float, ruler: str) -> None:
    assert lords(lon, DIG, True).bounds == ruler


@pytest.mark.parametrize(
    ("lon", "ruler"),
    [(0, "mars"), (10, "sun"), (20, "venus"), (30, "mercury"), (255, "moon"), (350, "mars"), (359.9, "mars")],
)
def test_chaldean_decans(lon: float, ruler: str) -> None:
    assert decan_ruler(lon, DIG) == ruler


def test_decan_table_scheme() -> None:
    table = replace(DIG, decan_scheme="table", decans={"aries": ("jupiter", "moon", "saturn")})
    assert decan_ruler(15, table) == "moon" and decan_ruler(45, table) == ""


def test_twelfth_parts() -> None:
    assert twelfth_part(2.5, 12) == 30  # Aries 2½° → Taurus
    assert twelfth_part(359, 12) == pytest.approx(318)  # Pisces 29° → Aquarius 18°
    assert twelfth_part(2.5, 13) == pytest.approx(32.5)
    assert planet_dignities("sun", 2.5, DIG, True).twelfth_part == 30
    assert planet_dignities("sun", 2.5, replace(DIG, twelfth_parts=0), True).twelfth_part is None


# ── solar phase ───────────────────────────────────────────────────────────────


def test_under_the_beams_weak_zone_and_heart() -> None:
    p = planet_phase("venus", 114.9, 1.2, 100, PHASE, None)
    assert p.under_beams and not p.weak and not p.in_heart and p.labels()[0] == "under the beams"
    assert not planet_phase("venus", 115.1, 1.2, 100, PHASE, None).under_beams
    assert planet_phase("venus", 91.5, 1.2, 100, PHASE, None).weak
    heart = planet_phase("venus", 100.5, 1.2, 100, PHASE, None)
    assert heart.in_heart and heart.labels()[0] == "in the heart"
    assert planet_phase("venus", 355, 1.2, 5, PHASE, None).under_beams  # across 0° Aries


def test_chariot_needs_the_beams_and_a_listed_dignity() -> None:
    mars_aries = planet_phase("mars", 12, 0.7, 20, PHASE, planet_dignities("mars", 12, DIG, True))
    assert mars_aries.under_beams and mars_aries.chariot == ("domicile",) and "in its chariot" in mars_aries.labels()
    far = planet_phase("mars", 12, 0.7, 60, PHASE, planet_dignities("mars", 12, DIG, True))
    assert far.chariot == ()
    no_trip = planet_phase("saturn", 12, 0.1, 20, PHASE, planet_dignities("saturn", 12, DIG, True))
    assert no_trip.chariot == ()  # triplicity isn't in the fixture's chariot list
    with_trip = planet_phase(
        "saturn", 12, 0.1, 20, replace(PHASE, chariot=("triplicity",)), planet_dignities("saturn", 12, DIG, True)
    )
    assert with_trip.chariot == ("triplicity",)


def test_morning_and_evening_risers() -> None:
    assert planet_phase("jupiter", 80, 0.1, 100, PHASE, None).labels()[:1] == ["morning riser"]
    near = planet_phase("jupiter", 90, 0.1, 100, PHASE, None)
    assert near.star == "morning" and not near.visible
    assert planet_phase("venus", 130, 1.2, 100, PHASE, None).star == "evening"
    assert planet_phase("moon", 130, 13, 100, PHASE, None).star == ""


def test_heliacal_emerging_and_sinking() -> None:
    emerging = planet_phase("mercury", 110, 1.9, 100, PHASE, None, later=(124, 107))
    sinking = planet_phase("mars", 120, 0.6, 100, PHASE, None, later=(112, 107))
    steady = planet_phase("saturn", 180, 0.1, 100, PHASE, None, later=(180, 107))
    assert (emerging.heliacal, sinking.heliacal, steady.heliacal) == ("emerging", "sinking", "")
    assert planet_phase("moon", 110, 13, 100, PHASE, None, later=(200, 107)).heliacal == ""
    off = replace(PHASE, heliacal_days=0)
    assert planet_phase("mercury", 110, 1.9, 100, off, None, later=(124, 107)).heliacal == ""


def test_speed_and_retrograde() -> None:
    fast = planet_phase("mars", 200, 0.7, 100, PHASE, None)
    slow = planet_phase("mars", 200, 0.3, 100, PHASE, None)
    retro = planet_phase("mars", 200, -0.2, 100, PHASE, None)
    assert (fast.speed, slow.speed, retro.retrograde) == ("additive", "subtractive", True)
    assert "retrograde" in retro.labels() and "subtractive" not in retro.labels()
    station = replace(PHASE, stationary_ratio=0.1)
    assert planet_phase("mars", 200, 0.02, 100, station, None).speed == "stationary"
    assert planet_phase("mars", 200, 0.3, 100, replace(PHASE, mean_motion={"mars": 0.2}), None).speed == "additive"
    sun = planet_phase("sun", 100, 1.01, 100, PHASE, None)
    assert sun.distance is None and sun.speed == "additive" and not sun.under_beams


# ── places ────────────────────────────────────────────────────────────────────


def test_triads() -> None:
    assert {n: triad_angle(n) for n in range(1, 13)} == {
        1: 1, 2: 1, 12: 1, 3: 4, 4: 4, 5: 4, 6: 7, 7: 7, 8: 7, 9: 10, 10: 10, 11: 10
    }  # fmt: skip


def test_places_from_the_pack() -> None:
    asc = 100  # Cancer rising
    moon = planet_place("moon", 255, asc, PLACES)  # Sagittarius → 6th
    assert (moon.place, moon.angularity, moon.triad, moon.good, moon.busy) == (6, "declining", 7, False, False)
    venus = planet_place("venus", 17, asc, PLACES)  # Aries → 10th
    assert (venus.place, venus.angularity, venus.good, venus.busy, venus.joy) == (10, "angular", True, True, False)
    sun = planet_place("sun", 345, asc, PLACES)  # Pisces → 9th, the Sun's joy in the fixture
    assert sun.place == 9 and sun.joy and "its joy" in sun.labels()
    bare = planet_place("sun", 345, asc, None)
    assert bare.good is None and bare.busy is None and not bare.joy


# ── the whole chart ───────────────────────────────────────────────────────────


def test_analyse_whole_chart_with_citations() -> None:
    c = chart(100, sun=345, moon=(255, 13.9), mercury=(3, 1.9), venus=17, mars=297, jupiter=327, saturn=4)
    r = analyse(c, D)
    assert r.day and r.sect and r.sect.light == "sun" and r.asc_place_sign == "Cancer"
    assert [p.key for p in r.planets] == ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn"]
    assert r.planet("moon").place.place == 6 and r.planet("venus").place.place == 10
    assert r.planet("mercury").sect.sect == "nocturnal"  # type: ignore[union-attr]
    assert {k: r.cites[k] for k in ("sect", "dignities", "phase", "places")} == {
        "sect": "p. 1", "dignities": "p. 2", "phase": "p. 12", "places": "p. 7"
    }  # fmt: skip
    assert r.cites["conditions.striking_with_a_ray"] == "p. 6" and r.cites["lots.fortune"] == "p. 3"
    assert any("heliacal" in n for n in r.notes)
    data = r.to_dict()
    assert json.dumps(data) and data["planets"][4]["dignities"]["exaltation"] is True
    close = chart(100, sun=355, mercury=(3, 1.9))
    later = chart(100, sun=2, mercury=20)
    assert analyse(close, D, later).planet("mercury").phase.heliacal == "emerging"  # type: ignore[union-attr]


def test_analyse_with_only_some_sections() -> None:
    c = chart(100, sun=345)
    r = analyse(c, Doctrine(places=PLACES))
    assert r.sect is None and r.planet("sun").dignities is None and r.planet("sun").place.place == 9
    from astrolog_skills.errors import AstroError

    with pytest.raises(AstroError):
        analyse(c, Doctrine(lots=D.lots))


# ── command ───────────────────────────────────────────────────────────────────


def test_doctrine_cli(fake_astrolog: Path) -> None:
    pack = loader.user_dir() / "doctrine-test"
    pack.mkdir(parents=True)
    (pack / "method.toml").write_text(FIXTURE.read_text())
    add = ("chart", "add", "Ein", "--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00")
    assert run_cli(*add).returncode == 0
    res = run_cli("--json", "doctrine", "--chart", "Ein", "--pack", "doctrine-test")
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["pack"] == "doctrine-test" and len(data["planets"]) == 7 and data["cites"]["phase"] == "p. 12"
    assert not any("heliacal" in n for n in data["notes"])  # the later chart was cast
    shown = run_cli("doctrine", "--chart", "Ein", "--pack", "doctrine-test")
    assert shown.returncode == 0 and "rising" in shown.stdout and "p. 12" not in shown.stdout  # citations off
    cited = run_cli("--cite", "doctrine", "--chart", "Ein", "--pack", "doctrine-test")
    assert cited.returncode == 0 and "phase p. 12" in cited.stdout
    missing = run_cli("--json", "doctrine", "--chart", "Ein", "--pack", "psychological")
    assert missing.returncode != 0 and "no doctrine" in (missing.stdout + missing.stderr)


# ── against the real Astrolog ─────────────────────────────────────────────────


@pytest.fixture
def real(monkeypatch: pytest.MonkeyPatch) -> Path:
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    for candidate in (os.environ.get("REAL_ASTROLOG", ""), str(home / "astrolog" / "astrolog")):
        if candidate and Path(candidate).is_file():
            monkeypatch.setenv("ASTROLOG_BIN", candidate)
            return Path(candidate)
    pytest.skip("no real Astrolog found")


@pytest.mark.astrolog
def test_einstein_as_the_worked_example_describes(real: Path) -> None:
    from astrolog_skills.engine import profile as P
    from astrolog_skills.engine.cast import cast
    from astrolog_skills.engine.moment import Moment

    c = cast(Moment("1879-03-14", "11:30", "LMT", 48.4, 10.0, "Einstein"), P.load("default"))
    r = analyse(c, D)
    # a day chart with Cancer rising, the Moon in the 6th place and Venus in the 10th
    assert r.day and r.asc_place_sign == "Cancer"
    assert r.planet("moon").place.place == 6 and r.planet("venus").place.place == 10
    mercury = r.planet("mercury").phase
    assert mercury and mercury.under_beams and mercury.star == "evening"
