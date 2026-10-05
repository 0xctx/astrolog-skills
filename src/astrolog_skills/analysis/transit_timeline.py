"""Transit timelines: every transit to the natal chart over a window of days — to natal planets and angles, and to
natal midpoints — with the days it is in orb and each exact date, and the patterns transits form in harmonic charts.

Everything defaults to the tradition pack and the chart's settings:
- bodies: the chart's (profile and pack `[chart]`), transiting and natal; the Moon doesn't transit here (daily steps
  are too coarse for it).
- aspects and orbs: to planets and angles, the pack's transit aspects and orbs; to midpoints, its midpoint aspects
  and orbs (the classic reading: the birth chart's midpoints in ordinary degrees).
- harmonic patterns: the pack's pattern rules (orb in the harmonic chart, minimum size, which bodies).
Each transit carries the harmonic of its aspect (a septile is H7), so the harmonics being activated show at a glance;
a pattern names the harmonic chart to open (`astro view --harmonic H --transits DATE`).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from itertools import combinations
from typing import Any

import numpy as np

from astrolog_skills.analysis.aspects import ANGLE_KEYS
from astrolog_skills.analysis.aspects_registry import BY_KEY, AspectType
from astrolog_skills.analysis.harmonics import harmonic_lon
from astrolog_skills.analysis.method import Method
from astrolog_skills.analysis.midpoints import limit_for, midpoint
from astrolog_skills.analysis.patterns import Pattern, find_patterns, lower_harmonic_pairs
from astrolog_skills.analysis.transits import daily_skies, natal_targets
from astrolog_skills.engine.model import ChartModel
from astrolog_skills.engine.profile import Profile
from astrolog_skills.errors import AstroError

NEVER = ("south_node",)  # always opposite the North Node: its transits only repeat the North Node's
TOO_FAST = ("moon",)


@dataclass
class Passage:
    """One stretch of a transit in orb (a retrograde can bring it back: that is another passage)."""

    transit: str
    natal: str  # "venus", "asc" or a midpoint "venus/mars"
    aspect: str
    harmonic: int  # the aspect's harmonic: septile 7, novile 9, square 4…
    enters: str  # ISO dates; the window's first or last day when it is already (still) in orb
    leaves: str
    exact: list[str]  # every exact date in the stretch
    peak: str  # the tightest day: the first exact date, or the day of the smallest orb
    orb: float  # the tightest orb in the stretch
    limit: float
    strength: float  # at its tightest: 1 when exact, falling to 0 at the edge of the orb

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HarmonicPattern:
    """Bodies together in a harmonic chart (all within the pack's pattern orb), transiting and natal at once."""

    harmonic: int
    transits: list[str]
    natal: list[str]
    starts: str
    ends: str
    peak: str  # the tightest day
    span: float  # the widest pairwise separation that day, in the harmonic chart
    strength: float  # 1 − span ÷ the pattern orb, as for any pattern

    @property
    def size(self) -> int:
        return len(self.transits) + len(self.natal)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "size": self.size}


@dataclass
class Selection:
    """Which transits to follow; empty = the chart's and the pack's own."""

    transiting: tuple[str, ...] = ()
    natal: tuple[str, ...] = ()
    aspects: tuple[str, ...] = ()  # aspect keys, or "h7" for every aspect of a harmonic
    midpoints: bool = True

    def check(self, natal: ChartModel, skies: list[ChartModel]) -> None:
        """Names the chart doesn't have fail with the way to add them."""
        moving = {p.key for p in skies[0].points}
        fixed = {p.key for p in natal.points} | set(ANGLE_KEYS)
        for kind, names, have in (("transiting", self.transiting, moving), ("natal", self.natal, fixed)):
            missing = [n for n in names if n not in have]
            if missing:
                raise AstroError(
                    f"The chart has no {kind} {', '.join(missing)}.", fix="add bodies with --points +ceres,+chiron …"
                )
        unknown = [a for a in self.aspects if a not in BY_KEY and not (a[:1] == "h" and a[1:].isdigit())]
        if unknown:
            raise AstroError(
                f"Unknown aspect: {', '.join(unknown)}.", fix="e.g. --aspects conjunction,septile or h5,h7"
            )

    def keeps(self, aspect: AspectType) -> bool:
        return not self.aspects or aspect.key in self.aspects or f"h{aspect.harmonic}" in self.aspects


def _unwrapped(skies: list[ChartModel], keys: list[str]) -> np.ndarray:
    """[day][body] longitudes made continuous across 0° Aries (each day's motion taken the short way)."""
    lons = np.array([[next(p.lon for p in s.points if p.key == k) for k in keys] for s in skies])
    return np.rad2deg(np.unwrap(np.deg2rad(lons), axis=0))


