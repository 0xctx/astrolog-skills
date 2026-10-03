"""The triplicity lords of the sect light: the support of the life in its first and second parts, and when the
second lord takes over."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from astrolog_skills.analysis.doctrine.dignities import lords
from astrolog_skills.analysis.doctrine.places import ANGULARITY, place_of
from astrolog_skills.analysis.doctrine.rules import SIGN_KEYS, Doctrine
from astrolog_skills.analysis.doctrine.sect import above_horizon
from astrolog_skills.analysis.timing.ascension import ascensional_times
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.zodiac import SIGNS, sign_index
from astrolog_skills.errors import AstroError

ROLES = ("first", "second", "cooperating")


@dataclass(frozen=True)
class TriplicityLord:
    role: str
    planet: str
    sign: str
    place: int
    angularity: str
    quality: str  # from the pack: good / middling / bad ("" when the pack gives none)
    minor_years: float | None
    ascensional_years: float | None  # ascensional time of the sign it occupies, at the birth latitude

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SectLightReport:
    light: str
    sign: str
    lords: list[TriplicityLord]
    changeover: list[dict[str, Any]] = field(default_factory=list)  # candidate years for the second lord
    cite: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sect_light_lords(chart: ChartModel, doctrine: Doctrine, lat: float) -> SectLightReport:
    if doctrine.dignities is None or not doctrine.dignities.triplicity:
        raise AstroError("The pack has no triplicity table in [dignities].")
    asc = chart.angles["asc"]
    day = above_horizon(chart.point("sun").lon, asc)
    light = "sun" if day else "moon"
    light_lon = chart.point(light).lon
    trip = lords(light_lon, doctrine.dignities, day).triplicity
    rules = doctrine.sect_light
    quality = rules.quality if rules else {}
    years = doctrine.periods.minor_years if doctrine.periods else {}
    asc_times = ascensional_times(lat)
    out = []
    for role, planet in zip(ROLES, trip, strict=True):
        lon = chart.point(planet).lon
        place = place_of(lon, asc)
        angularity = ANGULARITY[(place - 1) % 3]
        out.append(
            TriplicityLord(
                role,
                planet,
                SIGNS[sign_index(lon)],
                place,
                angularity,
                quality.get(angularity, ""),
                years.get(planet),
                asc_times[SIGN_KEYS[sign_index(lon)]],
            )
        )
    candidates = []
    second = out[1]
    for method in rules.changeover if rules else ():
        value = second.minor_years if method == "minor_years" else second.ascensional_years
        if value is not None:
            n = round(value)
            candidates.append(
                {"method": method, "planet": second.planet, "years": value, "year_of_life": n, "ages": [n - 1, n]}
            )
    return SectLightReport(light, SIGNS[sign_index(light_lon)], out, candidates, rules.cite if rules else "")
