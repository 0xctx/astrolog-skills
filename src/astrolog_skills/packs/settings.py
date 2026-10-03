"""Which chart settings a command uses, and whether readings cite their sources.

Layers, lowest first: the active profile → the pack's [chart] → your saved adjustments for that pack
(`astro packs settings`) → this command's flags (`astro --houses … --zodiac … --points …`). Naming a profile with
`--profile` means exactly that profile: the pack's settings and your saved ones are skipped, the flags still apply.
"""

from __future__ import annotations

from typing import Any

from astrolog_skills import config
from astrolog_skills.engine import profile as profiles
from astrolog_skills.engine.objects import TRADITIONAL
from astrolog_skills.engine.profile import ChartSettings, Profile, chart_settings, overlay
from astrolog_skills.errors import AstroError
from astrolog_skills.packs import loader
from astrolog_skills.packs.loader import Pack

_flags = ChartSettings()  # this command's global flags (set once by cli/app.py)
_cite = False


def set_flags(flags: ChartSettings, cite: bool = False) -> None:
    global _flags, _cite
    _flags, _cite = flags, cite


def citations() -> bool:
    """Readings cite source pages only when asked: `--cite`, or `readings.citations = true` in the config."""
    return _cite or bool(config.load().get("readings", {}).get("citations", False))


def saved(pack: str) -> ChartSettings:
    return saved_from(config.load().get("pack_settings", {}).get(pack, {}), pack)


def saved_from(raw: dict[str, Any], pack: str) -> ChartSettings:
    return chart_settings(
        raw.get("zodiac"), raw.get("houses"), raw.get("node"), raw.get("points"), raw.get("ayanamsa"),
        where=f"your saved settings for '{pack}' (config.toml)",
    )  # fmt: skip


def save(pack: str, s: ChartSettings | None) -> None:
    """Store (or with None, forget) your adjustments for a pack."""
    cfg = config.load()
    table: dict[str, Any] = cfg.setdefault("pack_settings", {})
    if s:
        table[pack] = s.to_dict()
    else:
        table.pop(pack, None)
    config.save(cfg)


def chart_profile(profile: str | None = None, pack: Pack | None = None) -> Profile:
    """The settings to cast with: see the module docstring for the layers."""
    if profile:
        prof = profiles.load(profile)
    else:
        prof = profiles.active()
        if pack is not None:
            prof = overlay(prof, pack.method.chart, pack.name)
            prof = overlay(prof, saved(pack.name), "your settings")
    prof = overlay(prof, _flags, "this command")
    if pack is not None and pack.method.doctrine is not None:
        missing = [k for k in TRADITIONAL if k not in prof.objects]
        if missing:
            raise AstroError(
                f"Pack '{pack.name}' needs the seven planets; these settings leave out {', '.join(missing)}.",
                fix="add them back, e.g. --points +" + ",+".join(missing),
            )
    return prof


def with_midpoints(pack: Pack, how: str | None) -> Pack:
    """The pack with its midpoint method set for this command (--midpoints old|new)."""
    if not how:
        return pack
    if how not in ("old", "new"):
        raise AstroError(f"--midpoints must be old or new, not '{how}'.")
    from dataclasses import replace

    return replace(pack, method=replace(pack.method, midpoint_method=how))


def resolve(profile: str | None, pack: str | None) -> tuple[Profile, Pack]:
    """The pack (named, or the profile's own) and the settings to cast with."""
    tradition = loader.load(pack or (profiles.load(profile) if profile else profiles.active()).pack)
    return chart_profile(profile, tradition), tradition
