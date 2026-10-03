from __future__ import annotations

from pathlib import Path

import pytest

from astrolog_skills import config, paths
from astrolog_skills.errors import AstroError


def test_data_dir_honours_env(isolated: Path) -> None:
    assert paths.data_dir() == isolated / "data"
    assert paths.config_path() == isolated / "data" / "config.toml"


def test_ensure_data_dir_is_idempotent() -> None:
    created = paths.ensure_data_dir()
    assert paths.data_dir() in created
    for name in paths.SUBDIRS:
        assert (paths.data_dir() / name).is_dir()
    assert paths.ensure_data_dir() == []


def test_load_defaults_without_file() -> None:
    cfg = config.load()
    assert cfg["display"]["width"] == 80
    assert cfg["astrolog"]["path"] == ""


def test_set_and_get_with_coercion() -> None:
    config.set_value("display.width", "120")
    config.set_value("display.glyphs", "no")
    assert config.get("display.width") == 120
    assert config.get("display.glyphs") is False
    assert "width = 120" in paths.config_path().read_text()


def test_unknown_key_lists_valid_keys() -> None:
    with pytest.raises(AstroError) as err:
        config.set_value("nope", "1")
    assert err.value.fix and "display.width" in err.value.fix


@pytest.mark.parametrize("raw", ["maybe", ""])
def test_bad_bool(raw: str) -> None:
    with pytest.raises(AstroError):
        config.set_value("display.glyphs", raw)


def test_width_range() -> None:
    with pytest.raises(AstroError):
        config.set_value("display.width", "20")


def test_atomic_save_leaves_no_tmp_and_drops_none() -> None:
    config.save(config.load())
    leftovers = list(paths.data_dir().glob("*.tmp"))
    assert leftovers == []
    text = paths.config_path().read_text()
    assert "lat" not in text  # None values are not written (TOML has no null)


def test_corrupt_config_gives_fix() -> None:
    paths.ensure_data_dir()
    paths.config_path().write_text("this is = = not toml")
    with pytest.raises(AstroError) as err:
        config.load()
    assert err.value.fix and "config.toml" in err.value.fix


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("10E00 48N24", (48.4, 10.0)),
        ("48N24 10E00", (48.4, 10.0)),
        ("48.4N 10.0E", (48.4, 10.0)),
        ("48.4, 10.0", (48.4, 10.0)),
        ("74W00 40N43", (40.716667, -74.0)),
        ("33.87S 151.21E", (-33.87, 151.21)),
    ],
)
def test_parse_location(text: str, expected: tuple[float, float]) -> None:
    assert config.parse_location(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["somewhere", "1 2 3", "95N00 10E00", "10.0"])
def test_parse_location_rejects(text: str) -> None:
    with pytest.raises(AstroError):
        config.parse_location(text)


def test_set_location_roundtrip() -> None:
    config.set_location("48N24 10E00", "Ulm")
    assert config.location() == pytest.approx((48.4, 10.0))
    assert config.load()["defaults"]["location"]["name"] == "Ulm"


def test_location_none_by_default() -> None:
    assert config.location() is None
