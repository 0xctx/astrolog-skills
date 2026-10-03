"""Chart sets for research: a named, reproducible definition (source + filters) in ~/.astrolog-skills/sets/."""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import tomli_w

from astrolog_skills.charts import adb, chartlist, csv_import, store
from astrolog_skills.charts.records import SetRecord
from astrolog_skills.engine.batch import BatchChart, batch
from astrolog_skills.engine.profile import Profile
from astrolog_skills.errors import AstroError
from astrolog_skills.paths import data_dir

KINDS = ("charts", "csv", "adb")
RESEARCH_DATATYPES = {"anonymous", "research"}  # ADB groups of unnamed people (e.g. "C-Section …")


@dataclass
class SetFilter:
    ratings: list[str] = field(default_factory=list)  # e.g. ["AA", "A"]; empty = any
    categories: list[str] = field(default_factory=list)  # prefixes, any may match
    exclude_categories: list[str] = field(default_factory=list)
    gender: str = ""  # "m" | "f" | ""
    datatypes: list[str] = field(default_factory=list)  # e.g. ["Public Figure"]; empty = any
    exclude_research: bool = True
    name_contains: str = ""

    def keep(self, r: SetRecord) -> bool:
        if self.ratings and r.rating.upper() not in {x.upper() for x in self.ratings}:
            return False
        cats = [c.casefold() for c in r.categories]
        if self.categories and not any(c.startswith(p.casefold()) for p in self.categories for c in cats):
            return False
        if any(c.startswith(p.casefold()) for p in self.exclude_categories for c in cats):
            return False
        if self.gender and r.gender != self.gender.lower():
            return False
        if self.datatypes and r.datatype.casefold() not in {d.casefold() for d in self.datatypes}:
            return False
        if self.exclude_research and r.datatype.casefold() in RESEARCH_DATATYPES:
            return False
        return not self.name_contains or self.name_contains.casefold() in r.name.casefold()


@dataclass
class ChartSet:
    name: str
    kind: str
    path: str = ""  # csv / adb source file
    charts: list[str] = field(default_factory=list)  # kind = charts
    description: str = ""
    filter: SetFilter = field(default_factory=SetFilter)

    def to_toml(self) -> str:
        data: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "source": {"kind": self.kind, "path": self.path, "charts": self.charts},
            "filter": asdict(self.filter),
        }
        return "# astrolog-skills chart set — edit the filter and re-run\n" + tomli_w.dumps(data)


def sets_dir() -> Path:
    return data_dir() / "sets"


def create(
    name: str,
    kind: str,
    *,
    path: str = "",
    charts: list[str] | None = None,
    description: str = "",
    filter_: SetFilter | None = None,
    overwrite: bool = False,
) -> ChartSet:
    if kind not in KINDS:
        raise AstroError(f"Unknown set source '{kind}'.", fix="use charts, csv or adb")
    s = ChartSet(
        store.slug(name),
        kind,
        str(Path(path).expanduser().resolve()) if path else "",
        list(charts or []),
        description,
        filter_ or SetFilter(),
    )
    target = sets_dir() / f"{s.name}.toml"
    if target.exists() and not overwrite:
        raise AstroError(f"A set called '{s.name}' already exists.", fix="add --replace to overwrite it")
    records(s)  # validate the source before saving
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(s.to_toml(), encoding="utf-8")
    return s


def load(name: str) -> ChartSet:
    path = sets_dir() / f"{store.slug(name)}.toml"
    if not path.exists():
        known = ", ".join(p.stem for p in sorted(sets_dir().glob("*.toml"))) if sets_dir().is_dir() else ""
        raise AstroError(
            f"No chart set called '{name}'.", fix=f"sets: {known}" if known else "create one with `astro set create`"
        )
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    src = raw.get("source", {})
    return ChartSet(
        raw.get("name", path.stem),
        src.get("kind", ""),
        src.get("path", ""),
        list(src.get("charts", [])),
        raw.get("description", ""),
        SetFilter(**raw.get("filter", {})),
    )


def list_sets() -> list[ChartSet]:
    return [load(p.stem) for p in sorted(sets_dir().glob("*.toml"))] if sets_dir().is_dir() else []


def remove(name: str) -> None:
    path = sets_dir() / f"{store.slug(name)}.toml"
    if not path.exists():
        raise AstroError(f"No chart set called '{name}'.")
    path.unlink()


def _source(s: ChartSet) -> tuple[list[SetRecord], dict[str, int]]:
    if s.kind == "adb":
        return adb.load(Path(s.path))
    if s.kind == "csv":
        return csv_import.load(Path(s.path))
    out: list[SetRecord] = []
    for chart_name in s.charts:
        record = store.load(chart_name)
        moment = record.moment()
        assert moment.utc is not None
        out.append(
            SetRecord(
                id=f"chart:{store.slug(record.name)}",
                name=record.name,
                utc=moment.utc,
                lat=record.lat,
                lon=record.lon,
                place=record.place,
                rating=record.rating,
                categories=list(record.tags),
                source="charts",
            )
        )
    return out, {"usable": len(out)}


def records(s: ChartSet) -> tuple[list[SetRecord], dict[str, int]]:
    """The set's charts after filtering, plus counts (entries read, skipped, kept)."""
    all_records, stats = _source(s)
    kept = [r for r in all_records if s.filter.keep(r)]
    return kept, {**stats, "kept": len(kept)}


def cast_set(s: ChartSet, profile: Profile, limit: int | None = None) -> list[tuple[SetRecord, BatchChart]]:
    """Cast every chart in the set with one Astrolog batch run (arc-second rows)."""
    recs = records(s)[0][:limit] if limit else records(s)[0]
    if not recs:
        return []
    by_id = {r.id: r for r in recs}
    list_file = chartlist.write(recs, data_dir() / "cache" / f"set-{s.name}.as")
    pairs = []
    for chart in batch(["-i", str(list_file)], profile):
        rid = chartlist.id_of(chart.name)
        if rid in by_id:
            pairs.append((by_id[rid], chart))
    return pairs
