from __future__ import annotations

import pytest

from astrolog_skills.engine import houses, objects, zodiac
from astrolog_skills.errors import AstroError


@pytest.mark.parametrize(
    ("lon", "minutes", "seconds"),
    [
        (353.507747, "23°30′ Pisces", "23°30′27″ Pisces"),
        (29.99999999, "29°59′ Aries", "29°59′59″ Aries"),
        (360.0, "0°00′ Aries", "0°00′00″ Aries"),
        (-0.5, "29°30′ Pisces", "29°30′00″ Pisces"),
    ],
)
def test_format_position(lon: float, minutes: str, seconds: str) -> None:
    assert zodiac.format_position(lon) == minutes
    assert zodiac.format_position(lon, seconds=True) == seconds


def test_sign_element_mode() -> None:
    assert (zodiac.sign_of(95), zodiac.element_of(95), zodiac.mode_of(95)) == ("Cancer", "water", "cardinal")
    assert (zodiac.sign_of(359.9), zodiac.mode_of(359.9)) == ("Pisces", "mutable")


def test_parse_astrolog_position() -> None:
    assert zodiac.parse_astrolog_position("17Ari11'59\"") == pytest.approx(17.199722, abs=1e-6)
    assert zodiac.parse_astrolog_position(" 9Can23'58\"") == pytest.approx(99.399444, abs=1e-6)
    with pytest.raises(ValueError):
        zodiac.parse_astrolog_position("17Xyz11'59\"")


@pytest.mark.parametrize(
    ("value", "token", "offset"),
    [
        ("lahiri", "Lahiri", 0.883208),
        ("Lahiri", "Lahiri", 0.883208),
        ("KP", "Krishnamurti", 0.98006),
        ("fagan", "Fagan", 0.0),
        ("Djwhal Khul", "Djwhal", -3.619379),
        ("usha", "Usha-Shasi", 4.682759),
        ("1.5", "1.5", 1.5),
        (-2.0, "-2.0", -2.0),
    ],
)
def test_resolve_ayanamsa(value: str | float, token: str, offset: float) -> None:
    got = zodiac.resolve_ayanamsa(value)
    assert got[0] == token and got[1] == pytest.approx(offset)


@pytest.mark.parametrize("value", ["Sassanian", "Aldebaran", "Bhasin", ""])
def test_unknown_ayanamsa_is_an_error_not_silent_fagan(value: str) -> None:
    """Regression guard: Astrolog silently uses Fagan-Bradley for names it doesn't know."""
    with pytest.raises(AstroError) as err:
        zodiac.resolve_ayanamsa(value)
    assert err.value.fix and "lahiri" in err.value.fix


@pytest.mark.parametrize(
    ("value", "key", "number"),
    [
        ("placidus", "placidus", 0),
        ("Whole", "whole-sign", 14),
        ("whole sign", "whole-sign", 14),
        (14, "whole-sign", 14),
        ("14", "whole-sign", 14),
        ("Regiomontanus", "regiomontanus", 5),
        ("equal-mc", "equal-mc", 11),
    ],
)
def test_resolve_house_system(value: str | int, key: str, number: int) -> None:
    got = houses.resolve_house_system(value)
    assert got[0] == key and got[2] == number


def test_whole_sign_is_14_not_12() -> None:
    """An early version used -c 12 (Pullen Sinusoidal Ratio) believing it was Whole Sign."""
    assert houses.HOUSE_SYSTEMS["whole-sign"][1] == 14
    assert houses.HOUSE_SYSTEMS["pullen-sr"][1] == 12


def test_unknown_house_system() -> None:
    with pytest.raises(AstroError):
        houses.resolve_house_system("banana")


def test_all_23_house_systems_unique() -> None:
    numbers = [n for _, n in houses.HOUSE_SYSTEMS.values()]
    assert sorted(numbers) == list(range(23))


def test_resolve_objects_order_and_south_node() -> None:
    got = [o.key for o in objects.resolve_objects(["south_node", "sun", "sun", "chiron"])]
    assert got == ["sun", "chiron", "north_node", "south_node"]
    with pytest.raises(AstroError):
        objects.resolve_objects(["sun", "planet-x"])
