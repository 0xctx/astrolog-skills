"""Aspects between chart points, by a tradition's rules: orb, strength (tighter = stronger), applying/separating."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from astrolog_skills.analysis.aspects_registry import BY_KEY, AspectType
from astrolog_skills.analysis.harmonics import harmonic_chart
from astrolog_skills.analysis.method import Method
from astrolog_skills.engine.model import ChartModel

ANGLE_KEYS = ("asc", "mc")
ANGLE_NAMES = {"asc": "Ascendant", "mc": "Midheaven"}


@dataclass
class Aspect:
    a: str
    b: str
    aspect: str
    angle: float  # exact angle of the aspect
    separation: float  # actual angular distance
    orb: float  # |separation − angle|
    limit: float  # allowed orb
    strength: float  # 1 at exact, 0 at the edge of the orb
    applying: bool | None  # None when a speed is unknown (angles)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def separation(a: float, b: float) -> float:
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def _applying(lon_a: float, speed_a: float, lon_b: float, speed_b: float, angle: float) -> bool:
    """Is the orb shrinking? Look a small step ahead using the daily speeds."""
    step = 0.01
    now = abs(separation(lon_a, lon_b) - angle)
    later = abs(separation(lon_a + speed_a * step, lon_b + speed_b * step) - angle)
    return later < now


def find_aspects(chart: ChartModel, method: Method, harmonic: int = 1, include_angles: bool = True) -> list[Aspect]:
    """All aspects in the chart (or its harmonic chart). In a harmonic chart the overtone orbs apply
    (method.harmonic_chart_orbs); in the natal chart, the pack's aspect set and orb rule."""
    source = harmonic_chart(chart, harmonic) if harmonic > 1 else chart
    bodies: list[tuple[str, float, float | None]] = [(p.key, p.lon, p.speed) for p in source.points]
    if include_angles:
        bodies += [(k, source.angles[k], None) for k in ANGLE_KEYS if k in source.angles]
    if harmonic > 1:
        types: list[tuple[AspectType, float]] = [(BY_KEY[k], orb) for k, orb in method.harmonic_chart_orbs.items()]
    else:
        types = [(a, method.orb_for(a)) for a in method.aspect_types]
    found: list[Aspect] = []
    for i, (ka, la, sa) in enumerate(bodies):
        for kb, lb, sb in bodies[i + 1 :]:
            if {ka, kb} == {"north_node", "south_node"} or (ka in ANGLE_KEYS and kb in ANGLE_KEYS):
                continue
            sep = separation(la, lb)
            best: Aspect | None = None
            for aspect, limit in types:
                orb = abs(sep - aspect.angle)
                if orb <= limit and (best is None or orb / limit < best.orb / best.limit):
                    applying = _applying(la, sa, lb, sb, aspect.angle) if sa is not None and sb is not None else None
                    best = Aspect(
                        ka,
                        kb,
                        aspect.key,
                        aspect.angle,
                        round(sep, 6),
                        round(orb, 6),
                        limit,
                        round(1 - orb / limit, 4) if limit else 1.0,
                        applying,
                    )
            if best:
                found.append(best)
    return sorted(found, key=lambda x: -x.strength)
