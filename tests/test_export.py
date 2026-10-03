from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from astrolog_skills.analysis.aspects import find_aspects
from astrolog_skills.analysis.midpoints import midpoint_contacts
from astrolog_skills.analysis.patterns import score_harmonic
from astrolog_skills.engine import profile as P
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.moment import Moment
from astrolog_skills.errors import AstroError
from astrolog_skills.export import html
from astrolog_skills.packs import loader
from astrolog_skills.render import theme

EINSTEIN = Moment("1879-03-14", "11:30", "LMT", 48.4, 10.0, "Albert Einstein")
CORE = Path(__file__).resolve().parents[1] / "presets" / "default" / "core.js"


@pytest.fixture
def page(fake_astrolog: Path) -> tuple[dict, str]:
    data = html.payload(cast(EINSTEIN, P.load("default")), loader.load("vibrational"), theme.load("default"), 1)
    return data, html.render(data)


def test_self_contained(page: tuple[dict, str]) -> None:
    _, text = page
    assert re.search(r"(src|href)\s*=\s*[\"']https?:", text) is None
    assert "@import" not in text and "url(http" not in text and "<link" not in text
    for placeholder in ("/*@STYLE@*/", "/*@CORE@*/", "/*@APP@*/", "@DATA@", "@TITLE@"):
        assert placeholder not in text
    assert "<title>Albert Einstein · astrolog-skills</title>" in text


def test_embedded_json_is_escaped(fake_astrolog: Path) -> None:
    moment = Moment("2000-01-01", "12:00", "UTC", 0.0, 0.0, "</script><script>alert(1)</script> & <b>")
    data = html.payload(cast(moment, P.load("default")), loader.load("psychological"), theme.load("default"))
    text = html.render(data)
    assert "</script><script>alert(1)" not in text
    body = re.search(r'<script type="application/json" id="chart-data">(.*?)</script>', text, re.S)
    assert body and json.loads(body.group(1))["chart"]["name"].startswith("</script>")
    assert "<title>&lt;/script&gt;" in text


def test_payload_contents(page: tuple[dict, str]) -> None:
    data, text = page
    assert data["pack"]["midpoints"]["orb"] == 1.5 and data["display"]["orbs"] == "harmonic"
    assert all("harmonic" in a for a in data["pack"]["aspects"])
    assert [a["key"] for a in data["pack"]["midpoints"]["aspects"]] == [a["key"] for a in data["pack"]["aspects"]]
    assert 'id="tabs"' in text and 'id="tree"' in text
    # no aspect table on plain chart pages (by design); study pages build one beside the wheel from the study
    assert data.get("study") is None and "if (!box || !S || !S.configurations) return;" in text
    pack = data["pack"]
    assert {a["key"] for a in pack["aspects"]} >= {"conjunction", "quintile", "septile"}
    assert pack["patterns"]["weights"]["sun|moon"] == 10
    assert list(data["theme"]["elements"]["air"]["header_bg"]) == [200, 180, 250]


