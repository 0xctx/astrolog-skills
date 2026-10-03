"""Every aspect the toolkit knows, with its harmonic: an aspect of angle k·360/H belongs to harmonic H."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AspectType:
    key: str
    name: str
    angle: float
    harmonic: int
    glyph: str
    letters: str
    family: str  # conjunction | hard | soft | green | pink | quintile | septile | novile | decile


def _a(key: str, name: str, k: int, h: int, glyph: str, letters: str, family: str) -> AspectType:
    return AspectType(key, name, round(360 * k / h, 6), h, glyph, letters, family)


ASPECTS: tuple[AspectType, ...] = (
    _a("conjunction", "conjunction", 0, 1, "☌", "Cj", "conjunction"),
    _a("opposition", "opposition", 1, 2, "☍", "Op", "hard"),
    _a("trine", "trine", 1, 3, "△", "Tr", "soft"),
    _a("square", "square", 1, 4, "□", "Sq", "hard"),
    _a("quintile", "quintile", 1, 5, "Q", "Q", "quintile"),
    _a("biquintile", "biquintile", 2, 5, "bQ", "bQ", "quintile"),
    _a("sextile", "sextile", 1, 6, "✶", "Sx", "soft"),
    _a("septile", "septile", 1, 7, "S", "S", "septile"),
    _a("biseptile", "biseptile", 2, 7, "bS", "bS", "septile"),
    _a("triseptile", "triseptile", 3, 7, "tS", "tS", "septile"),
    _a("semisquare", "semisquare", 1, 8, "∠", "SQ", "pink"),
    _a("sesquiquadrate", "sesquiquadrate", 3, 8, "⚼", "Ses", "pink"),
    _a("novile", "novile", 1, 9, "N", "N", "novile"),
    _a("binovile", "binovile", 2, 9, "bN", "bN", "novile"),
    _a("quadnovile", "quadnovile", 4, 9, "qN", "qN", "novile"),
    _a("decile", "decile", 1, 10, "D", "D", "decile"),
    _a("tridecile", "tridecile", 3, 10, "tD", "tD", "decile"),
    _a("semisextile", "semisextile", 1, 12, "⚺", "SS", "green"),
    _a("quincunx", "quincunx", 5, 12, "⚻", "Qx", "green"),
)
BY_KEY = {a.key: a for a in ASPECTS}
MAJOR = ("conjunction", "opposition", "trine", "square", "sextile")
