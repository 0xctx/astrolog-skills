"""A natal chart read through a pack's doctrine: sect, dignities, solar phase and places for the seven planets."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from astrolog_skills.analysis.doctrine.conditions import Condition, conditions, exchanges
from astrolog_skills.analysis.doctrine.configurations import Pair, configurations
from astrolog_skills.analysis.doctrine.dignities import PlanetDignities, planet_dignities
from astrolog_skills.analysis.doctrine.extras import (
    Assembly,
    MercuryRole,
    VoidMoon,
    angle_places,
    assemblies,
    busy_by_angle,
    mercury_role,
    porphyry_house,
    proper_face,
    running_in_the_void,
)
from astrolog_skills.analysis.doctrine.lots import Lot, compute_lots
from astrolog_skills.analysis.doctrine.phase import PlanetPhase, planet_phase
from astrolog_skills.analysis.doctrine.places import PlanetPlace, planet_place
from astrolog_skills.analysis.doctrine.rulers import Topic, places, topic
from astrolog_skills.analysis.doctrine.rules import SEVEN, Doctrine
from astrolog_skills.analysis.doctrine.sect import ChartSect, PlanetSect, above_horizon, chart_sect, planet_sect
from astrolog_skills.analysis.doctrine.summary import Testimony, judge, planet_tokens
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.zodiac import sign_of
from astrolog_skills.errors import AstroError


@dataclass(frozen=True)
class PlanetDoctrine:
    key: str
    lon: float
    position: str
    sect: PlanetSect | None
    dignities: PlanetDignities | None
    phase: PlanetPhase | None
    place: PlanetPlace
    flags: tuple[str, ...] = ()  # further findings: proper_face, busy_by_angle, running_in_the_void
    busy_by: str = ""  # the angle ("asc", "mc") whose degree makes this declining planet busy
    quadrant: int | None = None  # its quadrant house (information only), when the pack asks

    def to_dict(self) -> dict[str, Any]:
        return {
            "flags": list(self.flags),
            "busy_by": self.busy_by,
            "quadrant": self.quadrant,
            "key": self.key,
            "lon": self.lon,
            "position": self.position,
            "sect": self.sect.to_dict() if self.sect else None,
            "dignities": self.dignities.to_dict() if self.dignities else None,
            "phase": self.phase.to_dict() if self.phase else None,
            "place": self.place.to_dict(),
        }


@dataclass(frozen=True)
class NatalDoctrine:
    chart: str
    day: bool
    sect: ChartSect | None
    asc_place_sign: str
    planets: list[PlanetDoctrine]
    cites: dict[str, str]
    notes: list[str] = field(default_factory=list)
    configurations: list[Pair] = field(default_factory=list)
    conditions: list[Condition] = field(default_factory=list)
    exchanges: list[tuple[str, str]] = field(default_factory=list)
    lots: dict[str, Lot] = field(default_factory=dict)
    lot_topics: dict[str, Topic] = field(default_factory=dict)
    places: list[Topic] = field(default_factory=list)
    testimony: dict[str, Testimony] = field(default_factory=dict)  # planet → its good and bad testimonies
    lot_testimony: dict[str, Testimony] = field(default_factory=dict)
    angle_places: dict[str, int] = field(default_factory=dict)  # "mc"/"ic" → the whole-sign place holding the degree
    assemblies: list[Assembly] = field(default_factory=list)
    void_moon: VoidMoon | None = None
    mercury: MercuryRole | None = None

    def planet(self, key: str) -> PlanetDoctrine:
        return next(p for p in self.planets if p.key == key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chart": self.chart,
            "day": self.day,
            "sect": self.sect.to_dict() if self.sect else None,
            "rising_sign": self.asc_place_sign,
            "planets": [p.to_dict() for p in self.planets],
            "cites": self.cites,
            "notes": self.notes,
            "configurations": [c.to_dict() for c in self.configurations],
            "conditions": [c.to_dict() for c in self.conditions],
            "exchanges": [list(x) for x in self.exchanges],
            "lots": {k: v.to_dict() for k, v in self.lots.items()},
            "lot_topics": {k: v.to_dict() for k, v in self.lot_topics.items()},
            "places": [t.to_dict() for t in self.places],
            "testimony": {k: v.to_dict() for k, v in self.testimony.items()},
            "lot_testimony": {k: v.to_dict() for k, v in self.lot_testimony.items()},
            "angle_places": self.angle_places,
            "assemblies": [a.to_dict() for a in self.assemblies],
            "void_moon": self.void_moon.to_dict() if self.void_moon else None,
            "mercury": self.mercury.to_dict() if self.mercury else None,
        }


def analyse(chart: ChartModel, doctrine: Doctrine, later: ChartModel | None = None) -> NatalDoctrine:
    """Apply the doctrine to a chart; `later` is the same chart cast the pack's heliacal days afterwards."""
    if doctrine.sect is None and doctrine.dignities is None and doctrine.phase is None and doctrine.places is None:
        raise AstroError("This pack's doctrine has no sect, dignities, phase or places rules to apply.")
    asc = chart.angles["asc"]
    sun = chart.point("sun").lon
    day = above_horizon(sun, asc)
    cs = chart_sect(doctrine.sect, sun, asc) if doctrine.sect else None
    notes: list[str] = []
    planets = []
    moon = chart.point("moon").lon
    void = running_in_the_void(chart, doctrine.configs) if doctrine.configs and doctrine.configs.void_range else None
    rules = doctrine.places
    for key in SEVEN:
        p = chart.point(key)
        dig = planet_dignities(key, p.lon, doctrine.dignities, day) if doctrine.dignities else None
        ps = planet_sect(key, p.lon, sun, asc, day, doctrine.sect, doctrine.dignities) if doctrine.sect else None
        if ps and ps.note and "not computed" in ps.note:
            notes.append(f"{key}: {ps.note}")
        ph = None
        if doctrine.phase:
            pair = (later.point(key).lon, later.point("sun").lon) if later is not None else None
            ph = planet_phase(key, p.lon, p.speed, sun, doctrine.phase, dig, pair)
        place = planet_place(key, p.lon, asc, rules)
        flags: list[str] = []
        busy_by = ""
        if rules and rules.busy_by_angle and place.angularity == "declining":
            busy_by = busy_by_angle(p.lon, chart, rules)
            if busy_by:
                place = replace(place, busy=True)
                flags.append("busy_by_angle")
        if (
            doctrine.dignities
            and doctrine.dignities.proper_face
            and proper_face(key, p.lon, sun, moon, doctrine.dignities)
        ):
            flags.append("proper_face")
        if key == "moon" and void and void.void:
            flags.append("running_in_the_void")
        quadrant = porphyry_house(p.lon, asc, chart.angles["mc"]) if rules and rules.quadrant else None
        planets.append(PlanetDoctrine(key, p.lon, p.text, ps, dig, ph, place, tuple(flags), busy_by, quadrant))
    if doctrine.phase and doctrine.phase.heliacal_days and later is None:
        notes.append("heliacal phases need the chart cast again a few days later; not computed")
    cites = {
        name: part.cite
        for name in ("sect", "dignities", "phase", "places", "scoring")
        if (part := getattr(doctrine, name)) is not None and part.cite
    }
    cites |= {f"conditions.{k}": c.cite for k, c in doctrine.conditions.items() if c.cite}
    cites |= {f"lots.{k}": lot.cite for k, lot in doctrine.lots.items() if lot.cite}
    if doctrine.configs and doctrine.configs.cite:
        cites["configurations"] = doctrine.configs.cite
    found = conditions(chart, doctrine, day)
    swaps = exchanges(chart, doctrine)
    lots = compute_lots(chart, doctrine, day) if doctrine.lots else {}
    missing = [k for k in doctrine.lots if k not in lots]
    if missing:
        notes.append(f"lots left out until the chart records the native's sex: {', '.join(missing)}")
    lot_topics = {k: topic(f"lot:{k}", v.lon, chart, doctrine, day, found) for k, v in lots.items()}
    testimony = {p.key: judge(planet_tokens(p, found, swaps), doctrine.scoring) for p in planets}
    lot_testimony = {k: judge(t.checklist, doctrine.scoring, lot=True) for k, t in lot_topics.items()}
    return NatalDoctrine(
        chart.name,
        day,
        cs,
        sign_of(asc),
        planets,
        cites,
        notes,
        configurations(chart, SEVEN),
        found,
        swaps,
        lots,
        lot_topics,
        places(chart, doctrine, day, found),
        testimony,
        lot_testimony,
        angle_places(chart) if rules and rules.angle_degrees else {},
        assemblies(chart, doctrine.configs) if doctrine.configs and doctrine.configs.assembly else [],
        void,
        mercury_role(chart, doctrine.sect, doctrine.dignities)
        if doctrine.sect and doctrine.sect.mercury_role
        else None,
    )