def test_preset_override_and_errors(fake_astrolog: Path, tmp_path: Path) -> None:
    mine = html.user_dir() / "mine"
    shutil.copytree(html.builtin_dir() / "default", mine)
    (mine / "style.css").write_text("body { color: hotpink; }")
    data = html.payload(cast(EINSTEIN, P.load("default")), loader.load("psychological"), theme.load("default"))
    assert "hotpink" in html.render(data, "mine")
    with pytest.raises(AstroError):
        html.render(data, "nope")
    (mine / "core.js").unlink()
    with pytest.raises(AstroError):
        html.render(data, "mine")


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("pack_name", ["psychological", "vibrational"])
def test_browser_maths_equals_python(fake_astrolog: Path, tmp_path: Path, pack_name: str) -> None:
    chart = cast(EINSTEIN, P.load("default"))
    pack = loader.load(pack_name)
    data = html.payload(chart, pack, theme.load("default"))
    (tmp_path / "data.json").write_text(json.dumps(data))
    script = f"""
      const C = require({json.dumps(str(CORE))});
      const D = require({json.dumps(str(tmp_path / "data.json"))});
      const out = {{}};
      const pack = m => Object.fromEntries(Object.entries(m).map(([k, v]) =>
        [k, v.map(c => [c.a, c.b, c.aspect, +c.orb.toFixed(4), +c.strength.toFixed(4), c.vibration])]));
      for (let h = 1; h <= 12; h++) {{
        out[h] = {{ aspects: C.aspects(D.chart, D.pack, h).map(a => [a.a, a.b, a.aspect, +a.orb.toFixed(4)]),
                    score: C.score(D.chart, D.pack, h),
                    old: pack(C.midpointContacts(D.chart, D.pack, h, "old")),
                    new: pack(C.midpointContacts(D.chart, D.pack, h, "new")) }};
      }}
      console.log(JSON.stringify(out));
    """
    js = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    lons = {p.key: p.lon for p in chart.points}
    for h in range(1, 13):
        py = sorted((a.a, a.b, a.aspect, a.orb) for a in find_aspects(chart, pack.method, h))
        got = sorted(tuple(x) for x in js[str(h)]["aspects"])
        assert [x[:3] for x in got] == [x[:3] for x in py], h
        assert [x[3] for x in got] == pytest.approx([x[3] for x in py], abs=2e-4), h
        ref = score_harmonic(lons, h, pack.method)
        assert js[str(h)]["score"]["score1"] == ref.score1
        assert js[str(h)]["score"]["score2"] == pytest.approx(ref.score2, abs=1e-3)
        assert [p["bodies"] for p in js[str(h)]["score"]["patterns"]] == [p.bodies for p in ref.patterns]
        for how in ("old", "new"):
            mids = midpoint_contacts(chart, pack.method, h, how)
            assert set(js[str(h)][how]) == set(mids), (h, how)
            for focus, contacts in mids.items():
                got_m = js[str(h)][how][focus]
                assert sorted(x[:3] for x in got_m) == sorted([c.a, c.b, c.aspect] for c in contacts), (h, how, focus)
                assert sorted(x[3] for x in got_m) == pytest.approx(sorted(c.orb for c in contacts), abs=2e-4)
                assert sorted(x[4] for x in got_m) == pytest.approx(sorted(c.strength for c in contacts), abs=2e-4)
                assert sorted((x[0], x[1], x[5]) for x in got_m) == sorted((c.a, c.b, c.vibration) for c in contacts)


def test_parse_harmonics() -> None:
    assert html.parse_harmonics("7", 180) == [7]
    assert html.parse_harmonics("1-4", 180) == [1, 2, 3, 4]
    assert html.parse_harmonics(" 11, 5,7,5 ", 180) == [5, 7, 11]
    assert html.parse_harmonics("1-3,16,20", 180) == [1, 2, 3, 16, 20]
    for bad in ("", "x", "0", "5-2", "1-200", "3,,4"):
        with pytest.raises(AstroError):
            html.parse_harmonics(bad, 180)


def test_harmonics_label_and_file_names(fake_astrolog: Path) -> None:
    assert html.harmonics_label([7]) == "7" and html.harmonics_label([1, 2, 3]) == "1-3"
    assert html.harmonics_label([1, 5, 7]) == "1_5_7"
    chart = cast(EINSTEIN, P.load("default"))
    assert html.export_path(chart, [1]).name == "albert-einstein.html"
    assert html.export_path(chart, [7]).name == "albert-einstein-h7.html"
    assert html.export_path(chart, [1, 5, 7]).name == "albert-einstein-h1_5_7.html"


def test_payload_harmonics_and_no_play_button(fake_astrolog: Path) -> None:
    chart = cast(EINSTEIN, P.load("default"))
    data = html.payload(chart, loader.load("vibrational"), theme.load("default"), [7, 5, 5])
    assert data["harmonics"] == [5, 7] and data["harmonic"] == 5
    assert html.payload(chart, loader.load("vibrational"), theme.load("default"), 7)["harmonics"] == [7]
    text = html.render(data)
    assert 'id="play"' not in text and "setInterval" not in text and 'id="hwrap"' in text
    # minimal page: title, wheel, slider (multi-harmonic only), aspect & midpoint trees — nothing else
    for gone in ('id="positions"', 'id="balance"', 'id="patterns"', 'id="chips"', 'id="legend"', 'id="mode"'):
        assert gone not in text


