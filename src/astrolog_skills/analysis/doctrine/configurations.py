"""Configurations between whole signs and by degree: aversion, right and left, overcoming, applying or separating."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from astrolog_skills.analysis.aspects_registry import BY_KEY as ASPECTS
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.zodiac import sign_index

# Signs apart → the configuration between them; the others (1, 5, 7, 11) are aversion.
BY_SIGNS = {
    0: "conjunction",
    2: "sextile",
    10: "sextile",
    3: "square",
    9: "square",
    4: "trine",
    8: "trine",
    6: "opposition",
}
RIGHT = {2: "sextile", 3: "square", 4: "trine"}  # signs from the planet on the right (earlier) to the one on the left


def signs_apart(a: float, b: float) -> int:
    """Whole signs counted forward from a to b."""
    return (sign_index(b) - sign_index(a)) % 12


def sign_aspect(a: float, b: float) -> str | None:
    """The sign-based configuration between two longitudes (conjunction = the same sign), or None for aversion."""
    return BY_SIGNS.get(signs_apart(a, b))


def overcoming(a: float, b: float) -> str | None:
    """The configuration by which a (on the right, earlier in the zodiac) overcomes b, or None."""
    return RIGHT.get(signs_apart(a, b))


def gap(target: float, point: float) -> float:
    """target − point on the shortest arc, in (−180, 180]."""
    d = (target - point) % 360
    return d - 360 if d > 180 else d


def ray_points(actor: float, aspect: str, direction: str) -> list[float]:
    """Where an actor's ray of this aspect falls: backward = earlier in the zodiac, forward = later."""
    angle = ASPECTS[aspect].angle
    if angle in (0, 180):
        return [(actor + angle) % 360]
    back, ahead = (actor - angle) % 360, (actor + angle) % 360
    return {"backward": [back], "forward": [ahead]}.get(direction, [back, ahead])


def closest(target: float, actor: float, aspect: str, direction: str = "any") -> float:
    """The target's signed distance from the nearest exact ray of this aspect."""
    return min((gap(target, p) for p in ray_points(actor, aspect, direction)), key=abs)


def is_applying(distance: float, target_speed: float, actor_speed: float) -> bool:
    """Is the target closing on the exact point? (The point moves with the actor.)"""
    rate = target_speed - actor_speed
    return distance * rate < 0


@dataclass(frozen=True)
class Pair:
    a: str
    b: str
    aspect: str | None  # by sign; None = aversion
    overcomes: str  # "a", "b" or "" (who is on the right by sextile, square or trine)
    domination: bool  # overcoming by a superior square
    distance: float | None  # degrees from the exact aspect (by the nearer ray), None in aversion
    applying: bool | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def configurations(chart: ChartModel, keys: tuple[str, ...]) -> list[Pair]:
    out = []
    for i, ka in enumerate(keys):
        for kb in keys[i + 1 :]:
            a, b = chart.point(ka), chart.point(kb)
            aspect = sign_aspect(a.lon, b.lon)
            if overcoming(a.lon, b.lon):
                winner, by = "a", overcoming(a.lon, b.lon)
            elif overcoming(b.lon, a.lon):
                winner, by = "b", overcoming(b.lon, a.lon)
            else:
                winner, by = "", None
            dist = applying = None
            if aspect is not None:
                dist = closest(a.lon, b.lon, aspect)
                applying = is_applying(dist, a.speed, b.speed) if dist else None
                dist = abs(dist)
            out.append(Pair(ka, kb, aspect, winner, by == "square", dist, applying))
    return out
