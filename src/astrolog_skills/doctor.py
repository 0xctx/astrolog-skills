"""`astro doctor`: independent checks that each report what's wrong and exactly how to fix it."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from astrolog_skills import config, firstlight
from astrolog_skills.astrolog import locate
from astrolog_skills.astrolog.run import INSTALL_FIX, expressions
from astrolog_skills.engine.profile import NEUTRAL_PINS
from astrolog_skills.errors import AstroError
from astrolog_skills.paths import CALLER_PATH_ENV, config_path, data_dir, ensure_data_dir, plugin_root

Status = Literal["ok", "warn", "fail", "info", "skip"]

# Einstein, 14 Mar 1879 11:30 LMT, Ulm (Rodden AA). Sun = 353.5077° (23°30′ Pisces) in 7.80 and 8.00.
SMOKE_CHART = ["-qa", "3", "14", "1879", "11:30", "LMT", "10:00E", "48:24N", *NEUTRAL_PINS, "_s", "-c", "0"]
SMOKE_SUN = 353.5077
SMOKE_TOLERANCE = 0.001


@dataclass
class CheckResult:
    id: str
    title: str
    status: Status
    detail: str = ""
    fix: str | None = None


@dataclass
class DoctorReport:
    ok: bool
    checks: list[CheckResult]
    astrolog_path: str | None = None
    astrolog_version: str | None = None
    ephemeris: str | None = None
    data_dir: str = ""
    first_light: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class _State:
    binary: Path | None = None
    version: tuple[int, int] | None = None


def _check_data_dir(_: _State) -> CheckResult:
    try:
        created = ensure_data_dir()
        made_config = config.ensure_exists()
        probe = data_dir() / "cache" / ".write-test"
        probe.write_text("ok")
        probe.unlink()
    except OSError as err:
        return CheckResult(
            "data_dir",
            "Your data folder",
            "fail",
            f"can't write to {data_dir()} ({err.strerror})",
            fix=f"make {data_dir()} writable, or choose another folder: export ASTROLOG_SKILLS_HOME=/path",
        )
    detail = str(data_dir())
    if made_config or created:
        detail += " — created" + (" with a fresh config.toml" if made_config else "")
    return CheckResult("data_dir", "Your data folder", "ok", detail)


def _check_found(state: _State) -> CheckResult:
    configured = locate.configured_path()
    stale = configured is not None and not locate.is_runnable(configured)
    found = locate.find()
    if not found:
        return CheckResult(
            "astrolog_found",
            "Astrolog",
            "fail",
            f"not found (configured path {configured} is gone)" if stale else "not found on this computer",
            fix="build the official Astrolog 8.00 for you: `astro astrolog install` (preview, then --yes) — "
            "or point to yours: `astro config set astrolog.path /path/to/astrolog`",
        )
    state.binary = found.path
    if configured is None or stale:
        config.set_value("astrolog.path", str(found.path))
    if stale:
        return CheckResult(
            "astrolog_found",
            "Astrolog",
            "warn",
            f"{found.path}  [{found.source}] — the configured {configured} is gone; config updated",
        )
    return CheckResult("astrolog_found", "Astrolog", "ok", f"{found.path}  [{found.source}]")


def _check_version(state: _State) -> CheckResult:
    assert state.binary
    state.version = locate.version(state.binary)
    text = locate.version_text(state.version)
    if state.version is None:
        return CheckResult("version", "Version", "warn", "couldn't read the version banner — continuing")
    if state.version < locate.MIN_VERSION:
        return CheckResult(
            "version",
            "Version",
            "fail",
            f"{text} is too old (needs 7.80 or newer)",
            fix="install the current official release: `astro astrolog install --yes`",
        )
    if state.version < locate.LATEST_KNOWN_VERSION:
        return CheckResult(
            "version",
            "Version",
            "ok",
            f"{text} · {locate.LATEST_KNOWN} is available: `astro astrolog install --yes`",
        )
    return CheckResult("version", "Version", "ok", f"{text} (latest)")


def _check_path_length(state: _State) -> CheckResult:
    assert state.binary
    length = locate.ephem_path_length(state.binary)
    if not locate.path_length_ok(state.binary):
        return CheckResult(
            "path_length",
            "Install path",
            "fail",
            f"{length} characters — Astrolog silently stops working above ~255",
            fix="install to a shorter folder, e.g. `astro astrolog install --yes` (uses ~/.astrolog-skills/astrolog)",
        )
    return CheckResult("path_length", "Install path", "ok", f"{length} characters")


def _check_ephemeris(state: _State) -> CheckResult:
    assert state.binary
    eph = locate.ephemeris(state.binary)
    if eph.mode == "swiss":
        return CheckResult("ephemeris", "Ephemeris", "ok", f"Swiss Ephemeris files ({eph.files} in {eph.directory})")
    return CheckResult(
        "ephemeris",
        "Ephemeris",
        "info",
        "built-in calculation (accurate to about an arc-second) — `astro astrolog install --yes` adds Swiss files",
    )


# astrolog.as lines that would change results if astrolog-skills didn't pin its own settings.
_OVERRIDES = {
    "=s": "sidereal zodiac",
    "-s": "sidereal zodiac",
    "=Yn": "true node",
    "-x": "a harmonic chart",
    "=h": "heliocentric positions",
    "=YT": "true (not apparent) positions",
    "=YV": "topocentric positions",
    "=sr": "equatorial positions",
    "=p": "progressions",
}


def _check_settings_file(state: _State) -> CheckResult:
    assert state.binary
    path = state.binary.parent / "astrolog.as"
    if not path.exists():
        return CheckResult("settings_file", "astrolog.as", "info", "none next to Astrolog — built-in defaults")
    found: list[str] = []
    for line in path.read_text(encoding="latin-1").splitlines():
        head = line.split(";", 1)[0].split()
        if not head:
            continue
        if head[0] in _OVERRIDES and not (head[0] == "-x" and head[1:2] == ["1"]):
            found.append(_OVERRIDES[head[0]])
        elif head[0] == "-c" and head[1:2] and not head[1].lower().startswith("plac") and head[1] != "0":
            found.append(f"{head[1]} houses")
    if not found:
        return CheckResult("settings_file", "astrolog.as", "ok", "standard settings")
    return CheckResult(
        "settings_file",
        "astrolog.as",
        "info",
        "sets "
        + ", ".join(dict.fromkeys(found))
        + " — astrolog-skills pins its own settings, so results aren't affected",
    )


def _check_smoke(state: _State) -> CheckResult:
    assert state.binary
    try:
        (sun,) = expressions(state.binary, SMOKE_CHART, ["ObjLon O_Sun"])
    except AstroError as err:
        return CheckResult("smoke_chart", "Test chart", "fail", err.message, fix=err.fix or INSTALL_FIX)
    if abs(sun - SMOKE_SUN) > SMOKE_TOLERANCE:
        return CheckResult(
            "smoke_chart",
            "Test chart",
            "fail",
            f"Einstein's Sun came out at {sun:.4f}°, expected {SMOKE_SUN:.4f}°",
            fix="check your astrolog.as for unusual defaults (e.g. sidereal zodiac), or reinstall",
        )
    return CheckResult(
        "smoke_chart",
        "Test chart",
        "ok",
        f"Einstein's Sun at {firstlight.format_position(sun)} — calculations verified",
    )


def _check_shadowing(_: _State) -> CheckResult:
    ours = Path(os.path.realpath(plugin_root() / "bin" / "astro"))
    caller_path = os.environ.get(CALLER_PATH_ENV)
    # Resolve against the caller's PATH: `uv run` prepends its venv, which would always find our own entry point.
    seen = shutil.which("astro", path=caller_path) if caller_path is not None else shutil.which("astro")
    if not seen:
        return CheckResult("shadowing", "`astro` command", "info", "not on PATH here (normal outside Claude Code)")
    seen_real = Path(os.path.realpath(seen))
    # Without bin/astro (e.g. `uv run astro` in development) the venv's entry point is this toolkit too.
    dev_entry_point = caller_path is None and seen_real.parent == Path(sys.executable).parent
    if seen_real != ours and not dev_entry_point:
        return CheckResult(
            "shadowing",
            "`astro` command",
            "warn",
            f"`astro` on your PATH is {seen}, not this plugin",
            fix=f"another program is called astro (e.g. the Astro web framework); use {ours} or remove the other one",
        )
    return CheckResult("shadowing", "`astro` command", "ok", "resolves to this plugin")


def _check_poppler(_: _State) -> CheckResult:
    """Only needed for book sources (PDF extraction and page images), so missing is a warning."""
    from astrolog_skills.sources.extract import poppler_hint

    missing = [tool for tool in ("pdftotext", "pdftoppm", "pdfinfo") if shutil.which(tool) is None]
    if missing:
        return CheckResult(
            "poppler",
            "PDF tools",
            "warn",
            f"{', '.join(missing)} not found — only needed to add PDF books as sources",
            fix=poppler_hint(),
        )
    return CheckResult("poppler", "PDF tools", "ok", "pdftotext and pdftoppm found — PDF sources work")


def _check_ocr(_: _State) -> CheckResult:
    """Only needed for scanned books (PDFs without a text layer): missing is information, not a problem."""
    from astrolog_skills.sources.extract import ocr_hint

    if shutil.which("ocrmypdf") is None:
        return CheckResult(
            "ocr", "OCR for scanned books", "info", "ocrmypdf not found — only for scanned PDFs", fix=ocr_hint()
        )
    return CheckResult("ocr", "OCR for scanned books", "ok", "ocrmypdf found — scanned PDFs are read by OCR")


CHECKS: list[tuple[Callable[[_State], CheckResult], bool]] = [
    # (check, needs a working Astrolog binary)
    (_check_data_dir, False),
    (_check_found, False),
    (_check_version, True),
    (_check_path_length, True),
    (_check_ephemeris, True),
    (_check_settings_file, True),
    (_check_smoke, True),
    (_check_shadowing, False),
    (_check_poppler, False),
    (_check_ocr, False),
]

_SKIP_TITLES = {
    "_check_version": ("version", "Version"),
    "_check_path_length": ("path_length", "Install path"),
    "_check_ephemeris": ("ephemeris", "Ephemeris"),
    "_check_settings_file": ("settings_file", "astrolog.as"),
    "_check_smoke": ("smoke_chart", "Test chart"),
}


def run_all(with_first_light: bool = True) -> DoctorReport:
    state = _State()
    results: list[CheckResult] = []
    for check, needs_binary in CHECKS:
        if needs_binary and state.binary is None:
            cid, title = _SKIP_TITLES[check.__name__]
            results.append(CheckResult(cid, title, "skip", "needs Astrolog"))
            continue
        results.append(check(state))
    ok = not any(r.status == "fail" for r in results)
    report = DoctorReport(
        ok=ok,
        checks=results,
        astrolog_path=str(state.binary) if state.binary else None,
        astrolog_version=locate.version_text(state.version) if state.binary else None,
        ephemeris=locate.ephemeris(state.binary).mode if state.binary else None,
        data_dir=str(data_dir()),
        extra={"config": str(config_path())},
    )
    if ok and with_first_light and state.binary:
        try:
            from astrolog_skills.engine.profile import active, pins

            report.first_light = firstlight.first_light(state.binary, location=config.location(), pins=pins(active()))
        except AstroError:
            report.first_light = None
    return report
