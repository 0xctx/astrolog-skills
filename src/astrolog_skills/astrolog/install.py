"""Install Astrolog from its official source (github.com/CruiserOne/Astrolog), only with consent.

Linux/macOS: download the pinned release tarball, verify its SHA-256, switch off X11 (headless — the
plugin draws in the terminal), `make`, and copy the program + data files into ~/.astrolog-skills/astrolog.
Windows: the pinned official CLI zip already contains astrolog.exe.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from astrolog_skills import config, packages
from astrolog_skills.astrolog import locate
from astrolog_skills.astrolog.run import expressions
from astrolog_skills.errors import AstroError
from astrolog_skills.paths import data_dir

Progress = Callable[[str], None]

# Data files copied next to the binary (those that exist in a given release).
DATA_FILES = (
    "astrolog.as",
    "atlas.as",
    "timezone.as",
    "astrolog.htm",
    "changes.htm",
    "license.htm",
    "astexo.csv",
)


@dataclass(frozen=True)
class Release:
    version: str
    source_url: str
    source_sha256: str
    windows_url: str
    windows_sha256: str


RELEASES: dict[str, Release] = {
    "8.00": Release(
        version="8.00",
        source_url="https://github.com/CruiserOne/Astrolog/archive/refs/tags/v8.00.tar.gz",
        source_sha256="14ef68986e00ca46e7a5703f46348ee8be9b474efde56c060a8a9285e60dc838",
        windows_url="https://github.com/CruiserOne/Astrolog/releases/download/v8.00/ast80cli.zip",
        windows_sha256="0f35b75b002a20aeea71554cc096f105febba5c73a7fa495b11a6b59af38d6d8",
    ),
}
DEFAULT_VERSION = "8.00"


@dataclass
class InstallPlan:
    version: str
    method: str  # "source-build" | "windows-zip"
    url: str
    sha256: str
    prefix: Path
    exists: bool
    force: bool
    prerequisites: dict[str, str | None] = field(default_factory=dict)  # tool -> path or None

    @property
    def missing(self) -> list[str]:
        return [tool for tool, path in self.prerequisites.items() if path is None]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "method": self.method,
            "url": self.url,
            "sha256": self.sha256,
            "prefix": str(self.prefix),
            "exists": self.exists,
            "force": self.force,
            "prerequisites": self.prerequisites,
            "missing": self.missing,
        }


def default_prefix() -> Path:
    return data_dir() / "astrolog"


def is_windows() -> bool:
    return sys.platform == "win32"


def compiler_hint(os_release: str | None = None) -> str:
    """The one command that installs a C/C++ compiler and make on this OS."""
    return packages.hint(
        {"dnf": "gcc-c++ make", "apt": "build-essential", "pacman": "base-devel", "zypper": "gcc-c++ make",
         "apk": "build-base"},
        mac="xcode-select --install",
        windows="nothing to build: the official prebuilt astrolog.exe is unpacked instead",
        otherwise="install a C/C++ compiler (gcc or clang) and make with your package manager",
        os_release=os_release,
    )  # fmt: skip


def plan(version: str = DEFAULT_VERSION, prefix: Path | None = None, force: bool = False) -> InstallPlan:
    if version not in RELEASES:
        raise AstroError(f"Unknown Astrolog version '{version}'.", fix="available: " + ", ".join(RELEASES))
    rel = RELEASES[version]
    prefix = (prefix or default_prefix()).expanduser().resolve()
    if is_windows():
        p = InstallPlan(version, "windows-zip", rel.windows_url, rel.windows_sha256, prefix, prefix.exists(), force)
    else:
        # Astrolog's Makefile compiles .cpp files with make's $(CXX) and links with `cc` — both are needed.
        prereq = {
            "make": shutil.which("make"),
            "cc": shutil.which("cc"),
            "c++": shutil.which("g++") or shutil.which("c++") or shutil.which("clang++"),
        }
        p = InstallPlan(
            version, "source-build", rel.source_url, rel.source_sha256, prefix, prefix.exists(), force, prereq
        )
    if len(str(prefix / "ephem" / "sepl_18.se1")) >= locate.MAX_EPHEM_PATH:
        raise AstroError(
            f"The install folder path is too long for Astrolog ({prefix}).",
            fix="choose a shorter folder with --prefix, e.g. --prefix ~/astrolog8",
        )
    return p


def check_ready(p: InstallPlan) -> None:
    if p.missing:
        raise AstroError(
            "Building Astrolog needs make, cc and a C++ compiler (missing: " + ", ".join(p.missing) + ").",
            fix=f"run `{compiler_hint()}` in your terminal, then try again",
        )
    if p.exists and not p.force:
        raise AstroError(
            f"Astrolog is already installed at {p.prefix}.",
            fix="add --force to replace it (the old one is kept as .bak)",
        )


def download(url: str, dest: Path, progress: Progress) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "astrolog-skills-installer"})
    try:
        with urllib.request.urlopen(request, timeout=60) as resp, open(dest, "wb") as f:
            total = int(resp.headers.get("Content-Length") or 0)
            got = 0
            last = 0.0
            while chunk := resp.read(256 * 1024):
                f.write(chunk)
                got += len(chunk)
                if time.monotonic() - last > 0.5:
                    last = time.monotonic()
                    size = f"{got / 1e6:.1f} MB" + (f" of {total / 1e6:.1f} MB" if total else "")
                    progress(f"downloading… {size}")
    except OSError as err:
        raise AstroError(f"Download failed: {err}.", fix="check your internet connection and try again") from err


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def disable_x11(header: Path) -> None:
    """Comment out `#define X11` so Astrolog builds headless (no X Window libraries needed)."""
    lines = header.read_text(encoding="latin-1").splitlines(keepends=True)
    hits = [i for i, line in enumerate(lines) if line.startswith("#define X11 ") or line.strip() == "#define X11"]
    if len(hits) != 1:
        raise AstroError("Unexpected Astrolog source layout (couldn't find `#define X11`).", fix="please report this")
    lines[hits[0]] = "//" + lines[hits[0]]
    header.write_text("".join(lines), encoding="latin-1")


def build(src: Path, log: Path, progress: Progress, cxx: str | None = None) -> Path:
    disable_x11(src / "astrolog.h")
    libs = "-lm" if sys.platform == "darwin" else "-lm -ldl"
    jobs = str(os.cpu_count() or 2)
    progress(f"compiling Astrolog ({jobs} cores)…")
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w") as out:
        proc = subprocess.run(
            ["make", f"-j{jobs}", f"LIBS={libs}", *([f"CXX={cxx}"] if cxx else [])],
            cwd=src,
            stdout=out,
            stderr=subprocess.STDOUT,
            check=False,
        )
    binary = src / "astrolog"
    if proc.returncode != 0 or not binary.exists():
        tail = "".join(log.read_text(errors="replace").splitlines(keepends=True)[-20:])
        raise AstroError(f"The build failed (exit {proc.returncode}). Last lines:\n{tail}", fix=f"full log: {log}")
    return binary


def _extract_source(archive: Path, into: Path) -> Path:
    with tarfile.open(archive) as tar:
        tar.extractall(into, filter="data")
    roots = [p for p in into.iterdir() if p.is_dir()]
    if len(roots) != 1 or not (roots[0] / "astrolog.h").exists():
        raise AstroError("The downloaded source doesn't look like Astrolog.", fix="please report this")
    return roots[0]


def _extract_windows(archive: Path, into: Path) -> Path:
    with zipfile.ZipFile(archive) as z:
        z.extractall(into)
    if not (into / "astrolog.exe").exists():
        raise AstroError("The downloaded zip has no astrolog.exe.", fix="please report this")
    return into


def _install_files(src: Path, binary: Path, prefix: Path, force: bool) -> None:
    if prefix.exists():
        if not force:
            raise AstroError(f"Astrolog is already installed at {prefix}.", fix="add --force to replace it")
        backup = prefix.with_name(prefix.name + ".bak")
        if backup.exists():
            shutil.rmtree(backup)
        prefix.rename(backup)
    prefix.mkdir(parents=True)
    target = prefix / binary.name
    shutil.copy2(binary, target)
    target.chmod(0o755)
    for name in DATA_FILES:
        if (src / name).exists():
            shutil.copy2(src / name, prefix / name)
    if (src / "ephem").is_dir():
        shutil.copytree(src / "ephem", prefix / "ephem")


def execute(p: InstallPlan, progress: Progress = lambda _: None) -> dict[str, Any]:
    check_ready(p)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="astrolog-build-") as tmp:
        work = Path(tmp)
        archive = work / ("astrolog.zip" if p.method == "windows-zip" else "astrolog.tar.gz")
        progress(f"downloading Astrolog {p.version} from the official repository…")
        download(p.url, archive, progress)
        progress("verifying checksum…")
        got = sha256(archive)
        if got != p.sha256:
            raise AstroError(
                f"Checksum mismatch — the download isn't the official release (got {got[:12]}…).",
                fix="nothing was installed; try again later, and report it if it persists",
            )
        extract_to = work / "src"
        extract_to.mkdir()
        if p.method == "windows-zip":
            src = _extract_windows(archive, extract_to)
            binary = src / "astrolog.exe"
        else:
            src = _extract_source(archive, extract_to)
            cxx = p.prerequisites.get("c++")
            binary = build(src, data_dir() / "cache" / "astrolog-build.log", progress, cxx)
        progress(f"installing into {p.prefix}…")
        _install_files(src, binary, p.prefix, p.force)

    installed = p.prefix / binary.name
    progress("verifying calculations…")
    from astrolog_skills.doctor import SMOKE_CHART, SMOKE_SUN, SMOKE_TOLERANCE

    (sun,) = expressions(installed, SMOKE_CHART, ["ObjLon O_Sun"])
    if abs(sun - SMOKE_SUN) > SMOKE_TOLERANCE:
        raise AstroError(f"Installed, but the test chart is wrong (Sun {sun:.4f}°).", fix="run `astro doctor`")
    config.set_value("astrolog.path", str(installed))
    return {
        "ok": True,
        "version": p.version,
        "path": str(installed),
        "ephemeris": locate.ephemeris(installed).mode,
        "seconds": round(time.monotonic() - started, 1),
        "platform": platform.system(),
    }
