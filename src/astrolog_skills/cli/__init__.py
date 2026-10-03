"""CLI entry point: auto-discovers command modules so new command groups never edit a shared list."""

from __future__ import annotations

import importlib
import pkgutil
import sys

from astrolog_skills.cli import commands
from astrolog_skills.cli.app import app
from astrolog_skills.errors import AstroError
from astrolog_skills.ui import make_output

_registered = False


def register_all() -> list[str]:
    """Import every module in `cli/commands/` and call its `register(app)`. Returns module names."""
    global _registered
    names = sorted(m.name for m in pkgutil.iter_modules(commands.__path__) if not m.name.startswith("_"))
    if not _registered:
        for name in names:
            module = importlib.import_module(f"{commands.__name__}.{name}")
            module.register(app)
        _registered = True
    return names


def main() -> None:
    register_all()
    try:
        app()  # Typer handles --help, usage errors and exit codes itself
    except AstroError as err:
        args = sys.argv[1:]
        make_output(as_json="--json" in args, plain="--plain" in args).error(err)
        sys.exit(1)
