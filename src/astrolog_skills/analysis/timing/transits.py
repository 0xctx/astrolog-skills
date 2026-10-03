"""Transits read through the time lords: sign ingresses, sign-based configurations from them, and exact hits —
weighed only when a time lord is involved or the profected sign is entered."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from itertools import pairwise
from typing import Any

from astrolog_skills.analysis.aspects_registry import BY_KEY as ASPECTS
from astrolog_skills.analysis.doctrine.configurations import gap, sign_aspect
from astrolog_skills.analysis.doctrine.lots import compute_lots
from astrolog_skills.analysis.doctrine.rules import SEVEN, Doctrine
from astrolog_skills.analysis.doctrine.sect import above_horizon
from astrolog_skills.analysis.timing.profections import age_on, profection
from astrolog_skills.charts import chartlist
from astrolog_skills.charts.records import SetRecord
from astrolog_skills.engine.batch import batch
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.profile import Profile
from astrolog_skills.engine.zodiac import SIGNS, sign_index
from astrolog_skills.paths import data_dir

Positions = dict[str, tuple[float, float]]  # planet → (longitude, speed)


def daily(profile: Profile, start: date, days: int, lat: float, lon: float) -> list[tuple[date, Positions]]:
    """The seven planets at noon UT for each day — one Astrolog batch run."""
    noon = datetime(start.year, start.month, start.day, 12)
    records = [SetRecord(f"d{k}", f"day {k}", noon + timedelta(days=k), lat, lon) for k in range(days + 1)]
    listing = chartlist.write(records, data_dir() / "cache" / "timing-days.as")
    cast = {chartlist.id_of(c.name): c for c in batch(["-i", str(listing)], profile)}
    out = []
    for k in range(days + 1):
        chart = cast.get(f"d{k}")
        if chart is not None:
            out.append(
                (start + timedelta(days=k), {p: (chart.points[p]["lon"], chart.points[p]["speed"]) for p in SEVEN})
            )
    return out


@dataclass(frozen=True)
class TransitEvent:
    date: str
    kind: str  # ingress | exact
    planet: str
    sign: str
    why: list[str]  # lord of the year, planet in the profected sign, into the profected sign
    target: str = ""  # exact: the natal point
    aspect: str = ""
    retrograde: bool = False
    configures: list[str] = field(default_factory=list)  # ingress: natal points the new sign sees, "point:aspect"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def natal_points(natal: ChartModel, doctrine: Doctrine) -> dict[str, float]:
    points = {k: natal.point(k).lon for k in SEVEN}
    points |= {"asc": natal.angles["asc"], "mc": natal.angles["mc"]}
    day = above_horizon(natal.point("sun").lon, natal.angles["asc"])
    if doctrine.lots:
        lots = compute_lots(natal, doctrine, day)
        points |= {f"lot:{k}": lots[k].lon for k in ("fortune", "spirit") if k in lots}
    return points


def time_lord_transits(
    natal: ChartModel,
    doctrine: Doctrine,
    birth: date,
    days: list[tuple[date, Positions]],
    aspects: tuple[str, ...] = ("conjunction", "sextile", "square", "trine", "opposition"),
) -> list[TransitEvent]:
    kinds = set(doctrine.transits.kinds) if doctrine.transits else {"ingress", "sign_configurations", "exact"}
    targets = natal_points(natal, doctrine)
    events: list[TransitEvent] = []
    for (d0, prev), (d1, now) in pairwise(days):
        year = profection(natal, doctrine, birth, age_on(birth, d1))
        lords = {year.lord: "lord of the year"} | {p: "in the profected sign" for p in year.planets_in_sign}
        for planet, (lon, speed) in now.items():
            why = [lords[planet]] if planet in lords else []
            old, new = sign_index(prev[planet][0]), sign_index(lon)
            if "ingress" in kinds and old != new:
                # the Moon enters every sign each month: only its ingresses as a time lord count
                into = SIGNS[new] == year.sign and (planet != "moon" or bool(why))
                reasons = [*why, *(["into the profected sign"] if into else [])]
                if reasons:
                    configures = []
                    if "sign_configurations" in kinds and why:
                        configures = [
                            f"{k}:{asp}" for k, v in targets.items() if (asp := sign_aspect(new * 30.0, v)) is not None
                        ]
                    events.append(
                        TransitEvent(
                            d1.isoformat(),
                            "ingress",
                            planet,
                            SIGNS[new],
                            reasons,
                            retrograde=speed < 0,
                            configures=configures,
                        )
                    )
            if "exact" in kinds and why and planet != "moon":
                for key, target in targets.items():
                    if key == planet:
                        continue
                    for aspect in aspects:
                        angle = ASPECTS[aspect].angle
                        for point in {round((target + angle) % 360, 6), round((target - angle) % 360, 6)}:
                            before, after = gap(prev[planet][0], point), gap(lon, point)
                            if (before * after < 0 and abs(before - after) < 20) or after == 0:
                                when = d1 if abs(after) <= abs(before) else d0
                                events.append(
                                    TransitEvent(
                                        when.isoformat(), "exact", planet, SIGNS[new], why, key, aspect, speed < 0
                                    )
                                )
    return sorted(events, key=lambda e: (e.date, e.kind, e.planet, e.target))
