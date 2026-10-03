"""Lots: the distance between two points, projected from a third — every formula shape a pack can write."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from astrolog_skills.analysis.doctrine.phase import separation
from astrolog_skills.analysis.doctrine.places import place_of
from astrolog_skills.analysis.doctrine.rules import SIGN_KEYS, Doctrine, LotRule, Phase
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.zodiac import sign_index, sign_of
from astrolog_skills.errors import AstroError


@dataclass(frozen=True)
class Lot:
    name: str
    lon: float
    sign: str
    place: int
    lord: str  # domicile lord of its sign ("" without a domicile table)
    points: tuple[str, str]  # measured from the first to the second
    project_from: str
    reversed: bool  # night reversal applied
    version: str = ""
    fallback: bool = False  # the fallback formula was used
    cite: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LotResolver:
    def __init__(self, chart: ChartModel, doctrine: Doctrine, day: bool) -> None:
        self.chart, self.doctrine, self.day = chart, doctrine, day
        self.asc = chart.angles["asc"]
        self.lots: dict[str, Lot] = {}
        self._busy: set[str] = set()

    def point(self, name: str) -> float:
        if name.startswith("lot:"):
            return self.lot(name[4:]).lon
        if name.startswith("sign:"):
            return SIGN_KEYS.index(name[5:]) * 30.0
        if name.startswith("ruler:place:"):
            sign = SIGN_KEYS[(sign_index(self.asc) + int(name.rsplit(":", 1)[1]) - 1) % 12]
            domicile = self.doctrine.dignities.domicile if self.doctrine.dignities else {}
            if sign not in domicile:
                raise AstroError(f"{name} needs a domicile table in [dignities].")
            return self.chart.point(domicile[sign]).lon
        if name.startswith("place:"):
            return ((sign_index(self.asc) + int(name.split(":")[1]) - 1) % 12) * 30.0
        if name in ("asc", "mc"):
            return self.chart.angles[name]
        return self.chart.point(name).lon

    def _fallback_applies(self, when: str) -> bool:
        planet = when.removesuffix("_under_beams")
        orb = (self.doctrine.phase or Phase()).under_beams
        return planet != "sun" and separation(self.chart.point(planet).lon, self.chart.point("sun").lon) <= orb

    def lot(self, name: str) -> Lot:
        if name in self.lots:
            return self.lots[name]
        if name in self._busy:
            raise AstroError(f"Lot '{name}' depends on itself.")
        if name not in self.doctrine.lots:
            raise AstroError(f"No lot called '{name}' in this pack.")
        self._busy.add(name)
        try:
            return self._compute(name)
        finally:
            self._busy.discard(name)

    def _compute(self, name: str) -> Lot:
        top = self.doctrine.lots[name]
        rule: LotRule = top.effective(str(self.chart.moment.get("sex", "")))
        if top.by_sex and not (rule.points or rule.day or rule.night):
            raise AstroError(f"Lot '{name}' depends on the native's sex, which isn't recorded for this chart.",
                             fix="astro chart add NAME … --sex male|female")  # fmt: skip
        used_fallback = bool(rule.fallback and self._fallback_applies(rule.fallback.when))
        if used_fallback and rule.fallback:
            pts, reverse = rule.fallback.points, rule.fallback.reverse
        elif rule.day or rule.night:
            pts, reverse = (rule.day or rule.night) if self.day else (rule.night or rule.day), False
        else:
            pts, reverse = rule.points, rule.reverse
        a, b = pts
        flipped = reverse and not self.day
        if flipped:
            a, b = b, a
        d = (self.point(b) - self.point(a)) % 360
        if rule.distance == "shortest" and d > 180:
            d = 360 - d
        lon = (self.point(rule.project_from) + d) % 360
        domicile = self.doctrine.dignities.domicile if self.doctrine.dignities else {}
        sign = SIGN_KEYS[sign_index(lon)]
        result = Lot(
            name,
            round(lon, 6),
            sign_of(lon),
            place_of(lon, self.asc),
            domicile.get(sign, ""),
            (a, b),
            rule.project_from,
            flipped,
            top.version,
            used_fallback,
            rule.cite or top.cite,
        )
        self.lots[name] = result
        return result


def compute_lots(chart: ChartModel, doctrine: Doctrine, day: bool) -> dict[str, Lot]:
    """Every lot the pack defines; one that needs the native's sex (and any built on it) is left out when the chart
    doesn't record it."""
    r = LotResolver(chart, doctrine, day)
    for name in doctrine.lots:
        try:
            r.lot(name)
        except AstroError as err:
            if "native's sex" not in err.message:
                raise
    return {name: r.lots[name] for name in doctrine.lots if name in r.lots}
