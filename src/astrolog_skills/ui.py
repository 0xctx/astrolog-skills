"""Output modes shared by every command: rich (truecolor), plain, and json.

Rich output is *forced* to truecolor because Claude Code's `!` runs commands without a TTY,
and rich would otherwise strip every colour. Claude itself reads `--plain` or `--json`.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from rich.console import Console

from astrolog_skills.errors import AstroError

Mode = Literal["rich", "plain", "json"]
RGB = tuple[int, int, int]

# One palette for the whole toolkit; terminal themes start from these tokens.
PALETTE: dict[str, RGB] = {
    "accent": (120, 220, 235),
    "ok": (120, 220, 140),
    "warn": (255, 205, 70),
    "bad": (255, 95, 95),
    "dim": (140, 150, 190),
    "gold": (255, 230, 140),
    "text": (235, 240, 255),
    # element colours — air is lavender, deliberately not yellow
    "fire": (255, 150, 125),
    "earth": (135, 215, 145),
    "air": (200, 180, 250),
    "water": (135, 190, 255),
}


def rgb(name: str) -> str:
    """Rich style string for a palette colour, e.g. `rgb('accent')` → 'rgb(120,220,235)'."""
    r, g, b = PALETTE[name]
    return f"rgb({r},{g},{b})"


def _plain_requested() -> bool:
    return bool(os.environ.get("NO_COLOR")) or os.environ.get("ASTRO_PLAIN", "") not in ("", "0")


@dataclass
class Output:
    mode: Mode
    console: Console
    err_console: Console = field(default_factory=lambda: Console(stderr=True, highlight=False))

    @property
    def is_json(self) -> bool:
        return self.mode == "json"

    def emit(self, data: object, render: Callable[[Console], None] | None = None) -> None:
        """Print `data` as JSON in json mode; otherwise call the human renderer."""
        if self.is_json or render is None:
            sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n")
            sys.stdout.flush()
        else:
            render(self.console)

    def status(self, message: str) -> None:
        """Progress/status lines: stderr in json mode so stdout stays one clean document."""
        if self.is_json:
            self.err_console.print(message, markup=False)
        else:
            self.console.print(message)

    def error(self, err: AstroError) -> None:
        if self.is_json:
            sys.stdout.write(json.dumps(err.to_dict(), ensure_ascii=False, indent=2) + "\n")
            return
        c = self.console
        c.print(f"[bold {rgb('bad')}]✗[/] [bold]{_escape(err.message)}[/]")
        if err.fix:
            c.print(f"  [{rgb('accent')}]→ fix:[/] {_escape(err.fix)}")


def _escape(text: str) -> str:
    from rich.markup import escape

    return escape(text)


def make_output(plain: bool = False, as_json: bool = False, width: int | None = None) -> Output:
    if as_json:
        return Output("json", Console(no_color=True, highlight=False, width=width or 100))
    if plain or _plain_requested():
        return Output(
            "plain",
            Console(no_color=True, force_terminal=False, highlight=False, width=width or 160, emoji=False),
        )
    return Output(
        "rich",
        Console(force_terminal=True, color_system="truecolor", highlight=False, width=width or 80, emoji=False),
    )
