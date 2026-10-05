"""Shared helpers for views: labels, short names, the data a view needs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from astrolog_skills.analysis.aspects import Aspect, find_aspects
from astrolog_skills.analysis.harmonics import harmonic_chart
from astrolog_skills.analysis.patterns import HarmonicScore, Pattern, score_harmonic
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.zodiac import sign_index
from astrolog_skills.packs.loader import Pack
from astrolog_skills.render.theme import Theme

SHORT = {"north_node": "N Node", "south_node": "S Node", "fortune": "Fortune", "vertex": "Vertex"}
LETTERS = {
    "sun": "Su",
    "moon": "Mo",
    "mercury": "Me",
    "venus": "Ve",
    "mars": "Ma",
    "jupiter": "Ju",
    "saturn": "Sa",
    "uranus": "Ur",
    "neptune": "Ne",
    "pluto": "Pl",
    "chiron": "Ch",
    "north_node": "NN",
    "south_node": "SN",
    "lilith": "Li",
    "ceres": "Ce",
    "pallas": "Pa",
    "juno": "Jn",
    "vesta": "Vs",
    "fortune": "PF",
    "vertex": "Vx",
    "asc": "AC",
    "mc": "MC",
}


def short_name(key: str, name: str) -> str:
    return SHORT.get(key, name)


def symbol(key: str, glyph: str, theme: Theme) -> str:
    """Planet glyph, or two letters for fonts without astrology symbols. Angles are always letters."""
    if key in ("asc", "mc"):
        return LETTERS[key]
    return glyph if theme.glyphs and len(glyph) == 1 else LETTERS.get(key, glyph[:2])


def degree_text(lon: float) -> str:
    d = lon % 30
    total = int(d * 60 + 1e-7)
    return f"{total // 60:2d}°{total % 60:02d}′"


@dataclass
class ViewData:
    """Everything views draw from: the (harmonic) chart and the pack's results for it."""

    natal: ChartModel
    chart: ChartModel  # the chart shown (harmonic chart when harmonic > 1)
    pack: Pack
    harmonic: int
    aspects: list[Aspect]
    patterns: HarmonicScore
    transit: ChartModel | None = None
    transit_aspects: list[Any] | None = None
    transit_patterns: list[Pattern] | None = None  # with a transit chart: patterns that need a transit ("t:saturn")
    natal_orbs: bool = False  # harmonic charts: show orbs ÷ H (natal degrees) instead of as measured in that chart
    study: dict[str, Any] | None = (
        None  # doctrine and time lords (analysis/doctrine/explain.py), when the pack has them
    )

    @property
    def orb_scale(self) -> int:
        """Divide a harmonic-chart orb by this to display it (display.orbs)."""
        return self.harmonic if self.natal_orbs else 1

    def orb_note(self) -> str:
        if self.harmonic == 1:
            return ""
        if self.natal_orbs:
            return f"orbs in natal degrees (H{self.harmonic} orb ÷ {self.harmonic})"
        return f"orbs as measured in the H{self.harmonic} chart"

    @classmethod
    def build(
        cls,
        natal: ChartModel,
        pack: Pack,
        harmonic: int = 1,
        transit: ChartModel | None = None,
        natal_orbs: bool = False,
    ) -> ViewData:
        """`transit` (a chart for another moment) is shown alongside: in harmonic H both charts are multiplied by H
        (the harmonic transit chart) and read with the pack's transit aspects and orbs, in that chart's degrees."""
        from astrolog_skills.analysis.transits import transit_aspects

        shown = harmonic_chart(natal, harmonic)
        lons = {p.key: p.lon for p in natal.points}
        with_transit = harmonic_chart(transit, harmonic) if transit is not None else None
        found = transit_aspects(shown, with_transit, pack.method) if with_transit is not None else None
        joining = None
        if transit is not None:
            from astrolog_skills.analysis.transit_timeline import joined

            bodies = set(pack.method.pattern_bodies)
            natal_lons = {p.key: p.lon for p in natal.points if p.key in bodies}
            moving = {p.key: p.lon for p in transit.points if p.key in bodies}
            joining = joined(natal_lons, moving, harmonic, pack.method)
        return cls(
            natal,
            shown,
            pack,
            harmonic,
            find_aspects(natal, pack.method, harmonic),
            score_harmonic(lons, harmonic, pack.method),
            with_transit,
            found,
            joining,
            natal_orbs,
        )


def element_index(lon: float) -> int:
    return sign_index(lon) % 4
