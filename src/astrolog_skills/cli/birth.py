"""Birth data from command-line options — shared by every command that casts a chart."""

from __future__ import annotations

from astrolog_skills import config
from astrolog_skills.charts import store
from astrolog_skills.engine.moment import Moment
from astrolog_skills.errors import AstroError

EXAMPLE = 'e.g. --chart Einstein, or --date 1879-03-14 --time 11:30 --place "Ulm, Germany" (--tz and --at optional)'


def moment_from_options(
    *,
    chart: str | None = None,
    date: str | None = None,
    time: str | None = None,
    tz: str | None = None,
    place: str | None = None,
    at: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    name: str = "",
    now: bool = False,
) -> tuple[Moment, list[str]]:
    """→ (moment, notes about lookups). Sources, in order: a saved chart, --now, or date/time + place/coordinates."""
    if chart:
        record = store.load(chart)
        return record.moment(), []
    if at:
        lat, lon = config.parse_location(at)
    if now:
        if place:
            record, _notes = store.build(name or "Now", "2000-01-01", "12:00", tz="UTC", place=place)
            lat, lon = record.lat, record.lon
        loc = (lat, lon) if lat is not None and lon is not None else config.location()
        if loc is None:
            raise AstroError(
                "--now needs a place.", fix='add --place "Ulm, Germany", or set: astro config set location …'
            )
        return Moment.now(loc[0], loc[1], name or "Now"), []
    missing = [flag for flag, value in (("--date", date), ("--time", time)) if not value]
    if not place and (lat is None or lon is None):
        missing.append("--place or --at")
    if missing:
        raise AstroError("Missing " + ", ".join(missing) + ".", fix=EXAMPLE)
    assert date and time
    record, notes = store.build(name, date, time, tz=tz, place=place, lat=lat, lon=lon)
    return record.moment(), notes
