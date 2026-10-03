from __future__ import annotations

import json
import os
import pwd
import tomllib
from dataclasses import replace
from pathlib import Path

import pytest

from astrolog_skills.analysis.doctrine import parse_doctrine
from astrolog_skills.analysis.doctrine.conditions import conditions, exchanges
from astrolog_skills.analysis.doctrine.configurations import (
    closest,
    configurations,
    is_applying,
    overcoming,
    ray_points,
    sign_aspect,
)
from astrolog_skills.analysis.doctrine.engine import analyse
from astrolog_skills.analysis.doctrine.lots import compute_lots
from astrolog_skills.analysis.doctrine.rulers import topic
from astrolog_skills.analysis.doctrine.rules import SEVEN, Doctrine, LotRule, Scoring
from astrolog_skills.analysis.doctrine.summary import judge
from astrolog_skills.engine.model import ChartModel, Point
from astrolog_skills.engine.objects import BY_KEY
from astrolog_skills.errors import AstroError
from astrolog_skills.packs.crosscheck import astrolog_parts
from tests.conftest import run_cli

FIXTURE = Path(__file__).parent / "fixtures" / "doctrine_pack.toml"
D = parse_doctrine(tomllib.loads(FIXTURE.read_text()), "t")
assert D is not None
SPEEDS = {"sun": 1.0, "moon": 13.0, "mercury": 1.4, "venus": 1.2, "mars": 0.6, "jupiter": 0.1, "saturn": 0.05}
# far apart, in aversion-free spots that don't touch the test planets unless placed
PARK = {"sun": 200.0, "moon": 230.0, "mercury": 185.0, "venus": 215.0, "mars": 245.0, "jupiter": 260.0, "saturn": 275.0}


def chart(asc: float = 0.0, **lons: float | tuple[float, float]) -> ChartModel:
    pts = []
    for key in SEVEN:
        v = lons.get(key, PARK[key])
        lon, speed = v if isinstance(v, tuple) else (v, SPEEDS[key])
        pts.append(Point(key, BY_KEY[key].name, BY_KEY[key].glyph, lon, 0.0, speed))
    return ChartModel("t", {}, {}, pts, [], {"asc": asc, "mc": (asc + 270) % 360})


def only(d: Doctrine, *names: str) -> Doctrine:
    return replace(d, conditions={k: v for k, v in d.conditions.items() if k in names})


def found(
    c: ChartModel, *names: str, day: bool = True, target: str | None = None, actor: str | None = None
) -> list[tuple[str, str, str, str]]:
    return [
        (x.target, x.actor, x.effect, x.aspect)
        for x in conditions(c, only(D, *names), day)
        if (target is None or x.target == target) and (actor is None or x.actor == actor)
    ]


# ── configurations ────────────────────────────────────────────────────────────


def test_sign_configurations_and_overcoming() -> None:
    cap = 285.0  # a planet in Capricorn overcomes Taurus by trine, Aries by square, Pisces by sextile
    assert overcoming(cap, 45) == "trine" and overcoming(cap, 15) == "square" and overcoming(cap, 345) == "sextile"
    for later in (195, 165, 225):  # and is overcome from Libra, Virgo and Scorpio
        assert overcoming(cap, later) is None and overcoming(later, cap) in ("square", "trine", "sextile")
    assert sign_aspect(15, 195) == "opposition" and overcoming(15, 195) is None
    assert sign_aspect(15, 45) is None and sign_aspect(15, 20) == "conjunction"  # aversion; same sign


def test_rays_and_applying() -> None:
    assert ray_points(130, "trine", "backward") == [10.0] and ray_points(130, "trine", "forward") == [250.0]
    assert sorted(ray_points(130, "square", "any")) == [40.0, 220.0] and ray_points(130, "opposition", "any") == [310]
    d = closest(254.53, 16.99, "trine", "backward")
    assert d == pytest.approx(-2.46) and is_applying(d, 13.9, 1.2) and not is_applying(d, 0.5, 1.2)


def test_pairs() -> None:
    pairs = {(p.a, p.b): p for p in configurations(chart(mercury=100, jupiter=340, mars=10), SEVEN)}
    mj = pairs[("mercury", "jupiter")]
    assert mj.aspect == "trine" and mj.overcomes == "b" and not mj.domination
    mm = pairs[("mercury", "mars")]
    assert mm.aspect == "square" and mm.overcomes == "b" and mm.domination


