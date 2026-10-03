"""Settings profiles: what the user picks ("use my Vedic profile") → the Astrolog switches pinned on every call.

Pinning matters: Astrolog reads `astrolog.as` next to its binary on every run, and a user's settings there
(sidereal zodiac, another house system, a harmonic chart…) would otherwise silently change every result.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from astrolog_skills import config
from astrolog_skills.engine.houses import resolve_house_system
from astrolog_skills.engine.objects import Obj, resolve_objects
from astrolog_skills.engine.zodiac import resolve_ayanamsa
from astrolog_skills.errors import AstroError
from astrolog_skills.paths import data_dir, plugin_root

# Settings that would change positions if astrolog.as switched them on — always forced to the neutral value.
NEUTRAL_PINS = [
    "=b",  # use ephemeris files when present
    "_YT",
    "_YV",
    "_h",
    "_sr",
    "_Yh",  # apparent, geocentric, ecliptic longitudes
    "_p",
    "_1",
    "_Ys",
    "_c3",  # no progression, no solar chart, no alt. sidereal, 2D houses
    "-x",
    "1",  # no harmonic chart (harmonics are computed in Python)
    "-Yz",
    "0",
    "-YzO",
    "0",
    "-YzC",
    "0",  # no time or position offsets
]


@dataclass(frozen=True)
class Profile:
    name: str
    description: str = ""
    zodiac: str = "tropical"  # tropical | sidereal
    ayanamsa: str = ""  # sidereal only
    houses: str = "placidus"
    node: str = "true"  # true | mean
    objects: tuple[str, ...] = ()
    pack: str = "psychological"
    theme: str = "default"
    source: str = field(default="", compare=False)  # file it came from

    # derived, validated views ---------------------------------------------------
    @property
    def object_list(self) -> list[Obj]:
        return resolve_objects(self.objects)

    @property
    def house_system(self) -> tuple[str, str, int]:
        return resolve_house_system(self.houses)

    @property
    def sidereal(self) -> bool:
        return self.zodiac == "sidereal"

    def ayanamsa_info(self) -> tuple[str, float, str] | None:
        return resolve_ayanamsa(self.ayanamsa) if self.sidereal else None

    def summary(self) -> str:
        zodiac = f"sidereal ({self.ayanamsa_info()[2]})" if self.sidereal else "tropical"  # type: ignore[index]
        return f"{zodiac} · {self.house_system[1]} houses · {self.node} node"

    def to_dict(self) -> dict[str, Any]:
        info = self.ayanamsa_info()
        return {
            "name": self.name,
            "description": self.description,
            "zodiac": self.zodiac,
            "ayanamsa": info[2] if info else None,
            "ayanamsa_offset": info[1] if info else None,
            "houses": self.house_system[1],
            "node": self.node,
            "objects": [o.key for o in self.object_list],
            "pack": self.pack,
            "theme": self.theme,
            "source": self.source,
        }


@dataclass(frozen=True)
class ChartSettings:
    """Part of a profile, laid over one: a pack's [chart], your saved adjustments for a pack, or a command's flags.

    `points`: plain keys replace the object list; `+key` adds one, `-key` drops one.
    """

    zodiac: str | None = None  # tropical | sidereal
    ayanamsa: str | None = None
    houses: str | None = None
    node: str | None = None
    points: tuple[str, ...] = ()
    cite: str = ""

    def __bool__(self) -> bool:
        return any((self.zodiac, self.ayanamsa, self.houses, self.node, self.points))

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {k: v for k, v in (("zodiac", self.zodiac), ("ayanamsa", self.ayanamsa),
                               ("houses", self.houses), ("node", self.node)) if v}  # fmt: skip
        if self.points:
            out["points"] = list(self.points)
        return out


def chart_settings(
    zodiac: str | None = None,
    houses: str | None = None,
    node: str | None = None,
    points: str | list[str] | tuple[str, ...] | None = None,
    ayanamsa: str | None = None,
    cite: str = "",
    where: str = "chart settings",
) -> ChartSettings:
    """Checked settings. `zodiac` may name an ayanamsa ("lahiri"), which means sidereal with it."""
    z = (zodiac or "").strip().lower() or None
    if z and z not in ("tropical", "sidereal"):
        z, ayanamsa = "sidereal", zodiac
    if ayanamsa and z is None:  # an ayanamsa on its own means sidereal
        z = "sidereal"
    if z == "sidereal" and not ayanamsa:
        raise AstroError(f"{where}: a sidereal zodiac needs an ayanamsa.", fix='e.g. zodiac = "lahiri"')
    if isinstance(points, str):
        points = [t for t in points.replace(" ", ",").split(",") if t]
    tokens = tuple(str(t).strip().lower() for t in (points or ()))
    n = (node or "").strip().lower() or None
    try:
        if ayanamsa and z != "tropical":
            resolve_ayanamsa(ayanamsa)
        if houses:
            resolve_house_system(houses)
        resolve_objects([t.lstrip("+-") for t in tokens])
    except AstroError as err:
        raise AstroError(f"{where}: {err.message}", fix=err.fix) from err
    if n and n not in ("true", "mean"):
        raise AstroError(f"{where}: node must be 'true' or 'mean', not '{n}'.")
    return ChartSettings(z, str(ayanamsa) if ayanamsa and z != "tropical" else None, houses, n, tokens, cite)


def parse_chart_settings(raw: dict[str, Any] | None, where: str) -> ChartSettings | None:
    """A pack's [chart] table."""
    if not raw:
        return None
    unknown = sorted(set(raw) - {"zodiac", "ayanamsa", "houses", "node", "objects", "cite"})
    if unknown:
        raise AstroError(f"{where}: unknown [chart] key(s) {', '.join(unknown)}.",
                         fix="known: zodiac, ayanamsa, houses, node, objects, cite")  # fmt: skip
    return chart_settings(
        raw.get("zodiac"), raw.get("houses"), raw.get("node"), raw.get("objects"), raw.get("ayanamsa"),
        str(raw.get("cite", "")), f"{where} [chart]",
    )  # fmt: skip


