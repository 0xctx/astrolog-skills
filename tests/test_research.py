from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest

from astrolog_skills.analysis.patterns import score_harmonic
from astrolog_skills.charts import sets
from astrolog_skills.charts.records import SetRecord
from astrolog_skills.engine import profile as P
from astrolog_skills.errors import AstroError
from astrolog_skills.packs import loader
from astrolog_skills.research import runs, sweep, vector


def test_vector_scores_equal_the_reference_engine() -> None:
    base = loader.load("vibrational").method
    bodies = list(base.pattern_bodies)
    lons = np.random.default_rng(7).uniform(0, 360, (120, len(bodies)))
    for method in (base, dataclasses.replace(base, exclude_lower_harmonics=True)):
        for h in (1, 2, 5, 7, 12, 30):
            s1, s2 = vector.scores(lons, bodies, method, h)
            for n in range(0, 120, 11):
                ref = score_harmonic(dict(zip(bodies, lons[n], strict=True)), h, method)
                assert ref.score1 == s1[n] and ref.score2 == pytest.approx(float(s2[n]), abs=1e-3)


def test_vector_five_planet_group() -> None:
    m = loader.load("vibrational").method
    bodies = list(m.pattern_bodies)
    row = np.array([[0.0, 2.0, 4.0, 6.0, 8.0, 100.0, 150.0, 200.0, 250.0, 300.0]])
    s1, _ = vector.scores(row, bodies, m, 1)
    assert s1[0] == 5


def _rec(i: int, y: int, mo: int, d: int, h: int = 12) -> SetRecord:
    return SetRecord(f"r{i}", f"R{i}", datetime(y, mo, d, h, 0, tzinfo=UTC), 10.0 + i, 20.0 + i)


def test_control_records_recombine_real_components() -> None:
    records = [_rec(0, 1980, 2, 29, 5), _rec(1, 1981, 7, 10, 17), _rec(2, 1990, 12, 31, 0)]
    groups = sweep.control_records(records, shuffles=4, sample=10, seed=3)
    assert len(groups) == 4 and all(len(g) == 3 for g in groups)
    years = {r.utc.year for r in records}
    for g in groups:
        for c in g:
            assert (
                c.utc.year in years
                and c.utc.hour in {5, 17, 0}
                and (c.lat, c.lon) in {(10.0, 20.0), (11.0, 21.0), (12.0, 22.0)}
            )
            assert c.source == "control"
    # 29 Feb only survives in a leap year
    assert all(not (c.utc.month == 2 and c.utc.day == 29 and c.utc.year % 4) for g in groups for c in g)
    assert sweep.control_records(records, 4, 10, 3)[0][0].utc == groups[0][0].utc  # seeded → repeatable


def _csv_set(tmp: Path, n: int = 40, name: str = "demo") -> str:
    lines = ["name,date,time,tz,lat,lon,rating"]
    rng = np.random.default_rng(11)
    for i in range(n):
        y, mo, d = 1930 + int(rng.integers(0, 70)), 1 + int(rng.integers(0, 12)), 1 + int(rng.integers(0, 28))
        lines.append(
            f"P{i},{y}-{mo:02d}-{d:02d},{int(rng.integers(0, 24)):02d}:{int(rng.integers(0, 60)):02d},UTC,48.4,10.0,AA"
        )
    path = tmp / f"{name}.csv"
    path.write_text("\n".join(lines) + "\n")
    sets.create(name, "csv", path=str(path))
    return name


def test_sweep_end_to_end(fake_astrolog: Path, tmp_path: Path) -> None:
    name = _csv_set(tmp_path)
    result = sweep.sweep(name, P.load("vibrational"), loader.load("vibrational"), 1, 12, shuffles=6, seed=2, top=3)
    assert result.count == 40 and set(result.measures) == {"new", "old", "aspects"}
    for stats in result.measures.values():
        assert [s.harmonic for s in stats] == list(range(1, 13))
        for s in stats:
            assert s.expected > 0 and 0 < s.p_family <= 1 and len(s.top) == 3
    assert len(result.charts) == 40 and len(result.charts[0]["strongest"]) == 3
    again = sweep.sweep(name, P.load("vibrational"), loader.load("vibrational"), 1, 12, shuffles=6, seed=2, top=3)
    assert again.to_dict() == result.to_dict()  # same seed, same answer


def test_sweep_with_control_set(fake_astrolog: Path, tmp_path: Path) -> None:
    a, b = _csv_set(tmp_path, 30, "a"), _csv_set(tmp_path, 25, "b")
    result = sweep.sweep(a, P.load("vibrational"), loader.load("vibrational"), 1, 4, shuffles=4, control=b)
    assert all(s.control_mean is not None for stats in result.measures.values() for s in stats)
    only = sweep.sweep(a, P.load("vibrational"), loader.load("vibrational"), 1, 4, shuffles=4, measures=("old",))
    assert list(only.measures) == ["old"] and only.params["measures"] == ["old"]
    with pytest.raises(AstroError):
        sweep.sweep(a, P.load("vibrational"), loader.load("vibrational"), 1, 4, shuffles=4, measures=("magic",))


def test_sweep_refuses_tiny_sets_and_missing_planets(fake_astrolog: Path, tmp_path: Path) -> None:
    tiny = _csv_set(tmp_path, 5, "tiny")
    with pytest.raises(AstroError) as err:
        sweep.sweep(tiny, P.load("vibrational"), loader.load("vibrational"), 1, 4, shuffles=3)
    assert "too few" in err.value.message
    big = _csv_set(tmp_path, 20, "big")
    with pytest.raises(AstroError) as err:
        sweep.sweep(big, P.load("vedic-lahiri"), loader.load("vibrational"), 1, 4, shuffles=3)
    assert "uranus" in err.value.message


def test_runs_save_list_load(fake_astrolog: Path, tmp_path: Path) -> None:
    name = _csv_set(tmp_path)
    pack = loader.load("vibrational")
    result = sweep.sweep(name, P.load("vibrational"), pack, 1, 3, shuffles=3)
    path = runs.save(result, pack)
    listed = runs.list_runs()
    assert listed[0]["id"] == path.stem and listed[0]["range"] == [1, 3] and listed[0]["count"] == 40
    loaded = runs.load(path.stem[:15])
    assert loaded["meta"]["pack"]["method_sha256"] and loaded["meta"]["set"]["kind"] == "csv"
    assert loaded["meta"]["params"]["baseline"].startswith("recombined")
    with pytest.raises(AstroError):
        runs.load("nope")
