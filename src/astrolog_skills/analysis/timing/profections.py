"""Annual profections: one sign per year from a starting point; the year's sign, place, lord and activated planets."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from astrolog_skills.analysis.doctrine.lots import compute_lots
from astrolog_skills.analysis.doctrine.places import place_of
from astrolog_skills.analysis.doctrine.rules import SEVEN, SIGN_KEYS, Doctrine, Profections
from astrolog_skills.analysis.doctrine.sect import above_horizon
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.zodiac import SIGNS, sign_index
from astrolog_skills.errors import AstroError


def anniversary(birth: date, years: int) -> date:
    """The birthday `years` after birth (29 February falls on the 28th in common years)."""
    try:
        return birth.replace(year=birth.year + years)
    except ValueError:
        return birth.replace(year=birth.year + years, day=28)


def age_on(birth: date, on: date) -> int:
    age = on.year - birth.year
    return age if on >= anniversary(birth, age) else age - 1


@dataclass(frozen=True)
class ProfectionYear:
    start: str  # the starting point
    age: int
    begins: str
    ends: str
    sign: str
    place: int  # whole-sign place from the Ascendant
    lord: str
    lord_place: int | None
    planets_in_sign: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def start_longitude(chart: ChartModel, doctrine: Doctrine, start: str) -> float:
    asc = chart.angles["asc"]
    day = above_horizon(chart.point("sun").lon, asc)
    if start == "asc":
        return asc
    if start in ("sect_light", "contrary_light"):
        light = "sun" if (start == "sect_light") == day else "moon"
        return chart.point(light).lon
    if start.startswith("place:"):
        return ((sign_index(asc) + int(start[6:]) - 1) % 12) * 30.0
    if start.startswith("lot:"):
        lots = compute_lots(chart, doctrine, day)
        if start[4:] not in lots:
            raise AstroError(f"The pack has no lot '{start[4:]}' to profect from.")
        return lots[start[4:]].lon
    if start in SEVEN:
        return chart.point(start).lon
    raise AstroError(f"Can't profect from '{start}'.", fix="asc, sect_light, contrary_light, a planet, lot:x, place:n")


def profection(chart: ChartModel, doctrine: Doctrine, birth: date, age: int, start: str = "asc") -> ProfectionYear:
    rules = doctrine.profections or Profections()
    if age < 0:
        raise AstroError("The age must be 0 or more.")
    first = sign_index(start_longitude(chart, doctrine, start))
    idx = (first + age * rules.step_signs) % 12
    domicile = doctrine.dignities.domicile if doctrine.dignities else {}
    lord = domicile.get(SIGN_KEYS[idx], "")
    asc = chart.angles["asc"]
    in_sign = [k for k in SEVEN if sign_index(chart.point(k).lon) == idx] if rules.planets_in_sign else []
    return ProfectionYear(
        start,
        age,
        anniversary(birth, age).isoformat(),
        anniversary(birth, age + 1).isoformat(),
        SIGNS[idx],
        (idx - sign_index(asc)) % 12 + 1,
        lord,
        place_of(chart.point(lord).lon, asc) if lord else None,
        in_sign,
    )
