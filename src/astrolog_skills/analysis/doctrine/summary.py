"""Each planet's findings as tokens, sorted into the good and bad testimonies the pack's [scoring] names."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from astrolog_skills.analysis.doctrine.conditions import Condition
from astrolog_skills.analysis.doctrine.rules import Scoring

if TYPE_CHECKING:
    from astrolog_skills.analysis.doctrine.engine import PlanetDoctrine


@dataclass(frozen=True)
class Testimony:
    tokens: list[str]  # every finding that holds
    good: list[str] = field(default_factory=list)
    bad: list[str] = field(default_factory=list)
    score: float | None = None  # weights mode only

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def planet_tokens(p: PlanetDoctrine, found: list[Condition], exchanges: list[tuple[str, str]]) -> list[str]:
    t: list[str] = []
    if p.sect and p.sect.of_sect is not None:
        t.append("of_sect" if p.sect.of_sect else "contrary_to_sect")
        if p.sect.rejoices_hemisphere:
            t.append("rejoices_hemisphere")
        if p.sect.rejoices_sign:
            t.append("rejoices_sign")
    if p.dignities:
        g = p.dignities
        t += [n for n in ("domicile", "exaltation", "bounds", "decan", "adversity", "depression") if getattr(g, n)]
        if g.triplicity:
            t.append("triplicity")
        if g.triplicity == "sect ruler":
            t.append("triplicity_sect_ruler")
    if p.phase:
        ph = p.phase
        flags = {
            "under_beams": ph.under_beams,
            "in_heart": ph.in_heart,
            "chariot": bool(ph.chariot),
            "morning_riser": ph.star == "morning" and ph.visible,
            "evening_riser": ph.star == "evening" and ph.visible,
            "heliacal_emerging": ph.heliacal == "emerging",
            "heliacal_sinking": ph.heliacal == "sinking",
            "retrograde": ph.retrograde,
        }
        t += [k for k, on in flags.items() if on]
        if ph.speed and not ph.retrograde:
            t.append(ph.speed)
    pl = p.place
    t.append(pl.angularity)
    if pl.good is not None:
        t.append("good_place" if pl.good else "bad_place")
    if pl.busy is not None:
        t.append("busy" if pl.busy else "not_busy")
    if pl.joy:
        t.append("joy")
    t += list(p.flags)
    mine = [c for c in found if c.target == p.key]
    if any(c.effect == "bonify" for c in mine):
        t.append("bonified")
    if any(c.effect == "maltreat" for c in mine):
        t.append("maltreated")
    if any(c.effect == "bonify" and c.actor_of_sect for c in mine):
        t.append("bonified_by_sect_benefic")
    if any(c.effect == "maltreat" and c.actor_of_sect is False for c in mine):
        t.append("maltreated_by_contrary_malefic")
    if any(c.reception for c in mine):
        t.append("reception")
    if any(p.key in pair for pair in exchanges):
        t.append("exchange")
    return t


def judge(tokens: list[str], scoring: Scoring | None, lot: bool = False) -> Testimony:
    if scoring is None:
        return Testimony(tokens)
    good_set = scoring.lot_good if lot else scoring.good
    bad_set = scoring.lot_bad if lot else scoring.bad
    good = [x for x in tokens if x in good_set]
    bad = [x for x in tokens if x in bad_set]
    score = None
    if scoring.mode == "weights" and not lot:
        score = round(sum(scoring.weights.get(x, 0.0) for x in tokens), 3)
    return Testimony(tokens, good, bad, score)
