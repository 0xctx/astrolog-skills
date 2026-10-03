"""Places, saved charts and sets against the real Astrolog + atlas: `uv run pytest -m astrolog`."""

from __future__ import annotations

import os
import pwd
from datetime import UTC, datetime
from pathlib import Path

import pytest

from astrolog_skills import places
from astrolog_skills.charts import sets, store
from astrolog_skills.charts.records import SetRecord
from astrolog_skills.engine import profile as P
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.moment import Moment
from astrolog_skills.errors import AstroError

pytestmark = pytest.mark.astrolog
FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def real(monkeypatch: pytest.MonkeyPatch) -> Path:
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    for candidate in (os.environ.get("REAL_ASTROLOG", ""), str(home / "astrolog" / "astrolog")):
        if candidate and Path(candidate).is_file() and (Path(candidate).parent / "atlas.as").is_file():
            monkeypatch.setenv("ASTROLOG_BIN", candidate)
            return Path(candidate)
    pytest.skip("no real Astrolog with atlas.as found (set REAL_ASTROLOG)")


def test_real_atlas(real: Path) -> None:
    assert places.resolve("Ulm, Germany").tz == "Europe/Berlin"
    assert places.resolve("Zürich").tz == "Europe/Zurich"
    assert places.resolve("New York, NY").tz == "America/New_York"
    with pytest.raises(AstroError):
        places.resolve("Springfield")


def test_saved_chart_matches_direct_cast(real: Path) -> None:
    record, _ = store.build("Einstein", "1879-03-14", "11:30", place="Ulm, Germany")
    store.save(record)
    saved = cast(store.load("Einstein").moment(), P.load("default"))
    direct = cast(Moment("1879-03-14", "11:30", "LMT", record.lat, record.lon), P.load("default"))
    assert saved.point("sun").lon == pytest.approx(direct.point("sun").lon, abs=1e-6)


def test_csv_set_batch_matches_individual_casts(real: Path) -> None:
    s = sets.create("csv", "csv", path=str(FIXTURES / "charts.csv"))
    pairs = sets.cast_set(s, P.load("default"))
    assert len(pairs) == 3
    for record, chart in pairs:
        when = (record.utc.strftime("%Y-%m-%d"), record.utc.strftime("%H:%M:%S"))
        single = cast(Moment(*when, "UTC", record.lat, record.lon), P.load("default"))
        for key in ("sun", "moon", "mercury", "chiron"):
            assert chart.lon(key) == pytest.approx(single.point(key).lon, abs=0.0003), (record.name, key)


def test_julian_record_through_batch(real: Path, tmp_path: Path) -> None:
    """Cardano (b. 24 Sep 1501 Julian): ADB lists Sun 10°41′ Libra, Moon 10°40′ Pisces, Asc 6°21′ Taurus."""
    cardano = SetRecord(
        "adb2", "Girolamo Cardano", datetime(1501, 10, 4, 17, 52, 20, tzinfo=UTC), 45 + 10 / 60, 9 + 10 / 60
    )
    from astrolog_skills.charts import chartlist
    from astrolog_skills.engine.batch import batch

    listing = chartlist.write([cardano], tmp_path / "c.as")
    (chart,) = batch(["-i", str(listing)], P.load("default"))
    assert chart.lon("sun") == pytest.approx(190 + 41 / 60, abs=0.02)
    assert chart.lon("moon") == pytest.approx(340 + 40 / 60, abs=0.02)
    assert chart.angles["asc"] == pytest.approx(36 + 21 / 60, abs=0.02)
