"""Harmonic charts: each position multiplied by H (verified identical to Astrolog's `-x H`)."""

from __future__ import annotations

import copy

from astrolog_skills.engine.model import ChartModel, Point
from astrolog_skills.errors import AstroError


def harmonic_lon(lon: float, h: int) -> float:
    return (lon * h) % 360.0


def harmonic_chart(chart: ChartModel, h: int) -> ChartModel:
    """A copy of the chart with every point (and the angles) in harmonic H. Houses don't carry over."""
    if h < 1:
        raise AstroError(f"Harmonic must be 1 or more, not {h}.")
    if h == 1:
        return chart
    out = copy.deepcopy(chart)
    out.points = [Point(p.key, p.name, p.glyph, harmonic_lon(p.lon, h), p.lat, p.speed * h, None) for p in chart.points]
    out.angles = {k: round(harmonic_lon(v, h), 6) for k, v in chart.angles.items()}
    out.cusps = []
    out.harmonic = h
    return out
