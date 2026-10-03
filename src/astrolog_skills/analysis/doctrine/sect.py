"""Sect: day or night chart, each planet's sect, and whether it rejoices — all from the pack's [sect] rules."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from astrolog_skills.analysis.doctrine.rules import SIGN_KEYS, Dignities, SectRules
from astrolog_skills.engine.zodiac import sign_index


def above_horizon(lon: float, asc: float) -> bool:
    """Above the Ascendant–Descendant axis, judged by ecliptic degrees (the Descendant itself counts as above)."""
    return (lon - asc) % 360 >= 180


def morning_star(lon: float, sun: float) -> bool:
    """Earlier in the zodiac than the Sun (up to the opposition), so it rises before the Sun."""
    return 0 < (sun - lon) % 360 < 180


@dataclass(frozen=True)
class ChartSect:
    day: bool
    light: str  # the luminary of the sect: "sun" | "moon"
    benefic: str  # the benefic of the sect ("" when the pack's lists don't settle it)
    malefic: str
    cite: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlanetSect:
    sect: str  # "diurnal" | "nocturnal" | "" (neutral or unresolved)
    of_sect: bool | None
    above: bool
    rejoices_hemisphere: bool | None
    rejoices_sign: bool | None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def chart_sect(rules: SectRules, sun: float, asc: float) -> ChartSect:
    day = above_horizon(sun, asc)
    members = rules.diurnal if day else rules.nocturnal
    benefic = next((b for b in rules.benefics if b in members), "")
    malefic = next((m for m in rules.malefics if m in members), "")
    return ChartSect(day, "sun" if day else "moon", benefic, malefic, rules.cite)


def planet_sect(
    planet: str, lon: float, sun: float, asc: float, day: bool, rules: SectRules, dignities: Dignities | None
) -> PlanetSect:
    above = above_horizon(lon, asc)
    note = ""
    if planet in rules.diurnal:
        sect = "diurnal"
    elif planet in rules.nocturnal:
        sect = "nocturnal"
    elif planet == "mercury" and rules.mercury == "morning_evening":
        sect = "diurnal" if morning_star(lon, sun) else "nocturnal"
        note = "morning star" if sect == "diurnal" else "evening star"
    elif planet == "mercury" and rules.mercury in ("configured_with", "bounds_ruler"):
        sect, note = "", f"sect by {rules.mercury.replace('_', ' ')} is not computed yet"
    else:
        sect = ""
    if not sect:
        return PlanetSect("", None, above, None, None, note)
    diurnal = sect == "diurnal"
    of_sect = diurnal == day
    hemisphere = (above == day) if diurnal else (above != day)
    return PlanetSect(
        sect,
        of_sect,
        above,
        hemisphere if rules.rejoicing.by_hemisphere else None,
        _rejoices_sign(diurnal, lon, rules, dignities),
        note,
    )


def _rejoices_sign(diurnal: bool, lon: float, rules: SectRules, dignities: Dignities | None) -> bool | None:
    s = sign_index(lon)
    how = rules.rejoicing.by_sign
    if how == "gender":  # fire and air signs are masculine
        return (s % 2 == 0) == diurnal
    if how == "hemisphere":  # Leo through Capricorn is the diurnal half
        return (4 <= s <= 9) == diurnal
    if how == "domicile_lord" and dignities is not None and dignities.domicile:
        lord = dignities.domicile[SIGN_KEYS[s]]
        if lord in rules.diurnal:
            return diurnal
        if lord in rules.nocturnal:
            return not diurnal
    return None
