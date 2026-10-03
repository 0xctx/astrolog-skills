from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from astrolog_skills.astrolog import run
from astrolog_skills.errors import AstroError

EINSTEIN = ["-qa", "3", "14", "1879", "11:30", "LMT", "10:00E", "48:24N"]


def test_expressions_parse_stderr(fake_astrolog: Path) -> None:
    sun, moon = run.expressions(fake_astrolog, EINSTEIN, ["ObjLon O_Sun", "ObjLon O_Moo"])
    assert sun == pytest.approx(353.507748)
    assert moon == pytest.approx(254.525911)


def test_missing_values_raise_with_fix(fake_astrolog: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ASTROLOG_BROKEN", "1")
    with pytest.raises(AstroError) as err:
        run.expressions(fake_astrolog, EINSTEIN, ["ObjLon O_Sun"])
    assert "0 of 1" in err.value.message
    assert err.value.fix and "astro doctor" in err.value.fix


def test_missing_binary(tmp_path: Path) -> None:
    with pytest.raises(AstroError) as err:
        run.run(tmp_path / "nope", ["-Hc"])
    assert err.value.fix and "astro astrolog install" in err.value.fix


def test_not_executable(tmp_path: Path) -> None:
    f = tmp_path / "astrolog"
    f.write_text("#!/bin/sh\n")
    f.chmod(0o644)
    with pytest.raises(AstroError) as err:
        run.run(f, ["-Hc"])
    assert err.value.fix and "chmod" in err.value.fix


def test_timeout(monkeypatch: pytest.MonkeyPatch, fake_astrolog: Path) -> None:
    def slow(*_a: object, **_k: object) -> None:
        raise subprocess.TimeoutExpired(cmd="astrolog", timeout=1)

    monkeypatch.setattr(subprocess, "run", slow)
    with pytest.raises(AstroError) as err:
        run.run(fake_astrolog, ["-Hc"], timeout=1)
    assert "longer than" in err.value.message


def test_latin1_output_does_not_crash(tmp_path: Path) -> None:
    f = tmp_path / "astrolog"
    f.write_bytes(b"#!/bin/sh\nprintf 'Z\\374rich\\n'\n")
    f.chmod(0o755)
    assert "Zürich" in run.run(f, []).stdout
