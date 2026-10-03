from __future__ import annotations

from datetime import UTC, datetime

import pytest

from astrolog_skills.engine.moment import Moment, astrolog_coord
from astrolog_skills.errors import AstroError

BERLIN = (52.52, 13.405)


def test_lmt_einstein() -> None:
    m = Moment("1879-03-14", "11:30", "LMT", 48.4, 10.0, "Einstein")
    assert m.utc == datetime(1879, 3, 14, 10, 50, tzinfo=UTC)
    assert m.offset_hours == pytest.approx(10 / 15)
    assert m.cast_args() == ["-qa", "3", "14", "1879", "10:50:00", "0", "10:00:00E", "48:24:00N"]


@pytest.mark.parametrize(("date", "utc_hour"), [("2026-07-01", 10), ("2026-01-15", 11)])
def test_iana_daylight_saving(date: str, utc_hour: int) -> None:
    assert Moment(date, "12:00", "Europe/Berlin", *BERLIN).utc.hour == utc_hour  # type: ignore[union-attr]


def test_nonexistent_time_in_dst_gap() -> None:
    with pytest.raises(AstroError) as err:
        Moment("2026-03-29", "02:30", "Europe/Berlin", *BERLIN)
    assert "didn't exist" in err.value.message and err.value.fix and "+01:00" in err.value.fix


def test_ambiguous_time_takes_first_and_flags() -> None:
    m = Moment("2026-10-25", "02:30", "Europe/Berlin", *BERLIN)
    assert m.ambiguous and m.utc == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    assert any("twice" in w for w in m.warnings)


@pytest.mark.parametrize(
    ("tz", "utc"),
    [
        ("+05:30", "06:30"),
        ("-0800", "20:00"),
        ("+5", "07:00"),
        ("UTC", "12:00"),
        ("GMT", "12:00"),
        ("UTC+02:00", "10:00"),
    ],
)
def test_fixed_offsets(tz: str, utc: str) -> None:
    m = Moment("2026-06-10", "12:00", tz, *BERLIN)
    assert m.utc.strftime("%H:%M") == utc  # type: ignore[union-attr]


def test_crossing_midnight_changes_the_ut_date() -> None:
    m = Moment("1990-05-01", "23:05:30", "America/New_York", 40.7128, -74.006)
    assert m.cast_args()[:5] == ["-qa", "5", "2", "1990", "3:05:30"]
    assert m.cast_args()[6:] == ["74:00:22W", "40:42:46N"]


def test_seconds_and_fractions() -> None:
    m = Moment("2000-01-01", "12:00:30.5", "UTC", 0.0, 0.0)
    assert m.cast_args()[4] == "12:00:30.50"


@pytest.mark.parametrize(
    ("value", "pos", "neg", "seconds", "text"),
    [
        (10.0, "E", "W", False, "10:00E"),
        (-74.0, "E", "W", False, "74:00W"),
        (48.4, "N", "S", True, "48:24:00N"),
        (-33.8688, "N", "S", True, "33:52:08S"),
        (0.99999, "E", "W", True, "1:00:00E"),
    ],
)
def test_lettered_coordinates(value: float, pos: str, neg: str, seconds: bool, text: str) -> None:
    assert astrolog_coord(value, pos, neg, seconds) == text


def test_pre_gregorian_and_polar_warnings() -> None:
    m = Moment("1500-01-01", "12:00", "UTC", 70.0, 20.0)
    assert any("Julian" in w for w in m.warnings) and any("polar" in w for w in m.warnings)


@pytest.mark.parametrize(
    ("date", "time", "tz", "message"),
    [
        ("1879-13-01", "11:30", "UTC", "isn't a date"),
        ("1879-03-14", "25:00", "UTC", "valid clock time"),
        ("1879-03-14", "11h30", "UTC", "isn't a clock time"),
        ("1879-03-14", "11:30", "Mars/Olympus", "Unknown time zone"),
    ],
)
def test_bad_input(date: str, time: str, tz: str, message: str) -> None:
    with pytest.raises(AstroError) as err:
        Moment(date, time, tz, 0.0, 0.0)
    assert message in err.value.message


def test_bad_coordinates() -> None:
    with pytest.raises(AstroError):
        Moment("2000-01-01", "12:00", "UTC", 95.0, 0.0)


def test_now() -> None:
    m = Moment.now(48.4, 10.0)
    assert m.tz == "UTC" and m.name == "Now" and m.utc is not None


def test_iana_before_standard_time_uses_birthplace_lmt() -> None:
    """Europe/Berlin in 1879 is Berlin's LMT (+0:53:28); a birth in Ulm kept Ulm's own time (+0:40)."""
    m = Moment("1879-03-14", "11:30", "Europe/Berlin", 48.4, 10.0)
    assert m.utc == datetime(1879, 3, 14, 10, 50, tzinfo=UTC)
    assert any("local mean time" in w for w in m.warnings)


def test_iana_after_standard_time_uses_zone() -> None:
    m = Moment("1900-06-01", "12:00", "Europe/Berlin", 48.4, 10.0)
    assert m.utc == datetime(1900, 6, 1, 11, 0, tzinfo=UTC) and not m.warnings
