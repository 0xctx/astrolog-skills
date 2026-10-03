from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from astrolog_skills.charts import adb, chartlist, csv_import, sets, store
from astrolog_skills.charts.records import SetRecord
from astrolog_skills.engine import profile as P
from astrolog_skills.engine.moment import julian_calendar
from astrolog_skills.errors import AstroError
from tests.conftest import FIXTURES

ADB = FIXTURES / "adb_sample.xml"


# ── saved charts ──────────────────────────────────────────────────────────────
def test_build_from_place_uses_zone_and_birthplace_lmt(atlas: Path) -> None:
    record, notes = store.build("Einstein", "1879-03-14", "11:30", place="Ulm, Germany", rating="aa", tags=["x"])
    assert record.tz == "Europe/Berlin" and record.rating == "AA" and record.place == "Ulm, Germany"
    assert any("Ulm" in n for n in notes)
    assert record.moment().utc.strftime("%H:%M") == "10:50"  # type: ignore[union-attr]  # Ulm's LMT, not Berlin's


def test_build_from_coordinates_borrows_nearest_zone(atlas: Path) -> None:
    record, notes = store.build("X", "2000-06-01", "12:00", lat=48.5, lon=10.1)
    assert record.tz == "Europe/Berlin" and "nearest" in notes[0]


def test_build_needs_a_place() -> None:
    with pytest.raises(AstroError):
        store.build("X", "2000-06-01", "12:00", tz="UTC")


def test_bad_rating_and_bad_time(atlas: Path) -> None:
    with pytest.raises(AstroError):
        store.build("X", "2000-06-01", "12:00", place="Paris", rating="ZZ")
    with pytest.raises(AstroError):
        store.build("X", "2026-03-29", "02:30", place="Ulm, Germany")  # DST gap


def test_save_load_list_remove(atlas: Path) -> None:
    record, _ = store.build("Anna Müller", "1990-05-01", "14:20", place="Paris")
    path = store.save(record)
    assert path.name == "anna-muller.toml"
    assert store.load("anna müller") == record == store.load("anna-muller")
    with pytest.raises(AstroError):
        store.save(record)
    store.save(record, overwrite=True)
    assert [r.name for r in store.list_charts()] == ["Anna Müller"]
    store.remove("Anna Müller")
    with pytest.raises(AstroError):
        store.load("Anna Müller")


def test_damaged_chart_file() -> None:
    store.charts_dir().mkdir(parents=True, exist_ok=True)
    (store.charts_dir() / "bad.toml").write_text("name = = broken")
    with pytest.raises(AstroError) as err:
        store.load("bad")
    assert err.value.fix and "bad.toml" in err.value.fix


# ── Astro-Databank ────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("text", "value"), [("48n24", 48.4), ("9e10", 9.166667), ("33s52", -33.866667), ("0w07", -0.116667)]
)
def test_parse_coord(text: str, value: float) -> None:
    assert adb.parse_coord(text) == pytest.approx(value, abs=1e-6)


def test_adb_load_and_stats() -> None:
    records, stats = adb.load(ADB)
    assert stats["entries"] == 5 and stats["skipped_no_time"] == 1 and stats["usable"] == 4
    ada = next(r for r in records if r.name == "Ada Tester")
    assert ada.utc == datetime(1879, 3, 14, 10, 50, tzinfo=UTC).replace(microsecond=ada.utc.microsecond)
    assert (ada.rating, ada.gender, ada.datatype, ada.id) == ("AA", "f", "Public Figure", "adb1")
    assert ada.lat == pytest.approx(48.4) and ada.categories[0] == "Vocation : Science : Physics"


def test_adb_julian_record_is_true_gregorian_ut() -> None:
    early = next(r for r in adb.load(ADB)[0] if r.name == "Julian Early")
    assert early.utc.date() == date(1501, 10, 4)  # 24 Sep 1501 Julian
    assert julian_calendar(early.utc.date()) == (1501, 9, 24)


def test_adb_cache_reused() -> None:
    first = adb.load(ADB)
    assert list((P.user_dir().parent / "cache").glob("adb-*.json"))
    assert adb.load(ADB) == first


def test_adb_categories_counts() -> None:
    assert adb.categories(ADB, "music") == [
        ("Vocation : Entertain/Music : Composer/ Arranger", 1),
        ("Vocation : Entertain/Music : Instrumentalist", 1),
    ]


def test_adb_bad_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.xml"
    bad.write_text("<not closed")
    with pytest.raises(AstroError):
        adb.load(bad)
    with pytest.raises(AstroError):
        adb.load(tmp_path / "missing.xml")


# ── CSV ───────────────────────────────────────────────────────────────────────
def test_csv_import(atlas: Path) -> None:
    records, stats = csv_import.load(FIXTURES / "charts.csv")
    assert [r.name for r in records] == ["Ada One", "Bea Two", "Cy Three"] and stats["usable"] == 3
    assert records[0].categories == ["physics", "test"] and records[2].place == "Paris, France"
    assert records[1].utc == datetime(1990, 7, 1, 12, 0, 15, tzinfo=UTC)


