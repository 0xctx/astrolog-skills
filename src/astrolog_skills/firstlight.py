"""First light: the sky right now, as proof that everything works."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from astrolog_skills.astrolog.run import expressions
from astrolog_skills.engine.moment import astrolog_coord
from astrolog_skills.engine.zodiac import ELEMENTS, SIGNS, element_of, format_position, sign_of

__all__ = ["ELEMENTS", "SIGNS", "astrolog_coord", "element_of", "first_light", "format_position", "phase", "sign_of"]

PHASES = (
    "New Moon",
    "Waxing Crescent",
    "First Quarter",
    "Waxing Gibbous",
    "Full Moon",
    "Waning Gibbous",
    "Last Quarter",
    "Waning Crescent",
)


def phase(sun: float, moon: float) -> tuple[str, float, float]:
    """(phase name, illuminated fraction 0..1, elongation degrees)."""
    elong = (moon - sun) % 360
    name = PHASES[int(((elong + 22.5) % 360) // 45)]
    lit = (1 - math.cos(math.radians(elong))) / 2
    return name, lit, elong


def chart_args(when: datetime, location: tuple[float, float] | None) -> list[str]:
    utc = when.astimezone(UTC)
    lat, lon = location if location else (0.0, 0.0)
    return [
        "-qa",
        str(utc.month),
        str(utc.day),
        str(utc.year),
        f"{utc.hour}:{utc.minute:02d}",
        "0",
        astrolog_coord(lon, "E", "W"),
        astrolog_coord(lat, "N", "S"),
    ]


def first_light(
    binary: Path,
    when: datetime | None = None,
    location: tuple[float, float] | None = None,
    pins: list[str] | None = None,
) -> dict[str, Any]:
    """The sky now. `pins` = the active profile's settings (so a sidereal user sees sidereal positions)."""
    when = when or datetime.now(UTC)
    args = [*chart_args(when, location), *(pins or []), "-R0", "Sun", "Moo"]
    sun, moon, asc = expressions(binary, args, ["ObjLon O_Sun", "ObjLon O_Moo", "ObjLon O_Asc"])
    name, lit, elong = phase(sun, moon)
    data: dict[str, Any] = {
        "time_utc": when.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "sun": {"lon": round(sun, 6), "text": format_position(sun), "element": element_of(sun)},
        "moon": {
            "lon": round(moon, 6),
            "text": format_position(moon),
            "element": element_of(moon),
            "phase": name,
            "illumination": round(lit, 3),
            "elongation": round(elong, 3),
        },
        "rising": None,
    }
    if location:
        data["rising"] = {"lon": round(asc, 6), "text": format_position(asc), "element": element_of(asc)}
    return data
