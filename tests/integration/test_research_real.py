"""Research sweeps with the real Astrolog: `uv run pytest -m astrolog` (+ `-m "network"` for the ADB sample)."""

from __future__ import annotations

import os
import pwd
import time
from pathlib import Path

import numpy as np
import pytest

from astrolog_skills.charts import sets
from astrolog_skills.engine import profile as P
from astrolog_skills.packs import loader
from astrolog_skills.research import sweep


@pytest.fixture
def real(monkeypatch: pytest.MonkeyPatch) -> Path:
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    for candidate in (os.environ.get("REAL_ASTROLOG", ""), str(home / "astrolog" / "astrolog")):
        if candidate and Path(candidate).is_file():
            monkeypatch.setenv("ASTROLOG_BIN", candidate)
            return Path(candidate)
    pytest.skip("no real Astrolog found")


@pytest.mark.astrolog
def test_real_csv_sweep(real: Path, tmp_path: Path) -> None:
    rng = np.random.default_rng(5)
    rows = ["name,date,time,tz,lat,lon"]
    for i in range(60):
        y, m, d = 1900 + int(rng.integers(0, 100)), 1 + int(rng.integers(0, 12)), 1 + int(rng.integers(0, 28))
        hh, mm = int(rng.integers(0, 24)), int(rng.integers(0, 60))
        rows.append(f"P{i},{y}-{m:02d}-{d:02d},{hh:02d}:{mm:02d},UTC,48.4,10.0")
    path = tmp_path / "people.csv"
    path.write_text("\n".join(rows) + "\n")
    sets.create("people", "csv", path=str(path))
    result = sweep.sweep("people", P.load("vibrational"), loader.load("vibrational"), 1, 16, shuffles=8)
    assert result.count == 60
    every = [s for stats in result.measures.values() for s in stats]
    assert len(result.measures) == 3 and all(abs(s.z) < 6 for s in every)  # random people vs recombined controls


@pytest.mark.astrolog
@pytest.mark.network
def test_real_adb_sample_sweep_is_calibrated_and_fast(real: Path) -> None:
    from astrolog_skills.cli.commands.data import fetch_sample

    sample = fetch_sample()
    sets.create("aa", "adb", path=str(sample), filter_=sets.SetFilter(ratings=["AA"]))
    started = time.perf_counter()
    result = sweep.sweep("aa", P.load("vibrational"), loader.load("vibrational"), 1, 32, shuffles=20)
    assert time.perf_counter() - started < 60
    # A set against its own recombined controls should look like "no effect" by every measure: z centred on 0 and few
    # large values. (One harmonic reaching the smallest possible adjusted p, 1/21, happens ~5% of runs by chance.)
    for measure, stats in result.measures.items():
        zs = np.array([s.z for s in stats])
        assert abs(zs.mean()) < 1 and (np.abs(zs) > 3).sum() <= 2, measure
