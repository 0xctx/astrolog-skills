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
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.profile import Profile
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
    targets = {p.key: p.lon for p in natal.points}
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


@dataclass
class Window:
    transit: str
    natal: str
    aspect: str
    exact: str | None  # ISO date of the tightest day (None if it stays within orb without perfecting)
    min_orb: float
    enters: str  # first day within orb in the window
    leaves: str  # last day within orb in the window

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def window(
    natal: ChartModel, profile: Profile, method: Method, start: datetime, days: int, lat: float, lon: float
) -> list[Window]:
    """Cast one chart per day (one Astrolog batch run) and track each transit's tightest day within the window."""
    records = [SetRecord(f"d{k}", f"day {k}", start + timedelta(days=k), lat, lon) for k in range(days + 1)]
    listing = chartlist.write(records, data_dir() / "cache" / "transit-window.as")
    days_cast = {chartlist.id_of(c.name): c for c in batch(["-i", str(listing)], profile)}
    targets = natal_targets(natal)
    types = [(a, method.transit_orb(a)) for a in method.transit_types()]
    track: dict[tuple[str, str, str], list[tuple[int, float]]] = {}
    for k in range(days + 1):
        chart = days_cast.get(f"d{k}")
        if chart is None:
            continue
        for tkey, row in chart.points.items():
            if tkey in ("south_node", "moon"):  # the Moon moves ~13°/day: too fast for daily steps
                continue
            for nk, nlon in targets.items():
                sep = separation(row["lon"], nlon)
                for aspect, limit in types:
                    orb = abs(sep - aspect.angle)
                    if orb <= limit:
                        track.setdefault((tkey, nk, aspect.key), []).append((k, orb))
    out = []
    for (tkey, nk, akey), hits in track.items():
        k_best, best = min(hits, key=lambda h: h[1])
        inside = k_best not in (hits[0][0], hits[-1][0]) or len(hits) == 1 or best < 0.1
        exact = (start + timedelta(days=k_best)).date().isoformat() if inside else None
        out.append(
            Window(
                tkey,
                nk,
                akey,
                exact,
                round(best, 4),
                (start + timedelta(days=hits[0][0])).date().isoformat(),
                (start + timedelta(days=hits[-1][0])).date().isoformat(),
            )
        )
    return sorted(out, key=lambda w: (w.exact or w.enters, w.min_orb))
