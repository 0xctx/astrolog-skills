"""A pack's chart settings ([chart]), the user's adjustments over them, and citations off by default."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from astrolog_skills import config
from astrolog_skills.analysis.doctrine.explain import without_citations
from astrolog_skills.engine import profile as profiles
from astrolog_skills.engine.profile import ChartSettings, chart_settings, overlay, parse_chart_settings
from astrolog_skills.errors import AstroError
from astrolog_skills.packs import loader, settings
from tests.conftest import run_cli

FIXTURE = Path(__file__).parent / "fixtures" / "doctrine_pack.toml"
CHART = """
[chart]
zodiac = "tropical"
houses = "whole-sign"
objects = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "north_node", "south_node"]
cite = "p. 4"
"""
SEVEN = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn"]


@pytest.fixture(autouse=True)
def no_flags() -> Iterator[None]:
    settings.set_flags(ChartSettings())
    yield
    settings.set_flags(ChartSettings())


@pytest.fixture
def trad() -> str:
    """A user pack with doctrine and a [chart] section."""
    folder = loader.user_dir() / "trad"
    folder.mkdir(parents=True)
    (folder / "method.toml").write_text(FIXTURE.read_text() + CHART)
    return "trad"


# ── parsing ───────────────────────────────────────────────────────────────────


def test_parse_chart_settings() -> None:
    s = parse_chart_settings({"zodiac": "tropical", "houses": "whole-sign", "objects": SEVEN, "cite": "p. 4"}, "t")
    assert s is not None and s.houses == "whole-sign" and s.points == tuple(SEVEN) and s.cite == "p. 4"
    assert parse_chart_settings(None, "t") is None
    named = chart_settings(zodiac="lahiri")  # an ayanamsa means sidereal
    assert (named.zodiac, named.ayanamsa) == ("sidereal", "lahiri")
    alone = chart_settings(ayanamsa="lahiri")  # an ayanamsa alone means sidereal too
    assert (alone.zodiac, alone.ayanamsa) == ("sidereal", "lahiri")
    assert chart_settings(zodiac="tropical", ayanamsa="lahiri").ayanamsa is None


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"zodiac": "sidereal"}, "needs an ayanamsa"),
        ({"houses": "nowhere"}, "house"),
        ({"objects": ["sun", "dragon"]}, "dragon"),
        ({"node": "wobbly"}, "node"),
        ({"colour": "red"}, r"unknown \[chart\] key"),
        ({"zodiac": "not-an-ayanamsa"}, "yanamsa"),
    ],
)
def test_bad_chart_settings(raw: dict[str, object], message: str) -> None:
    with pytest.raises(AstroError, match=message):
        parse_chart_settings(raw, "t")


def test_bad_chart_section_fails_at_load() -> None:
    folder = loader.user_dir() / "broken"
    folder.mkdir(parents=True)
    (folder / "method.toml").write_text(FIXTURE.read_text() + '\n[chart]\nhouses = "nowhere"\n')
    with pytest.raises(AstroError, match="broken"):
        loader.load("broken")


# ── layers ────────────────────────────────────────────────────────────────────


def test_points_replace_add_drop() -> None:
    base = profiles.load("default")
    assert overlay(base, chart_settings(points="sun,moon"), "x").objects == ("sun", "moon")
    added = overlay(base, chart_settings(points="+ceres,-pluto"), "x").objects
    assert "ceres" in added and "pluto" not in added and "saturn" in added
    assert overlay(base, chart_settings(points="sun,moon,+ceres"), "x").objects == ("sun", "moon", "ceres")
    assert overlay(base, ChartSettings(), "x") is base  # nothing to lay over


def test_tropical_clears_the_ayanamsa() -> None:
    vedic = profiles.load("vedic-lahiri")
    assert vedic.sidereal
    tropical = overlay(vedic, chart_settings(zodiac="tropical"), "x")
    assert not tropical.sidereal and tropical.ayanamsa == ""


def test_layers_pack_then_saved_then_flags(trad: str) -> None:
    pack = loader.load(trad)
    used = settings.chart_profile(None, pack)
    assert used.name == "default + trad" and used.houses == "whole-sign" and used.objects[-1] == "south_node"
    settings.save(trad, chart_settings(houses="placidus", points="+ceres"))
    used = settings.chart_profile(None, pack)
    assert used.houses == "placidus" and "ceres" in used.objects and used.name.endswith("your settings")
    settings.set_flags(chart_settings(zodiac="lahiri", houses="koch"))
    used = settings.chart_profile(None, pack)
    assert used.houses == "koch" and used.sidereal and "ceres" in used.objects  # flags over saved over the pack
    settings.save(trad, None)
    settings.set_flags(ChartSettings())
    assert settings.chart_profile(None, pack).houses == "whole-sign"


def test_naming_a_profile_skips_the_pack_and_saved_settings(trad: str) -> None:
    pack = loader.load(trad)
    settings.save(trad, chart_settings(houses="koch"))
    used = settings.chart_profile("default", pack)
    assert used.name == "default" and used.houses == "placidus"
    settings.set_flags(chart_settings(houses="equal"))
    assert settings.chart_profile("default", pack).houses == "equal"  # flags still apply


def test_doctrine_needs_the_seven_planets(trad: str) -> None:
    settings.set_flags(chart_settings(points="-saturn"))
    with pytest.raises(AstroError, match="saturn"):
        settings.chart_profile(None, loader.load(trad))
    assert settings.chart_profile(None, None).objects  # no pack, no such need


def test_resolve_uses_the_profile_pack_when_none_named() -> None:
    prof, pack = settings.resolve(None, None)
    assert pack.name == profiles.active().pack and prof.name == "default"  # the psychological pack has no [chart]


# ── the command ───────────────────────────────────────────────────────────────


def ok(*args: str) -> dict:  # type: ignore[type-arg]
    done = run_cli("--json", *args)
    assert done.returncode == 0, done.stdout + done.stderr
    return json.loads(done.stdout)  # type: ignore[no-any-return]


def test_packs_settings_command(trad: str) -> None:
    shown = ok("packs", "settings", trad)
    assert shown["pack_settings"]["houses"] == "whole-sign" and shown["your_settings"] is None
    assert shown["result"]["houses"] == "Whole Sign"
    saved = ok("packs", "settings", trad, "--houses", "placidus", "--points", "+ceres")
    assert saved["your_settings"] == {"houses": "placidus", "points": ["+ceres"]}
    assert saved["result"]["houses"] == "Placidus" and "ceres" in saved["result"]["objects"]
    more = ok("packs", "settings", trad, "--points", "+chiron")  # builds on what was saved
    assert more["your_settings"]["points"] == ["+ceres", "+chiron"] and more["your_settings"]["houses"] == "placidus"
    bad = run_cli("--json", "packs", "settings", trad, "--points", "-saturn")
    assert bad.returncode != 0 and "saturn" in bad.stdout
    assert ok("packs", "settings", trad)["your_settings"]["points"] == ["+ceres", "+chiron"]  # nothing broken kept
    assert ok("packs", "settings", trad, "--reset")["your_settings"] is None
    assert "pack_settings" not in config.load() or trad not in config.load()["pack_settings"]
    assert ok("packs", "show", trad)["chart"]["cite"] == "p. 4"


def test_global_flags_reach_the_cast(fake_astrolog: Path, trad: str) -> None:
    add = ("chart", "add", "Ein", "--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00")
    assert run_cli(*add).returncode == 0
    data = ok("--houses", "placidus", "--points", "+ceres", "report-data", "--chart", "Ein", "--pack", trad)
    used = data["packs"][0]["settings"]
    assert used["houses"] == "Placidus" and "ceres" in used["objects"] and used["name"].endswith("this command")
    assert run_cli("--houses", "nowhere", "packs", "list").returncode != 0


# ── citations ─────────────────────────────────────────────────────────────────


def test_without_citations() -> None:
    study = {
        "cites": {"sect": "p. 1"},
        "profection_cite": "p. 2",
        "lots": [{"name": "fortune", "cite": "p. 3", "note": "kept"}],
        "glossary": {"sect": {"title": "Sect", "text": "…", "pages": "p. 4"}},
        "sources": {"pages": 698},
    }
    bare = without_citations(study)
    assert bare == {
        "lots": [{"name": "fortune", "note": "kept"}],
        "glossary": {"sect": {"title": "Sect", "text": "…"}},
        "sources": {"pages": 698},  # a page count, not a citation
    }
    assert study["cites"]  # the original is untouched


def test_citations_off_by_default_on_when_asked(fake_astrolog: Path, trad: str) -> None:
    add = ("chart", "add", "Ein", "--date", "1879-03-14", "--time", "11:30", "--tz", "LMT", "--at", "48N24 10E00")
    assert run_cli(*add).returncode == 0
    base = ("report-data", "--chart", "Ein", "--pack", trad)
    plain = ok(*base)
    assert plain["citations"] is False
    assert '"cite' not in json.dumps(plain["packs"][0]["study"])
    cited = ok("--cite", *base)
    assert cited["citations"] is True and cited["packs"][0]["study"]["cites"]
    assert run_cli("config", "set", "readings.citations", "true").returncode == 0
    assert ok(*base)["citations"] is True
