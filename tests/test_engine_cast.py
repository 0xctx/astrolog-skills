from __future__ import annotations

from pathlib import Path

import pytest

from astrolog_skills.engine import profile as P
from astrolog_skills.engine.cast import cast, expression_list
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.moment import Moment
from astrolog_skills.errors import AstroError

EINSTEIN = Moment("1879-03-14", "11:30", "LMT", 48.4, 10.0, "Einstein")


def test_cast_default(fake_astrolog: Path) -> None:
    c = cast(EINSTEIN)
    assert c.name == "Einstein" and c.profile["name"] == "default"
    assert [p.key for p in c.points][-3:] == ["chiron", "north_node", "south_node"]
    sun = c.point("sun")
    assert sun.lon == pytest.approx(353.507748) and sun.sign == "Pisces" and sun.house == 10
    assert c.point("uranus").retrograde and not sun.retrograde
    assert len(c.cusps) == 12 and c.angles["asc"] == pytest.approx(101.646405)
    assert c.angles["dsc"] == pytest.approx(281.646405)
    assert c.astrolog["version"] == "8.00"


def test_south_node_is_derived(fake_astrolog: Path) -> None:
    c = cast(EINSTEIN)
    north, south = c.point("north_node"), c.point("south_node")
    assert south.lon == pytest.approx((north.lon + 180) % 360)
    assert south.lat == -north.lat and south.house == (north.house + 5) % 12 + 1  # type: ignore[operator]


def test_restricted_objects_are_never_read(fake_astrolog: Path) -> None:
    """Chiron is off by default in Astrolog and reads 0.0 — the profile's -R0 list must enable it."""
    assert cast(EINSTEIN).point("chiron").lon == pytest.approx(35.54469)


def test_sidereal_profile(fake_astrolog: Path) -> None:
    c = cast(EINSTEIN, P.load("vedic-lahiri"))
    assert c.point("sun").lon == pytest.approx((353.507748 - 23.0 - 0.883208) % 360)
    assert c.profile["ayanamsa_offset"] == pytest.approx(0.883208)
    assert "uranus" not in [p.key for p in c.points]


def test_wrong_applied_ayanamsa_is_caught(fake_astrolog: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ASTROLOG_S1", "0.0")  # Astrolog silently fell back to Fagan-Bradley
    with pytest.raises(AstroError) as err:
        cast(EINSTEIN, P.load("vedic-lahiri"))
    assert "Lahiri" in err.value.message


def test_expression_list_order() -> None:
    exprs = expression_list(P.load("vibrational").object_list)
    assert exprs[:4] == ["ObjLon O_Sun", "ObjLat O_Sun", "ObjDir O_Sun", "ObjHouse O_Sun"]
    assert exprs[-3:] == ["ObjLon O_Asc", "ObjLon O_Mid", "_s1"]
    assert not any("O_None" in e for e in exprs)  # the derived south node is never requested


def test_model_round_trip(fake_astrolog: Path) -> None:
    c = cast(EINSTEIN)
    again = ChartModel.from_dict(c.to_dict())
    assert again.to_dict() == c.to_dict()


def test_missing_astrolog() -> None:
    with pytest.raises(AstroError) as err:
        cast(EINSTEIN)
    assert err.value.fix and "astro astrolog install" in err.value.fix