def _points(current: tuple[str, ...], tokens: tuple[str, ...]) -> tuple[str, ...]:
    plain = [t for t in tokens if t[:1] not in "+-"]
    out = list(plain) if plain else list(current)
    for t in tokens:
        if t.startswith("+") and t[1:] not in out:
            out.append(t[1:])
        elif t.startswith("-") and t[1:] in out:
            out.remove(t[1:])
    return tuple(out)


def overlay(p: Profile, s: ChartSettings | None, label: str) -> Profile:
    """The profile with these settings laid over it, named after the layers ("default + hellenistic")."""
    if not s:
        return p
    sidereal = s.zodiac == "sidereal" or (s.zodiac is None and p.sidereal)
    changed = replace(
        p,
        name=f"{p.name} + {label}",
        zodiac=s.zodiac or p.zodiac,
        ayanamsa=(s.ayanamsa or p.ayanamsa) if sidereal else "",
        houses=s.houses or p.houses,
        node=s.node or p.node,
        objects=_points(p.objects, s.points),
    )
    validate(changed)
    return changed


def builtin_dir() -> Path:
    return plugin_root() / "profiles"


def user_dir() -> Path:
    return data_dir() / "profiles"


def _from_toml(path: Path) -> Profile:
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as err:
        raise AstroError(f"Can't read profile {path}: {err}", fix=f"fix or delete {path}") from err
    zodiac = raw.get("zodiac", {})
    points = raw.get("points", {})
    links = raw.get("links", {})
    profile = Profile(
        name=str(raw.get("name") or path.stem),
        description=str(raw.get("description", "")),
        zodiac=str(zodiac.get("type", "tropical")).lower(),
        ayanamsa=str(zodiac.get("ayanamsa", "")),
        houses=str(raw.get("houses", {}).get("system", "placidus")),
        node=str(points.get("node", "true")).lower(),
        objects=tuple(points.get("objects", ())),
        pack=str(links.get("pack", "psychological")),
        theme=str(links.get("theme", "default")),
        source=str(path),
    )
    validate(profile)
    return profile


def validate(p: Profile) -> None:
    where = f"profile '{p.name}' ({p.source or 'in memory'})"
    if p.zodiac not in ("tropical", "sidereal"):
        raise AstroError(f"{where}: zodiac.type must be 'tropical' or 'sidereal', not '{p.zodiac}'.")
    if p.sidereal and not p.ayanamsa:
        raise AstroError(f"{where}: a sidereal zodiac needs zodiac.ayanamsa.", fix='e.g. ayanamsa = "lahiri"')
    if p.sidereal:
        try:
            resolve_ayanamsa(p.ayanamsa)
        except AstroError as err:
            raise AstroError(f"{where}: {err.message}", fix=err.fix) from err
    if p.node not in ("true", "mean"):
        raise AstroError(f"{where}: points.node must be 'true' or 'mean', not '{p.node}'.")
    if not p.objects:
        raise AstroError(f"{where}: points.objects is empty.", fix='e.g. objects = ["sun", "moon", …]')
    for check in (lambda: resolve_house_system(p.houses), lambda: resolve_objects(p.objects)):
        try:
            check()
        except AstroError as err:
            raise AstroError(f"{where}: {err.message}", fix=err.fix) from err


def list_profiles() -> dict[str, Path]:
    """name → file; a user profile with the same name replaces the built-in one."""
    found: dict[str, Path] = {}
    for directory in (builtin_dir(), user_dir()):
        if directory.is_dir():
            for path in sorted(directory.glob("*.toml")):
                found[path.stem] = path
    return found


def load(name: str) -> Profile:
    available = list_profiles()
    if name not in available:
        raise AstroError(f"No profile called '{name}'.", fix="available: " + ", ".join(available))
    return _from_toml(available[name])


def active_name() -> str:
    return str(config.load()["defaults"]["profile"] or "default")


def active() -> Profile:
    return load(active_name())


def create(name: str, from_: str = "default") -> Path:
    if not name.replace("-", "").replace("_", "").isalnum():
        raise AstroError(f"'{name}' isn't a good profile name.", fix="use letters, digits, - and _")
    target = user_dir() / f"{name}.toml"
    if target.exists():
        raise AstroError(f"You already have a profile called '{name}'.", fix=f"edit it: {target}")
    source = list_profiles().get(from_)
    if not source:
        raise AstroError(f"No profile called '{from_}' to copy from.")
    target.parent.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8")
    lines = [f'name = "{name}"' if line.startswith("name =") else line for line in text.splitlines()]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _from_toml(target)  # validate the copy
    return target


def pins(p: Profile, extra_codes: tuple[str, ...] = ()) -> list[str]:
    """Every switch that makes Astrolog compute exactly what this profile says — used on every call.

    `extra_codes` switches on more Astrolog objects than the profile lists (e.g. "Asc", "Mid" for batch rows).
    """
    zodiac = ["-s", resolve_ayanamsa(p.ayanamsa)[0]] if p.sidereal else ["_s"]
    codes = [o.code for o in p.object_list if o.code] + list(extra_codes)
    return [
        *NEUTRAL_PINS,
        *zodiac,
        "-c",
        str(p.house_system[2]),
        "=Yn" if p.node == "true" else "_Yn",
        "-R0",
        *codes,
    ]
