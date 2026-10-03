from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from astrolog_skills import firstlight


@pytest.mark.parametrize(
    ("elong", "name"),
    [
        (0, "New Moon"),
        (45, "Waxing Crescent"),
        (90, "First Quarter"),
        (135, "Waxing Gibbous"),
        (180, "Full Moon"),
        (225, "Waning Gibbous"),
        (270, "Last Quarter"),
        (315, "Waning Crescent"),
        (359, "New Moon"),
        (22, "New Moon"),
        (23, "Waxing Crescent"),
    ],
)
def test_phase_names(elong: float, name: str) -> None:
    assert firstlight.phase(100.0, 100.0 + elong)[0] == name


@pytest.mark.parametrize(("elong", "lit"), [(0, 0.0), (90, 0.5), (180, 1.0), (270, 0.5)])
def test_illumination(elong: float, lit: float) -> None:
    assert firstlight.phase(0.0, elong)[1] == pytest.approx(lit)


@pytest.mark.parametrize(
    ("lon", "text"),
    [
        (353.507747, "23°30′ Pisces"),
        (0.0, "0°00′ Aries"),
        (29.9999, "29°59′ Aries"),
        (360.0, "0°00′ Aries"),
        (186.77, "6°46′ Libra"),
        (-1.0, "29°00′ Pisces"),
    ],
)
def test_format_position(lon: float, text: str) -> None:
    assert firstlight.format_position(lon) == text


def test_elements() -> None:
    assert [firstlight.element_of(i * 30 + 1) for i in range(4)] == ["fire", "earth", "air", "water"]


@pytest.mark.parametrize(
    ("value", "pos", "neg", "text"),
    [
        (10.0, "E", "W", "10:00E"),
        (-74.0, "E", "W", "74:00W"),
        (48.4, "N", "S", "48:24N"),
        (-33.87, "N", "S", "33:52S"),
    ],
)
def test_astrolog_coord(value: float, pos: str, neg: str, text: str) -> None:
    assert firstlight.astrolog_coord(value, pos, neg) == text


def test_chart_args_utc() -> None:
    when = datetime(2026, 9, 29, 21, 5, tzinfo=UTC)
    assert firstlight.chart_args(when, (48.4, 10.0)) == [
        "-qa",
        "9",
        "29",
        "2026",
        "21:05",
        "0",
        "10:00E",
        "48:24N",
    ]
    assert firstlight.chart_args(when, None)[-2:] == ["0:00E", "0:00N"]


def test_first_light_payload(fake_astrolog: Path) -> None:
    data = firstlight.first_light(fake_astrolog, datetime(2026, 9, 29, 21, 5, tzinfo=UTC), (48.4, 10.0))
    assert data["sun"]["text"] == "6°46′ Libra" and data["sun"]["element"] == "air"
    assert data["moon"]["phase"] == "Waning Gibbous"
    assert data["rising"]["text"].endswith("Cancer")
    assert data["time_utc"] == "2026-09-29 21:05 UTC"