# ── conditions (published examples where there are some) ─────────────────────


def test_overcoming_benefic_trine_or_square_malefic_square_only() -> None:
    mercury_cancer = 100.0
    assert found(chart(mercury=mercury_cancer, jupiter=345), "overcoming", target="mercury") == [
        ("mercury", "jupiter", "bonify", "trine")
    ]
    assert found(chart(mercury=mercury_cancer, jupiter=15), "overcoming", target="mercury")[0][2:] == (
        "bonify",
        "square",
    )
    assert found(chart(mercury=mercury_cancer, mars=15), "overcoming", target="mercury") == [
        ("mercury", "mars", "maltreat", "square")
    ]
    assert found(chart(mercury=mercury_cancer, mars=345), "overcoming", target="mercury") == []  # a malefic's trine


def test_opposition_and_trine() -> None:
    assert found(chart(moon=190, mars=10), "opposition_trine", target="moon") == [
        ("moon", "mars", "maltreat", "opposition")
    ]
    assert found(chart(moon=190, jupiter=70), "opposition_trine", target="moon") == [
        ("moon", "jupiter", "bonify", "trine")
    ]


def test_counteraction_by_the_lord_s_place() -> None:
    # Mercury in Capricorn (Saturn's domicile); Virgo rising; Saturn in Leo = the 12th
    c = chart(asc=160, mercury=280, saturn=130, mars=10, sun=60, moon=100)
    x = conditions(c, only(D, "counteraction"), day=False)
    assert ("mercury", "saturn", "maltreat") in [(f.target, f.actor, f.effect) for f in x]
    good = chart(asc=160, mercury=280, saturn=200)  # Saturn in Libra = the 2nd: not listed
    assert not [f for f in conditions(good, only(D, "counteraction"), True) if f.target == "mercury"]


def test_enclosure_by_rays_and_intervention() -> None:
    # Mars 11° Cancer; Venus 10° Virgo sends a sextile to 10° Cancer, Jupiter 13° Aries a square to 13° Cancer
    c = chart(mars=101, venus=160, jupiter=13)
    assert found(c, "enclosure", target="mars") == [("mars", "jupiter+venus", "bonify", "")]
    broken = chart(mars=101, venus=160, jupiter=13, mercury=102)  # a body in between: intervention
    assert found(broken, "enclosure", target="mars") == []


def test_enclosure_by_bodies() -> None:
    # the Sun at 26°14′ Aquarius between Saturn at 25° and Mars at 26°30′ Aquarius
    c = chart(sun=326.23, saturn=325.0, mars=326.5)
    assert found(c, "enclosure", target="sun") == [("sun", "mars+saturn", "maltreat", "")]


def test_adherence_needs_the_target_applying() -> None:
    assert found(chart(mercury=(108, 1.5), saturn=(110, 0.05)), "adherence", target="mercury") == [
        ("mercury", "saturn", "maltreat", "conjunction")
    ]
    assert found(chart(mercury=(112, 1.5), saturn=(110, 0.05)), "adherence", target="mercury") == []  # separating
    assert found(chart(mercury=(105, 1.5), saturn=(110, 0.05)), "adherence", target="mercury") == []  # beyond 3°
    assert found(chart(moon=(100, 13), saturn=(110, 0.05)), "adherence", target="moon")  # the Moon's 13°


def test_striking_with_a_ray_backwards() -> None:
    # the Moon at 19° Pisces applying to a square with Mars at 21° Gemini: Mars strikes it
    c = chart(moon=(349, 13), mars=(81, 0.6))
    assert found(c, "striking_with_a_ray", target="moon", actor="mars") == [("moon", "mars", "maltreat", "square")]
    # Mars earlier in the zodiac casts its square forward, not backward: no strike
    assert found(chart(moon=(171, 13), mars=(81, 0.6)), "striking_with_a_ray", target="moon", actor="mars") == []


