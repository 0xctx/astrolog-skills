"""Zodiacal releasing: periods through the signs from a lot, on up to four levels, with the source's flags."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any

from astrolog_skills.analysis.doctrine.configurations import signs_apart
from astrolog_skills.analysis.doctrine.lots import compute_lots
from astrolog_skills.analysis.doctrine.rules import SEVEN, SIGN_KEYS, Doctrine, Releasing, SectRules
from astrolog_skills.analysis.doctrine.sect import above_horizon
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.zodiac import SIGNS, sign_index
from astrolog_skills.errors import AstroError


@dataclass(frozen=True)
class Period:
    level: int
    sign: str
    begins: str
    ends: str
    lord: str = ""
    from_fortune: int = 0  # place of the sign counted from Fortune's sign
    peak: int = 0  # 1 = the strongest peak in the pack's ranking; 0 = not a peak
    triad: str = ""  # relative to the Fortune angles: "beginning", "angle", "end"
    loosing: bool = False  # the loosing of the bond: the jump to the opposite sign
    completion: bool = False  # back at the starting sign after a loosing
    in_sign: list[str] = field(default_factory=list)  # natal planets in the sign
    superior_square: list[str] = field(default_factory=list)  # planets overcoming the sign by square
    opposite: list[str] = field(default_factory=list)
    inferior_square: list[str] = field(default_factory=list)
    benefic_angle: bool = False  # the sign is in or square/opposite the benefic of the sect
    malefic_angle: bool = False  # … the malefic contrary to the sect
    holds_ruler: bool = False  # a subperiod in the sign that holds the ruler of the period above it

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Releaser:
    """Everything a releasing run needs from the chart."""

    rules: Releasing
    lot: str
    start_sign: int
    birth: datetime
    fortune_sign: int
    planets: dict[str, int]  # planet → sign index
    domicile: dict[str, str]
    benefic: str
    malefic: str
    shifted: bool = False  # Spirit moved on from Fortune's sign
    _cache: dict[int, int] = field(default_factory=dict)

    def unit_days(self, level: int) -> float:
        return float(self.rules.year_days) / 12.0 ** (level - 1)

    def length(self, sign: int, level: int) -> float:
        return self.rules.periods[SIGN_KEYS[sign]] * self.unit_days(level)

    def describe(
        self,
        level: int,
        sign: int,
        begins: datetime,
        ends: datetime,
        loosing: bool,
        completion: bool,
        parent: int | None = None,
    ) -> Period:
        place = (sign - self.fortune_sign) % 12 + 1
        peaks = self.rules.peaks
        triad = "angle" if place in (1, 4, 7, 10) else "end" if place in (2, 5, 8, 11) else "beginning"

        def by(apart: int) -> list[str]:
            return [k for k, s in self.planets.items() if (sign - s) % 12 == apart]

        def angular_to(planet: str) -> bool:
            return bool(planet) and signs_apart(self.planets[planet] * 30.0, sign * 30.0) in (0, 3, 6, 9)

        return Period(
            level,
            SIGNS[sign],
            begins.date().isoformat(),
            ends.date().isoformat(),
            self.domicile.get(SIGN_KEYS[sign], ""),
            place,
            peaks.index(place) + 1 if place in peaks else 0,
            triad,
            loosing,
            completion,
            by(0),
            by(3),  # a planet three signs earlier overcomes the sign by square
            by(6),
            by(9),
            angular_to(self.benefic),
            angular_to(self.malefic),
            self.rules.ruler_sign
            and parent is not None
            and self.planets.get(self.domicile.get(SIGN_KEYS[parent], ""), -1) == sign,
        )

    def subperiods(
        self, level: int, parent: int, begins: datetime, ends: datetime
    ) -> Iterator[tuple[int, datetime, datetime, bool, bool]]:
        """(sign, begins, ends, loosing, completion) for the subperiods of a period in `parent`."""
        sign, t = parent, begins
        loosed = False
        first = True
        while t < ends:
            loosing = completion = False
            if not first and sign == parent:
                if self.rules.loosing_of_bond and not loosed:
                    sign, loosed, loosing = (parent + 6) % 12, True, True
                elif loosed:
                    completion = True
            end = min(t + timedelta(days=self.length(sign, level)), ends)
            yield sign, t, end, loosing, completion
            t, first = end, False
            sign = (sign + 1) % 12

    def periods(self, until: datetime, levels: int | None = None, since: datetime | None = None) -> list[Period]:
        depth = min(levels or self.rules.levels, 4)
        out: list[Period] = []

        def walk(
            level: int, sign: int, begins: datetime, ends: datetime, loosing: bool, completion: bool, parent: int | None
        ) -> None:
            if since is None or ends > since:
                out.append(self.describe(level, sign, begins, ends, loosing, completion, parent))
                if level < depth:
                    for s, b, e, lo, co in self.subperiods(level + 1, sign, begins, ends):
                        if b >= until:
                            break
                        walk(level + 1, s, b, e, lo, co, sign)

        sign, t = self.start_sign, self.birth
        while t < until:
            end = t + timedelta(days=self.length(sign, 1))
            walk(1, sign, t, end, False, False, None)
            t, sign = end, (sign + 1) % 12
        return out


def releaser(chart: ChartModel, doctrine: Doctrine, birth: datetime, lot: str) -> Releaser:
    rules = doctrine.releasing
    if rules is None or len(rules.periods) != 12:
        raise AstroError("The pack has no [timing.releasing] periods for the twelve signs.")
    day = above_horizon(chart.point("sun").lon, chart.angles["asc"])
    lots = compute_lots(chart, doctrine, day)
    for needed in (lot, "fortune"):
        if needed not in lots:
            raise AstroError(f"The pack has no lot '{needed}' to release from.", fix="lots: " + ", ".join(lots))
    start = sign_index(lots[lot].lon)
    fortune = sign_index(lots["fortune"].lon)
    shifted = False
    if rules.same_sign_shift and lot == "spirit" and start == fortune:
        start, shifted = (start + 1) % 12, True
    sect = doctrine.sect or SectRules()
    members = sect.diurnal if day else sect.nocturnal
    benefic = next((b for b in sect.benefics if b in members), "")
    malefic = next((m for m in sect.malefics if m not in members), "")
    return Releaser(
        rules,
        lot,
        start,
        birth,
        fortune,
        {k: sign_index(chart.point(k).lon) for k in SEVEN},
        doctrine.dignities.domicile if doctrine.dignities else {},
        benefic,
        malefic,
        shifted,
    )


def current(periods: list[Period], on: str) -> list[Period]:
    """The period on each level that contains a date (YYYY-MM-DD)."""
    return [p for p in periods if p.begins <= on < p.ends]
