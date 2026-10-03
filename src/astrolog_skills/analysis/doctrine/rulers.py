"""Rulers of the places and lots, and the checklist for judging a place or lot through its sign and its lord."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from astrolog_skills.analysis.doctrine.conditions import Condition
from astrolog_skills.analysis.doctrine.configurations import sign_aspect
from astrolog_skills.analysis.doctrine.dignities import planet_dignities
from astrolog_skills.analysis.doctrine.phase import separation
from astrolog_skills.analysis.doctrine.places import place_of
from astrolog_skills.analysis.doctrine.rules import SEVEN, SIGN_KEYS, Doctrine, Phase, SectRules
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.zodiac import SIGNS, sign_index


@dataclass(frozen=True)
class Topic:
    """A place or a lot, judged through its sign and its domicile lord."""

    name: str  # "place 1" … or "lot:fortune"
    sign: str
    place: int
    lord: str
    lord_place: int | None
    configured: list[str] = field(default_factory=list)  # planets configured to the sign (by sign, incl. copresent)
    checklist: list[str] = field(default_factory=list)  # tokens of the lot checklist that hold

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def topic(
    name: str,
    lon: float,
    chart: ChartModel,
    doctrine: Doctrine,
    day: bool,
    found: list[Condition],
) -> Topic:
    sect = doctrine.sect or SectRules()
    asc = chart.angles["asc"]
    lons = {k: chart.point(k).lon for k in SEVEN}
    place = place_of(lon, asc)
    domicile = doctrine.dignities.domicile if doctrine.dignities else {}
    lord = domicile.get(SIGN_KEYS[sign_index(lon)], "")
    tokens: list[str] = []
    places = doctrine.places
    if places and place in places.good:
        tokens.append("lot_good_place")
    if places and place in places.bad:
        tokens.append("lot_bad_place")
    configured = [k for k, v in lons.items() if sign_aspect(v, lon) is not None]
    for group, word in ((sect.benefics, "benefic"), (sect.malefics, "malefic")):
        if any(sign_aspect(lons[k], lon) == "conjunction" for k in group):
            tokens.append(f"{word}_copresent")
        if any(sign_aspect(lons[k], lon) not in (None, "conjunction") for k in group):
            tokens.append(f"{word}_configured")
        if all(sign_aspect(lons[k], lon) is None for k in group):  # none of them sees the lot
            tokens.append(f"{word}_in_aversion")
    lord_place = None
    if lord:
        lord_lon = lons[lord]
        lord_place = place_of(lord_lon, asc)
        if lord in sect.benefics:
            tokens.append("lord_benefic")
        if lord in sect.malefics:
            tokens.append("lord_malefic")
        if doctrine.dignities:
            dig = planet_dignities(lord, lord_lon, doctrine.dignities, day)
            if dig.domicile or dig.exaltation:
                tokens.append("lord_well_placed_by_sign")
            if dig.adversity or dig.depression:
                tokens.append("lord_poorly_placed_by_sign")
        if places and lord_place in places.good:
            tokens.append("lord_good_place")
        if places and lord_place in places.bad:
            tokens.append("lord_bad_place")
        tokens.append("lord_configured" if sign_aspect(lord_lon, lon) is not None else "lord_not_configured")
        for group, word in ((sect.benefics, "benefics"), (sect.malefics, "malefics")):
            others = [k for k in group if k != lord]
            if any(sign_aspect(lons[k], lord_lon) is not None for k in others):
                tokens.append(f"lord_configured_to_{word}")
            elif others:
                tokens.append(f"lord_in_aversion_to_{word}")
        effects = {c.effect for c in found if c.target == lord}
        tokens.append("lord_bonified" if "bonify" in effects else "lord_not_bonified")
        tokens.append("lord_maltreated" if "maltreat" in effects else "lord_not_maltreated")
        orb = (doctrine.phase or Phase()).under_beams
        beams = lord != "sun" and separation(lord_lon, lons["sun"]) <= orb
        tokens.append("lord_under_beams" if beams else "lord_not_under_beams")
    return Topic(name, SIGNS[sign_index(lon)], place, lord, lord_place, configured, tokens)


def places(chart: ChartModel, doctrine: Doctrine, day: bool, found: list[Condition]) -> list[Topic]:
    first = sign_index(chart.angles["asc"])
    return [topic(f"place {n}", ((first + n - 1) % 12) * 30.0 + 15, chart, doctrine, day, found) for n in range(1, 13)]