def test_export_cli_harmonic_options(fake_astrolog: Path) -> None:
    from tests.conftest import run_cli

    base = ("--json", "export", "html", "--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00")
    one = json.loads(run_cli(*base, "--harmonic", "7").stdout)
    assert one["harmonics"] == [7] and one["path"].endswith("-h7.html")
    some = json.loads(run_cli(*base, "--harmonics", "1,5,7", "--pack", "vibrational").stdout)
    assert some["harmonics"] == [1, 5, 7] and some["path"].endswith("-h1_5_7.html")
    default = json.loads(run_cli(*base, "--pack", "psychological").stdout)
    assert default["harmonics"] == list(range(1, 13))  # the pack's range
    both = run_cli(*base, "--harmonic", "7", "--harmonics", "1-3")
    assert both.returncode == 1
    high = json.loads(run_cli(*base, "--harmonics", "360").stdout)
    assert high["harmonics"] == [360] and "birth time" in high["notes"][0]
    assert not one["notes"]  # H7: a minute moves the Moon well under a degree


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_note_keys_match_between_browser_and_python(fake_astrolog: Path, tmp_path: Path) -> None:
    from astrolog_skills.export import notes

    chart = cast(EINSTEIN, P.load("default"))
    pack = loader.load("vibrational")
    data = html.payload(chart, pack, theme.load("default"))
    (tmp_path / "data.json").write_text(json.dumps(data))
    script = f"""
      const C = require({json.dumps(str(CORE))});
      const D = require({json.dumps(str(tmp_path / "data.json"))});
      const keys = [];
      for (const h of [1, 7]) {{
        for (const a of C.aspects(D.chart, D.pack, h)) {{
          if (a.a !== "south_node" && a.b !== "south_node") keys.push(`h${{h}}:${{a.a}}-${{a.aspect}}-${{a.b}}`);
        }}
        for (const [f, list] of Object.entries(C.midpointContacts(D.chart, D.pack, h))) {{
          for (const c of list) keys.push(`h${{h}}:${{f}}@${{c.a}}/${{c.b}}-${{c.aspect}}`);
        }}
      }}
      console.log(JSON.stringify(keys));
    """
    js = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    assert sorted(js) == sorted(c["key"] for c in notes.contacts(chart, pack.method, [1, 7]))


def test_notes_load_check_and_export(fake_astrolog: Path) -> None:
    from astrolog_skills.export import notes
    from tests.conftest import run_cli

    chart = cast(EINSTEIN, P.load("default"))
    pack = loader.load("psychological")
    known = notes.contacts(chart, pack.method, [1])
    aspect = next(c for c in known if c["kind"] == "aspect")
    path = notes.notes_path(chart, "psychological")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"contacts": {aspect["key"]: "  A note.  ", "h1:nope": "x", "h1:blank": " "}}))
    got = notes.load(path)
    assert got[aspect["key"]] == "A note." and "h1:blank" not in got
    report = notes.check(got, known)
    assert report["written"] == 1 and report["unknown_keys"] == ["h1:nope"]
    assert all(m["key"] != aspect["key"] for m in report["missing_tight_aspects"])
    only_sun = notes.check(got, known, defined={"sun"})
    assert only_sun["missing_tight_aspects"] == [] and only_sun["no_meanings_in_pack"] > 0
    (path.parent / "bad.json").write_text("{not json")
    with pytest.raises(AstroError):
        notes.load(path.parent / "bad.json")
    base = ("--json", "export", "html", "--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00")
    plain_page = json.loads(run_cli(*base, "--name", "Albert Einstein", "--pack", "psychological", "-H", "1").stdout)
    assert plain_page["reading_notes"] == 0 and "A note." not in Path(plain_page["path"]).read_text()  # off by default
    named = run_cli(*base, "--name", "Albert Einstein", "--pack", "psychological", "-H", "1", "--notes", str(path))
    assert json.loads(named.stdout)["reading_notes"] == 2  # naming a notes file implies --interp
    res = json.loads(
        run_cli(*base, "--name", "Albert Einstein", "--pack", "psychological", "-H", "1", "--interp").stdout
    )
    assert res["reading_notes"] == 2
    page = Path(res["path"]).read_text()
    assert "A note." in page and '"interp":true' in page


def test_notes_cli(fake_astrolog: Path) -> None:
    from tests.conftest import run_cli

    add = ("chart", "add", "Ein", "--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00")
    assert run_cli(*add).returncode == 0
    keys = json.loads(run_cli("--json", "notes", "keys", "--chart", "Ein", "--harmonics", "1,7").stdout)
    assert keys["path"].endswith("notes/ein-psychological.json") and keys["harmonics"] == [1, 7]
    assert {c["kind"] for c in keys["contacts"]} == {"aspect", "midpoint"}
    Path(keys["path"]).parent.mkdir(parents=True, exist_ok=True)
    Path(keys["path"]).write_text(json.dumps({"contacts": {keys["contacts"][0]["key"]: "Note."}}))
    check = json.loads(run_cli("--json", "notes", "check", "--chart", "Ein", "--harmonics", "1,7").stdout)
    assert check["written"] == 1 and check["unknown_keys"] == []
