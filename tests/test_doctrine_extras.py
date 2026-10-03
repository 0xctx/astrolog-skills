"""Further Hellenistic techniques: proper face, the angles' degrees, busy by an angle, quadrant houses, assembly, the
Moon running in the void, containment, Mercury's role, the Marriage lot by sex, and releasing's ruler flag. Synthetic
positions; the examples are the published ones where the texts give them."""

from __future__ import annotations

import tomllib
from dataclasses import replace
from datetime import datetime

import pytest

from astrolog_skills.analysis.doctrine.engine import analyse
from astrolog_skills.analysis.doctrine.explain import build_study
from astrolog_skills.analysis.doctrine.extras import (
    angle_places,
    assemblies,
    busy_by_angle,
    mercury_role,
    porphyry_house,
    proper_face,
    running_in_the_void,
)
from astrolog_skills.analysis.doctrine.rules import SEVEN, SIGN_KEYS, Configs, parse_doctrine
from astrolog_skills.analysis.timing.releasing import Releaser
from astrolog_skills.engine.model import ChartModel, Point
from astrolog_skills.engine.objects import BY_KEY
from astrolog_skills.errors import AstroError
from astrolog_skills.packs import loader

# the built-in pack itself (a user's own pack of the same name would replace it in loader.load)
_raw = tomllib.loads((loader.builtin_dir() / "hellenistic" / "method.toml").read_text())
D = parse_doctrine(_raw, "built-in hellenistic")
assert D is not None
PARK = {"sun": 345.0, "moon": 255.0, "mercury": 3.0, "venus": 17.0, "mars": 297.0, "jupiter": 327.0, "saturn": 4.0}
SPEED = {"sun": 1.0, "moon": 13.0, "mercury": 1.4, "venus": 1.2, "mars": 0.6, "jupiter": 0.2, "saturn": 0.1}


def chart(
    asc: float = 100.0, mc: float | None = None, sex: str = "", **lons: float | tuple[float, float]
) -> ChartModel:
    pts = []
    for k in SEVEN:
        v = lons.get(k, PARK[k])
        lon, speed = v if isinstance(v, tuple) else (v, SPEED[k])
        pts.append(Point(k, BY_KEY[k].name, BY_KEY[k].glyph, lon, 0.0, speed))
    moment = {"date": "1950-01-01", "utc": "1950-01-01T12:00:00", "sex": sex}
    return ChartModel("t", moment, {}, pts, [], {"asc": asc, "mc": (asc + 270) % 360 if mc is None else mc})


def test_proper_face() -> None:
    g = D.dignities
    assert g is not None
    assert proper_face("venus", 285.0, 225.0, 100.0, g)  # Sun in Scorpio, Venus two signs later in Capricorn
    assert not proper_face("venus", 315.0, 225.0, 100.0, g)
    assert proper_face("venus", 65.0, 300.0, 125.0, g)  # Venus in Gemini two signs before the Moon in Leo
    assert not proper_face("sun", 10.0, 10.0, 10.0, g)


def test_the_angles_degrees() -> None:
    c = chart(asc=5.0, mc=305.0)  # Aries rising, the Midheaven in Aquarius: the 11th place
    assert angle_places(c) == {"mc": 11, "ic": 5}
    assert porphyry_house(45.0, 0.0, 270.0) == 2 and porphyry_house(275.0, 0.0, 270.0) == 10


def test_busy_by_an_angle_degree() -> None:
    """The published example: the Ascendant at 14° Leo, Jupiter at 15° Aries in the 9th, a declining place."""
    c = chart(asc=134.0, jupiter=15.0)
    assert D.places is not None and busy_by_angle(15.0, c, D.places) == "asc"
    jup = analyse(c, D).planet("jupiter")
    assert jup.place.angularity == "declining" and jup.place.busy and jup.busy_by == "asc"
    assert "busy_by_angle" in jup.flags
    assert busy_by_angle(20.0, c, D.places) == ""  # 6° from the trine: too far


def test_assembly() -> None:
    c = chart(mercury=(3.0, 1.5), venus=(17.0, 1.2), saturn=(200.0, 0.1))
    found = assemblies(c, Configs(assembly=15))
    assert [(a.a, a.b, a.distance) for a in found] == [("mercury", "venus", 14.0)]
    assert assemblies(chart(mercury=(3.0, 1.5), venus=(5.0, 1.2), saturn=(200.0, 0.1)), Configs(assembly=15)) == []


