"""Windows support that can be checked from any OS: the cmd launcher matches the bash one, and Astrolog is looked for
in the usual Windows places. (Windows itself is untested.)"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

from astrolog_skills.astrolog import locate

BIN = Path(__file__).resolve().parents[1] / "bin"


def test_the_cmd_launcher_matches_the_bash_one() -> None:
    bash = (BIN / "astro").read_text()
    cmd = (BIN / "astro.cmd").read_bytes()
    assert b"\r\n" in cmd and b"\n" not in cmd.replace(b"\r\n", b"")  # CRLF only, as cmd needs
    text = cmd.decode()
    for var in ("ASTROLOG_SKILLS_PLUGIN_ROOT", "ASTROLOG_SKILLS_CALLER_PATH", "UV_PROJECT_ENVIRONMENT"):
        assert var in bash and var in text, var
    run = re.search(r"uv run (.*?) python -m astrolog_skills", bash)
    assert run and f"uv run {run.group(1).replace('$root', '%ROOT%')} python -m astrolog_skills %*" in text
    assert "exit /b 127" in text and "install.ps1" in text  # uv missing: the Windows install line


def test_astrolog_is_looked_for_in_windows_places(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(locate.shutil, "which", lambda _name: None)  # which() itself can't run as win32 on Linux
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "PF"))
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LA"))
    systems = [p for p, source in locate.candidates() if source == "system"]
    names = {p.name for p in systems}
    assert tmp_path / "PF" / "Astrolog" / locate.EXE in systems and tmp_path / "LA" / "Astrolog" / locate.EXE in systems
    assert Path("C:/Astrolog") / locate.EXE in systems and len(names) == 1
    assert not any(str(p).startswith("/usr") for p in systems)
