from __future__ import annotations

import hashlib
import io
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from astrolog_skills import config
from astrolog_skills.astrolog import install
from astrolog_skills.errors import AstroError
from tests.conftest import FAKE

HEADER = (
    "/* astrolog.h */\n"
    "//#define PC /* Unix */\n"
    "#define X11 /* Comment out if you don't have X windows */\n"
    "#define GRAPH\n"
)


def _makefile() -> str:
    # The "build" produces a fake astrolog; it also proves X11 was switched off before make ran.
    shim = f'#!/bin/sh\\nexec "{sys.executable}" "{FAKE}" "$$@"\\n'
    return f"astrolog:\n\tgrep -q '^//#define X11' astrolog.h\n\tprintf '{shim}' > astrolog\n\tchmod +x astrolog\n"


def make_source_tarball(path: Path, header: str = HEADER) -> str:
    files = {
        "Astrolog-8.00/astrolog.h": header,
        "Astrolog-8.00/Makefile": _makefile(),
        "Astrolog-8.00/astrolog.as": "; defaults\n",
        "Astrolog-8.00/atlas.as": "; atlas\n",
        "Astrolog-8.00/timezone.as": "; zones\n",
        "Astrolog-8.00/ephem/sepl_18.se1": "",
        "Astrolog-8.00/ephem/semo_18.se1": "",
    }
    with tarfile.open(path, "w:gz") as tar:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def local_release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    archive = tmp_path / "v8.00.tar.gz"
    digest = make_source_tarball(archive)
    rel = install.Release("8.00", archive.as_uri(), digest, "file:///nope.zip", "0" * 64)
    monkeypatch.setitem(install.RELEASES, "8.00", rel)
    return archive


def test_plan_defaults(local_release: Path, isolated: Path) -> None:
    p = install.plan()
    assert p.method == "source-build"
    assert p.prefix == (isolated / "data" / "astrolog").resolve()
    assert not p.exists and set(p.prerequisites) == {"make", "cc", "c++"}


def test_unknown_version() -> None:
    with pytest.raises(AstroError) as err:
        install.plan("1.0")
    assert err.value.fix and "8.00" in err.value.fix


def test_prefix_too_long(tmp_path: Path) -> None:
    with pytest.raises(AstroError):
        install.plan(prefix=tmp_path / ("x" * 200))


