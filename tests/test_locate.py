from __future__ import annotations

from pathlib import Path

import pytest

from astrolog_skills import config
from astrolog_skills.astrolog import locate
from tests.conftest import write_fake_astrolog


def test_nothing_found() -> None:
    assert locate.find() is None


def test_env_found(fake_astrolog: Path) -> None:
    found = locate.find()
    assert found and found.path == fake_astrolog.resolve() and found.source == "env"


def test_config_beats_env(fake_astrolog: Path, tmp_path: Path) -> None:
    other = write_fake_astrolog(tmp_path / "other")
    config.set_value("astrolog.path", str(other))
    found = locate.find()
    assert found and found.source == "config" and found.path == other.resolve()


def test_home_install_found(isolated: Path) -> None:
    shim = write_fake_astrolog(isolated / "home" / "astrolog")
    found = locate.find()
    assert found and found.source == "home" and found.path == shim.resolve()


def test_installed_beats_home(isolated: Path) -> None:
    write_fake_astrolog(isolated / "home" / "astrolog")
    ours = write_fake_astrolog(isolated / "data" / "astrolog")
    found = locate.find()
    assert found and found.source == "installed" and found.path == ours.resolve()


@pytest.mark.parametrize(("banner", "expected"), [("8.00", (8, 0)), ("7.80", (7, 80)), ("7.70", (7, 70))])
def test_version(fake_astrolog: Path, monkeypatch: pytest.MonkeyPatch, banner: str, expected: tuple[int, int]) -> None:
    monkeypatch.setenv("FAKE_ASTROLOG_VERSION", banner)
    assert locate.version(fake_astrolog) == expected


def test_version_compare() -> None:
    assert (7, 70) < locate.MIN_VERSION <= (7, 80) < (8, 0)
    assert locate.version_text((8, 0)) == "8.00"
    assert locate.version_text(None) == "unknown"


def test_ephemeris_modes(tmp_path: Path, fake_astrolog: Path) -> None:
    assert locate.ephemeris(fake_astrolog).mode == "swiss"
    bare = write_fake_astrolog(tmp_path / "bare")
    assert locate.ephemeris(bare).mode == "builtin"


def test_path_length(tmp_path: Path) -> None:
    deep = tmp_path / ("x" * 60) / ("y" * 60) / ("z" * 60)
    shim = write_fake_astrolog(deep)
    assert not locate.path_length_ok(shim)
    assert locate.path_length_ok(Path("/opt/a/astrolog"))


def test_version_is_cached_per_binary(fake_astrolog: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    real_run = locate.run

    def spy(binary: Path, args: list[str], timeout: float = 30) -> object:
        calls.append(args)
        return real_run(binary, args, timeout=timeout)

    monkeypatch.setattr(locate, "run", spy)
    locate._version_uncached.cache_clear()
    assert locate.version(fake_astrolog) == locate.version(fake_astrolog) == (8, 0)
    assert len(calls) == 1
    import os

    os.utime(fake_astrolog, ns=(1, 1))  # a reinstall changes mtime → probed again
    locate.version(fake_astrolog)
    assert len(calls) == 2
