"""Bonification and maltreatment: which benefic or malefic acts on which planet, by the pack's [conditions] rules."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from astrolog_skills.analysis.doctrine.configurations import (
    BY_SIGNS,
    closest,
    gap,
    is_applying,
    overcoming,
    ray_points,
    sign_aspect,
    signs_apart,
)
from astrolog_skills.analysis.doctrine.places import place_of
from astrolog_skills.analysis.doctrine.rules import SEVEN, SIGN_KEYS, ConditionRule, Doctrine, SectRules
from astrolog_skills.engine.model import ChartModel, Point
from astrolog_skills.engine.zodiac import sign_index


@dataclass(frozen=True)
class Condition:
    target: str
    actor: str  # one planet, or "venus+jupiter" for an enclosure
    condition: str  # the pack's rule name
    effect: str  # "bonify" | "maltreat"
    aspect: str = ""
    distance: float | None = None  # degrees from exact, for degree-based conditions
    applying: bool | None = None
    actor_of_sect: bool | None = None  # the actor (all actors) belongs to the chart's sect
    reception: bool = False  # one of the two is in the other's domicile
    cite: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class _Ctx:
    def __init__(self, chart: ChartModel, doctrine: Doctrine, day: bool) -> None:
        self.p = {k: chart.point(k) for k in SEVEN}
        self.asc = chart.angles["asc"]
        self.sect = doctrine.sect or SectRules()
        self.members = set(self.sect.diurnal if day else self.sect.nocturnal)
        self.domicile = doctrine.dignities.domicile if doctrine.dignities else {}

    def nature(self, planet: str) -> str:
        if planet in self.sect.benefics:
            return "bonify"
        if planet in self.sect.malefics:
            return "maltreat"
        return ""

    def actors(self, target: str) -> list[str]:
        return [k for k in (*self.sect.benefics, *self.sect.malefics) if k != target and k in self.p]

    def lord(self, planet: str) -> str:
        return self.domicile.get(SIGN_KEYS[sign_index(self.p[planet].lon)], "")

    def reception(self, a: str, b: str) -> bool:
        return self.lord(a) == b or self.lord(b) == a

    def finding(self, rule: ConditionRule, target: str, actor: str, effect: str, **kw: Any) -> Condition:
        return Condition(
            target,
            actor,
            rule.name,
            effect,
            actor_of_sect=all(a in self.members for a in actor.split("+")),
            cite=rule.cite,
            **kw,
        )


def _aspects(rule: ConditionRule, effect: str) -> tuple[str, ...]:
    return rule.bonify if effect == "bonify" else rule.maltreat


def _sign_based(ctx: _Ctx, rule: ConditionRule, target: str) -> list[Condition]:
    out = []
    t = ctx.p[target]
    for actor in ctx.actors(target):
        effect = ctx.nature(actor)
        a = ctx.p[actor]
        if rule.kind == "overcoming":
            aspect = overcoming(a.lon, t.lon)
        elif rule.kind == "copresence":
            aspect = "conjunction" if sign_aspect(a.lon, t.lon) == "conjunction" else None
        else:
            aspect = sign_aspect(a.lon, t.lon)
            if aspect and rule.side == "right" and aspect != "opposition" and signs_apart(a.lon, t.lon) > 6:
                aspect = None
        if aspect is None or (rule.kind != "copresence" and aspect not in _aspects(rule, effect)):
            continue
        out.append(ctx.finding(rule, target, actor, effect, aspect=aspect, reception=ctx.reception(target, actor)))
    return out


def _orb(rule: ConditionRule, target: str) -> float:
    return rule.moon_orb if target == "moon" and rule.moon_orb else rule.orb


def _degree_based(ctx: _Ctx, rule: ConditionRule, target: str) -> list[Condition]:
    out = []
    t = ctx.p[target]
    for actor in ctx.actors(target):
        effect = ctx.nature(actor)
        a = ctx.p[actor]
        aspects = ("conjunction",) if rule.kind == "adherence" else _aspects(rule, effect)
        best: tuple[float, str] | None = None
        for aspect in aspects:
            d = closest(t.lon, a.lon, aspect, rule.direction if rule.kind == "degree_aspect" else "any")
            if abs(d) <= _orb(rule, target) and (best is None or abs(d) < abs(best[0])):
                best = (d, aspect)
        if best is None:
            continue
        d, aspect = best
        applying = is_applying(d, t.speed, a.speed)
        if (rule.applying or rule.kind == "adherence") and not applying:
            continue
        out.append(
            ctx.finding(
                rule,
                target,
                actor,
                effect,
                aspect=aspect,
                distance=round(abs(d), 4),
                applying=applying,
                reception=ctx.reception(target, actor),
            )
        )
    return out


def _enclosure(ctx: _Ctx, rule: ConditionRule, target: str) -> list[Condition]:
    t = ctx.p[target]
    body_orb = rule.body_orb or rule.orb
    points: list[tuple[float, str]] = []  # (signed distance from the target, owner)
    for owner, p in ctx.p.items():
        if owner == target:
            continue
        d = gap(p.lon, t.lon)
        if 0 < abs(d) <= body_orb:
            points.append((d, owner))
        for aspect in rule.rays:
            for ray in ray_points(p.lon, aspect, "any"):
                d = gap(ray, t.lon)
                if 0 < abs(d) <= rule.orb:
                    points.append((d, owner))
    before = [x for x in points if x[0] < 0]
    after = [x for x in points if x[0] > 0]
    if not before or not after:
        return []
    first, second = max(before)[1], min(after)[1]  # the nearest on each side: anything nearer would intervene
    effects = {ctx.nature(first), ctx.nature(second)}
    if len(effects) != 1 or "" in effects:
        return []
    effect = effects.pop()
    actor = first if first == second else "+".join(sorted({first, second}))
    return [ctx.finding(rule, target, actor, effect)]


CONTAINMENT_RAYS = ("sextile", "square", "trine", "opposition")


def _containment(ctx: _Ctx, rule: ConditionRule, target: str) -> list[Condition]:
    """By sign: one benefic or malefic casts its rays onto both signs either side of the planet, and no other planet
    is configured to it by sign (which would interpose)."""
    t = ctx.p[target]
    s = sign_index(t.lon)
    rays = rule.rays or CONTAINMENT_RAYS
    out = []
    for actor in ctx.actors(target):
        effect = ctx.nature(actor)
        a = sign_index(ctx.p[actor].lon)
        if not all(BY_SIGNS.get((side - a) % 12) in rays for side in ((s - 1) % 12, (s + 1) % 12)):
            continue
        others = [k for k in SEVEN if k not in (target, actor)]
        if any(sign_aspect(ctx.p[k].lon, t.lon) is not None for k in others):
            continue
        out.append(
            ctx.finding(rule, target, actor, effect, aspect="containment", reception=ctx.reception(target, actor))
        )
    return out


def _counteraction(ctx: _Ctx, rule: ConditionRule, target: str) -> list[Condition]:
    lord = ctx.lord(target)
    if not lord or lord == target:
        return []
    effect = ctx.nature(lord)
    place = place_of(ctx.p[lord].lon, ctx.asc)
    places = rule.bonify_places if effect == "bonify" else rule.maltreat_places if effect == "maltreat" else ()
    if place not in places:
        return []
    return [ctx.finding(rule, target, lord, effect, aspect=f"lord in place {place}")]


def conditions(chart: ChartModel, doctrine: Doctrine, day: bool) -> list[Condition]:
    ctx = _Ctx(chart, doctrine, day)
    out: list[Condition] = []
    for rule in doctrine.conditions.values():
        for target in SEVEN:
            if rule.kind in ("overcoming", "sign_aspect", "copresence"):
                out += _sign_based(ctx, rule, target)
            elif rule.kind in ("degree_aspect", "adherence"):
                out += _degree_based(ctx, rule, target)
            elif rule.kind == "enclosure":
                out += _enclosure(ctx, rule, target)
            elif rule.kind == "counteraction":
                out += _counteraction(ctx, rule, target)
            elif rule.kind == "containment":
                out += _containment(ctx, rule, target)
    return out


def exchanges(chart: ChartModel, doctrine: Doctrine) -> list[tuple[str, str]]:
    """Pairs of planets in each other's domiciles."""
    domicile = doctrine.dignities.domicile if doctrine.dignities else {}
    pts: dict[str, Point] = {k: chart.point(k) for k in SEVEN}

    def lord(k: str) -> str:
        return domicile.get(SIGN_KEYS[sign_index(pts[k].lon)], "")

    return [(a, b) for i, a in enumerate(SEVEN) for b in SEVEN[i + 1 :] if lord(a) == b and lord(b) == a]