def test_missing_compiler_gives_os_hint(local_release: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(install.shutil, "which", lambda _name: None)
    monkeypatch.setattr(install, "compiler_hint", lambda: "sudo dnf install gcc-c++ make")
    p = install.plan()
    assert p.missing == ["make", "cc", "c++"]
    with pytest.raises(AstroError) as err:
        install.check_ready(p)
    assert err.value.fix and "dnf install gcc-c++ make" in err.value.fix


@pytest.mark.parametrize(
    ("os_release", "hint"),
    [
        ("ID=fedora\nVERSION_ID=42\n", "dnf install gcc-c++ make"),
        ("ID=ubuntu\nID_LIKE=debian\n", "apt install build-essential"),
        ('ID="linuxmint"\nID_LIKE="ubuntu debian"\n', "apt install build-essential"),
        ("ID=arch\n", "pacman -S base-devel"),
        ('ID="opensuse-tumbleweed"\nID_LIKE="opensuse suse"\n', "zypper install"),
        ("ID=alpine\n", "apk add build-base"),
        ("ID=weird\n", "package manager"),
    ],
)
def test_compiler_hint(os_release: str, hint: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert hint in install.compiler_hint(os_release)


def test_compiler_hint_macos(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    assert install.compiler_hint("") == "xcode-select --install"


def test_disable_x11(tmp_path: Path) -> None:
    header = tmp_path / "astrolog.h"
    header.write_text(HEADER)
    install.disable_x11(header)
    text = header.read_text()
    assert "//#define X11 " in text and "\n#define X11" not in text and "#define GRAPH" in text


def test_disable_x11_unexpected_layout(tmp_path: Path) -> None:
    header = tmp_path / "astrolog.h"
    header.write_text("/* nothing here */\n")
    with pytest.raises(AstroError):
        install.disable_x11(header)


def test_end_to_end_local_build(local_release: Path, isolated: Path) -> None:
    p = install.plan()
    messages: list[str] = []
    result = install.execute(p, progress=messages.append)
    target = isolated / "data" / "astrolog"
    assert result["ok"] and result["version"] == "8.00" and result["ephemeris"] == "swiss"
    assert (
        (target / "astrolog").exists()
        and (target / "atlas.as").exists()
        and (target / "ephem" / "sepl_18.se1").exists()
    )
    assert config.load()["astrolog"]["path"] == str(target / "astrolog")
    assert any("checksum" in m for m in messages) and any("compiling" in m for m in messages)


def test_existing_prefix_needs_force(local_release: Path, isolated: Path) -> None:
    install.execute(install.plan())
    with pytest.raises(AstroError) as err:
        install.execute(install.plan())
    assert err.value.fix and "--force" in err.value.fix
    install.execute(install.plan(force=True))
    assert (isolated / "data" / "astrolog.bak" / "astrolog").exists()


def test_checksum_mismatch_installs_nothing(
    local_release: Path, isolated: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rel = install.RELEASES["8.00"]
    monkeypatch.setitem(install.RELEASES, "8.00", install.Release("8.00", rel.source_url, "f" * 64, "", ""))
    with pytest.raises(AstroError) as err:
        install.execute(install.plan())
    assert "Checksum mismatch" in err.value.message
    assert not (isolated / "data" / "astrolog").exists()


def test_build_failure_shows_log(tmp_path: Path, isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "bad.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name, text in {
            "Astrolog-8.00/astrolog.h": HEADER,
            "Astrolog-8.00/Makefile": "astrolog:\n\t@echo compiler exploded; exit 2\n",
        }.items():
            info = tarfile.TarInfo(name)
            info.size = len(text)
            tar.addfile(info, io.BytesIO(text.encode()))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    monkeypatch.setitem(install.RELEASES, "8.00", install.Release("8.00", archive.as_uri(), digest, "", ""))
    with pytest.raises(AstroError) as err:
        install.execute(install.plan())
    assert "compiler exploded" in err.value.message
    assert err.value.fix and "astrolog-build.log" in err.value.fix


def test_windows_zip(tmp_path: Path, isolated: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    archive = tmp_path / "ast80cli.zip"
    shim = f'#!/bin/sh\nexec "{sys.executable}" "{FAKE}" "$@"\n'
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("astrolog.exe", shim)
        z.writestr("atlas.as", "; atlas\n")
        z.writestr("ephem/sepl_18.se1", "")
        z.writestr("ephem/semo_18.se1", "")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    monkeypatch.setitem(install.RELEASES, "8.00", install.Release("8.00", "", "", archive.as_uri(), digest))
    monkeypatch.setattr(install, "is_windows", lambda: True)
    p = install.plan()
    assert p.method == "windows-zip"
    result = install.execute(p)
    assert result["path"].endswith("astrolog.exe")
    assert (isolated / "data" / "astrolog" / "atlas.as").exists()


@pytest.mark.network
@pytest.mark.build
def test_real_official_build(tmp_path: Path) -> None:
    """Downloads the real v8.00 source, verifies the pinned checksum, builds headless, runs the smoke chart."""
    prefix = Path("/tmp") / f"ast-test-{tmp_path.name[-8:]}"
    try:
        result = install.execute(install.plan(prefix=prefix))
        assert result["ok"] and result["ephemeris"] == "swiss"
    finally:
        import shutil

        shutil.rmtree(prefix, ignore_errors=True)


def test_c_compiler_without_cplusplus_is_not_enough(local_release: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: the Makefile compiles with g++ (make's CXX) and links with cc; gcc alone must not pass."""
    present = {"make": "/usr/bin/make", "cc": "/usr/bin/cc", "gcc": "/usr/bin/gcc"}
    monkeypatch.setattr(install.shutil, "which", lambda name: present.get(name))
    p = install.plan()
    assert p.missing == ["c++"]
    with pytest.raises(AstroError):
        install.check_ready(p)


def test_found_cxx_is_passed_to_make(local_release: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    real_run = install.subprocess.run

    def spy(cmd: list[str], **kwargs: object) -> object:
        calls.append(cmd)
        return real_run(cmd, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr(install.subprocess, "run", spy)
    p = install.plan()
    install.execute(p)
    make = next(c for c in calls if c[0] == "make")
    assert f"CXX={p.prerequisites['c++']}" in make
