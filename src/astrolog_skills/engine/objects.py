"""Chart objects: our keys ↔ Astrolog's codes (for `-R0` / `O_xxx`) and its 4-letter batch labels."""

from __future__ import annotations

from dataclasses import dataclass

from astrolog_skills.errors import AstroError


@dataclass(frozen=True)
class Obj:
    key: str
    name: str
    glyph: str
    code: str | None  # Astrolog object code (`-R0 Sun`, `O_Sun`); None = derived here
    batch_label: str | None  # label at the start of `-5e -b0` rows
    kind: str  # luminary | planet | centaur | node | point | asteroid | part


OBJECTS: tuple[Obj, ...] = (
    Obj("sun", "Sun", "☉", "Sun", "Sun", "luminary"),
    Obj("moon", "Moon", "☽", "Moo", "Moon", "luminary"),
    Obj("mercury", "Mercury", "☿", "Mer", "Merc", "planet"),
    Obj("venus", "Venus", "♀", "Ven", "Venu", "planet"),
    Obj("mars", "Mars", "♂", "Mar", "Mars", "planet"),
    Obj("jupiter", "Jupiter", "♃", "Jup", "Jupi", "planet"),
    Obj("saturn", "Saturn", "♄", "Sat", "Satu", "planet"),
    Obj("uranus", "Uranus", "♅", "Ura", "Uran", "planet"),
    Obj("neptune", "Neptune", "♆", "Nep", "Nept", "planet"),
    Obj("pluto", "Pluto", "♇", "Plu", "Plut", "planet"),
    Obj("chiron", "Chiron", "⚷", "Chi", "Chir", "centaur"),
    Obj("north_node", "North Node", "☊", "Nor", "Nort", "node"),
    Obj("south_node", "South Node", "☋", None, None, "node"),
    Obj("lilith", "Lilith", "⚸", "Lil", "Lili", "point"),
    Obj("ceres", "Ceres", "⚳", "Cer", "Cere", "asteroid"),
    Obj("pallas", "Pallas", "⚴", "Pal", "Pall", "asteroid"),
    Obj("juno", "Juno", "⚵", "Jun", "Juno", "asteroid"),
    Obj("vesta", "Vesta", "⚶", "Ves", "Vest", "asteroid"),
    Obj("fortune", "Part of Fortune", "⊗", "For", "Fort", "part"),
    Obj("vertex", "Vertex", "Vx", "Ver", "Vert", "point"),
)
BY_KEY = {o.key: o for o in OBJECTS}
BY_BATCH_LABEL = {o.batch_label: o for o in OBJECTS if o.batch_label}

TRADITIONAL = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn")
MODERN = (*TRADITIONAL, "uranus", "neptune", "pluto")
DEFAULT_SET = (*MODERN, "chiron", "north_node", "south_node")


def resolve_objects(keys: list[str] | tuple[str, ...]) -> list[Obj]:
    """Validate keys, drop duplicates, keep registry order; the South Node needs the North Node."""
    wanted = {k.strip().lower() for k in keys}
    unknown = sorted(wanted - BY_KEY.keys())
    if unknown:
        raise AstroError(f"Unknown object(s): {', '.join(unknown)}.", fix="valid objects: " + ", ".join(BY_KEY))
    if "south_node" in wanted:
        wanted.add("north_node")
    return [o for o in OBJECTS if o.key in wanted]
