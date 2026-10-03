"""Transits with the real Astrolog: `uv run pytest -m astrolog`."""

from __future__ import annotations

import os
import pwd
from datetime import UTC, datetime
from pathlib import Path

import pytest

from astrolog_skills.analysis.transits import transit_aspects, window
from astrolog_skills.engine import profile as P
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.moment import Moment
from astrolog_skills.packs import loader

pytestmark = pytest.mark.astrolog


@pytest.fixture
def real(monkeypatch: pytest.MonkeyPatch) -> Path:
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    for candidate in (os.environ.get("REAL_ASTROLOG", ""), str(home / "astrolog" / "astrolog")):
        if candidate and Path(candidate).is_file():
            monkeypatch.setenv("ASTROLOG_BIN", candidate)
            return Path(candidate)
    pytest.skip("no real Astrolog found")


def test_saturn_return_is_found(real: Path) -> None:
    """Einstein's first Saturn return (Saturn back to ~4° Aries) fell in 1908."""
    natal = cast(Moment("1879-03-14", "11:30", "LMT", 48.4, 10.0, "Einstein"), P.load("default"))
    method = loader.load("psychological").method
    found = window(natal, P.load("default"), method, datetime(1907, 6, 1, 12, tzinfo=UTC), 540, 48.4, 10.0)
    returns = [w for w in found if (w.transit, w.natal, w.aspect) == ("saturn", "saturn", "conjunction")]
    assert returns and returns[0].min_orb < 0.2 and returns[0].exact and returns[0].exact.startswith(("1907", "1908"))
    sky = cast(Moment(returns[0].exact, "12:00", "UTC", 48.4, 10.0), P.load("default"))
    assert any(t.transit == "saturn" and t.natal == "saturn" for t in transit_aspects(natal, sky, method))
