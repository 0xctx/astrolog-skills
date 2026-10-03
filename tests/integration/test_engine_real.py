"""The engine against the real Astrolog: `uv run pytest -m astrolog`."""

from __future__ import annotations

import os
import pwd
import shutil
from pathlib import Path

import pytest

from astrolog_skills.engine import profile as P
from astrolog_skills.engine.batch import batch
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.moment import Moment
from astrolog_skills.engine.raw import raw
from astrolog_skills.engine.zodiac import AYANAMSAS

pytestmark = pytest.mark.astrolog
EINSTEIN = Moment("1879-03-14", "11:30", "LMT", 48.4, 10.0, "Einstein")
TOL = 0.001


@pytest.fixture
def real(monkeypatch: pytest.MonkeyPatch) -> Path:
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    for candidate in (os.environ.get("REAL_ASTROLOG", ""), str(home / "astrolog" / "astrolog")):
        if candidate and Path(candidate).is_file():
            monkeypatch.setenv("ASTROLOG_BIN", candidate)
            return Path(candidate)
    pytest.skip("no real Astrolog found (set REAL_ASTROLOG)")


def test_einstein_default(real: Path) -> None:
    c = cast(EINSTEIN, P.load("default"))
    expected = {"sun": 353.5077, "moon": 254.5259, "chiron": 35.5447, "north_node": 302.7313}
    for key, lon in expected.items():
        assert c.point(key).lon == pytest.approx(lon, abs=TOL), key
    assert c.angles["asc"] == pytest.approx(101.6464, abs=TOL)
    assert c.point("uranus").retrograde and c.point("sun").house == 10


def test_mean_node(real: Path, tmp_path: Path) -> None:
    mine = P.user_dir() / "mean.toml"
    mine.parent.mkdir(parents=True, exist_ok=True)
    mine.write_text('[points]\nnode = "mean"\nobjects = ["sun", "north_node"]\n')
    assert cast(EINSTEIN, P.load("mean")).point("north_node").lon == pytest.approx(301.4804, abs=TOL)


def test_lahiri_whole_sign(real: Path) -> None:
    c = cast(EINSTEIN, P.load("vedic-lahiri"))
    assert c.point("sun").lon == pytest.approx(331.3335, abs=TOL)
    assert c.cusps[1] % 30 == pytest.approx(0.0, abs=1e-6)  # whole-sign cusps sit on sign boundaries


@pytest.mark.parametrize("key", list(AYANAMSAS))
def test_every_registered_ayanamsa_is_applied(real: Path, key: str) -> None:
    mine = P.user_dir() / f"s-{key}.toml"
    mine.parent.mkdir(parents=True, exist_ok=True)
    mine.write_text(f'[zodiac]\ntype = "sidereal"\nayanamsa = "{key}"\n[points]\nobjects = ["sun"]\n')
    cast(EINSTEIN, P.load(f"s-{key}"))  # raises if Astrolog applied a different offset


def test_pins_beat_a_hostile_astrolog_as(real: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A user's astrolog.as that switches on sidereal/whole-sign/true node/harmonic 5 must not change results."""
    copy = tmp_path / "ast"
    copy.mkdir()
    for name in ("astrolog", "atlas.as", "timezone.as"):
        if (real.parent / name).exists():
            shutil.copy2(real.parent / name, copy / name)
    shutil.copytree(real.parent / "ephem", copy / "ephem")
    settings = (real.parent / "astrolog.as").read_text(encoding="latin-1")
    (copy / "astrolog.as").write_text(settings + "\n-s Lahiri\n-c 14\n=Yn\n-x 5\n", encoding="latin-1")
    monkeypatch.setenv("ASTROLOG_BIN", str(copy / "astrolog"))
    c = cast(EINSTEIN, P.load("default"))
    assert c.point("sun").lon == pytest.approx(353.5077, abs=TOL)
    assert c.cusps[1] == pytest.approx(118.6172, abs=TOL)  # Placidus, not whole sign


def test_raw_listing(real: Path) -> None:
    _, done = raw(["-v"], EINSTEIN, P.load("default"))
    assert done.returncode == 0 and "23Pis30" in done.stdout


def test_batch_round_trip(real: Path, tmp_path: Path) -> None:
    lst = tmp_path / "list.as"
    raw(["-o", str(lst)], EINSTEIN, P.load("default"))
    charts = batch(["-i", str(lst), "-il", str(lst)], P.load("default"))
    assert charts and charts[-1].lon("sun") == pytest.approx(353.5077, abs=0.001)
    assert "chiron" in charts[-1].points and set(charts[-1].angles) == {"asc", "mc"}
