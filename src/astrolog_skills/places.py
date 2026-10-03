"""Place lookup from Astrolog's own atlas (GeoNames: every place over 500 people, with its IANA time zone).

atlas.as rows are tab-separated: longitude (NEGATIVE = EAST, Astrolog's convention), latitude, region code
(upper case = country, lower case = US state / Canadian province), name, time zone (blank = same as the row above).
"""

from __future__ import annotations

import functools
import math
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from astrolog_skills.astrolog import locate
from astrolog_skills.errors import AstroError
from astrolog_skills.regions import ALIASES, COUNTRIES, SUBDIVISIONS, region_label


@dataclass(frozen=True)
class Place:
    name: str
    region: str  # atlas code: "DE", or "mt" for Montana
    lat: float
    lon: float  # east positive
    tz: str

    @property
    def label(self) -> str:
        return f"{self.name}, {region_label(self.region)}"

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "label": self.label}


_GERMAN = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})


def fold(text: str) -> str:
    """'São Paulo' → 'sao paulo' (atlas names are plain ASCII)."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold().strip()


# The atlas mixes English names for big cities (Munich, Vienna) with local ones for others (Koeln, Zuerich).
_EXONYMS = {
    "muenchen": "munich",
    "munchen": "munich",
    "cologne": "koeln",
    "koln": "koeln",
    "zurich": "zuerich",
    "nuremberg": "nuernberg",
    "nurnberg": "nuernberg",
    "wien": "vienna",
    "roma": "rome",
    "praha": "prague",
    "warszawa": "warsaw",
    "moskva": "moscow",
    "lisboa": "lisbon",
    "firenze": "florence",
    "venezia": "venice",
    "napoli": "naples",
    "milano": "milan",
    "torino": "turin",
    "geneve": "geneva",
    "genf": "geneva",
    "bruxelles": "brussels",
    "brussel": "brussels",
    "kobenhavn": "copenhagen",
    "athina": "athens",
    "beijing": "beijing",
    "peking": "beijing",
    "bombay": "mumbai",
    "calcutta": "kolkata",
    "madras": "chennai",
}


def variants(text: str) -> set[str]:
    """Spellings to try: accents dropped, German-style ('Zuerich'), and common English/local name pairs."""
    found = {fold(text), fold(text.translate(_GERMAN))}
    return found | {_EXONYMS[v] for v in found if v in _EXONYMS}


def atlas_path() -> Path:
    found = locate.find()
    candidates = [found.path.parent / "atlas.as"] if found else []
    for path in candidates:
        if path.is_file():
            return path
    raise AstroError(
        "Astrolog's atlas (atlas.as) wasn't found next to Astrolog.",
        fix="install the official Astrolog with `astro astrolog install --yes` (it includes the atlas), "
        'or give coordinates with --at "48N24 10E00" and a --tz',
    )


def load_atlas(path: Path | None = None) -> list[Place]:
    path = path or atlas_path()
    return _load(str(path), path.stat().st_mtime_ns)


@functools.lru_cache(maxsize=2)
def _load(path: str, _mtime: int) -> list[Place]:
    places: list[Place] = []
    tz = ""
    with open(path, encoding="latin-1") as f:
        for line in f:
            if not line or line[0] in ";@" or line.startswith("-YY"):
                continue
            parts = line.rstrip("\r\n").split("\t")  # some rows end in CRLF
            if len(parts) < 4:
                continue
            if len(parts) >= 5 and parts[4].strip():
                tz = parts[4].strip()
            try:
                places.append(Place(parts[3], parts[2], float(parts[1]), -float(parts[0]), tz))
            except ValueError:
                continue
    return places


def _hint_codes(hint: str) -> set[str]:
    """Region codes matching a hint: a code, a country, state or province name, or an alias."""
    h = fold(hint)
    codes: set[str] = set()
    if not h:
        return codes
    if h in ALIASES:
        codes.add(ALIASES[h])
    for code, name in COUNTRIES.items():
        if h in (code.casefold(), fold(name)):
            codes.add(code)
    for code, (name, _country) in SUBDIVISIONS.items():
        if h in (code, fold(name)):
            codes.add(code)
    return codes


def search(query: str, limit: int = 10) -> list[Place]:
    """Places matching 'Name' or 'Name, Country/State'. Exact names first, then names that start with the query."""
    name, _, hint = query.partition(",")
    targets = variants(name)
    if not any(targets):
        raise AstroError("Give a place name, e.g. 'Ulm, Germany'.")
    codes = _hint_codes(hint) if hint.strip() else set()
    if hint.strip() and not codes:
        raise AstroError(
            f"Don't know the country or state '{hint.strip()}'.", fix="use a name like 'Germany' or a code like 'DE'"
        )
    exact: list[Place] = []
    prefix: list[Place] = []
    for place in load_atlas():
        if (
            codes
            and place.region not in codes
            and not (any(c in COUNTRIES for c in codes) and _country_of(place.region) in codes)
        ):
            continue
        folded = fold(place.name)
        if folded in targets or folded in {f"{t} city" for t in targets}:  # "New York" → "New York City"
            exact.append(place)
        elif any(folded.startswith(t) for t in targets) and len(prefix) < limit:
            prefix.append(place)
    return (exact + prefix)[:limit]


def _country_of(region: str) -> str:
    return SUBDIVISIONS[region][1] if region in SUBDIVISIONS else region


def resolve(query: str) -> Place:
    """Exactly one place, or a clear error listing the candidates."""
    found = search(query, limit=12)
    targets = variants(query.partition(",")[0])
    exact = [p for p in found if fold(p.name) in targets]
    if not exact:  # "New York" means "New York City" when that's the only city-named match
        exact = [p for p in found if fold(p.name) in {f"{t} city" for t in targets}]
    if len(exact) == 1:
        return exact[0]
    if not exact:
        if len(found) == 1:
            return found[0]
        near = "; ".join(p.label for p in found[:6])
        raise AstroError(
            f"No place called '{query}'." + (f" Close: {near}." if near else ""),
            fix="check the spelling, add the country, or give coordinates with --at",
        )
    listed = "; ".join(p.label for p in exact[:10]) + (" …" if len(exact) > 10 else "")
    raise AstroError(
        f"'{query}' matches {len(exact)} places: {listed}.",
        fix="add the country or state, e.g. 'Ulm, Germany' or 'Springfield, Illinois'",
    )


def nearest(lat: float, lon: float) -> Place:
    """The atlas place closest to these coordinates (used to find a time zone for bare coordinates)."""

    def distance(p: Place) -> float:
        phi1, phi2 = math.radians(lat), math.radians(p.lat)
        dphi, dlmb = phi2 - phi1, math.radians(p.lon - lon)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
        return 2 * math.asin(min(1.0, math.sqrt(a)))

    return min(load_atlas(), key=distance)
