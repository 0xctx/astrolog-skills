from __future__ import annotations

from pathlib import Path

import pytest

from astrolog_skills import places
from astrolog_skills.errors import AstroError


def test_resolve_with_country(atlas: Path) -> None:
    p = places.resolve("Ulm, Germany")
    assert (p.region, p.tz) == ("DE", "Europe/Berlin")
    assert p.lon == pytest.approx(9.9916) and p.lat == pytest.approx(48.3984)  # atlas longitude is negative-east


@pytest.mark.parametrize("query", ["Ulm, DE", "ulm, germany", "Ulm, de"])
def test_country_code_and_case(atlas: Path, query: str) -> None:
    assert places.resolve(query).region == "DE"


def test_ambiguous_lists_candidates(atlas: Path) -> None:
    with pytest.raises(AstroError) as err:
        places.resolve("Ulm")
    assert "Montana" in err.value.message and "Germany" in err.value.message
    assert err.value.fix and "country" in err.value.fix


def test_us_state_hint(atlas: Path) -> None:
    assert places.resolve("Springfield, Illinois").tz == "America/Chicago"
    assert places.resolve("Springfield, MO").tz == "America/Chicago"  # blank zone inherits from the row above


def test_accents_german_style_and_exonyms(atlas: Path) -> None:
    assert places.resolve("Zürich").name == "Zuerich"
    assert places.resolve("Zurich").name == "Zuerich"
    assert places.resolve("München").name == "Munich"


def test_city_suffix_and_state_hint(atlas: Path) -> None:
    assert places.resolve("New York, NY").name == "New York City"
    assert places.resolve("New York").name == "New York City"


def test_crlf_rows_are_clean(atlas: Path) -> None:
    """Regression: some atlas rows end in CRLF, which left '\\r' in names and time zones."""
    p = places.resolve("Sydney")
    assert p.tz == "Australia/Sydney" and p.name == "Sydney"


def test_unknown_place_and_hint(atlas: Path) -> None:
    with pytest.raises(AstroError):
        places.resolve("Atlantis")
    with pytest.raises(AstroError) as err:
        places.resolve("Ulm, Narnia")
    assert "Narnia" in err.value.message


def test_prefix_search(atlas: Path) -> None:
    assert [p.name for p in places.search("Spring")] == ["Springfield", "Springfield"]


def test_nearest(atlas: Path) -> None:
    assert places.nearest(48.5, 10.1).label == "Ulm, Germany"
    assert places.nearest(40.0, -89.0).tz == "America/Chicago"


def test_missing_atlas(fake_astrolog: Path) -> None:
    with pytest.raises(AstroError) as err:
        places.resolve("Ulm")
    assert err.value.fix and "astro astrolog install" in err.value.fix