def targets(natal: ChartModel, sel: Selection, method: Method) -> list[tuple[str, float]]:
    """Natal planets and angles, then (when the pack reads midpoints) the midpoint of every pair of them."""
    points = [(k, lon) for k, lon in natal_targets(natal).items() if not sel.natal or k in sel.natal]
    if not (sel.midpoints and method.midpoint_aspects):
        return points
    return points + [(f"{a}/{b}", midpoint(x, y)) for (a, x), (b, y) in combinations(points, 2)]


def transiting(skies: list[ChartModel], sel: Selection) -> list[str]:
    keys = [p.key for p in skies[0].points if p.key not in NEVER]
    chosen = [k for k in keys if k in sel.transiting] if sel.transiting else [k for k in keys if k not in TOO_FAST]
    return chosen


def passages(
    natal: ChartModel, skies: list[ChartModel], start: datetime, method: Method, sel: Selection
) -> list[Passage]:
    """Every transit in orb during the window (one sky per day): the slowest transiting body first, its transits to
    planets before midpoints, then by date. Exact moments are found between the
    daily samples, so a quick transit that perfects and leaves within a day is still caught."""
    movers = transiting(skies, sel)
    fixed = targets(natal, sel, method)
    if not movers or not fixed:
        return []
    moving = _unwrapped(skies, movers)  # [day][mover]
    nat = np.array([lon for _, lon in fixed])
    is_mid = np.array(["/" in key for key, _ in fixed])
    s = moving[:, :, None] - nat[None, None, :]  # signed angle, continuous in time: [day][mover][target]
    day = [(start + timedelta(days=d)).date().isoformat() for d in range(len(skies))]
    groups = [(method.transit_types(), False), ([BY_KEY[k] for k in method.midpoint_aspects], True)]
    found: list[Passage] = []
    for types, to_midpoints in groups:
        which = is_mid if to_midpoints else ~is_mid
        if not which.any():
            continue
        for aspect in (a for a in types if sel.keeps(a)):
            limit = limit_for(aspect, "old", method) if to_midpoints else method.transit_orb(aspect)
            offsets = [aspect.angle] if aspect.angle in (0.0, 180.0) else [aspect.angle, -aspect.angle]
            dist = np.min([np.abs((s - o + 180.0) % 360.0 - 180.0) for o in offsets], axis=0)
            inside = (dist <= limit) & which[None, None, :]
            exact = np.zeros(s.shape, dtype=bool)  # an exact moment between day d and d+1 is marked on day d
            when = np.zeros(s.shape)
            for o in offsets:
                k = np.floor((s - o) / 360.0)
                crossed = (k[1:] != k[:-1]) & which[None, None, :]
                frac = (360.0 * np.maximum(k[1:], k[:-1]) + o - s[:-1]) / np.where(crossed, s[1:] - s[:-1], 1.0)
                exact[:-1] |= crossed
                when[:-1] = np.where(crossed, frac, when[:-1])
            hot = inside | exact
            for i, j in zip(*np.nonzero(hot.any(axis=0)), strict=True):
                found += _stretches(
                    hot[:, i, j], exact[:, i, j], when[:, i, j], dist[:, i, j], day, start,
                    movers[i], fixed[j][0], aspect, limit,
                )  # fmt: skip
    pace = dict(zip(movers, np.abs(np.diff(moving, axis=0)).mean(axis=0), strict=True))  # degrees a day, measured
    return sorted(found, key=lambda p: (pace[p.transit], "/" in p.natal, p.exact[0] if p.exact else p.enters))


def _stretches(
    hot: np.ndarray,
    exact: np.ndarray,
    when: np.ndarray,
    dist: np.ndarray,
    day: list[str],
    start: datetime,
    mover: str,
    target: str,
    aspect: AspectType,
    limit: float,
) -> list[Passage]:
    out = []
    days = np.nonzero(hot)[0]
    for run in np.split(days, np.nonzero(np.diff(days) > 1)[0] + 1):
        a, b = int(run[0]), int(run[-1])
        hits = [(start + timedelta(days=float(d) + float(when[d]))).date().isoformat() for d in run if exact[d]]
        orb = round(0.0 if hits else float(dist[a : b + 1].min()), 4)
        out.append(
            Passage(
                mover,
                target,
                aspect.key,
                aspect.harmonic,
                day[a],
                max(day[b], hits[-1]) if hits else day[b],  # a quick transit can perfect after the last sample
                hits,
                hits[0] if hits else day[a + int(np.argmin(dist[a : b + 1]))],
                orb,
                round(limit, 4),
                round(1.0 - orb / limit, 4),
            )
        )
    return out


