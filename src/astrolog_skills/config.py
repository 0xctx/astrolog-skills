"""`~/.astrolog-skills/config.toml`: small, human-editable, validated on every write."""

from __future__ import annotations

import copy
import os
import re
import tempfile
import tomllib
from pathlib import Path
from typing import Any

import tomli_w

from astrolog_skills.errors import AstroError
from astrolog_skills.paths import config_path, ensure_data_dir

DEFAULTS: dict[str, Any] = {
    "astrolog": {"path": ""},
    "defaults": {"profile": "default", "location": {"name": "", "lat": None, "lon": None}},
    "display": {"width": 80, "glyphs": True, "theme": "default", "orbs": "harmonic"},
    "readings": {"citations": False},
}

# Leaf keys users may set, with the type used to coerce text from the command line.
SETTABLE: dict[str, type] = {
    "astrolog.path": str,
    "defaults.profile": str,
    "defaults.location.name": str,
    "defaults.location.lat": float,
    "defaults.location.lon": float,
    "display.width": int,
    "display.glyphs": bool,
    "display.theme": str,
    "display.orbs": str,  # harmonic charts: "harmonic" (orbs as measured in that chart) or "natal" (÷ H)
    "readings.citations": bool,  # readings and pages cite the sources' page numbers
}


def _merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def _drop_none(data: dict[str, Any]) -> dict[str, Any]:
    return {k: (_drop_none(v) if isinstance(v, dict) else v) for k, v in data.items() if v is not None}


def load(path: Path | None = None) -> dict[str, Any]:
    path = path or config_path()
    if not path.exists():
        return copy.deepcopy(DEFAULTS)
    try:
        with open(path, "rb") as f:
            return _merge(DEFAULTS, tomllib.load(f))
    except tomllib.TOMLDecodeError as err:
        raise AstroError(
            f"Your config file isn't valid TOML ({err}).",
            fix=f"fix the file by hand, or delete it to start fresh: {path}",
        ) from err


def save(cfg: dict[str, Any], path: Path | None = None) -> Path:
    path = path or config_path()
    ensure_data_dir()
    text = tomli_w.dumps(_drop_none(cfg))
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, suffix=".tmp", encoding="utf-8") as tmp:
        tmp.write("# astrolog-skills settings — edit freely, or use `astro config set KEY VALUE`\n\n" + text)
    os.replace(tmp.name, path)
    return path


def ensure_exists() -> bool:
    """Write a default config if none exists. Returns True if it was created."""
    if config_path().exists():
        return False
    save(copy.deepcopy(DEFAULTS))
    return True


def get(key: str, cfg: dict[str, Any] | None = None) -> Any:
    node: Any = cfg if cfg is not None else load()
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            raise AstroError(f"Unknown setting '{key}'.", fix="valid keys: " + ", ".join(SETTABLE))
        node = node[part]
    return node


def _coerce(key: str, raw: str) -> Any:
    kind = SETTABLE[key]
    text = raw.strip()
    if kind is bool:
        if text.lower() in ("true", "yes", "on", "1"):
            return True
        if text.lower() in ("false", "no", "off", "0"):
            return False
        raise AstroError(f"'{raw}' isn't true/false for {key}.", fix=f"astro config set {key} true")
    try:
        return kind(text)
    except ValueError as err:
        raise AstroError(f"'{raw}' isn't a valid {kind.__name__} for {key}.") from err


def set_value(key: str, raw: str) -> dict[str, Any]:
    if key not in SETTABLE:
        raise AstroError(f"Unknown setting '{key}'.", fix="valid keys: " + ", ".join(SETTABLE))
    value = _coerce(key, raw)
    if key == "display.width" and not 60 <= value <= 240:
        raise AstroError("Width must be between 60 and 240 columns.")
    if key == "display.orbs" and value not in ("harmonic", "natal"):
        raise AstroError(
            f"display.orbs must be 'harmonic' or 'natal', not '{value}'.",
            fix="astro config set display.orbs harmonic   (orbs as measured in the harmonic chart)",
        )
    if key == "astrolog.path" and value:
        value = str(Path(value).expanduser())
    cfg = load()
    node = cfg
    *parents, leaf = key.split(".")
    for part in parents:
        node = node.setdefault(part, {})
    node[leaf] = value
    save(cfg)
    return cfg


# ── locations ────────────────────────────────────────────────────────────────

_DMS = re.compile(r"^(\d{1,3})([NSEW])(\d{1,2}(?:\.\d+)?)?$", re.I)  # 10E00, 48N24, 74W00
_DEC = re.compile(r"^(-?\d{1,3}(?:\.\d+)?)°?([NSEW])?$", re.I)  # 48.4N, 10.0E, -74.0


def _one(token: str) -> tuple[float, str | None]:
    token = token.strip().replace(" ", "")
    if m := _DMS.match(token):
        deg, hemi, minutes = int(m[1]), m[2].upper(), float(m[3] or 0)
        value = deg + minutes / 60
        return (-value if hemi in "SW" else value), ("lat" if hemi in "NS" else "lon")
    if m := _DEC.match(token):
        value, hemi = float(m[1]), (m[2] or "").upper()
        if hemi:
            return (-abs(value) if hemi in "SW" else abs(value)), ("lat" if hemi in "NS" else "lon")
        return value, None
    raise AstroError(f"Can't read the coordinate '{token}'.", fix='use e.g. "48N24 10E00" or "48.4, 10.0"')


def parse_location(text: str) -> tuple[float, float]:
    """Parse coordinates into (lat, lon), lon east-positive. Unlabelled pairs are read as 'lat, lon'."""
    parts = [p for p in re.split(r"[,\s]+", text.strip()) if p]
    if len(parts) != 2:
        raise AstroError(f"Expected two coordinates, got '{text}'.", fix='e.g. "48N24 10E00" or "48.4, 10.0"')
    (a, ka), (b, kb) = _one(parts[0]), _one(parts[1])
    if ka == "lon" or kb == "lat":
        a, b, ka, kb = b, a, kb, ka
    lat, lon = a, b
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise AstroError(f"'{text}' is outside the globe (lat ±90, lon ±180).")
    return round(lat, 6), round(lon, 6)


def set_location(text: str, name: str = "") -> dict[str, Any]:
    lat, lon = parse_location(text)
    cfg = load()
    cfg["defaults"]["location"] = {"name": name, "lat": lat, "lon": lon}
    save(cfg)
    return cfg


def location(cfg: dict[str, Any] | None = None) -> tuple[float, float] | None:
    loc = (cfg or load())["defaults"]["location"]
    if loc.get("lat") is None or loc.get("lon") is None:
        return None
    return float(loc["lat"]), float(loc["lon"])
