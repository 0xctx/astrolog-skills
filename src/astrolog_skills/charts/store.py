"""Saved charts: one human-editable TOML file per chart in ~/.astrolog-skills/charts/."""

from __future__ import annotations

import re
import tomllib
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import tomli_w

from astrolog_skills import places
from astrolog_skills.engine.moment import Moment
from astrolog_skills.errors import AstroError
from astrolog_skills.paths import data_dir

RATINGS = ("AA", "A", "B", "C", "DD", "X", "XX")
SEXES = ("male", "female")


@dataclass
class ChartRecord:
    name: str
    date: str
    time: str
    tz: str
    lat: float
    lon: float
    place: str = ""
    rating: str = ""  # Rodden rating: AA, A, B, C, DD, X, XX
    tags: list[str] = field(default_factory=list)
    source: str = ""
    notes: str = ""
    sex: str = ""  # male | female (some traditional lots differ by it); "" = not recorded

    def moment(self) -> Moment:
        return Moment(self.date, self.time, self.tz, self.lat, self.lon, self.name, self.sex)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def charts_dir() -> Path:
    return data_dir() / "charts"


def slug(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if not text:
        raise AstroError(f"'{name}' can't be used as a chart name.", fix="use letters or digits")
    return text


def path_for(name: str) -> Path:
    return charts_dir() / f"{slug(name)}.toml"


def build(
    name: str,
    date: str,
    time: str,
    *,
    tz: str | None = None,
    place: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    rating: str = "",
    tags: list[str] | None = None,
    source: str = "",
    notes: str = "",
    sex: str = "",
) -> tuple[ChartRecord, list[str]]:
    """Birth data → a validated record. A place supplies coordinates and time zone; bare coordinates borrow
    the time zone of the nearest atlas place. Returns (record, notes about what was looked up)."""
    notes_out: list[str] = []
    place_label = ""
    if place:
        found = places.resolve(place)
        place_label = found.label
        if lat is None or lon is None:
            lat, lon = found.lat, found.lon
        if not tz:
            tz = found.tz
            notes_out.append(f"time zone {tz} from {found.label}")
    if lat is None or lon is None:
        raise AstroError("Where was it?", fix='give --place "Ulm, Germany" or --at "48N24 10E00"')
    if not tz:
        near = places.nearest(lat, lon)
        tz = near.tz
        place_label = place_label or f"near {near.label}"
        notes_out.append(f"time zone {tz} from the nearest place, {near.label}")
    rating = rating.upper().strip()
    if rating and rating not in RATINGS:
        raise AstroError(f"'{rating}' isn't a Rodden rating.", fix="use one of: " + ", ".join(RATINGS))
    sex = sex.lower().strip()
    if sex and sex not in SEXES:
        raise AstroError(f"'{sex}' isn't male or female.", fix="--sex male or --sex female (or leave it out)")
    record = ChartRecord(
        name.strip(), date, time, tz, float(lat), float(lon), place_label, rating, list(tags or []), source, notes, sex
    )
    record.moment()  # validates date, time, zone, DST gaps
    return record, notes_out


def save(record: ChartRecord, overwrite: bool = False) -> Path:
    path = path_for(record.name)
    if path.exists() and not overwrite:
        raise AstroError(f"A chart called '{record.name}' already exists.", fix="add --replace to overwrite it")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {k: v for k, v in record.to_dict().items() if v not in ("", [], None)}
    path.write_text("# astrolog-skills chart — edit freely\n" + tomli_w.dumps(data), encoding="utf-8")
    return path


def load(name: str) -> ChartRecord:
    path = path_for(name)
    if not path.exists():
        known = ", ".join(r.name for r in list_charts()[:15])
        raise AstroError(
            f"No saved chart called '{name}'.",
            fix=f"saved charts: {known}" if known else "add one with `astro chart add`",
        )
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        return ChartRecord(**{k: raw[k] for k in raw if k in ChartRecord.__dataclass_fields__})
    except (tomllib.TOMLDecodeError, TypeError) as err:
        raise AstroError(f"Chart file {path} is damaged ({err}).", fix=f"fix or delete {path}") from err


def list_charts() -> list[ChartRecord]:
    if not charts_dir().is_dir():
        return []
    out: list[ChartRecord] = []
    for path in sorted(charts_dir().glob("*.toml")):
        try:
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
            out.append(ChartRecord(**{k: raw[k] for k in raw if k in ChartRecord.__dataclass_fields__}))
        except (tomllib.TOMLDecodeError, TypeError):
            continue
    return out


def remove(name: str) -> Path:
    path = path_for(name)
    if not path.exists():
        raise AstroError(f"No saved chart called '{name}'.")
    path.unlink()
    return path
