from __future__ import annotations

from pathlib import Path

import pytest

from astrolog_skills import config
from astrolog_skills.engine import profile as P
from astrolog_skills.errors import AstroError


def test_builtins_load_and_validate() -> None:
    names = set(P.list_profiles())
    assert {"default", "whole-sign", "vedic-lahiri", "vibrational"} <= names
    for name in names:
        P.validate(P.load(name))


def test_active_defaults_to_default() -> None:
    assert P.active().name == "default"


def test_default_pins() -> None:
    pins = P.pins(P.load("default"))
    assert pins[: len(P.NEUTRAL_PINS)] == P.NEUTRAL_PINS
    assert "_s" in pins and "=Yn" in pins
    assert pins[pins.index("-c") + 1] == "0"
    assert pins[pins.index("-R0") + 1 :] == [
        "Sun",
        "Moo",
        "Mer",
        "Ven",
        "Mar",
        "Jup",
        "Sat",
        "Ura",
        "Nep",
        "Plu",
        "Chi",
        "Nor",
    ]


def test_vedic_pins() -> None:
    pins = P.pins(P.load("vedic-lahiri"))
    assert pins[pins.index("-s") + 1] == "Lahiri" and "_s" not in pins
    assert pins[pins.index("-c") + 1] == "14" and "_Yn" in pins


def test_pins_neutralise_everything_that_moves_positions() -> None:
    pins = P.pins(P.load("default"))
    for switch in ("=b", "_YT", "_YV", "_h", "_sr", "_p", "_1", "_c3"):
        assert switch in pins
    assert pins[pins.index("-x") + 1] == "1"


def _write(tmp: Path, name: str, body: str) -> Path:
    d = P.user_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.toml"
    path.write_text(body)
    return path


def test_user_profile_overrides_builtin() -> None:
    _write(
        Path(),
        "default",
        'name = "default"\n[zodiac]\ntype = "sidereal"\nayanamsa = "raman"\n[points]\nobjects = ["sun"]\n',
    )
    p = P.load("default")
    assert p.sidereal and p.source.startswith(str(P.user_dir()))
    assert P.pins(p)[P.pins(p).index("-s") + 1] == "Raman"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ('[zodiac]\ntype = "starry"\n[points]\nobjects=["sun"]', "tropical"),
        ('[zodiac]\ntype = "sidereal"\n[points]\nobjects=["sun"]', "needs zodiac.ayanamsa"),
        ('[zodiac]\ntype = "sidereal"\nayanamsa = "Aldebaran"\n[points]\nobjects=["sun"]', "Unknown ayanamsa"),
        ('[houses]\nsystem = "banana"\n[points]\nobjects=["sun"]', "Unknown house system"),
        ('[points]\nnode = "wobbly"\nobjects=["sun"]', "true' or 'mean"),
        ("[points]\nobjects = []", "empty"),
        ('[points]\nobjects = ["sun", "vulcan"]', "Unknown object"),
        ("this is not toml", "Can't read profile"),
    ],
)
def test_invalid_profiles_explain_themselves(body: str, message: str) -> None:
    path = _write(Path(), "broken", body)
    with pytest.raises(AstroError) as err:
        P.load("broken")
    assert message in err.value.message
    assert "broken" in err.value.message or str(path) in err.value.message


def test_create_copies_and_refuses_overwrite() -> None:
    path = P.create("mine", from_="vedic-lahiri")
    assert path.exists() and 'name = "mine"' in path.read_text()
    assert P.load("mine").sidereal
    with pytest.raises(AstroError):
        P.create("mine")
    with pytest.raises(AstroError):
        P.create("bad name!")
    with pytest.raises(AstroError):
        P.create("other", from_="nope")


def test_unknown_profile() -> None:
    with pytest.raises(AstroError) as err:
        P.load("nope")
    assert err.value.fix and "default" in err.value.fix


def test_active_follows_config() -> None:
    config.set_value("defaults.profile", "whole-sign")
    assert P.active().name == "whole-sign"


def test_summary_and_dict() -> None:
    p = P.load("vedic-lahiri")
    assert "Lahiri" in p.summary() and "Whole Sign" in p.summary()
    d = p.to_dict()
    assert d["ayanamsa_offset"] == pytest.approx(0.883208) and d["objects"][-1] == "south_node"


def test_pins_extra_codes_extend_the_restriction_list() -> None:
    pins = P.pins(P.load("vedic-lahiri"), extra_codes=("Asc", "Mid"))
    tail = pins[pins.index("-R0") + 1 :]
    assert tail[-2:] == ["Asc", "Mid"] and "Sun" in tail