def test_running_in_the_void() -> None:
    rest = {k: (40.0 + 2 * i, 0.5) for i, k in enumerate(["sun", "mercury", "venus", "mars", "jupiter", "saturn"])}
    void = running_in_the_void(chart(moon=(0.0, 13.0), **rest), Configs(void_range=30))
    assert void.void and void.moon_travel is not None and void.moon_travel > 30
    rest["jupiter"] = (140.0, 0.1)  # its trine falls 20° ahead of the Moon
    near = running_in_the_void(chart(moon=(0.0, 13.0), **rest), Configs(void_range=30))
    assert not near.void and near.next_aspect == "trine jupiter" and near.moon_travel == pytest.approx(20.15, abs=0.05)


def test_containment() -> None:
    """The published example: the Moon in Virgo, Mars in Aries — contained; a benefic seeing the Moon breaks it."""
    others = {"sun": 135.0, "mercury": 140.0, "venus": 195.0, "jupiter": 200.0, "saturn": 130.0}
    found = analyse(chart(asc=0.0, moon=165.0, mars=10.0, **others), D).conditions
    assert [(c.actor, c.effect) for c in found if c.target == "moon" and c.condition == "containment"] == [
        ("mars", "maltreat")
    ]
    seen = analyse(chart(asc=0.0, moon=165.0, mars=10.0, **{**others, "jupiter": 285.0}), D).conditions
    assert not [c for c in seen if c.target == "moon" and c.condition == "containment"]


def test_mercury_role() -> None:
    assert D.sect is not None
    with_jupiter = chart(mercury=280.0, jupiter=285.0, saturn=100.0, venus=200.0, mars=150.0)
    role = mercury_role(with_jupiter, D.sect, D.dignities)  # Capricorn: with Jupiter, ruled by Saturn
    assert role.role == "mixed" and {x["planet"] for x in role.associations} == {"jupiter", "saturn"}
    far = {"sun": 30.0, "moon": 120.0, "jupiter": 100.0, "saturn": 10.0, "venus": 32.0, "mars": 190.0}
    alone = mercury_role(chart(mercury=255.0, **far), D.sect, D.dignities)  # Sagittarius, nothing close
    assert alone.role == "benefic" and alone.associations == [
        {"planet": "jupiter", "how": "rules its sign", "nature": "benefic"}
    ]


def test_the_marriage_lot_needs_the_native_s_sex() -> None:
    plain = analyse(chart(asc=0.0), D)
    assert "marriage" not in plain.lots and any("native's sex" in n for n in plain.notes)
    man, woman = analyse(chart(asc=0.0, sex="male"), D), analyse(chart(asc=0.0, sex="female"), D)
    sat, ven = PARK["saturn"], PARK["venus"]
    assert man.lots["marriage"].lon == pytest.approx((ven - sat) % 360)  # from Saturn to Venus, from the Ascendant
    assert woman.lots["marriage"].lon == pytest.approx((sat - ven) % 360)
    study = build_study(chart(asc=0.0), D, {})
    partnership = next(t for t in study["topics"] if t["name"] == "partnership")
    assert [c["ref"] for c in partnership["components"] if c["kind"] == "lot"] == ["lot:eros"]  # Marriage skipped


def test_career_takes_in_the_midheaven_degree_s_place() -> None:
    study = build_study(chart(asc=5.0, mc=305.0), D, {})
    career = next(t for t in study["topics"] if t["name"] == "career")
    titles = [c["title"] for c in career["components"] if c["kind"] == "place"]
    assert titles == ["The 10th place and its ruler", "The Midheaven degree's place (the 11th) and its ruler"]
    further = {f["key"] for f in study["further"]}
    assert {"midheaven_degree", "void_moon", "mercury_role"} <= further


def test_releasing_flags_the_general_period_ruler_s_sign() -> None:
    assert D.releasing is not None
    rules = replace(D.releasing, ruler_sign=True)
    cap = SIGN_KEYS.index("capricorn")
    gemini = SIGN_KEYS.index("gemini")
    domicile = D.dignities.domicile if D.dignities else {}
    r = Releaser(rules, "spirit", cap, datetime(2000, 1, 1), 0, {"saturn": gemini}, domicile, "", "")
    l2 = [p for p in r.periods(datetime(2030, 1, 1), 2) if p.level == 2]
    assert [p.sign for p in l2 if p.holds_ruler] == ["Gemini"]  # Saturn rules Capricorn and sits in Gemini


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"lots": {"x": {"by_sex": {"other": {"points": ["sun", "moon"]}}}}}, "male or female"),
        ({"configurations": {"assembly": 15, "colour": 1}}, "unknown key"),
        ({"places": {"quadrant": "koch"}}, "quadrant"),
        ({"places": {"busy_by_angle": {"aspects": ["wiggle"]}}}, "busy_by_angle"),
    ],
)
def test_bad_rules(raw: dict[str, object], message: str) -> None:
    with pytest.raises(AstroError, match=message):
        parse_doctrine(raw, "t")
