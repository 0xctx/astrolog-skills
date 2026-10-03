"""Where things live. User data never goes inside the plugin (its root is replaced on every update)."""

from __future__ import annotations

import os
from pathlib import Path

DATA_ENV = "ASTROLOG_SKILLS_HOME"
ROOT_ENV = "ASTROLOG_SKILLS_PLUGIN_ROOT"
CALLER_PATH_ENV = "ASTROLOG_SKILLS_CALLER_PATH"  # the PATH of whoever ran bin/astro (before uv changed it)

SUBDIRS = (
    "profiles",
    "charts",
    "sets",
    "data",
    "traditions",
    "presets",
    "themes",
    "exports",
    "research",
    "cache",
)


def data_dir() -> Path:
    """The user's data folder: `~/.astrolog-skills` unless ASTROLOG_SKILLS_HOME is set."""
    return Path(os.environ.get(DATA_ENV) or "~/.astrolog-skills").expanduser()


def config_path() -> Path:
    return data_dir() / "config.toml"


def ensure_data_dir() -> list[Path]:
    """Create the data folder and its subfolders if missing. Returns the paths that were created."""
    created: list[Path] = []
    for path in (data_dir(), *(data_dir() / name for name in SUBDIRS)):
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)
    return created


def plugin_root() -> Path:
    """The plugin checkout (exported by bin/astro), falling back to this source tree."""
    env = os.environ.get(ROOT_ENV)
    return Path(env) if env else Path(__file__).resolve().parents[2]