def test_engagement_out_of_sign_with_the_moon_s_range() -> None:
    # the Moon at 28° Capricorn applying to a square with Mars at 4° Scorpio (out of sign, 6° away)
    c = chart(moon=(298, 13), mars=(214, 0.6))
    assert found(c, "engagement", target="moon", actor="mars") == [("moon", "mars", "maltreat", "square")]
    assert found(chart(moon=(310, 13), mars=(214, 0.6)), "engagement", target="moon", actor="mars") == []


def test_reception_sect_and_exchange() -> None:
    x = conditions(chart(mercury=5, mars=285), only(D, "overcoming"), day=True)
    hit = next(f for f in x if f.target == "mercury" and f.actor == "mars")
    assert hit.reception and hit.actor_of_sect is False  # Mercury in Mars's Aries; Mars contrary by day
    found_night = conditions(chart(mercury=5, mars=285), only(D, "overcoming"), day=False)
    night = next(f for f in found_night if f.target == "mercury" and f.actor == "mars")
    assert night.actor_of_sect is True
    assert exchanges(chart(sun=10, mars=130), D) == [("sun", "mars")]


# ── lots ──────────────────────────────────────────────────────────────────────


def test_lot_formulas() -> None:
    c = chart(asc=100, sun=10, moon=70, saturn=40, mars=200, jupiter=230)
    day = compute_lots(c, D, day=True)
    night = compute_lots(c, D, day=False)
    assert day["fortune"].lon == 160 and night["fortune"].lon == 40 and night["fortune"].reversed
    assert day["spirit"].lon == 40 and night["spirit"].lon == 160
    assert day["eros"].lon == (100 + (40 - 160)) % 360  # Fortune → Spirit, projected from the Ascendant
    assert day["exaltation"].lon == 100 + 350 - 360  # Sun → 0° Aries
    assert night["exaltation"].lon == 100 + 30 - 70 + 360 - 360  # Moon → 0° Taurus
    assert day["death"].lon == (40 + (((90 + 7 * 30) % 360) - 70)) % 360  # Moon → place 8, from Saturn
    assert day["livelihood"].points == ("ruler:place:2", "place:2")
    # Foundation: the shorter way between Fortune and Spirit, so always below the horizon
    assert day["foundation"].lon == 100 + 120 and night["foundation"].lon == 100 + 120
    assert day["fortune"].sign == "Virgo" and day["fortune"].place == 3 and day["fortune"].lord == "mercury"


def test_lot_fallback_and_versions() -> None:
    near = chart(asc=0, sun=10, saturn=20, mars=200, jupiter=230)  # Saturn under the beams
    assert compute_lots(near, D, True)["father"].fallback
    far = chart(asc=0, sun=10, saturn=100)
    assert not compute_lots(far, D, True)["father"].fallback
    later = replace(D, lots={**D.lots, "eros": replace(D.lots["eros"], version="later")})
    assert compute_lots(far, later, True)["eros"].points == ("lot:spirit", "venus")
    loop = replace(D, lots={"a": LotRule("a", points=("lot:b", "sun")), "b": LotRule("b", points=("lot:a", "sun"))})
    with pytest.raises(AstroError):
        compute_lots(far, loop, True)


# ── rulers, checklist, summary ────────────────────────────────────────────────


def test_lot_checklist() -> None:
    # a lot in Aries (place 1, a good place); its lord Mars in Leo (place 5, configured by trine)
    c = chart(asc=5, mars=130, jupiter=250, venus=40, saturn=190, sun=300)
    t = topic("lot:x", 10, c, D, True, [])
    assert t.lord == "mars" and t.lord_place == 5 and t.sign == "Aries"
    for token in (
        "lot_good_place", "lord_malefic", "lord_good_place", "lord_configured", "benefic_configured",
        "malefic_configured", "lord_not_bonified", "lord_not_maltreated", "lord_not_under_beams",
    ):  # fmt: skip
        assert token in t.checklist, (token, t.checklist)
    # one benefic sees the lot (Jupiter by trine), so "benefics in aversion" does not hold
    assert "benefic_in_aversion" not in t.checklist
    blind = topic("lot:x", 10, chart(asc=5, mars=130, jupiter=40, venus=160, saturn=190, sun=300), D, True, [])
    assert "benefic_in_aversion" in blind.checklist and "benefic_configured" not in blind.checklist


