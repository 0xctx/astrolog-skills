"""Write Astrolog chart lists with seconds (Astrolog's own `-ol` drops them) and map batch rows back to records."""

from __future__ import annotations

import re
from pathlib import Path

from astrolog_skills.charts.records import SetRecord
from astrolog_skills.engine.moment import astrolog_coord, astrolog_ymd

_ID = re.compile(r"^\[([^\]]+)\] ")


def _clean(text: str) -> str:
    """Astrolog chart-list fields are double-quoted; a quote inside a name would end the field early."""
    return text.replace('"', "'").replace("\n", " ").strip()[:60]


def line(record: SetRecord) -> str:
    u = record.utc
    seconds = u.second + u.microsecond / 1_000_000
    clock = f"{u.hour}:{u.minute:02d}:{seconds:05.2f}" if u.microsecond else f"{u.hour}:{u.minute:02d}:{u.second:02d}"
    lon = astrolog_coord(record.lon, "E", "W", seconds=True)
    lat = astrolog_coord(record.lat, "N", "S", seconds=True)
    year, month, day = astrolog_ymd(u)  # Astrolog reads dates before 1582-10-15 as Julian-calendar
    label = f"[{record.id}] {_clean(record.name)}"
    return f'-qcl {month} {day} {year} {clock} ST 0 {lon} {lat} "{label}" "{_clean(record.place)}"'


def write(records: list[SetRecord], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(line(r) for r in records)
    path.write_text(
        "@AL780  ; Astrolog chart list written by astrolog-skills\n" + body + "\n", encoding="latin-1", errors="replace"
    )
    return path


def id_of(batch_name: str) -> str | None:
    m = _ID.match(batch_name)
    return m[1] if m else None
