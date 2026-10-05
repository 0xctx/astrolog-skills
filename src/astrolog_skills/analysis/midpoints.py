"""Midpoint structures: a body on (or in aspect to) the midpoint of two others, as in classic midpoint trees — and the
harmonics a chart's strongest structures live in.

Two ways of reading a midpoint in harmonic chart H (the pack's `[midpoints] method`):
- **old** — multiply every position by H and take the midpoint inside the H chart. It is an axis: a body on the far
  midpoint counts like one on the near midpoint. Orb `orb` for conjunction and opposition, the others in proportion
  (`orb` × 2 ÷ the aspect's harmonic: a square 45′ when `orb` is 1.5°).
- **new** — measure the angle from the body to the (near) midpoint in the natal chart and multiply that angle by H,
  then read it as any aspect: orb `new_orb` ÷ the aspect's harmonic (3° conjunction, 1.5° opposition, 45′ square).
  Each structure has one strength and its own vibration: the lowest harmonic where it is a conjunction.
At H1 the two measure the same natal angle, so the birth chart always uses the classic (old) reading.
Strength is 1 at exact and 0 at the edge of the orb.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from itertools import combinations
from typing import Any

from astrolog_skills.analysis.aspects import ANGLE_KEYS, separation
from astrolog_skills.analysis.aspects_registry import BY_KEY, AspectType
from astrolog_skills.analysis.chance import baseline, group_baseline
from astrolog_skills.analysis.harmonics import harmonic_chart
from astrolog_skills.analysis.method import Method
from astrolog_skills.analysis.patterns import Pattern, group_score, score_harmonic
from astrolog_skills.engine.model import ChartModel

SKIP = ("south_node",)  # always opposite the North Node: its midpoints only repeat the North Node's
METHODS = ("old", "new")


@dataclass
class MidpointContact:
    focus: str  # the body on the midpoint
    a: str
    b: str
    aspect: str  # from the focus to the midpoint: conjunction, opposition, square…
    midpoint: float  # old: the nearer midpoint in the harmonic chart; new: the nearer midpoint in the natal chart
    orb: float  # in degrees of the harmonic chart
    limit: float
    strength: float  # 1 at exact, 0 at the edge of the orb
    method: str = "old"
    natal_angle: float | None = None  # new: from the focus to the midpoint, natal degrees (0–180)
    vibration: int | None = None  # new: the structure's own harmonic (the lowest where it is a conjunction)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def midpoint(a: float, b: float) -> float:
    """The midpoint on the shorter arc between two longitudes."""
    diff = (b - a + 180.0) % 360.0 - 180.0
    return (a + diff / 2.0) % 360.0


def limit_for(aspect: AspectType, how: str, method: Method, new_orb: float | None = None) -> float:
    """The orb an aspect to a midpoint is allowed, in degrees of the harmonic chart."""
    if how == "new":
        return (new_orb or method.midpoint_new_orb) / aspect.harmonic
    return method.midpoint_orb if aspect.harmonic <= 2 else method.midpoint_orb * 2 / aspect.harmonic


def vibration(natal_angle: float, orb: float, highest: int) -> int | None:
    """The lowest harmonic (up to `highest`) in which this natal angle is a conjunction within `orb`."""
    for n in range(1, highest + 1):
        y = (natal_angle * n) % 360.0
        if min(y, 360.0 - y) <= orb:
            return n
    return None


def _positions(chart: ChartModel, harmonic: int) -> dict[str, float]:
    source = harmonic_chart(chart, harmonic) if harmonic > 1 else chart
    lons = {p.key: p.lon for p in source.points if p.key not in SKIP}
    lons.update({k: source.angles[k] for k in ANGLE_KEYS if k in source.angles})
    return lons


def _best(
    d: float, types: list[AspectType], how: str, method: Method, new_orb: float | None
) -> tuple[str, float, float] | None:
    """(aspect, orb, limit) of the strongest aspect at distance `d` (0–180) from the midpoint, or None."""
    keys = {t.key for t in types}
    best: tuple[float, float, str, float] | None = None
    for t in types:
        if how == "old" and t.harmonic <= 2:  # the axis: the far midpoint counts like the near one
            orb = min(d, 180.0 - d)
            key = "conjunction" if d < 90.0 else "opposition"
            key = key if key in keys else t.key
        else:
            orb, key = abs(d - t.angle), t.key
        limit = limit_for(t, how, method, new_orb)
        if orb <= limit and (best is None or (1.0 - orb / limit, -orb) > (best[0], -best[1])):
            best = (1.0 - orb / limit, orb, key, limit)
    return None if best is None else (best[2], best[1], best[3])


def shown_method(method: Method, harmonic: int) -> str:
    """The method a chart's midpoint lists use: the pack's, except at H1, where only the orb would differ."""
    return "old" if harmonic == 1 else method.midpoint_method


def midpoint_contacts(
    chart: ChartModel,
    method: Method,
    harmonic: int = 1,
    how: str | None = None,
    new_orb: float | None = None,
) -> dict[str, list[MidpointContact]]:
    """For every body (planets, points and the angles), the midpoints it contacts in harmonic chart H by the old or
    new method (default: the pack's; at H1 always the old one), strongest first."""
    how = how or shown_method(method, harmonic)
    natal = _positions(chart, 1)
    harm = _positions(chart, harmonic) if how == "old" else natal
    types = [BY_KEY[k] for k in method.midpoint_aspects]
    conj_orb = new_orb or method.midpoint_new_orb
    found: dict[str, list[MidpointContact]] = {k: [] for k in natal}
    for focus in natal:
        for a, b in combinations([k for k in natal if k != focus], 2):
            x = None
            if how == "old":
                mid = midpoint(harm[a], harm[b])
                d = separation(harm[focus], mid)
            else:
                mid = midpoint(natal[a], natal[b])
                x = separation(natal[focus], mid)
                y = (x * harmonic) % 360.0
                d = min(y, 360.0 - y)
            best = _best(d, types, how, method, new_orb)
            if best is None:
                continue
            key, orb, limit = best
            found[focus].append(
                MidpointContact(
                    focus,
                    a,
                    b,
                    key,
                    round(mid, 6),
                    round(orb, 6),
                    round(limit, 6),
                    round(1 - orb / limit, 4),
                    how,
                    None if x is None else round(x, 6),
                    None if x is None else vibration(x, conj_orb, method.harmonic_max),
                )
            )
        found[focus].sort(key=lambda c: (-c.strength, c.orb))
    return found


# ── strongest harmonics ──────────────────────────────────────────────────────


@dataclass
class Structure:
    focus: str
    a: str
    b: str
    strength: float
    harmonic: int  # new: its own vibration; old: the harmonic chart it was found in
    aspect: str = "conjunction"
    natal_angle: float | None = None
    fraction: str = ""  # new: the natal angle as a share of the circle, e.g. "2/17"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HarmonicStrength:
    harmonic: int
    new: float  # midpoint strength, new method (structures whose own vibration is this harmonic)
    old: float  # midpoint strength, old method (direct contacts in this harmonic chart)
    chance_new: float
    chance_old: float
    z_new: float  # how far above a random chart, in standard deviations
    z_old: float
    aspects: float  # the pack's two-planet score in this harmonic (score 2)
    groups: float = 0.0  # planet groups: 3+ planets all within the pattern orb in this harmonic chart (group_score)
    chance_groups: float = 0.0
    z_groups: float = 0.0
    new_structures: list[Structure] = field(default_factory=list)
    old_structures: list[Structure] = field(default_factory=list)
    group_list: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Ranking:
    harmonics: list[HarmonicStrength]
    structures: list[dict[str, Any]]  # the strongest new-method structures, each at its own vibration, with the old
    bodies: list[str]
    new_orb: float
    old_orb: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "harmonics": [h.to_dict() for h in self.harmonics],
            "structures": self.structures,
            "bodies": self.bodies,
            "orbs": {"new": self.new_orb, "old": self.old_orb},
            "default_by": self.default_by(),
        }

    def default_by(self) -> str:
        """The new method up to its ceiling (360 ÷ its orb: every structure has its own harmonic by then); planet groups
        for a range beyond it, where the new method has nothing left to count."""
        return "groups" if max(h.harmonic for h in self.harmonics) > 360 // self.new_orb else "new"

    def ranked(self, by: str = "new") -> list[HarmonicStrength]:
        field_ = {"new": "z_new", "old": "z_old", "aspects": "aspects", "groups": "z_groups"}[by]
        return sorted(self.harmonics, key=lambda h: (-float(getattr(h, field_)), h.harmonic))


