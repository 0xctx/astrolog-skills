"""Whole-sign places: number, angularity, angular triad, and the pack's good/bad/busy places and joys."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from astrolog_skills.analysis.doctrine.rules import Places
from astrolog_skills.engine.zodiac import sign_index

ANGULARITY = ("angular", "succedent", "declining")


def place_of(lon: float, asc: float) -> int:
    return (sign_index(lon) - sign_index(asc)) % 12 + 1


def triad_angle(place: int) -> int:
    """The angle a place belongs with: succedents follow their angle, declines precede the next one."""
    k = (place - 1) % 3
    return place if k == 0 else (place - 2) % 12 + 1 if k == 1 else place % 12 + 1


@dataclass(frozen=True)
class PlanetPlace:
    place: int
    angularity: str
    triad: int
    good: bool | None
    busy: bool | None
    joy: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def labels(self) -> list[str]:
        out = [self.angularity]
        if self.good is not None:
            out.append("good place" if self.good else "bad place")
        if self.busy is False:
            out.append("not busy")
        if self.joy:
            out.append("its joy")
        return out


def planet_place(planet: str, lon: float, asc: float, rules: Places | None) -> PlanetPlace:
    n = place_of(lon, asc)
    good: bool | None = None
    busy: bool | None = None
    if rules is not None:
        if n in rules.good:
            good = True
        elif n in rules.bad:
            good = False
        if rules.busy:
            busy = n in rules.busy
    joy = rules is not None and rules.joys.get(planet) == n
    return PlanetPlace(n, ANGULARITY[(n - 1) % 3], triad_angle(n), good, busy, joy)
