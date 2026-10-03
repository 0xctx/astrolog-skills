from __future__ import annotations

from itertools import combinations
from pathlib import Path

import pytest

from astrolog_skills.analysis.aspects import find_aspects, separation
from astrolog_skills.analysis.harmonics import harmonic_chart, harmonic_lon
from astrolog_skills.analysis.method import parse
from astrolog_skills.analysis.patterns import find_patterns, harmonic_profile, score_harmonic
from astrolog_skills.engine import profile as P
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.model import ChartModel, Point
from astrolog_skills.engine.moment import Moment
from astrolog_skills.packs import loader

EINSTEIN = Moment("1879-03-14", "11:30", "LMT", 48.4, 10.0, "Einstein")


def chart(points: dict[str, tuple[float, float]], angles: dict[str, float] | None = None) -> ChartModel:
    from astrolog_skills.engine.objects import BY_KEY

    pts = [Point(k, BY_KEY[k].name, BY_KEY[k].glyph, lon, 0.0, speed) for k, (lon, speed) in points.items()]
    return ChartModel("test", {}, {}, pts, [], angles or {"asc": 0.0, "mc": 270.0})


FIXED = parse(
    {
        "aspects": {"set": ["conjunction", "opposition", "square", "trine", "sextile", "quintile"]},
        "orbs": {
            "rule": "fixed",
            "conjunction": 8,
            "opposition": 8,
            "square": 7,
            "trine": 7,
            "sextile": 5,
            "quintile": 2,
        },
    },
    "t",
)


def test_separation() -> None:
    assert separation(350, 10) == 20 and separation(10, 190) == 180 and separation(0, 0) == 0


def test_exact_edge_and_outside() -> None:
    c = chart({"sun": (0.0, 1.0), "moon": (120.0, 13.0), "mars": (187.0, 0.5), "venus": (262.1, 1.2)})
    found = {(a.a, a.b): a for a in find_aspects(c, FIXED, include_angles=False)}
    assert found[("sun", "moon")].aspect == "trine" and found[("sun", "moon")].strength == 1.0
    assert found[("sun", "mars")].aspect == "opposition" and found[("sun", "mars")].orb == pytest.approx(7.0)
    assert ("sun", "venus") not in found  # 97.9° is outside the square's 7° orb


def test_overlapping_orbs_pick_the_relatively_tightest() -> None:
    # 70.5°: quintile (72, orb 2) 1.5 off = 75% of limit; sextile (60, orb 5) 10.5 off → only quintile fits
    c = chart({"sun": (0.0, 1.0), "moon": (70.5, 13.0)})
    (a,) = find_aspects(c, FIXED, include_angles=False)
    assert a.aspect == "quintile" and a.strength == pytest.approx(0.25)


def test_applying_and_separating() -> None:
    applying = chart({"sun": (0.0, 1.0), "moon": (115.0, 13.0)})  # Moon moving away from 0 toward the exact 120
    separating = chart({"sun": (0.0, 1.0), "moon": (125.0, 13.0)})
    assert find_aspects(applying, FIXED, include_angles=False)[0].applying is True
    assert find_aspects(separating, FIXED, include_angles=False)[0].applying is False


def test_angles_included_without_speed_and_nodes_skipped() -> None:
    c = chart(
        {"sun": (90.0, 1.0), "north_node": (10.0, -0.05), "south_node": (190.0, -0.05)}, {"asc": 0.0, "mc": 270.0}
    )
    found = find_aspects(c, FIXED)
    pairs = {(a.a, a.b) for a in found}
    assert ("sun", "asc") in pairs and ("north_node", "south_node") not in pairs and ("asc", "mc") not in pairs
    assert next(a for a in found if a.b == "asc").applying is None


def test_harmonic_lon_and_chart() -> None:
    assert harmonic_lon(353.507748, 7) == pytest.approx((353.507748 * 7) % 360)
    c = chart({"sun": (10.0, 1.0), "moon": (100.0, 13.0)})
    h5 = harmonic_chart(c, 5)
    assert (
        h5.harmonic == 5 and h5.point("sun").lon == pytest.approx(50.0) and h5.point("moon").lon == pytest.approx(140.0)
    )
    assert h5.cusps == [] and harmonic_chart(c, 1) is c


def test_harmonic_chart_uses_overtone_orbs() -> None:
    m = loader.load("vibrational").method
    # 3.1° apart natally → 15.5° apart in H5: a harmonic-chart conjunction within 16°
    c = chart({"sun": (0.0, 1.0), "moon": (3.1, 13.0)})
    (a,) = find_aspects(c, m, harmonic=5, include_angles=False)
    assert a.aspect == "conjunction" and a.limit == 16.0


def test_find_patterns_maximal_cliques() -> None:
    lons = {"sun": 0.0, "moon": 5.0, "mercury": 10.0, "venus": 14.0, "mars": 200.0, "jupiter": 205.0, "saturn": 29.0}
    pats = find_patterns(lons, orb=16.0, min_size=3)
    groups = [set(p.bodies) for p in pats]
    assert {"sun", "moon", "mercury", "venus"} in groups  # span 14
    assert {"moon", "mercury", "venus"} not in groups  # not maximal
    assert all(len(g) >= 3 for g in groups)
    for p in pats:
        assert p.span == pytest.approx(
            max(separation(lons[a], lons[b]) for a, b in combinations(p.bodies, 2)), abs=1e-4
        )


