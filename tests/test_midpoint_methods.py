"""Midpoint structures by the old and new methods, their own vibration, and the strongest harmonics against random
charts. The worked examples are the 2026 source's (numbers only; its rounded 18′ steps)."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from astrolog_skills.analysis import chance
from astrolog_skills.analysis.midpoints import midpoint_contacts, rank_harmonics, vibration
from astrolog_skills.engine.model import ChartModel, Point
from astrolog_skills.engine.objects import BY_KEY
from astrolog_skills.packs import loader
from tests.conftest import run_cli

VIB = loader.load("vibrational").method


def chart(**lons: float) -> ChartModel:
    pts = [Point(k, BY_KEY[k].name, BY_KEY[k].glyph, v, 1.0, 0.5) for k, v in lons.items()]
    return ChartModel("t", {}, {}, pts, [], {})


def contact(
    c: ChartModel, focus: str, a: str, b: str, h: int, how: str, aspects: tuple[str, ...]
) -> tuple[str, float] | None:
    m = replace(VIB, midpoint_choice=aspects)
    hit = next((x for x in midpoint_contacts(c, m, h, how)[focus] if {x.a, x.b} == {a, b}), None)
    return None if hit is None else (hit.aspect, round(hit.strength, 2))


# Moon 20°02′ from the Sun/Saturn midpoint: 9 × 20°02′ = 180°18′ (an 18′ orb in the 9th harmonic)
MOON = chart(sun=40.0, saturn=149.0, moon=94.5 - (20 + 0.3 / 9))
# Venus square the Moon/Neptune midpoint with a 23′ orb
VENUS = chart(moon=10.0, neptune=70.0, venus=130 + 23 / 60)


@pytest.mark.parametrize(
    ("h", "old", "new"),
    [
        (9, ("conjunction", 0.8), ("opposition", 0.8)),
        (18, ("opposition", 0.6), ("conjunction", 0.8)),
        (27, ("opposition", 0.4), ("opposition", 0.4)),
        (36, ("opposition", 0.2), ("conjunction", 0.6)),
        (72, None, ("conjunction", 0.2)),
    ],
)
def test_the_moon_example(h: int, old: tuple[str, float] | None, new: tuple[str, float]) -> None:
    axis = ("conjunction", "opposition")
    assert contact(MOON, "moon", "sun", "saturn", h, "old", axis) == old
    assert contact(MOON, "moon", "sun", "saturn", h, "new", axis) == new


@pytest.mark.parametrize(
    ("h", "old", "new"),
    [
        (1, ("square", 0.49), ("square", 0.49)),
        (2, ("opposition", 0.49), ("opposition", 0.49)),
        (4, None, ("conjunction", 0.49)),
    ],
)
def test_the_venus_example(h: int, old: tuple[str, float] | None, new: tuple[str, float]) -> None:
    dial = ("conjunction", "opposition", "square")
    assert contact(VENUS, "venus", "moon", "neptune", h, "old", dial) == old
    assert contact(VENUS, "venus", "moon", "neptune", h, "new", dial) == new


def test_own_vibration_and_natal_angle() -> None:
    hit = next(x for x in midpoint_contacts(MOON, VIB, 9, "new")["moon"] if {x.a, x.b} == {"sun", "saturn"})
    assert hit.vibration == 18 and hit.natal_angle == pytest.approx(20.0333, abs=1e-3) and hit.method == "new"
    assert vibration(20.0333, 3.0, 17) is None and vibration(0.5, 3.0, 32) == 1


def test_old_method_orbs_are_proportionate() -> None:
    """A square to a midpoint gets 45′, not the conjunction's 1.5° (the flat orb was a bug)."""
    loose = chart(moon=10.0, neptune=70.0, venus=130.0 + 1.0)  # square by 1°: in a flat 1.5° orb, out at 45′
    assert contact(loose, "venus", "moon", "neptune", 1, "old", ("conjunction", "opposition", "square")) is None
    tight = chart(moon=10.0, neptune=70.0, venus=130.0 + 0.5)
    assert contact(tight, "venus", "moon", "neptune", 1, "old", ("conjunction", "opposition", "square")) == (
        "square",
        round(1 - 0.5 / 0.75, 2),
    )


def test_the_pack_picks_the_method_and_the_orb() -> None:
    assert VIB.midpoint_method == "new" and VIB.midpoint_new_orb == 3.0 and VIB.midpoint_orb == 1.5
    assert loader.load("psychological").method.midpoint_method == "old"
    four = midpoint_contacts(MOON, VIB, 72, "new", new_orb=4.0)["moon"]
    hit = next(x for x in four if {x.a, x.b} == {"sun", "saturn"})
    assert hit.limit == 4.0 and hit.strength == pytest.approx(1 - 2.4 / 4, abs=0.01)


def test_the_birth_chart_uses_the_classic_method() -> None:
    # at H1 both methods measure the same angle; only the orb would differ, so the lists don't switch there
    lists = midpoint_contacts(VENUS, VIB, 1)
    assert {c.method for hits in lists.values() for c in hits} == {"old"}
    assert {c.method for hits in midpoint_contacts(VENUS, VIB, 4).values() for c in hits} == {"new"}
    app = (Path(__file__).resolve().parents[1] / "presets/default/app.js").read_text()
    assert 'state.h === 1 ? "old" : state.mid' in app and "sw.hidden = state.h === 1" in app


