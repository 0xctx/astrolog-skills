"""Published worked examples, reproduced by the doctrine engine with the real Astrolog — with the test fixture's rules
and with the built-in Hellenistic pack."""

from __future__ import annotations

import os
import pwd
import tomllib
from pathlib import Path
from typing import Any

import pytest

from astrolog_skills.analysis.doctrine import parse_doctrine
from astrolog_skills.analysis.doctrine.engine import analyse
from astrolog_skills.packs import loader

FIXTURES = Path(__file__).parent / "fixtures"
EXAMPLES: list[dict[str, Any]] = tomllib.loads((FIXTURES / "hellenistic_examples.toml").read_text())["example"]
pytestmark = pytest.mark.astrolog


@pytest.fixture
def real(monkeypatch: pytest.MonkeyPatch) -> Path:
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    for candidate in (os.environ.get("REAL_ASTROLOG", ""), str(home / "astrolog" / "astrolog")):
        if candidate and Path(candidate).is_file():
            monkeypatch.setenv("ASTROLOG_BIN", candidate)
            return Path(candidate)
    pytest.skip("no real Astrolog found")


@pytest.mark.parametrize("rules", ["fixture", "hellenistic"])
@pytest.mark.parametrize("ex", EXAMPLES, ids=[e["name"] for e in EXAMPLES])
def test_example(real: Path, ex: dict[str, Any], rules: str) -> None:
    from astrolog_skills.engine import profile as P
    from astrolog_skills.engine.cast import cast
    from astrolog_skills.engine.moment import Moment

    if rules == "fixture":
        doctrine = parse_doctrine(tomllib.loads((FIXTURES / "doctrine_pack.toml").read_text()), "fixture")
    else:
        doctrine = loader.load("hellenistic").method.doctrine
    assert doctrine is not None
    chart = cast(Moment(ex["date"], ex["time"], ex["tz"], ex["lat"], ex["lon"], ex["name"]), P.load("default"))
    r = analyse(chart, doctrine)
    assert r.day is ex["day"] and r.asc_place_sign == ex["rising"], ex["name"]
    for planet, place in ex.get("places", {}).items():
        assert r.planet(planet).place.place == place, f"{planet} {ex['name']}"
    for want in ex.get("conditions", []):
        hit = next(
            (
                c
                for c in r.conditions
                if (c.target, c.actor, c.condition) == (want["target"], want["actor"], want["condition"])
            ),
            None,
        )
        assert hit is not None, f"{want} {ex['name']}"
        assert hit.effect == want["effect"] and hit.aspect == want["aspect"] and hit.applying is want["applying"]
        assert hit.distance == pytest.approx(want["distance"], abs=0.01)
