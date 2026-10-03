"""Harmonic charts vs Astrolog's own -x, with the real binary: `uv run pytest -m astrolog`."""

from __future__ import annotations

import os
import pwd
from pathlib import Path

import pytest

from astrolog_skills.analysis.harmonics import harmonic_chart
from astrolog_skills.astrolog.run import expressions
from astrolog_skills.engine import profile as P
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.moment import Moment

pytestmark = pytest.mark.astrolog
EINSTEIN = Moment("1879-03-14", "11:30", "LMT", 48.4, 10.0, "Einstein")


@pytest.fixture
def real(monkeypatch: pytest.MonkeyPatch) -> Path:
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    for candidate in (os.environ.get("REAL_ASTROLOG", ""), str(home / "astrolog" / "astrolog")):
        if candidate and Path(candidate).is_file():
            monkeypatch.setenv("ASTROLOG_BIN", candidate)
            return Path(candidate)
    pytest.skip("no real Astrolog found")


@pytest.mark.parametrize("h", [5, 7, 13, 32])
def test_harmonic_chart_equals_astrolog_x(real: Path, h: int) -> None:
    profile = P.load("vibrational")
    ours = harmonic_chart(cast(EINSTEIN, profile), h)
    codes = {"sun": "Sun", "moon": "Moo", "saturn": "Sat", "pluto": "Plu"}
    # "-x H" after the pins overrides their neutral "-x 1": Astrolog's own harmonic chart
    theirs = expressions(
        real, [*EINSTEIN.cast_args(), *P.pins(profile), "-x", str(h)], [f"ObjLon O_{c}" for c in codes.values()]
    )
    for (key, _), value in zip(codes.items(), theirs, strict=True):
        diff = abs((ours.point(key).lon - value + 180) % 360 - 180)
        assert diff < 0.0005 * h, (key, h)
