"""Compare a pack's lots with Astrolog's own Arabic parts (`-P`) on a reference chart, matched by formula."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from astrolog_skills.analysis.doctrine.lots import LotResolver
from astrolog_skills.analysis.doctrine.rules import Doctrine, Problem
from astrolog_skills.analysis.doctrine.sect import above_horizon
from astrolog_skills.engine import profile as profiles
from astrolog_skills.engine.cast import cast
from astrolog_skills.engine.moment import Moment
from astrolog_skills.engine.raw import raw
from astrolog_skills.engine.zodiac import SIGN_ABBR
from astrolog_skills.errors import AstroError

REFERENCE = Moment("1879-03-14", "11:30", "LMT", 48.4, 10.0, "reference chart")
TOLERANCE = 0.02  # Astrolog prints whole arcminutes
CODES = {
    "Sun": "sun",
    "Moo": "moon",
    "Mer": "mercury",
    "Ven": "venus",
    "Mar": "mars",
    "Jup": "jupiter",
    "Sat": "saturn",
    "For": "lot:fortune",
    "Spi": "lot:spirit",
}
_PART = re.compile(
    r"^\s*\d+:\s+(?P<name>.+?)\s+(?P<deg>\d{1,2})(?P<sign>[A-Z][a-z]{2})(?P<min>\d{2})\s+\[[^\]]*\]\s+"
    r"\(Asc\s+-\s+(?P<a>\S+)\s+(?P<ra>R?)\s*\+\s+(?P<b>\S+)\s+(?P<rb>R?)\s*(?P<flip>[YN])\)"
)


def astrolog_parts(text: str) -> dict[tuple[str, str], tuple[str, float]]:
    """(from, to) → (Astrolog's name, longitude) for parts measured between planets, Fortune or Spirit."""
    out: dict[tuple[str, str], tuple[str, float]] = {}
    for line in text.splitlines():
        m = _PART.match(line)
        if not m or m["ra"] or m["rb"] or m["a"] not in CODES or m["b"] not in CODES or m["sign"] not in SIGN_ABBR:
            continue
        lon = SIGN_ABBR.index(m["sign"]) * 30 + int(m["deg"]) + int(m["min"]) / 60
        out.setdefault((CODES[m["a"]], CODES[m["b"]]), (m["name"].strip(), lon))
    return out


@dataclass
class CrossCheck:
    checked: list[str] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)


def lots_against_astrolog(doctrine: Doctrine) -> CrossCheck:
    result = CrossCheck()
    try:
        profile = profiles.active()
        chart = cast(REFERENCE, profile)
        _, done = raw(["-P"], REFERENCE, profile)
    except AstroError as err:
        result.problems.append(Problem("warn", "lots", f"Astrolog cross-check skipped: {err.message}"))
        return result
    parts = astrolog_parts(done.stdout)
    if not parts:
        result.problems.append(Problem("warn", "lots", "Astrolog -P gave no parts to compare; cross-check skipped"))
        return result
    day = above_horizon(chart.point("sun").lon, chart.angles["asc"])
    resolver = LotResolver(chart, doctrine, day)
    for name in doctrine.lots:
        try:
            lot = resolver.lot(name)
        except AstroError as err:
            result.problems.append(Problem("warn", f"lots.{name}", f"not cross-checked: {err.message}"))
            continue
        rule = doctrine.lots[name].effective()
        if lot.fallback or lot.project_from != "asc" or rule.distance != "zodiacal" or lot.points not in parts:
            continue
        theirs, at = parts[lot.points]
        diff = abs((lot.lon - at + 180) % 360 - 180)
        result.checked.append(name)
        if diff > TOLERANCE:
            result.problems.append(
                Problem(
                    "error",
                    f"lots.{name}",
                    f"differs from Astrolog's {theirs!r} by {diff:.2f}° on the reference chart",
                    "re-check the formula and its night reversal",
                )
            )
    return result
