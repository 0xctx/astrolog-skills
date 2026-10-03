from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from astrolog_skills.analysis.aspects_registry import BY_KEY
from astrolog_skills.analysis.method import parse
from astrolog_skills.analysis.transits import transit_aspects, window
from astrolog_skills.engine import profile as P
from astrolog_skills.engine.model import ChartModel, Point
from astrolog_skills.engine.objects import BY_KEY as OBJ
from astrolog_skills.errors import AstroError
from astrolog_skills.packs import loader


def model(points: dict[str, tuple[float, float]], angles: dict[str, float] | None = None) -> ChartModel:
    pts = [Point(k, OBJ[k].name, OBJ[k].glyph, lon, 0.0, speed) for k, (lon, speed) in points.items()]
    return ChartModel("t", {"lat": 48.4, "lon": 10.0, "date": "2000-01-01"}, {}, pts, [], angles or {})


def test_transit_orbs_default_and_override() -> None:
    vib = loader.load("vibrational").method
    assert vib.transit_orb(BY_KEY["conjunction"]) == 2.0  # min(16°, 2°)
    assert vib.transit_orb(BY_KEY["septile"]) == 1.0
    psy = loader.load("psychological").method
    assert psy.transit_orb(BY_KEY["semisextile"]) == 1.0
    custom = parse(
        {"orbs": {"rule": "harmonic"}, "transits": {"aspects": ["conjunction"], "orbs": {"conjunction": 3}}}, "t"
    )
    assert [a.key for a in custom.transit_types()] == ["conjunction"] and custom.transit_orb(BY_KEY["conjunction"]) == 3
    with pytest.raises(AstroError):
        parse({"orbs": {"rule": "harmonic"}, "transits": {"orbs": {"wobble": 1}}}, "t")


def test_transit_aspects_applying_and_angles() -> None:
    natal = model({"sun": (100.0, 1.0), "moon": (200.0, 13.0)}, {"asc": 10.0, "mc": 280.0})
    sky = model({"saturn": (99.0, 0.1), "mars": (201.5, -0.3), "south_node": (100.0, -0.05)})
    found = {(t.transit, t.natal): t for t in transit_aspects(natal, sky, loader.load("psychological").method)}
    assert found[("saturn", "sun")].aspect == "conjunction" and found[("saturn", "sun")].applying
    assert found[("mars", "moon")].applying  # retrograde Mars moving back toward the Moon
    assert ("south_node", "sun") not in found  # the transiting south node is implied by the north
    assert ("saturn", "asc") in found and found[("saturn", "asc")].aspect == "square"


def test_window_finds_exact_dates(fake_astrolog: Path) -> None:
    natal = model({"sun": (0.0, 1.0)})
    start = datetime(2000, 1, 1, 12, tzinfo=UTC)
    found = window(natal, P.load("default"), loader.load("psychological").method, start, 60, 48.4, 10.0)
    assert found and all(w.enters <= (w.exact or w.enters) <= w.leaves for w in found)
    assert all(w.transit != "moon" for w in found)
