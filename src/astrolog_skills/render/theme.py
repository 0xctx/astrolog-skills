"""Terminal themes: colours, shading and glyph choice in a TOML file. Yours (~/.astrolog-skills/themes) win."""

from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astrolog_skills.errors import AstroError
from astrolog_skills.paths import data_dir, plugin_root
from astrolog_skills.render.canvas import RGB

ELEMENTS = ("fire", "earth", "air", "water")
ELEMENT_KEYS = ("header_bg", "header_text", "body_bg", "texture", "accent")
UI_KEYS = (
    "page",
    "frame",
    "frame_text",
    "center_bg",
    "label",
    "text",
    "dim",
    "title",
    "retro",
    "grid_bg",
    "cell_a",
    "cell_b",
    "white",
)
FAMILIES = ("conjunction", "hard", "soft", "green", "pink", "quintile", "septile", "novile", "decile")


@dataclass(frozen=True)
class Theme:
    name: str
    label: str
    glyphs: bool
    shade: str
    ui: dict[str, RGB]
    elements: dict[str, dict[str, RGB]]
    aspects: dict[str, RGB]
    source: str = ""

    def element(self, index: int) -> dict[str, RGB]:
        return self.elements[ELEMENTS[index % 4]]

    def with_letters(self) -> Theme:
        return Theme(self.name, self.label, False, self.shade, self.ui, self.elements, self.aspects, self.source)


def mix(a: RGB, b: RGB, t: float) -> RGB:
    t = max(0.0, min(1.0, t))
    return (round(a[0] + (b[0] - a[0]) * t), round(a[1] + (b[1] - a[1]) * t), round(a[2] + (b[2] - a[2]) * t))


def builtin_dir() -> Path:
    return plugin_root() / "themes"


def user_dir() -> Path:
    return data_dir() / "themes"


def list_themes() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for d in (builtin_dir(), user_dir()):
        if d.is_dir():
            for path in sorted(d.glob("*.toml")):
                found[path.stem] = path
    return found


def _rgb(where: str, key: str, value: Any) -> RGB:
    if not (isinstance(value, list) and len(value) == 3 and all(isinstance(v, int) and 0 <= v <= 255 for v in value)):
        raise AstroError(f"{where}: {key} must be [r, g, b] with 0–255 values, not {value!r}.")
    return (value[0], value[1], value[2])


def load(name: str) -> Theme:
    path = list_themes().get(name)
    if path is None:
        raise AstroError(f"No theme called '{name}'.", fix="available: " + ", ".join(list_themes()))
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as err:
        raise AstroError(f"Can't read theme {path}: {err}", fix=f"fix or delete {path}") from err
    where = f"theme '{name}' ({path})"
    ui_t, el_t, asp_t = raw.get("ui", {}), raw.get("elements", {}), raw.get("aspects", {})
    missing = (
        [k for k in UI_KEYS if k not in ui_t]
        + [e for e in ELEMENTS if e not in el_t]
        + [f for f in FAMILIES if f not in asp_t]
    )
    if missing:
        raise AstroError(
            f"{where} is missing: {', '.join(missing)}.",
            fix="copy the default theme and edit that: astro theme copy default",
        )
    elements = {}
    for e in ELEMENTS:
        absent = [k for k in ELEMENT_KEYS if k not in el_t[e]]
        if absent:
            raise AstroError(f"{where}: elements.{e} is missing {', '.join(absent)}.")
        elements[e] = {k: _rgb(where, f"elements.{e}.{k}", el_t[e][k]) for k in ELEMENT_KEYS}
    shade = str(raw.get("shade", "░"))
    if len(shade) != 1:
        raise AstroError(f"{where}: shade must be one character.")
    return Theme(
        name=name,
        label=str(raw.get("label", name)),
        glyphs=bool(raw.get("glyphs", True)),
        shade=shade,
        ui={k: _rgb(where, f"ui.{k}", ui_t[k]) for k in UI_KEYS},
        elements=elements,
        aspects={f: _rgb(where, f"aspects.{f}", asp_t[f]) for f in FAMILIES},
        source=str(path),
    )


def copy_to_user(name: str, new_name: str | None = None) -> Path:
    source = list_themes().get(name)
    if source is None:
        raise AstroError(f"No theme called '{name}'.", fix="available: " + ", ".join(list_themes()))
    target = user_dir() / f"{new_name or name}.toml"
    if target.exists():
        raise AstroError(f"You already have a theme at {target}.", fix="edit it, or choose another name with --as")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target
