"""Further natal techniques a pack can switch on: proper face, the Midheaven and IC degrees' places, planets made busy
by the angles' degrees, quadrant positions, assembly, the Moon running in the void, and Mercury's role by association.
Each is pack data (rules.py); nothing here applies unless the pack asks for it."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from astrolog_skills.analysis.aspects import separation
from astrolog_skills.analysis.aspects_registry import BY_KEY as ASPECTS
from astrolog_skills.analysis.doctrine.configurations import closest, is_applying, sign_aspect
from astrolog_skills.analysis.doctrine.places import place_of
from astrolog_skills.analysis.doctrine.rules import SEVEN, SIGN_KEYS, Configs, Dignities, Places, SectRules
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.zodiac import sign_index

FIVE_ASPECTS = ("conjunction", "sextile", "square", "trine", "opposition")


# ── proper face ───────────────────────────────────────────────────────────────


def proper_face(planet: str, lon: float, sun: float, moon: float, g: Dignities) -> bool:
    """The planet stands in the same sign relation to the Sun (or the Moon) as its domicile does to theirs: a domicile
    n signs after the Sun's comes n signs after the Sun; one n signs before the Moon's, n signs before the Moon."""
    homes = {v: k for k, v in g.domicile.items() if v in ("sun", "moon")}
    if planet in ("sun", "moon") or "sun" not in homes or "moon" not in homes:
        return False
    leo, cancer = SIGN_KEYS.index(homes["sun"]), SIGN_KEYS.index(homes["moon"])
    p = sign_index(lon)
    for sign, lord in g.domicile.items():
        if lord != planet:
            continue
        d = SIGN_KEYS.index(sign)
        after_sun, before_moon = (d - leo) % 12, (cancer - d) % 12
        if 1 <= after_sun <= 5 and (p - sign_index(sun)) % 12 == after_sun:
            return True
        if 1 <= before_moon <= 5 and (sign_index(moon) - p) % 12 == before_moon:
            return True
    return False


# ── the angles' degrees ───────────────────────────────────────────────────────


def angle_places(chart: ChartModel) -> dict[str, int]:
    """The whole-sign places that hold the Midheaven and IC degrees (the 10th and 4th unless the signs are unequal)."""
    asc, mc = chart.angles["asc"], chart.angles["mc"]
    return {"mc": place_of(mc, asc), "ic": place_of((mc + 180.0) % 360.0, asc)}


def busy_by_angle(lon: float, chart: ChartModel, rules: Places) -> str:
    """For a planet in a declining place: the angle ("asc" or "mc") whose exact degree it aspects within the orb by
    one of the pack's aspects — which makes it busy — or ""."""
    for angle in ("asc", "mc"):
        point = chart.angles.get(angle)
        if point is None:
            continue
        for key in rules.busy_by_angle:
            if abs(separation(lon, point) - ASPECTS[key].angle) <= rules.busy_by_angle_orb:
                return angle
    return ""


def porphyry_house(lon: float, asc: float, mc: float) -> int:
    """The quadrant house (Porphyry: each quadrant between the angles trisected) a longitude falls in."""
    angles = [asc, (mc + 180.0) % 360.0, (asc + 180.0) % 360.0, mc]  # 1st, 4th, 7th, 10th cusps in zodiacal order
    for q in range(4):
        start, end = angles[q], angles[(q + 1) % 4]
        span = (end - start) % 360.0 or 360.0
        into = (lon - start) % 360.0
        if into < span:
            return q * 3 + 1 + min(int(into / (span / 3.0)), 2)
    return 1


# ── assembly and the void ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class Assembly:
    a: str  # the planet applying
    b: str
    distance: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def assemblies(chart: ChartModel, configs: Configs, engagement: float = 3.0) -> list[Assembly]:
    """Applying conjunctions beyond the engagement range but within the assembly range (in the same sign)."""
    out = []
    for i, x in enumerate(SEVEN):
        for y in SEVEN[i + 1 :]:
            a, b = chart.point(x), chart.point(y)
            if sign_aspect(a.lon, b.lon) != "conjunction":
                continue
            d = closest(a.lon, b.lon, "conjunction")
            if not engagement < abs(d) <= configs.assembly:
                continue
            fast, slow = (a, b) if abs(a.speed) >= abs(b.speed) else (b, a)
            if is_applying(closest(fast.lon, slow.lon, "conjunction"), fast.speed, slow.speed):
                out.append(Assembly(fast.key, slow.key, round(abs(d), 2)))
    return out


@dataclass(frozen=True)
class VoidMoon:
    void: bool
    next_aspect: str = ""  # the first exact aspect the Moon completes, e.g. "trine venus"
    moon_travel: float | None = None  # degrees the Moon moves before completing it

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def running_in_the_void(chart: ChartModel, configs: Configs) -> VoidMoon:
    """Does the Moon complete an exact aspect with any planet within the next `void_range` degrees of its motion?"""
    moon = chart.point("moon")
    best: tuple[float, str] | None = None
    for key in SEVEN:
        if key == "moon":
            continue
        p = chart.point(key)
        rate = moon.speed - p.speed
        if rate <= 0:
            continue
        for aspect in FIVE_ASPECTS:
            angle = ASPECTS[aspect].angle
            for target in {(p.lon + angle) % 360.0, (p.lon - angle) % 360.0}:
                ahead = (target - moon.lon) % 360.0
                travel = ahead / rate * moon.speed
                if best is None or travel < best[0]:
                    best = (travel, f"{aspect} {key}")
    if best is None:
        return VoidMoon(True)
    travel, what = best
    return VoidMoon(travel > configs.void_range, what, round(travel, 2))


# ── Mercury's role ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MercuryRole:
    role: str  # benefic | malefic | mixed | neutral
    associations: list[dict[str, str]] = field(default_factory=list)  # {planet, how, nature}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def mercury_role(chart: ChartModel, sect: SectRules, g: Dignities | None) -> MercuryRole:
    """Mercury adopts the role of the planets it is closely associated with: in the same sign, configured by degree
    within the association range, or ruling the sign it is in."""
    me = chart.point("mercury")
    links: list[dict[str, str]] = []
    for key in SEVEN:
        if key == "mercury":
            continue
        p = chart.point(key)
        if sign_aspect(me.lon, p.lon) == "conjunction":
            links.append({"planet": key, "how": "same sign"})
            continue
        for aspect in FIVE_ASPECTS[1:]:
            if abs(separation(me.lon, p.lon) - ASPECTS[aspect].angle) <= sect.association_orb:
                links.append({"planet": key, "how": f"{aspect} within {sect.association_orb:g}°"})
                break
    lord = (g.domicile if g else {}).get(SIGN_KEYS[sign_index(me.lon)], "")
    if lord and lord != "mercury" and not any(x["planet"] == lord for x in links):
        links.append({"planet": lord, "how": "rules its sign"})
    for x in links:
        x["nature"] = "benefic" if x["planet"] in sect.benefics else "malefic" if x["planet"] in sect.malefics else ""
    natures = {x["nature"] for x in links if x["nature"]}
    role = "mixed" if len(natures) == 2 else natures.pop() if natures else "neutral"
    return MercuryRole(role, links)
