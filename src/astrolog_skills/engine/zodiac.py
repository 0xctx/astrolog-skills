"""Signs, elements, modes, position formatting, and the verified ayanamsa registry."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from astrolog_skills.errors import AstroError

SIGNS = (
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
)
SIGN_ABBR = ("Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis")
ELEMENTS = ("fire", "earth", "air", "water")
MODES = ("cardinal", "fixed", "mutable")


def norm(lon: float) -> float:
    return lon % 360.0


def sign_index(lon: float) -> int:
    return int(norm(lon) // 30) % 12


def sign_of(lon: float) -> str:
    return SIGNS[sign_index(lon)]


def element_of(lon: float) -> str:
    return ELEMENTS[sign_index(lon) % 4]


def mode_of(lon: float) -> str:
    return MODES[sign_index(lon) % 3]


def degree_in_sign(lon: float) -> float:
    return norm(lon) % 30.0


def format_position(lon: float, seconds: bool = False) -> str:
    """353.507747 → '23°30′ Pisces' (or '23°30′27″ Pisces'). Truncates, never rounds up into the next unit."""
    lon = norm(lon)
    if seconds:
        total = math.floor(round(degree_in_sign(lon) * 3600, 6))
        return f"{total // 3600}°{total // 60 % 60:02d}′{total % 60:02d}″ {sign_of(lon)}"
    total = math.floor(round(degree_in_sign(lon) * 60, 6))
    return f"{total // 60}°{total % 60:02d}′ {sign_of(lon)}"


_ASTROLOG_POS = re.compile(r"^\s*(\d+)([A-Z][a-z]{2})(\d+)'(\d+)\"?\s*$")


def parse_astrolog_position(text: str) -> float:
    """Astrolog's `17Ari11'59"` → 17.1997…"""
    m = _ASTROLOG_POS.match(text)
    if not m or m[2] not in SIGN_ABBR:
        raise ValueError(f"not an Astrolog position: {text!r}")
    return SIGN_ABBR.index(m[2]) * 30 + int(m[1]) + int(m[3]) / 60 + int(m[4]) / 3600


# ── ayanamsas ────────────────────────────────────────────────────────────────
# Offsets are relative to Fagan-Bradley, as Astrolog reports them via the `_s1` AstroExpression.
# Astrolog silently falls back to Fagan-Bradley (0.0) for names it doesn't know, so only these are accepted.


@dataclass(frozen=True)
class Ayanamsa:
    key: str
    label: str
    token: str  # what Astrolog's `-s` accepts
    offset: float


AYANAMSAS: dict[str, Ayanamsa] = {
    a.key: a
    for a in (
        Ayanamsa("fagan-bradley", "Fagan-Bradley", "Fagan", 0.0),
        Ayanamsa("lahiri", "Lahiri (Chitrapaksha)", "Lahiri", 0.883208),
        Ayanamsa("krishnamurti", "Krishnamurti (KP)", "Krishnamurti", 0.98006),
        Ayanamsa("raman", "B.V. Raman", "Raman", 2.329509),
        Ayanamsa("yukteshwar", "Sri Yukteshwar", "Yukteshwar", 2.261497),
        Ayanamsa("deluce", "DeLuce", "DeLuce", -3.075453),
        Ayanamsa("djwhal-khul", "Djwhal Khul", "Djwhal", -3.619379),
        Ayanamsa("usha-shasi", "Usha-Shasi", "Usha-Shasi", 4.682759),
        Ayanamsa("galactic-center", "Galactic Center", "Galactic", -2.105736),
    )
}
_AYANAMSA_ALIASES = {
    "fagan": "fagan-bradley",
    "kp": "krishnamurti",
    "djwhal": "djwhal-khul",
    "usha": "usha-shasi",
    "galactic": "galactic-center",
    "chitrapaksha": "lahiri",
}


def resolve_ayanamsa(value: str | float) -> tuple[str, float, str]:
    """→ (Astrolog -s token, expected `_s1` offset, display label). Accepts a key, alias, label or a number."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        return repr(float(value)), float(value), f"custom {float(value):+.6f}°"
    text = str(value).strip()
    try:
        number = float(text)
    except ValueError:
        pass
    else:
        return repr(number), number, f"custom {number:+.6f}°"
    key = text.lower().replace(" ", "-").replace("_", "-")
    key = _AYANAMSA_ALIASES.get(key, key)
    for a in AYANAMSAS.values():
        if key in (a.key, a.token.lower(), a.label.lower().replace(" ", "-")):
            return a.token, a.offset, a.label
    raise AstroError(
        f"Unknown ayanamsa '{value}'.",
        fix="use one of: " + ", ".join(AYANAMSAS) + " — or a number of degrees relative to Fagan-Bradley",
    )