def test_judge_with_lists_and_weights() -> None:
    s = Scoring(good=("domicile",), bad=("retrograde",), weights={"domicile": 5, "retrograde": -3}, mode="weights")
    j = judge(["domicile", "retrograde", "angular"], s)
    assert j.good == ["domicile"] and j.bad == ["retrograde"] and j.score == 2
    assert judge(["domicile"], None).good == []


def test_analyse_has_everything() -> None:
    c = chart(asc=100, sun=345, moon=(255, 13.9), mercury=(3, 1.9), venus=17, mars=297, jupiter=327, saturn=4)
    r = analyse(c, D)
    data = json.loads(json.dumps(r.to_dict()))
    assert set(data) >= {"conditions", "lots", "lot_topics", "places", "testimony", "configurations", "exchanges"}
    assert len(data["places"]) == 12 and data["places"][0]["lord"] == "moon"
    assert "bonified" in data["testimony"]["moon"]["tokens"] and "bonified" in data["testimony"]["moon"]["good"]


# ── Astrolog's parts ──────────────────────────────────────────────────────────

SAMPLE = """Num.                    Name Position House Formula              Flip Type
  1:                 Fortune  2Ari39 [10th] (Asc   - Sun   + Moo   Y)
  6:        Property & Goods 25Aqu44 [ 9th] (Asc   -   2 R +   2   Y)
 13:          Expected Birth 24Vir36 [ 4th] (Asc   - Moo   + Moo R N)
 36:       Glory & Constancy 29Cap36 [ 8th] (Asc   - For   + Spi   Y)
"""


def test_astrolog_parts_parser() -> None:
    parts = astrolog_parts(SAMPLE)
    assert parts[("sun", "moon")] == ("Fortune", pytest.approx(2 + 39 / 60))
    assert parts[("lot:fortune", "lot:spirit")][1] == pytest.approx(9 * 30 + 29 + 36 / 60)
    assert len(parts) == 2  # ruler and house operands are skipped
    assert astrolog_parts("no parts here") == {}


# ── command and the real Astrolog ─────────────────────────────────────────────


def test_cli_sections(fake_astrolog: Path) -> None:
    from astrolog_skills.packs import loader

    pack = loader.user_dir() / "doctrine-test"
    pack.mkdir(parents=True)
    (pack / "method.toml").write_text(FIXTURE.read_text())
    add = ("chart", "add", "Ein", "--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00")
    assert run_cli(*add).returncode == 0
    shown = run_cli("doctrine", "--chart", "Ein", "--pack", "doctrine-test", "--show", "all")
    assert shown.returncode == 0 and "Lots" in shown.stdout and "Testimony" in shown.stdout
    bad = run_cli("doctrine", "--chart", "Ein", "--pack", "doctrine-test", "--show", "wheel")
    assert bad.returncode != 0 and "Unknown section" in (bad.stdout + bad.stderr)


@pytest.fixture
def real(monkeypatch: pytest.MonkeyPatch) -> Path:
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    for candidate in (os.environ.get("REAL_ASTROLOG", ""), str(home / "astrolog" / "astrolog")):
        if candidate and Path(candidate).is_file():
            monkeypatch.setenv("ASTROLOG_BIN", candidate)
            return Path(candidate)
    pytest.skip("no real Astrolog found")


@pytest.mark.astrolog
def test_einstein_moon_bonified_by_venus_ray(real: Path) -> None:
    from astrolog_skills.engine import profile as P
    from astrolog_skills.engine.cast import cast
    from astrolog_skills.engine.moment import Moment

    c = cast(Moment("1879-03-14", "11:30", "LMT", 48.4, 10.0, "Einstein"), P.load("default"))
    r = analyse(c, D)
    ray = next(x for x in r.conditions if x.target == "moon" and x.condition == "striking_with_a_ray")
    assert ray.actor == "venus" and ray.effect == "bonify" and ray.aspect == "trine" and ray.applying
    assert ray.distance == pytest.approx(2.46, abs=0.01)


@pytest.mark.astrolog
def test_lots_match_astrolog(real: Path) -> None:
    from astrolog_skills.packs.crosscheck import lots_against_astrolog

    result = lots_against_astrolog(D)
    assert {"fortune", "spirit", "eros"} <= set(result.checked)
    assert not [p for p in result.problems if p.level == "error"]
