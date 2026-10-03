"""Astrolog's 23 house systems (`-c <number>`)."""

from __future__ import annotations

from astrolog_skills.errors import AstroError

# key → (label, Astrolog number). Placidus/Koch fall back to Porphyry beyond ~66° latitude.
HOUSE_SYSTEMS: dict[str, tuple[str, int]] = {
    "placidus": ("Placidus", 0),
    "koch": ("Koch", 1),
    "equal": ("Equal", 2),
    "campanus": ("Campanus", 3),
    "meridian": ("Meridian", 4),
    "regiomontanus": ("Regiomontanus", 5),
    "porphyry": ("Porphyry", 6),
    "morinus": ("Morinus", 7),
    "topocentric": ("Topocentric", 8),
    "alcabitius": ("Alcabitius", 9),
    "krusinski": ("Krusinski", 10),
    "equal-mc": ("Equal (MC)", 11),
    "pullen-sr": ("Pullen Sinusoidal Ratio", 12),
    "pullen-sd": ("Pullen Sinusoidal Delta", 13),
    "whole-sign": ("Whole Sign", 14),
    "vedic": ("Vedic", 15),
    "sripati": ("Sripati", 16),
    "horizon": ("Horizon", 17),
    "apc": ("APC", 18),
    "carter": ("Carter Poli-Equatorial", 19),
    "sunshine": ("Sunshine", 20),
    "savard-a": ("Savard-A", 21),
    "null": ("Null", 22),
}
_ALIASES = {"whole": "whole-sign", "wholesign": "whole-sign", "ws": "whole-sign", "polich-page": "topocentric"}
QUADRANT_POLAR_FALLBACK = {"placidus", "koch"}


def resolve_house_system(value: str | int) -> tuple[str, str, int]:
    """→ (key, label, Astrolog number). Accepts a key, alias, label or number."""
    if isinstance(value, int) and not isinstance(value, bool):
        for key, (label, number) in HOUSE_SYSTEMS.items():
            if number == value:
                return key, label, number
    else:
        text = str(value).strip().lower().replace(" ", "-").replace("_", "-")
        if text.isdigit():
            return resolve_house_system(int(text))
        text = _ALIASES.get(text, text)
        for key, (label, number) in HOUSE_SYSTEMS.items():
            if text in (key, label.lower().replace(" ", "-")):
                return key, label, number
    raise AstroError(f"Unknown house system '{value}'.", fix="use one of: " + ", ".join(HOUSE_SYSTEMS))
