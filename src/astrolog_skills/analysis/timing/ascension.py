"""Ascensional times: how many degrees of the equator rise with each sign at a latitude (spherical astronomy of
the ecliptic itself — no planet positions involved)."""

from __future__ import annotations

import math

from astrolog_skills.analysis.doctrine.rules import SIGN_KEYS
from astrolog_skills.errors import AstroError

OBLIQUITY = 23.4393  # degrees, J2000


def _oblique_ascension(lon: float, lat: float, eps: float) -> float:
    e, lam, f = map(math.radians, (eps, lon, lat))
    ra = math.degrees(math.atan2(math.sin(lam) * math.cos(e), math.cos(lam))) % 360
    dec = math.asin(math.sin(e) * math.sin(lam))
    ad = math.degrees(math.asin(max(-1.0, min(1.0, math.tan(f) * math.tan(dec)))))
    return ra - ad


def ascensional_times(lat: float, obliquity: float = OBLIQUITY) -> dict[str, float]:
    """sign → degrees (read as years in the sect-light technique)."""
    if abs(lat) >= 90 - obliquity:
        raise AstroError(f"Ascensional times aren't defined at latitude {lat:g}° (some signs never rise).")
    out = {}
    for i, sign in enumerate(SIGN_KEYS):
        a = _oblique_ascension(i * 30.0, lat, obliquity)
        b = _oblique_ascension((i + 1) * 30.0, lat, obliquity)
        out[sign] = round((b - a) % 360, 2)
    return out