def test_score1_counts_four_body_subsets() -> None:
    m = loader.load("vibrational").method
    five = {"sun": 0.0, "moon": 2.0, "mercury": 4.0, "venus": 6.0, "mars": 8.0}
    s = score_harmonic(five, 1, m)
    assert s.score1 == 5  # C(5, 4): a 5-planet pattern counts as five 4-planet patterns
    assert s.score2 > 0 and s.patterns[0].size == 5


def test_score2_weights_and_tightness() -> None:
    m = loader.load("vibrational").method
    exact = score_harmonic({"sun": 0.0, "moon": 0.0}, 1, m)
    half = score_harmonic({"sun": 0.0, "moon": 8.0}, 1, m)
    assert exact.score2 == pytest.approx(10.0) and half.score2 == pytest.approx(5.0)


def test_pattern_bodies_filter() -> None:
    m = loader.load("vibrational").method  # ten planets only
    s = score_harmonic({"sun": 0.0, "moon": 1.0, "chiron": 2.0}, 1, m)
    assert s.patterns == []


def test_einstein_patterns(fake_astrolog: Path) -> None:
    """Values measured with the real Astrolog.

    H1: Sun–Mercury–Saturn 10.68°, Mercury–Venus–Saturn 13.84°; H7: Mercury–Saturn–Pluto 7.32°.
    """
    c = cast(EINSTEIN, P.load("vibrational"))
    m = loader.load("vibrational").method
    lons = {p.key: p.lon for p in c.points}
    h1 = score_harmonic(lons, 1, m)
    assert [(p.bodies, round(p.span, 1)) for p in h1.patterns] == [
        (["sun", "mercury", "saturn"], 10.7),
        (["mercury", "venus", "saturn"], 13.8),
    ]
    h7 = score_harmonic(lons, 7, m)
    assert [(p.bodies, round(p.span, 1)) for p in h7.patterns] == [(["mercury", "saturn", "pluto"], 7.3)]
    assert [s.harmonic for s in harmonic_profile(lons, m)] == list(range(1, 33))


def test_exclude_lower_harmonics() -> None:
    """A quintile (72°) is a conjunction in H10 too; with exclusion on it no longer counts in H10."""
    import dataclasses

    base = loader.load("vibrational").method
    on = dataclasses.replace(base, exclude_lower_harmonics=True)
    quintile = {"sun": 0.0, "moon": 72.0}
    assert score_harmonic(quintile, 10, base).score2 > 0
    assert score_harmonic(quintile, 10, on).score2 == 0
    assert score_harmonic(quintile, 5, on).score2 > 0  # still counts in its own harmonic
    # a pure H10 aspect (36°) is kept: it isn't within orb in H1, H2 or H5
    assert score_harmonic({"sun": 0.0, "moon": 36.0}, 10, on).score2 > 0


def test_midpoint_on_the_short_arc() -> None:
    from astrolog_skills.analysis.midpoints import midpoint

    assert midpoint(350, 10) == 0 and midpoint(10, 350) == 0 and midpoint(20, 60) == 40


def test_midpoint_contacts_name_the_aspect_to_the_midpoint() -> None:
    from astrolog_skills.analysis.midpoints import midpoint_contacts

    c = chart(
        {
            "moon": (350.0, 13.0),
            "mercury": (10.0, 1.0),  # Moon/Mercury midpoint = 0°
            "sun": (0.5, 1.0),  # on it
            "venus": (180.0, 1.0),  # opposite it
            "mars": (269.5, 0.5),  # square, 0.5° orb (a square's orb is 45′: in proportion to the 1.5° conjunction)
            "jupiter": (40.0, 0.1),  # nothing
            "north_node": (120.0, -0.05),
            "south_node": (300.0, -0.05),
        },
        {"asc": 200.0, "mc": 110.0},
    )
    found = midpoint_contacts(c, FIXED)
    on = {(x.a, x.b): x for x in found["sun"]}
    assert on[("moon", "mercury")].aspect == "conjunction" and on[("moon", "mercury")].orb == 0.5
    assert {(x.a, x.b, x.aspect) for x in found["venus"]} >= {("moon", "mercury", "opposition")}
    assert any((x.a, x.b, x.aspect) == ("moon", "mercury", "square") and x.orb == 0.5 for x in found["mars"])
    assert "south_node" not in found and all("south_node" not in (x.a, x.b) for xs in found.values() for x in xs)
    every = [x for xs in found.values() for x in xs]
    assert all(x.focus not in (x.a, x.b) and x.orb <= x.limit <= FIXED.midpoint_orb for x in every)
    assert all([x.strength for x in xs] == sorted((x.strength for x in xs), reverse=True) for xs in found.values())


def test_midpoint_settings_from_the_pack() -> None:
    from astrolog_skills.errors import AstroError

    base = {"orbs": {"rule": "harmonic"}}
    m = parse({**base, "midpoints": {"aspects": ["conjunction", "semisquare"], "orb": 1.0}}, "t")
    assert m.midpoint_aspects == ("conjunction", "semisquare") and m.midpoint_orb == 1.0
    assert parse(base, "t").midpoint_aspects == parse(base, "t").aspects  # default "all": the pack's own aspect set
    from astrolog_skills.analysis.method import Method

    assert Method(name="x", aspects=("trine",)).midpoint_aspects == ("trine",)  # one default, however it's built
    assert parse({**base, "midpoints": {"aspects": "all"}}, "t").midpoint_aspects == parse(base, "t").aspects
    with pytest.raises(AstroError):
        parse({**base, "midpoints": {"aspects": ["wobble"]}}, "t")
    with pytest.raises(AstroError):
        parse({**base, "midpoints": {"orb": 9}}, "t")
    assert loader.load("vibrational").method.midpoint_orb == 1.5
