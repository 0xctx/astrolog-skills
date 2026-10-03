"""Shared fixtures: every test gets its own HOME and data folder, and never sees the real Astrolog."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

FAKE = Path(__file__).parent / "fakes" / "fake_astrolog.py"
REPO = Path(__file__).resolve().parents[1]


def write_fake_astrolog(directory: Path, name: str = "astrolog") -> Path:
    """A shell shim that runs the fake with this interpreter (absolute paths, so it can be copied)."""
    directory.mkdir(parents=True, exist_ok=True)
    shim = directory / name
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE}" "$@"\n')
    shim.chmod(0o755)
    return shim


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("ASTROLOG_SKILLS_HOME", str(tmp_path / "data"))
    monkeypatch.delenv("ASTROLOG_BIN", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("ASTRO_PLAIN", raising=False)
    # PATH without any astrolog/astro, but with the basics (sh, python, make, cc).
    monkeypatch.setenv("PATH", os.pathsep.join(["/usr/bin", "/bin", str(Path(sys.executable).parent)]))
    return tmp_path


@pytest.fixture
def fake_astrolog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake Astrolog with Swiss ephemeris files next to it, configured via ASTROLOG_BIN."""
    install = tmp_path / "ast"
    shim = write_fake_astrolog(install)
    (install / "ephem").mkdir()
    for name in ("sepl_18.se1", "semo_18.se1"):
        (install / "ephem" / name).write_bytes(b"")
    monkeypatch.setenv("ASTROLOG_BIN", str(shim))
    return shim


def run_cli(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run `python -m astrolog_skills` exactly as bin/astro does (stdout is a pipe, not a TTY)."""
    return subprocess.run(
        [sys.executable, "-m", "astrolog_skills", *args],
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
        cwd=REPO,
        check=False,
    )


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def atlas(fake_astrolog: Path) -> Path:
    """The synthetic atlas next to the fake Astrolog (where the real atlas.as lives)."""
    import shutil

    target = fake_astrolog.parent / "atlas.as"
    shutil.copy(FIXTURES / "atlas.as", target)
    return target