def _fraction(angle: float, harmonic: int) -> str:
    return f"{round(angle * harmonic / 360.0)}/{harmonic}"


def rank_harmonics(
    chart: ChartModel, method: Method, harmonics: list[int], new_orb: float | None = None, top: int = 3
) -> Ranking:
    """Each harmonic's midpoint strength by both methods against random charts, and its two-planet score; the
    structures are among the pack's pattern bodies (the planets)."""
    natal = {p.key: p.lon for p in chart.points}
    bodies = [k for k in method.pattern_bodies if k in natal]
    conj, old_orb = new_orb or method.midpoint_new_orb, method.midpoint_orb
    highest = max(harmonics)
    chance = baseline(len(bodies), highest, conj, old_orb)
    g_mean, g_sd = group_baseline(len(bodies), method.pattern_orb, method.pattern_min_size)
    moon = next((p.speed for p in chart.points if p.key == "moon"), None)
    trios = [(f, a, b) for f in bodies for a, b in combinations([x for x in bodies if x != f], 2)]
    by_vibration: dict[int, list[Structure]] = {}
    for f, a, b in trios:
        x = separation(natal[f], midpoint(natal[a], natal[b]))
        n = vibration(x, conj, highest)
        if n is None:
            continue
        y = (x * n) % 360.0
        strength = round(1 - min(y, 360.0 - y) / conj, 4)
        by_vibration.setdefault(n, []).append(
            Structure(f, a, b, strength, n, "conjunction", round(x, 4), _fraction(x, n))
        )
    rows = []
    old_at: dict[tuple[str, str, str, int], float] = {}
    for n in harmonics:
        olds = _old_direct(natal, trios, n, old_orb)
        old_at.update({(s.focus, s.a, s.b, n): s.strength for s in olds})
        news = sorted(by_vibration.get(n, []), key=lambda s: -s.strength)
        c = chance[n]
        new_sum, old_sum = sum(s.strength for s in news), sum(s.strength for s in olds)
        scored = score_harmonic(natal, n, method)
        g = group_score(scored.patterns)
        rows.append(
            HarmonicStrength(
                n,
                round(new_sum, 3),
                round(old_sum, 3),
                c.new_mean,
                c.old_mean,
                round((new_sum - c.new_mean) / c.new_sd, 1) if c.new_sd else 0.0,
                round((old_sum - c.old_mean) / c.old_sd, 1) if c.old_sd else 0.0,
                round(scored.score2, 3),
                round(g, 3),
                g_mean,
                round((g - g_mean) / g_sd, 1) if g_sd else 0.0,
                news[:top],
                olds[:top],
                [_group(p, n, method.pattern_orb, moon) for p in scored.patterns[:top]],
            )
        )
    shown = sorted((s for n in harmonics for s in by_vibration.get(n, [])), key=lambda s: (-s.strength, s.harmonic))
    structures = [
        {
            **s.to_dict(),
            "old": {f"H{m}": old_at.get((s.focus, s.a, s.b, m)) for m in _halves(s.harmonic) if m in harmonics},
        }
        for s in shown[:20]
    ]
    return Ranking(rows, structures, bodies, conj, old_orb)