def active_on(found: list[Passage], date: str) -> dict[int, int]:
    """How many transits each harmonic has in orb on a date, most first."""
    counts: dict[int, int] = defaultdict(int)
    for p in found:
        if p.enters <= date <= p.leaves:
            counts[p.harmonic] += 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def joined(natal: dict[str, float], moving: dict[str, float], h: int, method: Method) -> list[Pattern]:
    """The pack's patterns in harmonic chart H that need a transit: one or more transiting bodies (keys "t:saturn")
    together with two or more natal ones, all within the pattern orb."""
    both = {**natal, **{f"t:{k}": v for k, v in moving.items()}}
    orb = method.pattern_orb
    excluded = lower_harmonic_pairs(both, h, orb) if method.exclude_lower_harmonics else set()
    lons = {k: harmonic_lon(v, h) for k, v in both.items()}
    return [
        p
        for p in find_patterns(lons, orb, method.pattern_min_size, excluded)
        if any(k.startswith("t:") for k in p.bodies) and sum(not k.startswith("t:") for k in p.bodies) >= 2
    ]


def harmonic_patterns(
    natal: ChartModel,
    skies: list[ChartModel],
    start: datetime,
    method: Method,
    harmonics: list[int],
    sel: Selection,
) -> list[HarmonicPattern]:
    """Patterns in harmonic charts that need a transit: the pack's pattern bodies, natal and transiting, all within its
    pattern orb in harmonic chart H — at least one transiting body joining two or more natal ones. A pattern found in a
    lower harmonic that divides H isn't repeated in H. A transiting body joins only in harmonics where a day's motion
    stays inside half the orb, so daily steps can't skip past a pattern."""
    orb = method.pattern_orb
    bodies = set(method.pattern_bodies)
    natal_lons = {p.key: p.lon for p in natal.points if p.key in bodies and (not sel.natal or p.key in sel.natal)}
    movers = [k for k in transiting(skies, sel) if k in bodies]
    runs: dict[tuple[int, frozenset[str]], list[tuple[int, float]]] = defaultdict(list)
    for d, sky in enumerate(skies):
        pts = {p.key: p for p in sky.points}
        seen: dict[int, list[frozenset[str]]] = {}
        for h in harmonics:
            moving = {k: pts[k].lon for k in movers if abs(pts[k].speed) * h <= orb / 2}
            if not moving:
                continue
            seen[h] = []
            for p in joined(natal_lons, moving, h, method):
                group = frozenset(p.bodies)
                seen[h].append(group)
                if any(group <= g for e in seen if h % e == 0 and e < h for g in seen[e]):
                    continue  # the same bodies already together in a harmonic that divides this one
                runs[(h, group)].append((d, p.span))
    out = []
    iso = [(start + timedelta(days=d)).date().isoformat() for d in range(len(skies))]
    for (h, group), hits in runs.items():
        days = [d for d, _ in hits]
        for run in np.split(np.array(days), np.nonzero(np.diff(days) > 1)[0] + 1):
            spans = [sp for d, sp in hits if run[0] <= d <= run[-1]]
            peak = int(run[int(np.argmin(spans))])
            out.append(
                HarmonicPattern(
                    h,
                    sorted(k[2:] for k in group if k.startswith("t:")),
                    sorted(k for k in group if not k.startswith("t:")),
                    iso[int(run[0])],
                    iso[int(run[-1])],
                    iso[peak],
                    round(min(spans), 4),
                    round(1.0 - min(spans) / orb, 4),
                )
            )
    return sorted(out, key=lambda p: (-p.size, p.span, p.starts))


@dataclass
class Timeline:
    start: str
    days: int
    harmonics: list[int]  # searched for patterns
    passages: list[Passage]
    patterns: list[HarmonicPattern]
    skies: list[ChartModel]  # one per day (for pages that move the transiting planets); not in to_dict

    def to_dict(self, limit: int = 0, patterns: int = 40) -> dict[str, Any]:
        """`limit` passages (0 = all), slowest transiting body first; the strongest `patterns`."""
        shown = self.passages[:limit] if limit else self.passages
        return {
            "start": self.start,
            "days": self.days,
            "active": {f"H{h}": n for h, n in active_on(self.passages, self.start).items()},
            "harmonics": self.harmonics,
            "passages_total": len(self.passages),
            "passages": [p.to_dict() for p in shown],
            "patterns_total": len(self.patterns),
            "patterns": [p.to_dict() for p in self.patterns[:patterns]],
        }


def build(
    natal: ChartModel,
    profile: Profile,
    method: Method,
    start: datetime,
    days: int,
    lat: float,
    lon: float,
    sel: Selection,
    harmonics: str | None = None,
) -> Timeline:
    """The whole timeline: one sky per day, every passage, and the harmonic patterns (the pack's harmonic range unless
    `harmonics` names others, e.g. "1-32" or "5,7,9")."""
    from astrolog_skills.export.html import parse_harmonics

    skies = daily_skies(profile, start, days, lat, lon)
    sel.check(natal, skies)
    lo, hi = method.harmonic_range
    own = list(range(lo, hi + 1)) if method.reads_patterns else []  # a tradition without pattern rules: none
    hs = parse_harmonics(harmonics, 360) if harmonics else own
    return Timeline(
        start.date().isoformat(),
        days,
        hs,
        passages(natal, skies, start, method, sel),
        harmonic_patterns(natal, skies, start, method, hs, sel),
        skies,
    )
