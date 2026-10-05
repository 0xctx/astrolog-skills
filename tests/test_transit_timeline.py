"""Transit timelines: every transit to natal planets, angles and midpoints over a window (each retrograde pass and
exact date), tagged with its aspect's harmonic; the patterns transits form in harmonic charts; and the harmonic
transit chart (both charts × H) in the terminal view and the browser."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from astrolog_skills.analysis import transit_timeline as tt
from astrolog_skills.analysis.aspects_registry import BY_KEY as ASPECTS
from astrolog_skills.engine.model import ChartModel, Point
from astrolog_skills.engine.objects import BY_KEY
from astrolog_skills.errors import AstroError
from astrolog_skills.packs import loader
from tests.conftest import run_cli

VIB = loader.load("vibrational").method
SEVENTH = 360 / 7
START = datetime(2026, 1, 1, 0, tzinfo=UTC)
EIN = ("chart", "add", "Ein", "--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00")


def chart(speeds: dict[str, float] | None = None, **lons: float) -> ChartModel:
    speeds = speeds or {}
    pts = [Point(k, BY_KEY[k].name, BY_KEY[k].glyph, v, 0.0, speeds.get(k, 0.0)) for k, v in lons.items()]
    return ChartModel("t", {}, {}, pts, [], {})


def skies(track: dict[str, list[float]]) -> list[ChartModel]:
    n = len(next(iter(track.values())))
    return [
        chart({k: v[min(d + 1, n - 1)] - v[d] for k, v in track.items()}, **{k: v[d] for k, v in track.items()})
        for d in range(n)
    ]


def found(natal: ChartModel, track: dict[str, list[float]], sel: tt.Selection | None = None) -> list[tt.Passage]:
    return tt.passages(natal, skies(track), START, VIB, sel or tt.Selection())


def test_a_septile_transit_is_tagged_h7_with_its_exact_date() -> None:
    rows = found(chart(venus=0.0), {"saturn": [SEVENTH - 1.0 + 0.4 * d for d in range(6)]})
    sept = [r for r in rows if r.aspect == "septile"]
    assert len(sept) == 1 and sept[0].harmonic == 7 and sept[0].natal == "venus"
    assert sept[0].exact == ["2026-01-03"]  # 1° away at 0.4°/day: 2.5 days, Jan 3 at noon
    assert sept[0].limit == VIB.transit_orb(ASPECTS["septile"])


def test_every_retrograde_pass_is_an_exact_date() -> None:
    path = [SEVENTH - 0.5, SEVENTH + 0.3, SEVENTH + 0.5, SEVENTH + 0.2, SEVENTH - 0.3, SEVENTH - 0.4, SEVENTH + 0.4]
    sept = [r for r in found(chart(venus=0.0), {"saturn": path}) if r.aspect == "septile"]
    assert len(sept) == 1 and len(sept[0].exact) == 3  # direct, retrograde, direct again
    assert sept[0].exact == sorted(sept[0].exact)


def test_transits_to_natal_midpoints() -> None:
    natal = chart(sun=0.0, moon=40.0)  # Sun/Moon midpoint 20°
    rows = found(natal, {"jupiter": [19.0 + 0.2 * d for d in range(11)]})
    mid = next(r for r in rows if r.natal == "sun/moon" and r.aspect == "conjunction")
    assert mid.limit == VIB.midpoint_orb and mid.exact == ["2026-01-06"]  # the pack's midpoint orb
    assert not [r for r in found(natal, {"jupiter": [20.0] * 3}, tt.Selection(midpoints=False)) if "/" in r.natal]


def test_choosing_bodies_and_aspects() -> None:
    natal = chart(venus=0.0, mars=200.0)
    track = {"saturn": [SEVENTH] * 3, "jupiter": [90.0] * 3}
    only7 = found(natal, track, tt.Selection(aspects=("h7",), midpoints=False))
    assert {r.harmonic for r in only7} == {7}
    sat = found(natal, track, tt.Selection(transiting=("saturn",), natal=("venus",), midpoints=False))
    assert {(r.transit, r.natal) for r in sat} == {("saturn", "venus")}
    sky = skies(track)
    with pytest.raises(AstroError, match="no transiting ceres"):
        tt.Selection(transiting=("ceres",)).check(natal, sky)
    with pytest.raises(AstroError, match="Unknown aspect"):
        tt.Selection(aspects=("wobble",)).check(natal, sky)


def test_slowest_transits_come_first() -> None:
    rows = found(chart(venus=0.0), {"mars": [0.5 * d for d in range(5)], "saturn": [0.02 * d for d in range(5)]})
    assert rows[0].transit == "saturn"


def test_a_transit_joining_a_natal_harmonic_aspect_is_a_pattern() -> None:
    natal = chart(venus=0.0, mars=SEVENTH)  # a septile: together in H7
    track = {"saturn": [2 * SEVENTH + 0.03 * d for d in range(5)]}  # 2/7 of the circle from Venus: joins them in H7
    pats = tt.harmonic_patterns(natal, skies(track), START, VIB, list(range(1, 15)), tt.Selection())
    h7 = [p for p in pats if p.harmonic == 7]
    assert h7 and h7[0].transits == ["saturn"] and h7[0].natal == ["mars", "venus"] and h7[0].starts == "2026-01-01"
    assert not [p for p in pats if p.harmonic == 14]  # the same bodies in H14 belong to H7


def test_cli(fake_astrolog: Path) -> None:
    assert run_cli(*EIN).returncode == 0
    done = run_cli(
        "--json", "transits", "--chart", "Ein", "--on", "1921-11-09", "--days", "20", "--pack", "vibrational"
    )
    assert done.returncode == 0, done.stdout + done.stderr
    line = json.loads(done.stdout)["timeline"]
    assert line["days"] == 20 and line["passages_total"] >= len(line["passages"]) > 0
    assert {"harmonic", "exact", "enters", "leaves"} <= set(line["passages"][0]) and line["harmonics"][0] == 1
    shown = run_cli("transits", "--chart", "Ein", "--on", "1921-11-09", "--days", "20", "--aspects", "h7,h9")
    assert (
        shown.returncode == 0 and "Next 20 days" in shown.stdout and "Harmonic patterns with transits" in shown.stdout
    )
    bad = run_cli("transits", "--chart", "Ein", "--days", "5", "--transiting", "ceres")
    assert bad.returncode != 0 and "--points" in bad.stdout


def test_harmonic_views_carry_the_transits() -> None:
    from astrolog_skills.render.views.common import ViewData

    v = ViewData.build(chart(venus=10.0), loader.load("vibrational"), 7, chart(saturn=10.0 + SEVENTH))
    assert v.transit is not None and v.transit.harmonic == 7  # the harmonic transit chart: both × 7
    assert [(a.transit, a.natal, a.aspect) for a in v.transit_aspects or []] == [("saturn", "venus", "conjunction")]


def test_export_with_transits(fake_astrolog: Path, tmp_path: Path) -> None:
    assert run_cli(*EIN).returncode == 0
    page = tmp_path / "t.html"
    args = ("export", "html", "--chart", "Ein", "--pack", "vibrational", "--harmonics", "1-8", "--out", str(page))
    done = run_cli(*args, "--transits", "1921-11-09", "--days", "20")
    assert done.returncode == 0, done.stdout + done.stderr
    data = json.loads(page.read_text().split('id="chart-data">', 1)[1].split("</script>", 1)[0])
    t = data["transits"]
    assert t["days"] == 20 and len(t["passages"]) == t["passages_total"] and len(t["bodies"]["saturn"]) == 21
    assert "south_node" not in t["bodies"] and data["pack"]["transits"][0]["orb"] > 0
    assert run_cli(*args, "--transits", "1921-11-09", "--days", "0").returncode != 0


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_browser_harmonic_transit_chart_equals_python(fake_astrolog: Path, tmp_path: Path) -> None:
    from astrolog_skills.analysis.harmonics import harmonic_chart
    from astrolog_skills.analysis.transits import transit_aspects
    from astrolog_skills.engine import profile as P
    from astrolog_skills.engine.cast import cast
    from astrolog_skills.export import html
    from astrolog_skills.render import theme
    from tests.test_export import CORE, EINSTEIN

    natal = cast(EINSTEIN, P.load("default"))
    sky = chart(
        sun=231.4, mercury=250.2, venus=190.7, mars=172.3, jupiter=180.9, saturn=183.6, uranus=327.1, pluto=99.8
    )
    pack = loader.load("vibrational")
    (tmp_path / "data.json").write_text(json.dumps(html.payload(natal, pack, theme.load("default"))))
    script = f"""
      const C = require({json.dumps(str(CORE))});
      const D = require({json.dumps(str(tmp_path / "data.json"))});
      const out = {{}};
      const sky = {json.dumps({p.key: p.lon for p in sky.points})};
      for (const h of [1, 5, 7, 17]) out[h] = C.transitContacts(D.chart, D.pack, h, sky)
        .map(c => [c.transit, c.natal, c.aspect, +c.orb.toFixed(4)]);
      console.log(JSON.stringify(out));
    """
    js = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    for h in (1, 5, 7, 17):
        py = transit_aspects(harmonic_chart(natal, h), harmonic_chart(sky, h), pack.method)
        assert sorted((a.transit, a.natal, a.aspect) for a in py) == sorted(tuple(x[:3]) for x in js[str(h)]), h
        orbs = {(a.transit, a.natal): a.orb for a in py}
        assert all(abs(x[3] - orbs[(x[0], x[1])]) < 2e-4 for x in js[str(h)])


def test_the_harmonic_transit_chart_shows_the_groups_transits_form() -> None:
    from astrolog_skills.render import theme
    from astrolog_skills.render.views.chart import draw
    from astrolog_skills.render.views.common import ViewData

    natal = chart(venus=0.0, mars=SEVENTH, sun=200.0)
    v = ViewData.build(natal, loader.load("vibrational"), 7, chart(saturn=2 * SEVENTH))
    assert [p.bodies for p in v.transit_patterns or []] == [["venus", "mars", "t:saturn"]]
    text = draw(v, theme.load("default"), 80).plain()
    assert "GROUPS WITH TRANSITS" in text and "Ven-Mar-tSat" in text


def test_a_tradition_without_pattern_rules_reads_no_patterns() -> None:
    hel = loader.load("hellenistic").method
    assert not hel.reads_patterns and hel.harmonic_range == (1, 1)  # birth chart only: no harmonic patterns
    assert loader.load("vibrational").method.reads_patterns and loader.load("psychological").method.reads_patterns
