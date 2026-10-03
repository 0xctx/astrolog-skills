"""Essential dignities of a planet at a longitude, and the lords of any degree — from the pack's [dignities] tables."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from astrolog_skills.analysis.doctrine.rules import SIGN_KEYS, Dignities
from astrolog_skills.engine.zodiac import ELEMENTS, degree_in_sign, sign_index

# The descending order of the planets' speeds; the "chaldean" decan scheme runs through it.
CHALDEAN = ("saturn", "jupiter", "mars", "sun", "venus", "mercury", "moon")
CHALDEAN_START = CHALDEAN.index("mars")  # the first decan of Aries


@dataclass(frozen=True)
class Lords:
    """Who rules a degree."""

    domicile: str = ""
    exaltation: str = ""
    triplicity: tuple[str, ...] = ()  # (sect ruler, other ruler, participating)
    bounds: str = ""
    decan: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlanetDignities:
    lords: Lords
    domicile: bool
    adversity: bool
    exaltation: bool
    depression: bool
    triplicity: str  # "" | "sect ruler" | "out-of-sect ruler" | "participating"
    bounds: bool
    decan: bool
    twelfth_part: float | None  # longitude of the twelfth-part
    exaltation_degree: float | None = None  # the exalted degree when in the exaltation sign

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def labels(self) -> list[str]:
        out = [
            name
            for name, on in (
                ("domicile", self.domicile),
                ("exaltation", self.exaltation),
                ("bounds", self.bounds),
                ("decan", self.decan),
                ("adversity", self.adversity),
                ("depression", self.depression),
            )
            if on
        ]
        if self.triplicity:
            out.insert(2, f"triplicity ({self.triplicity})")
        return out


def decan_ruler(lon: float, g: Dignities) -> str:
    s, n = sign_index(lon), min(2, int(degree_in_sign(lon) // 10))
    if g.decan_scheme == "table":
        rulers = g.decans.get(SIGN_KEYS[s], ())
        return rulers[n] if len(rulers) == 3 else ""
    return CHALDEAN[(CHALDEAN_START + s * 3 + n) % 7]


def bounds_ruler(lon: float, g: Dignities) -> str:
    rows = g.bounds.get(g.bounds_scheme, {}).get(SIGN_KEYS[sign_index(lon)], ())
    deg = degree_in_sign(lon)
    return next((planet for planet, end in rows if deg < end), "")


def twelfth_part(lon: float, multiplier: int) -> float:
    return (sign_index(lon) * 30 + degree_in_sign(lon) * multiplier) % 360


def lords(lon: float, g: Dignities, day: bool) -> Lords:
    sign = SIGN_KEYS[sign_index(lon)]
    trip = g.triplicity.get(ELEMENTS[sign_index(lon) % 4], ())
    if len(trip) == 3 and not day:
        trip = (trip[1], trip[0], trip[2])
    exalted = next((p for p, (s, _) in g.exaltation.items() if s == sign), "")
    return Lords(g.domicile.get(sign, ""), exalted, trip, bounds_ruler(lon, g), decan_ruler(lon, g))


def planet_dignities(planet: str, lon: float, g: Dignities, day: bool) -> PlanetDignities:
    s = sign_index(lon)
    opposite = SIGN_KEYS[(s + 6) % 12]
    lord = lords(lon, g, day)
    exalt = g.exaltation.get(planet)
    in_exalt = bool(exalt and exalt[0] == SIGN_KEYS[s])
    trip = ""
    if planet in lord.triplicity:
        trip = ("sect ruler", "out-of-sect ruler", "participating")[lord.triplicity.index(planet)]
    return PlanetDignities(
        lords=lord,
        domicile=lord.domicile == planet,
        adversity=g.domicile.get(opposite) == planet,
        exaltation=in_exalt,
        depression=bool(exalt and exalt[0] == opposite),
        triplicity=trip,
        bounds=lord.bounds == planet,
        decan=lord.decan == planet,
        twelfth_part=twelfth_part(lon, g.twelfth_parts) if g.twelfth_parts else None,
        exaltation_degree=exalt[1] if exalt and in_exalt else None,
    )
