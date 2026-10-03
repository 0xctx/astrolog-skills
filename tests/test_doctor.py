from __future__ import annotations

from pathlib import Path

import pytest

from astrolog_skills import config, doctor, paths
from tests.conftest import write_fake_astrolog


def statuses(report: doctor.DoctorReport) -> dict[str, str]:
    return {c.id: c.status for c in report.checks}


def test_all_ok_saves_path_and_first_light(fake_astrolog: Path) -> None:
    report = doctor.run_all()
    s = statuses(report)
    assert report.ok, report.checks
    assert s["data_dir"] == s["astrolog_found"] == s["version"] == s["smoke_chart"] == "ok"
    assert s["ephemeris"] == "ok"
    assert config.load()["astrolog"]["path"] == str(fake_astrolog.resolve())
    assert report.first_light and report.first_light["sun"]["text"].endswith("Libra")
    assert report.first_light["rising"] is None


def test_first_light_rising_with_location(fake_astrolog: Path) -> None:
    config.set_location("48N24 10E00")
    report = doctor.run_all()
    assert report.first_light and report.first_light["rising"]["text"].endswith("Cancer")


def test_missing_astrolog_skips_and_explains() -> None:
    report = doctor.run_all()
    s = statuses(report)
    assert not report.ok
    assert s["astrolog_found"] == "fail"
    assert s["version"] == s["path_length"] == s["ephemeris"] == s["smoke_chart"] == "skip"
    fix = next(c.fix for c in report.checks if c.id == "astrolog_found")
    assert fix and "astro astrolog install" in fix and "astro config set astrolog.path" in fix
    assert report.first_light is None


def test_old_version_fails(fake_astrolog: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ASTROLOG_VERSION", "7.70")
    s = statuses(doctor.run_all())
    assert s["version"] == "fail"


def test_older_supported_version_mentions_upgrade(fake_astrolog: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ASTROLOG_VERSION", "7.80")
    check = next(c for c in doctor.run_all().checks if c.id == "version")
    assert check.status == "ok" and "8.00 is available" in check.detail


def test_broken_output_fails_smoke(fake_astrolog: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ASTROLOG_BROKEN", "1")
    report = doctor.run_all()
    assert statuses(report)["smoke_chart"] == "fail"
    assert not report.ok


def test_wrong_sun_fails_smoke(fake_astrolog: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ASTROLOG_SUN", "329.0")  # e.g. a sidereal default in astrolog.as
    check = next(c for c in doctor.run_all().checks if c.id == "smoke_chart")
    assert check.status == "fail" and "329.0000" in check.detail and check.fix


def test_builtin_ephemeris_is_info(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASTROLOG_BIN", str(write_fake_astrolog(tmp_path / "bare")))
    report = doctor.run_all()
    assert statuses(report)["ephemeris"] == "info" and report.ok


def test_long_path_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deep = tmp_path / ("x" * 70) / ("y" * 70) / ("z" * 70)
    monkeypatch.setenv("ASTROLOG_BIN", str(write_fake_astrolog(deep)))
    assert statuses(doctor.run_all())["path_length"] == "fail"


def test_shadowing_warns(fake_astrolog: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    other = tmp_path / "otherbin"
    other.mkdir()
    (other / "astro").write_text("#!/bin/sh\necho astro web framework\n")
    (other / "astro").chmod(0o755)
    monkeypatch.setenv("PATH", f"{other}:/usr/bin:/bin")
    check = next(c for c in doctor.run_all().checks if c.id == "shadowing")
    assert check.status == "warn" and "otherbin" in check.detail


def test_shadowing_info_when_absent(fake_astrolog: Path) -> None:
    check = next(c for c in doctor.run_all().checks if c.id == "shadowing")
    assert check.status in ("info", "ok")


def test_unwritable_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o500)
    monkeypatch.setenv("ASTROLOG_SKILLS_HOME", str(ro / "data"))
    try:
        check = doctor._check_data_dir(doctor._State())
    finally:
        ro.chmod(0o700)
    assert check.status == "fail" and check.fix and "ASTROLOG_SKILLS_HOME" in check.fix


def _shadow(monkeypatch: pytest.MonkeyPatch, caller_path: str) -> doctor.CheckResult:
    monkeypatch.setenv("ASTROLOG_SKILLS_CALLER_PATH", caller_path)
    return doctor._check_shadowing(doctor._State())


def test_shadowing_uses_callers_path_not_uv_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: under `uv run` the venv's own `astro` is first on PATH and hid a real shadowing program."""
    other = tmp_path / "webframework"
    other.mkdir()
    (other / "astro").write_text("#!/bin/sh\n")
    (other / "astro").chmod(0o755)
    ours = paths.plugin_root() / "bin"
    check = _shadow(monkeypatch, f"{other}:{ours}")
    assert check.status == "warn" and "webframework" in check.detail


def test_shadowing_ok_when_plugin_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    other = tmp_path / "webframework"
    other.mkdir()
    (other / "astro").write_text("#!/bin/sh\n")
    (other / "astro").chmod(0o755)
    check = _shadow(monkeypatch, f"{paths.plugin_root() / 'bin'}:{other}")
    assert check.status == "ok"


def test_shadowing_absent_from_callers_path(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _shadow(monkeypatch, "/usr/bin:/bin").status == "info"


def test_newer_than_latest_known_is_not_told_to_downgrade(fake_astrolog: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: versions were compared as strings, so "10.00" < "8.00"."""
    monkeypatch.setenv("FAKE_ASTROLOG_VERSION", "10.00")
    check = next(c for c in doctor.run_all().checks if c.id == "version")
    assert check.status == "ok" and "latest" in check.detail and "available" not in check.detail


def test_stale_configured_path_is_reported_and_replaced(fake_astrolog: Path, tmp_path: Path) -> None:
    """Regression: a deleted configured binary was silently ignored forever."""
    config.set_value("astrolog.path", str(tmp_path / "deleted" / "astrolog"))
    check = next(c for c in doctor.run_all().checks if c.id == "astrolog_found")
    assert check.status == "warn" and "gone" in check.detail
    assert config.load()["astrolog"]["path"] == str(fake_astrolog.resolve())


def test_stale_configured_path_and_nothing_else(tmp_path: Path) -> None:
    config.set_value("astrolog.path", str(tmp_path / "deleted" / "astrolog"))
    check = next(c for c in doctor.run_all().checks if c.id == "astrolog_found")
    assert check.status == "fail" and "is gone" in check.detail


def test_settings_file_reports_overrides(fake_astrolog: Path) -> None:
    (fake_astrolog.parent / "astrolog.as").write_text(
        "@AD780  ; settings\n_s      ; zodiac\n=s      ; sidereal!\n-c Whole ; houses\n=Yn\n-x 5\n"
    )
    check = next(c for c in doctor.run_all().checks if c.id == "settings_file")
    assert check.status == "info"
    for word in ("sidereal zodiac", "Whole houses", "true node", "a harmonic chart", "aren't affected"):
        assert word in check.detail


def test_settings_file_standard(fake_astrolog: Path) -> None:
    (fake_astrolog.parent / "astrolog.as").write_text("@AD780\n_s\n-c Plac\n_Yn\n-x 1\n")
    check = next(c for c in doctor.run_all().checks if c.id == "settings_file")
    assert check.status == "ok"


def test_smoke_chart_is_pinned() -> None:
    assert "_s" in doctor.SMOKE_CHART and "-x" in doctor.SMOKE_CHART
