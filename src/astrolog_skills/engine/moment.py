"""A birth or event moment: local clock time + time zone + place → UT and Astrolog's `-qa` arguments.

Time zones are resolved in Python (IANA history via zoneinfo/tzdata) and Astrolog is always given UT,
so there is exactly one well-tested path — and the chart records which offset was used.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from astrolog_skills.errors import AstroError

GREGORIAN_START = date(1582, 10, 15)
_OFFSET = re.compile(r"^(?:UTC|GMT|UT)?\s*([+-])(\d{1,2})(?::?(\d{2}))?$", re.I)


def astrolog_coord(value: float, positive: str, negative: str, seconds: bool = False) -> str:
    """10.0 → '10:00E' (or '10:00:00E'). Astrolog reads unsigned decimals as WEST, so always use letters."""
    hemi = positive if value >= 0 else negative
    if seconds:
        total = round(abs(value) * 3600)
        return f"{total // 3600}:{total // 60 % 60:02d}:{total % 60:02d}{hemi}"
    total = round(abs(value) * 60)
    return f"{total // 60}:{total % 60:02d}{hemi}"


def julian_calendar(d: date) -> tuple[int, int, int]:
    """A (proleptic) Gregorian date as the Julian-calendar (year, month, day) Astrolog expects before 1582-10-15."""
    jdn = d.toordinal() + 1721425
    c = jdn + 32082
    dd = (4 * c + 3) // 1461
    e = c - 1461 * dd // 4
    m = (5 * e + 2) // 153
    return dd - 4800 + m // 10, m + 3 - 12 * (m // 10), e - (153 * m + 2) // 5 + 1


def astrolog_ymd(utc: datetime) -> tuple[int, int, int]:
    """Calendar date to hand Astrolog for a true (Gregorian) UT: Julian calendar before 1582-10-15, like Astrolog."""
    if utc.date() < GREGORIAN_START:
        return julian_calendar(utc.date())
    return utc.year, utc.month, utc.day


def _parse_date(text: str) -> date:
    try:
        return date.fromisoformat(text.strip())
    except ValueError as err:
        raise AstroError(f"'{text}' isn't a date.", fix="use YYYY-MM-DD, e.g. 1879-03-14") from err


def _parse_time(text: str) -> time:
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})(?::(\d{2}(?:\.\d+)?))?\s*", text)
    if not m:
        raise AstroError(f"'{text}' isn't a clock time.", fix="use 24-hour HH:MM or HH:MM:SS, e.g. 11:30 or 23:05:30")
    hour, minute, second = int(m[1]), int(m[2]), float(m[3] or 0)
    if hour > 23 or minute > 59 or second >= 60:
        raise AstroError(f"'{text}' isn't a valid clock time.")
    whole = int(second)
    return time(hour, minute, whole, round((second - whole) * 1_000_000))


@dataclass
class Moment:
    date: str
    time: str
    tz: str
    lat: float
    lon: float
    name: str = ""
    sex: str = field(default="", compare=False)  # the native's sex, for the few rules that depend on it (lots)
    # filled in by resolve()
    utc: datetime | None = field(default=None, compare=False)
    offset_hours: float | None = field(default=None, compare=False)
    ambiguous: bool = field(default=False, compare=False)
    warnings: list[str] = field(default_factory=list, compare=False)

    def __post_init__(self) -> None:
        if not -90 <= self.lat <= 90 or not -180 <= self.lon <= 180:
            raise AstroError(f"Coordinates {self.lat}, {self.lon} are outside the globe.")
        self.resolve()

    def resolve(self) -> None:
        local = datetime.combine(_parse_date(self.date), _parse_time(self.time))
        if not 1 <= local.year <= 9999:
            raise AstroError("Years must be between 1 and 9999.")
        self.warnings = []
        tz = self.tz.strip()
        if tz.upper() == "LMT":
            offset = timedelta(hours=self.lon / 15)
            utc = (local - offset).replace(tzinfo=UTC)
        elif tz.upper() in ("UTC", "UT", "GMT", "Z"):
            offset = timedelta(0)
            utc = local.replace(tzinfo=UTC)
        elif m := _OFFSET.match(tz):
            sign = -1 if m[1] == "-" else 1
            offset = sign * timedelta(hours=int(m[2]), minutes=int(m[3] or 0))
            utc = local.replace(tzinfo=timezone(offset)).astimezone(UTC)
        else:
            utc, offset = self._iana(local, tz)
        if local.date() < GREGORIAN_START:
            self.warnings.append("date before 1582-10-15: read as a Julian-calendar date, as historical records are")
        if abs(self.lat) > 66:
            self.warnings.append("polar latitude: Placidus and Koch houses fall back to Porphyry here")
        self.utc = utc
        self.offset_hours = offset.total_seconds() / 3600

    def _iana(self, local: datetime, name: str) -> tuple[datetime, timedelta]:
        try:
            zone = ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError) as err:
            raise AstroError(
                f"Unknown time zone '{name}'.",
                fix="use an IANA zone like Europe/Berlin or America/New_York, an offset like +01:00, or LMT",
            ) from err
        first = local.replace(tzinfo=zone, fold=0)
        second = local.replace(tzinfo=zone, fold=1)
        # A clock time in a daylight-saving gap doesn't survive a round trip through UTC.
        if first.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != local:
            raise AstroError(
                f"{self.time} didn't exist on {self.date} in {name} — the clocks jumped forward (daylight saving).",
                fix="check the recorded time, or give the offset explicitly, e.g. --tz +01:00",
            )
        if first.utcoffset() != second.utcoffset():
            self.ambiguous = True
            self.warnings.append(
                f"{self.time} happened twice on {self.date} in {name} (clocks went back); used the first — "
                "give an explicit offset to choose the other"
            )
        if first.tzname() == "LMT":
            # Before standard time, clocks kept the *birthplace's* local mean time; the IANA zone's LMT is that of
            # its reference city (Europe/Berlin = Berlin's +0:53:28), which would be wrong for, say, Ulm (+0:40).
            offset = timedelta(hours=self.lon / 15)
            self.warnings.append(
                f"before standard time in {name}: used the birthplace's local mean time "
                f"(UT{offset.total_seconds() / 3600:+.4f}h)"
            )
            return (local - offset).replace(tzinfo=UTC), offset
        offset = first.utcoffset() or timedelta(0)
        return first.astimezone(UTC), offset

    def cast_args(self) -> list[str]:
        """Astrolog `-qa` arguments in UT (zone 0) with lettered coordinates."""
        assert self.utc is not None
        u = self.utc
        seconds = u.second + u.microsecond / 1_000_000
        clock = (
            f"{u.hour}:{u.minute:02d}:{seconds:05.2f}" if u.microsecond else f"{u.hour}:{u.minute:02d}:{u.second:02d}"
        )
        lon = astrolog_coord(self.lon, "E", "W", seconds=True)
        lat = astrolog_coord(self.lat, "N", "S", seconds=True)
        return ["-qa", str(u.month), str(u.day), str(u.year), clock, "0", lon, lat]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "date": self.date,
            "time": self.time,
            "tz": self.tz,
            "lat": self.lat,
            "lon": self.lon,
            "utc": self.utc.isoformat() if self.utc else None,
            "offset_hours": self.offset_hours,
            "ambiguous": self.ambiguous,
            "warnings": list(self.warnings),
            "sex": self.sex,
        }

    @classmethod
    def now(cls, lat: float, lon: float, name: str = "Now") -> Moment:
        u = datetime.now(UTC)
        return cls(u.date().isoformat(), u.strftime("%H:%M:%S"), "UTC", lat, lon, name)