def test_csv_errors_name_the_row(tmp_path: Path, atlas: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("name,date,time,lat,lon\nOk,2000-01-01,12:00,48.4,10.0\nBroken,2000-13-01,12:00,48.4,10.0\n")
    with pytest.raises(AstroError) as err:
        csv_import.load(bad)
    assert "row 3" in err.value.message
    missing = tmp_path / "missing.csv"
    missing.write_text("name,date\nx,2000-01-01\n")
    with pytest.raises(AstroError) as err:
        csv_import.load(missing)
    assert "time" in err.value.message


# ── chart lists ───────────────────────────────────────────────────────────────
def test_chartlist_line_seconds_quotes_and_julian() -> None:
    r = SetRecord("adb2", 'Say "Hi"', datetime(1501, 10, 4, 17, 52, 20, 6398, tzinfo=UTC), 45.1667, 9.1667, "Pavia")
    line = chartlist.line(r)
    assert line.startswith("-qcl 9 24 1501 17:52:20.01 ST 0 9:10:00E 45:10:00N")  # Julian date for Astrolog
    assert "\"[adb2] Say 'Hi'\"" in line
    assert chartlist.id_of("[adb2] Say 'Hi'") == "adb2" and chartlist.id_of("no id") is None


# ── sets ──────────────────────────────────────────────────────────────────────
def test_set_filters() -> None:
    s = sets.create("physics", "adb", path=str(ADB), filter_=sets.SetFilter(categories=["Vocation : Science"]))
    assert [r.name for r in sets.records(s)[0]] == ["Ada Tester"]
    anyone = sets.create("all", "adb", path=str(ADB))
    assert "C-Section 1" not in [r.name for r in sets.records(anyone)[0]]  # research groups excluded by default
    everyone = sets.create("everyone", "adb", path=str(ADB), filter_=sets.SetFilter(exclude_research=False))
    assert len(sets.records(everyone)[0]) == 4
    rated = sets.create("rated", "adb", path=str(ADB), filter_=sets.SetFilter(ratings=["AA", "A"], gender="m"))
    assert [r.name for r in sets.records(rated)[0]] == ["Mo Musician"]
    no_music = sets.create(
        "nm", "adb", path=str(ADB), filter_=sets.SetFilter(exclude_categories=["Vocation : Entertain"])
    )
    assert {r.name for r in sets.records(no_music)[0]} == {"Ada Tester"}


def test_set_roundtrip_list_remove() -> None:
    sets.create("physics", "adb", path=str(ADB), description="d", filter_=sets.SetFilter(ratings=["AA"]))
    loaded = sets.load("physics")
    assert loaded.filter.ratings == ["AA"] and loaded.description == "d"
    assert [s.name for s in sets.list_sets()] == ["physics"]
    with pytest.raises(AstroError):
        sets.create("physics", "adb", path=str(ADB))
    sets.remove("physics")
    with pytest.raises(AstroError):
        sets.load("physics")


def test_set_from_saved_charts_and_bad_kind(atlas: Path) -> None:
    store.save(store.build("Ada", "1879-03-14", "11:30", place="Ulm, Germany")[0])
    s = sets.create("mine", "charts", charts=["Ada"])
    assert sets.records(s)[0][0].id == "chart:ada"
    with pytest.raises(AstroError):
        sets.create("bad", "ftp")


def test_cast_set_maps_ids(fake_astrolog: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    listing = tmp_path / "listing.txt"
    listing.write_text(
        "Astrolog 7.80 chart for [adb1] Ada Tester\nheader\n"
        "Sun : 23Pis30'27\"   - 0:00'00\" (-) [10th house] [-] +0.9959570 +0.0000256\n"
        "Astrolog 7.80 chart for [zzz] Stranger\nheader\n"
        "Sun :  9Can23'58\"   - 0:00'00\" (-) [ 9th house] [-] +0.9534036 -0.0000186\n"
    )
    monkeypatch.setenv("FAKE_ASTROLOG_BATCH", str(listing))
    s = sets.create("physics", "adb", path=str(ADB), filter_=sets.SetFilter(categories=["Vocation : Science"]))
    pairs = sets.cast_set(s, P.load("default"))
    assert [r.name for r, _ in pairs] == ["Ada Tester"]  # the stranger's row is ignored
    assert pairs[0][1].lon("sun") == pytest.approx(353.5075, abs=1e-4)


def test_adb_cache_key_is_stable_across_processes() -> None:
    """Regression: the key used hash(), randomised per process, so no later command ever hit the cache."""
    import subprocess
    import sys

    code = f"from pathlib import Path; from astrolog_skills.charts import adb; adb.load(Path({str(ADB)!r}))"
    for _ in range(2):
        subprocess.run([sys.executable, "-c", code], check=True)
    assert len(list((P.user_dir().parent / "cache").glob("adb-*.json"))) == 1
