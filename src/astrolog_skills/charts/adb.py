"""Astro-Databank XML exports (your licensed copy, or the free public samples) → SetRecords.

Only ever read locally: ADB research data is © Astrodienst and must not be republished. UT comes from each
record's `jd_ut`, which also takes care of Julian-calendar births.
"""

from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from astrolog_skills.charts.records import SetRecord
from astrolog_skills.errors import AstroError
from astrolog_skills.paths import data_dir

UNIX_EPOCH_JD = 2440587.5
_COORD = re.compile(r"^(\d{1,3})([nsew])(\d{1,2})(?:(\d{2}))?$", re.I)
CACHE_VERSION = 1


def jd_to_utc(jd: float) -> datetime:
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(days=jd - UNIX_EPOCH_JD)


def parse_coord(text: str) -> float:
    """ADB's '45n10' / '9e10' / '122w25' (degrees, hemisphere, minutes[, seconds]) → signed degrees."""
    m = _COORD.match(text.strip())
    if not m:
        raise ValueError(f"bad ADB coordinate {text!r}")
    value = int(m[1]) + int(m[3]) / 60 + int(m[4] or 0) / 3600
    return -value if m[2].lower() in "sw" else value


def _text(elem: ET.Element | None) -> str:
    return (elem.text or "").strip() if elem is not None else ""


def iter_records(path: Path, stats: Counter[str] | None = None) -> Iterator[SetRecord]:
    """Stream the XML so even the full ~75,000-entry export stays light on memory."""
    stats = stats if stats is not None else Counter()
    try:
        for _event, entry in ET.iterparse(path, events=("end",)):
            if entry.tag != "adb_entry":
                continue
            stats["entries"] += 1
            record = _record(entry, stats)
            entry.clear()
            if record:
                yield record
    except ET.ParseError as err:
        raise AstroError(f"{path} isn't a readable Astro-Databank XML file ({err}).") from err


def _record(entry: ET.Element, stats: Counter[str]) -> SetRecord | None:
    public = entry.find("public_data")
    if public is None:
        stats["skipped_no_data"] += 1
        return None
    time_elem = public.find("bdata/sbtime")
    jd = time_elem.get("jd_ut") if time_elem is not None else None
    rating = _text(public.find("roddenrating"))
    if not jd or not _text(time_elem) or rating in ("X", "XX"):
        stats["skipped_no_time"] += 1
        return None
    place = public.find("bdata/place")
    try:
        lat = parse_coord(place.get("slati", "")) if place is not None else None
        lon = parse_coord(place.get("slong", "")) if place is not None else None
    except ValueError:
        lat = lon = None
    if lat is None or lon is None:
        stats["skipped_no_place"] += 1
        return None
    datatype = public.find("datatype")
    gender = public.find("gender")
    country = _text(public.find("bdata/country"))
    return SetRecord(
        id=f"adb{entry.get('adb_id', '')}",
        name=_text(public.find("sflname")) or _text(public.find("name")),
        utc=jd_to_utc(float(jd)),
        lat=lat,
        lon=lon,
        place=", ".join(p for p in (_text(place), country) if p),
        rating=rating,
        gender=(gender.get("csex", "") if gender is not None else "").lower(),
        datatype=datatype.get("sdatatype", "") if datatype is not None else "",
        categories=[_text(c) for c in entry.findall("research_data/categories/category") if _text(c)],
        source="adb",
    )


def load(path: Path) -> tuple[list[SetRecord], dict[str, int]]:
    """All usable records, cached (locally, in ~/.astrolog-skills/cache) per file version."""
    path = path.expanduser()
    if not path.is_file():
        raise AstroError(f"No file at {path}.", fix="download the free sample with `astro data fetch-sample`")
    stat = path.stat()
    # hashlib, not hash(): Python randomises str hashes per process, which would defeat the cache.
    key = hashlib.sha256(f"{path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|{CACHE_VERSION}".encode()).hexdigest()[
        :16
    ]
    cache = data_dir() / "cache" / f"adb-{key}.json"
    if cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
        if data.get("version") == CACHE_VERSION:
            return [SetRecord.from_dict(r) for r in data["records"]], data["stats"]
    stats: Counter[str] = Counter()
    records = list(iter_records(path, stats))
    stats["usable"] = len(records)
    cache.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "version": CACHE_VERSION,
        "stats": dict(stats),
        "records": [r.to_dict() for r in records],
    }
    cache.write_text(json.dumps(payload), encoding="utf-8")
    return records, dict(stats)


def categories(path: Path, grep: str = "") -> list[tuple[str, int]]:
    """Category names with how many usable records carry them (optionally filtered by a substring)."""
    counts: Counter[str] = Counter()
    for record in load(path)[0]:
        counts.update(set(record.categories))
    needle = grep.casefold()
    return sorted(((c, n) for c, n in counts.items() if needle in c.casefold()), key=lambda cn: (-cn[1], cn[0]))
