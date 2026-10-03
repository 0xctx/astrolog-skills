"""Against the real Astrolog on this machine: `uv run pytest -m astrolog` (skips if none is found)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from astrolog_skills import firstlight
from astrolog_skills.astrolog import locate
from astrolog_skills.astrolog.run import expressions
from astrolog_skills.doctor import SMOKE_CHART, SMOKE_SUN, SMOKE_TOLERANCE

pytestmark = pytest.mark.astrolog


@pytest.fixture
def real_astrolog(monkeypatch: pytest.MonkeyPatch) -> Path:
    # the autouse fixture replaced HOME; look at the real one via the password database
    import pwd

    real_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    for candidate in [
        os.environ.get("REAL_ASTROLOG", ""),
        str(real_home / "astrolog" / "astrolog"),
        str(real_home / ".astrolog-skills" / "astrolog" / "astrolog"),
    ]:
        if candidate and locate.is_runnable(Path(candidate)):
            monkeypatch.setenv("ASTROLOG_BIN", candidate)
            return Path(candidate)
    pytest.skip("no real Astrolog found (set REAL_ASTROLOG=/path/to/astrolog)")


def test_version_supported(real_astrolog: Path) -> None:
    v = locate.version(real_astrolog)
    assert v and v >= locate.MIN_VERSION


def test_einstein_smoke(real_astrolog: Path) -> None:
    (sun,) = expressions(real_astrolog, SMOKE_CHART, ["ObjLon O_Sun"])
    assert abs(sun - SMOKE_SUN) <= SMOKE_TOLERANCE


def test_first_light_sane(real_astrolog: Path) -> None:
    data = firstlight.first_light(real_astrolog, datetime(2026, 9, 29, 12, 0, tzinfo=UTC), (48.4, 10.0))
    assert data["sun"]["text"].endswith("Libra")  # the Sun is in Libra on 29 September
    for part in ("sun", "moon", "rising"):
        assert 0 <= data[part]["lon"] < 360
