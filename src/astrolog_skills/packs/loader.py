"""Tradition packs: one folder per tradition. Yours (~/.astrolog-skills/traditions/<name>) replaces the built-in one.

method.toml   calculation rules — read by the toolkit (aspects, orbs, harmonics, patterns, weights, midpoints)
meanings.md   what things mean — read by Claude when interpreting
process.md    how to read a chart in this tradition — followed by Claude
sources.toml  citations for everything above;  sources/  your library;  REVIEW.md  open questions
"""

from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from astrolog_skills.analysis.method import Method, merge, parse
from astrolog_skills.errors import AstroError
from astrolog_skills.paths import data_dir, plugin_root


@dataclass(frozen=True)
class Pack:
    name: str
    directory: Path
    method: Method
    user: bool
    extends: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.method.label or self.name

    def file(self, name: str) -> Path | None:
        path = self.directory / name
        return path if path.is_file() else None

    def to_dict(self) -> dict[str, Any]:
        m = self.method
        return {
            "name": self.name,
            "label": self.label,
            "directory": str(self.directory),
            "user": self.user,
            "extends": self.extends,
            "aspects": {a.key: round(m.orb_for(a), 4) for a in m.aspect_types},
            "orb_rule": m.orb_rule,
            "harmonic_range": list(m.harmonic_range),
            "patterns": {
                "orb": m.pattern_orb,
                "min_size": m.pattern_min_size,
                "strong_size": m.pattern_strong_size,
                "bodies": list(m.pattern_bodies),
            },
            "midpoints": {"aspects": list(m.midpoint_aspects), "orb": m.midpoint_orb},
            "doctrine": m.doctrine.summary() if m.doctrine else None,
            "chart": {**m.chart.to_dict(), "cite": m.chart.cite} if m.chart else None,
            "files": {n: bool(self.file(n)) for n in ("meanings.md", "process.md", "sources.toml", "REVIEW.md")},
            "sources": self.sources,
        }


def builtin_dir() -> Path:
    return plugin_root() / "traditions"


def user_dir() -> Path:
    return data_dir() / "traditions"


def list_packs() -> dict[str, Path]:
    """name → folder (a user pack with the same name replaces the built-in one)."""
    found: dict[str, Path] = {}
    for base in (builtin_dir(), user_dir()):
        if base.is_dir():
            for d in sorted(base.iterdir()):
                if (d / "method.toml").is_file():
                    found[d.name] = d
    return found


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as err:
        raise AstroError(f"Can't read {path}: {err}", fix=f"fix or delete {path}") from err


def raw_method(name: str, seen: tuple[str, ...] = ()) -> dict[str, Any]:
    packs = list_packs()
    if name not in packs:
        raise AstroError(f"No tradition pack called '{name}'.", fix="available: " + ", ".join(packs))
    if name in seen:
        raise AstroError(f"Tradition packs extend each other in a loop: {' → '.join((*seen, name))}.")
    raw = _read_toml(packs[name] / "method.toml")
    parent = raw.get("extends", "")
    if parent:
        base = raw_method(parent, (*seen, name))
        raw = merge(base, raw)
    raw["name"] = name
    return raw


def load(name: str) -> Pack:
    directory = list_packs().get(name)
    if directory is None:
        raise AstroError(f"No tradition pack called '{name}'.", fix="available: " + ", ".join(list_packs()))
    own = _read_toml(directory / "method.toml")
    method = parse(raw_method(name), f"pack '{name}' ({directory / 'method.toml'})")
    sources_file = directory / "sources.toml"
    sources = _read_toml(sources_file).get("source", []) if sources_file.is_file() else []
    return Pack(name, directory, method, str(directory).startswith(str(user_dir())), own.get("extends", ""), sources)


def copy_to_user(name: str, new_name: str | None = None) -> Path:
    """Copy a pack into your folder so you can edit it (same name = your copy replaces the built-in)."""
    source = list_packs().get(name)
    if source is None:
        raise AstroError(f"No tradition pack called '{name}'.", fix="available: " + ", ".join(list_packs()))
    target = user_dir() / (new_name or name)
    if target.exists():
        raise AstroError(f"You already have a pack at {target}.", fix="edit that one, or choose another name with --as")
    shutil.copytree(source, target)
    return target