OUTER = ("uranus", "neptune", "pluto")


def _group(p: Pattern, n: int, orb: float, moon_speed: float | None) -> dict[str, Any]:
    """A planet group with what a reader needs to weigh it: how exact the birth time must be when the Moon is in it
    (the minutes before the Moon would leave the group), and whether it is mostly generational (outer planets)."""
    minutes = None
    if "moon" in p.bodies and moon_speed:
        minutes = round((orb - p.span) / n / abs(moon_speed) * 1440)
    personal = [b for b in p.bodies if b not in OUTER]
    return {
        "bodies": p.bodies,
        "size": p.size,
        "span": p.span,
        "strength": p.strength,
        "moon_minutes": minutes,  # the birth time must be right within about this many minutes
        "exact_time": minutes is not None and minutes < 30,
        "generational": len(personal) <= 1,
    }


def _halves(n: int) -> list[int]:
    """The harmonics where the old method may show a structure of vibration n: n ÷ 2 (as an opposition) and n."""
    return [n // 2, n] if n % 2 == 0 else [n]


def _old_direct(natal: dict[str, float], trios: list[tuple[str, str, str]], n: int, orb: float) -> list[Structure]:
    """The old method's direct contacts (on either end of the midpoint axis) in harmonic chart n, strongest first."""
    h = {k: (v * n) % 360.0 for k, v in natal.items()}
    out = []
    for f, a, b in trios:
        s = separation(h[f], midpoint(h[a], h[b]))
        o = min(s, 180.0 - s)
        if o <= orb:
            out.append(Structure(f, a, b, round(1 - o / orb, 4), n, "conjunction" if s < 90 else "opposition"))
    return sorted(out, key=lambda s: -s.strength)