# ── chance and ranking ────────────────────────────────────────────────────────


def test_chance_baseline_is_stable_and_cached() -> None:
    chance.baseline.cache_clear()
    first = chance.baseline(5, 6, 3.0, 1.5)
    assert all(c.new_sd > 0 and c.old_sd > 0 for c in first.values()) and set(first) == set(range(1, 7))
    chance.baseline.cache_clear()
    assert chance.baseline(5, 6, 3.0, 1.5) == first  # read back from the cache file


def test_random_charts_centre_on_zero() -> None:
    """Scored against their own baseline, fresh random charts average close to 0σ."""
    base = chance.baseline(10, 12, 3.0, 1.5)
    rng = np.random.default_rng(99)
    new, _ = chance.sums(rng.uniform(0, 360, (200, 10)), 12, 3.0, 1.5)
    z = [(new[:, n].mean() - base[n].new_mean) / base[n].new_sd for n in range(1, 13)]
    assert abs(float(np.mean(z))) < 0.3


def test_an_exact_structure_tops_its_vibration() -> None:
    planets = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"]
    lons = dict(zip(planets, [3.0, 77.0, 131.0, 199.0, 241.0, 283.0, 311.0, 17.0, 157.0, 337.0], strict=True))
    lons["venus"] = (3.0 + 77.0) / 2 + 2 * 360 / 17  # Venus 2/17 of the circle from the Sun/Moon midpoint
    r = rank_harmonics(chart(**lons), VIB, list(range(1, 33)))
    h17 = next(h for h in r.harmonics if h.harmonic == 17)
    assert any((s.focus, s.a, s.b, s.strength) == ("venus", "sun", "moon", 1.0) for s in h17.new_structures)
    top = next(s for s in r.structures if (s["focus"], s["a"], s["b"]) == ("venus", "sun", "moon"))
    assert top["harmonic"] == 17 and top["fraction"] == "2/17" and top["strength"] == 1.0
    assert r.ranked("new")[0].harmonic in range(1, 33)
    assert r.ranked("aspects")[0].aspects >= r.ranked("aspects")[-1].aspects


# ── command and page ──────────────────────────────────────────────────────────


def ok(*args: str) -> dict:  # type: ignore[type-arg]
    done = run_cli("--json", *args)
    assert done.returncode == 0, done.stdout + done.stderr
    return json.loads(done.stdout)  # type: ignore[no-any-return]


def test_cli(fake_astrolog: Path) -> None:
    add = ("chart", "add", "Ein", "--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00")
    assert run_cli(*add).returncode == 0
    data = ok("harmonics", "--chart", "Ein", "--harmonics", "1-12")
    assert [h["harmonic"] for h in data["harmonics"]] == list(range(1, 13)) and len(data["ranked"]) == 8  # --top 8
    assert data["orbs"] == {"new": 3.0, "old": 1.5} and "z_new" in data["harmonics"][0]
    detail = ok("harmonics", "--chart", "Ein", "--harmonic", "5", "--orb-base", "4")
    assert detail["detail"]["harmonic"] == 5 and set(detail["detail"]["midpoints"]) == {"new", "old"}
    assert detail["orbs"]["new"] == 4.0
    for bad in (("--by", "magic"), ("--orb-base", "12")):
        assert run_cli("harmonics", "--chart", "Ein", *bad).returncode != 0
    shown = run_cli("harmonics", "--chart", "Ein", "--harmonics", "1,5,7,18")
    assert shown.returncode == 0 and "strongest harmonics H1, H5, H7, H18" in shown.stdout


def test_page_payload(fake_astrolog: Path, tmp_path: Path) -> None:
    import re

    add = ("chart", "add", "Ein", "--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00")
    assert run_cli(*add).returncode == 0

    def page(*extra: str) -> dict:  # type: ignore[type-arg]
        out = tmp_path / "p.html"
        args = ("export", "html", "--chart", "Ein", "--pack", "vibrational", "--out", str(out), *extra)
        assert run_cli(*args).returncode == 0
        return json.loads(re.search(r'id="chart-data">(.*?)</script>', out.read_text(), re.S).group(1))  # type: ignore[union-attr]

    many = page("--harmonics", "1-8")
    assert many["pack"]["midpoints"]["method"] == "new" and len(many["strongest"]["harmonics"]) == 8
    assert page("--harmonic", "5")["strongest"] is None
    assert page("--harmonics", "1-4", "--midpoints", "old")["pack"]["midpoints"]["method"] == "old"


def test_the_sweep_measures_a_chart_as_the_single_chart_tool_does() -> None:
    """chance.sums (vectorised, used by research sweeps) equals rank_harmonics (one chart) for both methods."""
    planets = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"]
    lons = [353.5, 254.4, 3.2, 17.1, 296.9, 327.2, 4.6, 151.3, 38.3, 54.6]
    r = rank_harmonics(chart(**dict(zip(planets, lons, strict=True))), VIB, list(range(1, 25)))
    new, old = chance.sums(np.array([lons]), 24, VIB.midpoint_new_orb, VIB.midpoint_orb)
    for h in r.harmonics:
        assert new[0, h.harmonic] == pytest.approx(h.new, abs=2e-3), h.harmonic
        assert old[0, h.harmonic] == pytest.approx(h.old, abs=2e-3), h.harmonic
