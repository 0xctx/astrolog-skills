"""Your own charts from a CSV file → SetRecords.

Columns (header row required): name, date (YYYY-MM-DD), time (HH:MM[:SS]), and either lat + lon or place;
optional: tz (needed with lat/lon unless the nearest place's zone is fine), rating, tags (separated by ;).
"""

from __future__ import annotations

import csv
from pathlib import Path

from astrolog_skills.charts.records import SetRecord
from astrolog_skills.charts.store import build
from astrolog_skills.errors import AstroError

REQUIRED = {"name", "date", "time"}


def load(path: Path) -> tuple[list[SetRecord], dict[str, int]]:
    path = path.expanduser()
    if not path.is_file():
        raise AstroError(f"No file at {path}.")
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = {c.strip().lower() for c in (reader.fieldnames or [])}
        missing = REQUIRED - columns
        if missing or not ({"lat", "lon"} <= columns or "place" in columns):
            need = sorted(missing) + ([] if {"lat", "lon"} <= columns or "place" in columns else ["lat+lon or place"])
            raise AstroError(
                f"{path.name} is missing columns: {', '.join(need)}.",
                fix="header row: name,date,time,tz,lat,lon,place,rating,tags",
            )
        records: list[SetRecord] = []
        for number, raw in enumerate(reader, start=2):
            row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
            try:
                record, _notes = build(
                    row["name"],
                    row["date"],
                    row["time"],
                    tz=row.get("tz") or None,
                    place=row.get("place") or None,
                    lat=float(row["lat"]) if row.get("lat") else None,
                    lon=float(row["lon"]) if row.get("lon") else None,
                    rating=row.get("rating", ""),
                )
            except (AstroError, ValueError) as err:
                message = err.message if isinstance(err, AstroError) else str(err)
                raise AstroError(f"{path.name}, row {number}: {message}", fix="fix that row and try again") from err
            moment = record.moment()
            assert moment.utc is not None
            records.append(
                SetRecord(
                    id=f"csv{number}",
                    name=record.name,
                    utc=moment.utc,
                    lat=record.lat,
                    lon=record.lon,
                    place=record.place,
                    rating=record.rating,
                    source="csv",
                    categories=[t.strip() for t in row.get("tags", "").split(";") if t.strip()],
                )
            )
    return records, {"rows": len(records), "usable": len(records)}
