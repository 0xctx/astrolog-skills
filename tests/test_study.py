from __future__ import annotations

import json
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

from astrolog_skills.analysis.doctrine import parse_doctrine
from astrolog_skills.analysis.doctrine.explain import build_study, ordinal, pos
from astrolog_skills.engine import profile as P
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.moment import Moment
from astrolog_skills.packs import loader
from astrolog_skills.packs.meanings import glossary, load
from astrolog_skills.render import compose, theme
from astrolog_skills.render.views.common import ViewData
from tests.conftest import run_cli

FIXTURE = Path(__file__).parent / "fixtures" / "doctrine_pack.toml"
D = parse_doctrine(tomllib.loads(FIXTURE.read_text()), "t")
EINSTEIN = Moment("1879-03-14", "11:30", "LMT", 48.4, 10.0, "Albert Einstein")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
MEANINGS = """# Test pack

## Planets
- **Sun** — light.

## Glossary
- **Of the sect** — works for the native. (p. 1)
- **Striking with a ray** — a ray cast back. (p. 6)
- **Opposition and trine** — a long title that names an aspect
  but must not become the opposition's meaning. (p. 6)
- **Peak period** — angular to Fortune. (p. 9-10)

## Lots
- **Fortune** — the body.
"""


def test_glossary_is_kept_apart_from_the_meanings() -> None:
    g = glossary(MEANINGS)
    assert set(g) == {"of_the_sect", "striking_with_a_ray", "opposition_and_trine", "peak_period"}
    assert (
        g["opposition_and_trine"]["text"].endswith("opposition's meaning.") and g["peak_period"]["pages"] == "p. 9-10"
    )
    assert load(None)["aspects"] == {}
    from astrolog_skills.packs.meanings import parse

    parsed = parse(MEANINGS)
    assert parsed["bodies"]["sun"] == "light." and "opposition" not in parsed["aspects"]


def test_formatting_helpers() -> None:
    assert pos(2.6634) == "2°39′ Aries" and pos(359.999) == "29°59′ Pisces"
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22)] == [
        "1st",
        "2nd",
        "3rd",
        "4th",
        "11th",
        "12th",
        "13th",
        "21st",
        "22nd",
    ]


@pytest.fixture
def study(fake_astrolog: Path) -> dict:  # type: ignore[type-arg]
    assert D is not None
    return build_study(cast(EINSTEIN, P.load("default")), D, glossary(MEANINGS), years=40)


def test_study_has_every_part(study: dict) -> None:  # type: ignore[type-arg]
    assert set(study) >= {
        "sect",
        "planets",
        "lots",
        "places",
        "profections",
        "releasing",
        "lords",
        "glossary",
        "birth",
        "end",
    }
    json.dumps(study)
    assert len(study["planets"]) == 7 and len(study["places"]) == 12
    assert study["end"] == "1919-03-14" and len(study["profections"]) == 41 * 3
    assert set(study["releasing"]) == {"fortune", "spirit"}
    # only the glossary entries the page uses travel with it
    assert set(study["glossary"]) <= set(glossary(MEANINGS))


def test_every_finding_explains_itself(study: dict) -> None:  # type: ignore[type-arg]
    for p in study["planets"]:
        for c in p["conditions"]:
            assert c["why"] and p["name"] in c["why"] and "sect" in c["why"], c
        for t in p["tokens"]:
            assert t["label"]
            if t["token"] in ("of_sect", "contrary_to_sect", "good_place", "bad_place", "domicile", "exaltation"):
                assert t["why"], t
    for lot in study["lots"]:
        assert lot["why"].startswith("From ") and lot["pos"] in lot["why"]
    assert all(pl["why"] for pl in study["places"])
    assert "horizon" in study["sect"]["why"]


