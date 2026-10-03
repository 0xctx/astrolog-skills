"""Find Astrolog, read its version, and inspect its ephemeris files."""

from __future__ import annotations

import functools
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from astrolog_skills import config
from astrolog_skills.astrolog.run import run
from astrolog_skills.paths import data_dir

MIN_VERSION = (7, 80)
LATEST_KNOWN = "8.00"
LATEST_KNOWN_VERSION = (8, 0)  # compare tuples, never strings ("10.00" < "8.00" as text)
# Swiss Ephemeris truncates paths over 255 chars and Astrolog then prints nothing; stay well below.
MAX_EPHEM_PATH = 200
BIN_ENV = "ASTROLOG_BIN"
_VERSION = re.compile(r"Astrolog version (\d+)\.(\d+)")
EXE = "astrolog.exe" if sys.platform == "win32" else "astrolog"


@dataclass(frozen=True)
class Found:
    path: Path
    source: str  # where it was found: config, env, PATH, installed, home, system


@dataclass(frozen=True)
class Ephemeris:
    mode: str  # "swiss" (Swiss Ephemeris files) or "builtin" (Astrolog's internal calculation)
    directory: Path
    files: int


def candidates() -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    if configured := config.load()["astrolog"]["path"]:
        found.append((Path(configured).expanduser(), "config"))
    if env := os.environ.get(BIN_ENV):
        found.append((Path(env).expanduser(), "env"))
    if on_path := shutil.which("astrolog"):
        found.append((Path(on_path), "PATH"))
    found.append((data_dir() / "astrolog" / EXE, "installed"))
    found.append((Path.home() / "astrolog" / EXE, "home"))
    if sys.platform == "win32":  # the usual places Windows users unpack Astrolog
        roots = [os.environ[v] for v in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA") if os.environ.get(v)]
        systems = [Path(r) / "Astrolog" / EXE for r in roots] + [Path("C:/Astrolog") / EXE]
    else:
        systems = [Path("/usr/local/bin/astrolog"), Path("/opt/astrolog/astrolog")]
    found += [(p, "system") for p in systems]
    return found


def is_runnable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def configured_path() -> Path | None:
    """The astrolog.path from config, if one is set."""
    value = config.load()["astrolog"]["path"]
    return Path(value).expanduser() if value else None


def find() -> Found | None:
    for path, source in candidates():
        if is_runnable(path):
            return Found(path.resolve(), source)
    return None


def version(binary: Path) -> tuple[int, int] | None:
    """Astrolog's version from its banner — cached per binary (a reinstall changes mtime/size, refreshing it)."""
    try:
        stat = binary.stat()
    except OSError:
        return _version_uncached(str(binary), 0, 0)
    return _version_uncached(str(binary), stat.st_mtime_ns, stat.st_size)


@functools.lru_cache(maxsize=16)
def _version_uncached(binary: str, _mtime: int, _size: int) -> tuple[int, int] | None:
    done = run(Path(binary), ["-Hc"], timeout=15)
    m = _VERSION.search(done.stdout + done.stderr)
    return (int(m[1]), int(m[2])) if m else None


def version_text(v: tuple[int, int] | None) -> str:
    return f"{v[0]}.{v[1]:02d}" if v else "unknown"


def ephemeris(binary: Path) -> Ephemeris:
    directory = binary.parent / "ephem"
    files = sorted(directory.glob("*.se1")) if directory.is_dir() else []
    names = [f.name for f in files]
    swiss = any(n.startswith("sepl_") for n in names) and any(n.startswith("semo_") for n in names)
    return Ephemeris("swiss" if swiss else "builtin", directory, len(files))


def ephem_path_length(binary: Path) -> int:
    return len(str(binary.parent / "ephem" / "sepl_18.se1"))


def path_length_ok(binary: Path) -> bool:
    return ephem_path_length(binary) < MAX_EPHEM_PATH
