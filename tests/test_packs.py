from __future__ import annotations

from pathlib import Path

import pytest

from astrolog_skills.analysis.aspects_registry import ASPECTS, BY_KEY
from astrolog_skills.analysis.method import parse
from astrolog_skills.errors import AstroError
from astrolog_skills.packs import loader


def test_registry_angles_follow_harmonics() -> None:
    assert len({a.key for a in ASPECTS}) == len(ASPECTS) == 19
    for a in ASPECTS:
        k = round(a.angle * a.harmonic / 360, 6)
        assert k == int(k) and a.angle <= 180
    assert BY_KEY["septile"].angle == pytest.approx(51.428571, abs=1e-6)


def test_builtin_packs_load() -> None:
    assert set(loader.list_packs()) >= {"vibrational", "psychological"}
    vib = loader.load("vibrational")
    assert vib.method.orb_rule == "harmonic" and not vib.user
    assert vib.method.orb_for(BY_KEY["quintile"]) == pytest.approx(3.2)  # 16/5 — not the source's "5 1/3" typo
    assert vib.method.orb_for(BY_KEY["semisquare"]) == pytest.approx(2.0)
    assert vib.file("REVIEW.md") and vib.sources[0]["author"]  # every source names its author


@pytest.mark.parametrize(
    ("a", "b", "weight"),
    [
        ("sun", "moon", 10),
        ("moon", "sun", 10),
        ("mars", "pluto", 5),
        ("venus", "neptune", 8),
        ("mercury", "saturn", 8),
        ("jupiter", "saturn", 3),
        ("saturn", "uranus", 3),
        ("jupiter", "neptune", 3),
        ("saturn", "pluto", 3),
        ("jupiter", "pluto", 2),
        ("uranus", "neptune", 2),
        ("uranus", "pluto", 1),
        ("neptune", "pluto", 1),
    ],
)
def test_vibrational_pair_weights(a: str, b: str, weight: float) -> None:
    assert loader.load("vibrational").method.weight(a, b) == weight


def _user_pack(name: str, text: str) -> Path:
    d = loader.user_dir() / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "method.toml").write_text(text)
    return d


def test_user_pack_replaces_builtin_and_copy() -> None:
    target = loader.copy_to_user("psychological")
    assert (target / "method.toml").exists() and loader.load("psychological").user
    with pytest.raises(AstroError):
        loader.copy_to_user("psychological")
    assert loader.copy_to_user("psychological", "mine").name == "mine"


def test_extends_merges_tables() -> None:
    _user_pack("tight", 'extends = "psychological"\nlabel = "Tight"\n[orbs]\nconjunction = 3\n')
    m = loader.load("tight").method
    assert m.orb_for(BY_KEY["conjunction"]) == 3 and m.orb_for(BY_KEY["trine"]) == 7  # inherited
    assert m.label == "Tight" and "quintile" in m.aspects


def test_extends_cycle_detected() -> None:
    _user_pack("a", 'extends = "b"\n')
    _user_pack("b", 'extends = "a"\n')
    with pytest.raises(AstroError) as err:
        loader.load("a")
    assert "loop" in err.value.message


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"aspects": {"set": ["conjunction", "wobble"]}}, "unknown aspect"),
        ({"orbs": {"rule": "vibes"}}, "orbs.rule"),
        ({"aspects": {"set": ["conjunction", "trine"]}, "orbs": {"conjunction": 8}}, "need a value for trine"),
        ({"orbs": {"rule": "harmonic", "base": -1}}, "orbs.base"),
        ({"orbs": {"rule": "harmonic", "banana": 3}}, "unknown aspect"),
        ({"orbs": {"rule": "harmonic"}, "harmonics": {"range": [5, 2]}}, "harmonics.range"),
        ({"orbs": {"rule": "harmonic"}, "patterns": {"bodies": ["sun", "vulcan"]}}, "unknown object"),
        ({"orbs": {"rule": "harmonic"}, "weights": {"rules": [{"pair": ["sun"], "weight": 1}]}}, "pair must be two"),
        ({"orbs": {"rule": "harmonic"}, "weights": {"rules": [{"pair": ["sun", "moon"], "weight": "big"}]}}, "weight"),
    ],
)
def test_method_validation(raw: dict[str, object], message: str) -> None:
    with pytest.raises(AstroError) as err:
        parse(raw, "test.toml")  # type: ignore[arg-type]
    assert message in err.value.message and "test.toml" in err.value.message


def test_unknown_pack() -> None:
    with pytest.raises(AstroError) as err:
        loader.load("astrology-of-cats")
    assert err.value.fix and "vibrational" in err.value.fix


def test_profiles_link_to_existing_packs() -> None:
    from astrolog_skills.engine import profile as profiles

    for name in profiles.list_profiles():
        assert profiles.load(name).pack in loader.list_packs()


def test_meanings_parsed_from_the_packs_own_words() -> None:
    from astrolog_skills.packs import meanings

    psych = meanings.load(loader.load("psychological").file("meanings.md"))
    assert psych["bodies"]["sun"].startswith("the core self")
    assert {"quintile", "biquintile", "semisquare", "sesquiquadrate", "conjunction"} <= set(psych["aspects"])
    assert psych["bodies"]["asc"] and psych["bodies"]["vertex"]
    vib = meanings.load(loader.load("vibrational").file("meanings.md"))
    assert vib["harmonics"]["7"].startswith("introversion") and len(vib["harmonics"]) == 32
    assert vib["bodies"]["saturn"] == "structure, discipline, limits"
    assert meanings.load(None) == {"bodies": {}, "aspects": {}, "harmonics": {}}
    text = "- **Mars ♂** — drive\n  that continues.\n- **H3** — ease [theory]\nSun — light · Moon — tides\n"
    got = meanings.parse(text)
    assert got["bodies"] == {"mars": "drive that continues.", "sun": "light", "moon": "tides"}
    assert got["harmonics"] == {"3": "ease [theory]"}
    both = meanings.parse("- **Ceres ⚳, Pallas ⚴** — nurture; pattern sense.\n- **Juno, Vesta** — only one clause\n")
    one_each = {"ceres": "nurture", "pallas": "pattern sense", "juno": "only one clause", "vesta": "only one clause"}
    assert both["bodies"] == one_each