def test_sect_spectrum_by_day(study: dict) -> None:  # type: ignore[type-arg]
    spectrum = [(x["key"], x["role"]) for x in study["sect"]["spectrum"]]
    if study["sect"]["day"]:
        assert spectrum == [
            ("jupiter", "most helpful"),
            ("venus", "helpful, restrained"),
            ("saturn", "difficult, restrained"),
            ("mars", "most difficult"),
        ]
    else:
        assert spectrum[0][0] == "venus" and spectrum[-1][0] == "saturn"


def test_glossary_terms_are_linked(study: dict) -> None:  # type: ignore[type-arg]
    terms = {t["term"] for p in study["planets"] for t in p["tokens"]} | {
        c["term"] for p in study["planets"] for c in p["conditions"]
    }
    assert terms - {""} <= set(study["glossary"])


# ── terminal views ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("width", [80, 120])
@pytest.mark.parametrize("glyphs", [True, False])
def test_study_views_fit_and_align(fake_astrolog: Path, width: int, glyphs: bool) -> None:
    assert D is not None
    pack = loader.load("psychological")
    data = ViewData.build(cast(EINSTEIN, P.load("default")), pack)
    data.study = build_study(data.natal, D, glossary(MEANINGS), years=40)
    th = theme.load("default") if glyphs else theme.load("default").with_letters()
    for name in compose.STUDY_VIEWS:
        canvas = compose.compose(data, th, [name], width)
        lines = ANSI.sub("", canvas.render()).splitlines()
        assert len({len(line) for line in lines}) == 1, name
        assert max(len(line) for line in canvas.plain().splitlines()) <= width
    text, left = compose.render_within_budget(data, th, list(compose.STUDY_VIEWS), width)
    assert len(text) <= compose.BUDGET
    plain = ANSI.sub("", text)
    assert "DOCTRINE" in plain and ("LOTS" in plain or "lots" in left)


def test_study_views_without_doctrine(fake_astrolog: Path) -> None:
    data = ViewData.build(cast(EINSTEIN, P.load("default")), loader.load("psychological"))
    text = compose.compose(data, theme.load("default"), ["doctrine"], 80).plain()
    assert "no doctrine rules" in text


def test_view_and_export_cli(fake_astrolog: Path, tmp_path: Path) -> None:
    pack = loader.user_dir() / "doctrine-test"
    pack.mkdir(parents=True)
    (pack / "method.toml").write_text(FIXTURE.read_text())
    (pack / "meanings.md").write_text(MEANINGS)
    add = ("chart", "add", "Ein", "--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00")
    assert run_cli(*add).returncode == 0
    shown = run_cli("view", "--chart", "Ein", "--pack", "doctrine-test", "--show", "doctrine,lots,timelords")
    assert shown.returncode == 0 and "DOCTRINE" in shown.stdout and "TIME LORDS" in shown.stdout
    out = tmp_path / "ein.html"
    done = run_cli("export", "html", "--chart", "Ein", "--pack", "doctrine-test", "--harmonic", "1", "--out", str(out))
    assert done.returncode == 0, done.stderr
    page = out.read_text()
    data = json.loads(re.search(r'<script type="application/json" id="chart-data">(.*?)</script>', page, re.S).group(1))  # type: ignore[union-attr]
    assert data["study"]["planets"] and data["study"]["glossary"]
    assert 'id="sections"' in page and 'id="timeline"' in page
    plain = run_cli(
        "export",
        "html",
        "--chart",
        "Ein",
        "--pack",
        "psychological",
        "--harmonic",
        "1",
        "--out",
        str(tmp_path / "p.html"),
    )
    assert plain.returncode == 0
    psych = json.loads(re.search(r'id="chart-data">(.*?)</script>', (tmp_path / "p.html").read_text(), re.S).group(1))  # type: ignore[union-attr]
    assert psych["study"] is None


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_preset_scripts_parse() -> None:
    root = Path(__file__).resolve().parents[1] / "presets" / "default"
    for name in ("app.js", "core.js"):
        assert subprocess.run(["node", "--check", str(root / name)], capture_output=True).returncode == 0, name
