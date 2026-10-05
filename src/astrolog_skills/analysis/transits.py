"""Transits: the sky at a moment compared with a natal chart, by the tradition pack's aspects and transit orbs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any

from astrolog_skills.analysis.aspects import ANGLE_KEYS, separation
from astrolog_skills.analysis.method import Method
from astrolog_skills.charts import chartlist
from astrolog_skills.charts.records import SetRecord
from astrolog_skills.engine.batch import batch
from astrolog_skills.engine.model import ChartModel, Point
from astrolog_skills.engine.profile import Profile
from astrolog_skills.errors import AstroError
from astrolog_skills.paths import data_dir

SLOW = {"jupiter", "saturn", "uranus", "neptune", "pluto", "chiron", "north_node", "south_node"}


@dataclass
class TransitAspect:
    transit: str
    natal: str
    aspect: str
    angle: float
    orb: float
    limit: float
    strength: float
    applying: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def natal_targets(natal: ChartModel) -> dict[str, float]:
    """Natal bodies and angles; not the South Node, whose contacts only mirror the North Node's."""
    targets = {p.key: p.lon for p in natal.points if p.key != "south_node"}
    targets.update({k: natal.angles[k] for k in ANGLE_KEYS if k in natal.angles})
    return targets


def transit_aspects(natal: ChartModel, transit: ChartModel, method: Method) -> list[TransitAspect]:
    """Every transiting body to every natal point (and angle); applying = the orb is shrinking."""
    targets = natal_targets(natal)
    types = [(a, method.transit_orb(a)) for a in method.transit_types()]
    found: list[TransitAspect] = []
    for tp in transit.points:
        if tp.key == "south_node":
            continue
        for nk, nlon in targets.items():
            sep = separation(tp.lon, nlon)
            best: TransitAspect | None = None
            for aspect, limit in types:
                orb = abs(sep - aspect.angle)
                if orb <= limit and (best is None or orb / limit < best.orb / best.limit):
                    later = abs(separation(tp.lon + tp.speed * 0.01, nlon) - aspect.angle)
                    best = TransitAspect(
                        tp.key,
                        nk,
                        aspect.key,
                        aspect.angle,
                        round(orb, 4),
                        limit,
                        round(1 - orb / limit, 4),
                        later < orb,
                    )
            if best:
                found.append(best)
    return sorted(found, key=lambda t: -t.strength)


def daily_skies(profile: Profile, start: datetime, days: int, lat: float, lon: float) -> list[ChartModel]:
    """One sky per day at the start's time of day, days + 1 of them (one Astrolog batch run)."""
    records = [SetRecord(f"d{k}", f"day {k}", start + timedelta(days=k), lat, lon) for k in range(days + 1)]
    listing = chartlist.write(records, data_dir() / "cache" / "transit-days.as")
    cast = {chartlist.id_of(c.name): c for c in batch(["-i", str(listing)], profile)}
    out = []
    for k in range(days + 1):
        c = cast.get(f"d{k}")
        if c is None:
            raise AstroError(f"Astrolog skipped day {k} of the transit window.", fix="run astro doctor")
        pts = [Point(key, key, "", float(r["lon"]), 0.0, float(r["speed"])) for key, r in c.points.items()]
        out.append(ChartModel(f"day {k}", {}, {}, pts, [], {}))
    return out
