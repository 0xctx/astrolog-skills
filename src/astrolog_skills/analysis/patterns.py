"""Vibrational-astrology patterns: groups of planets that are all conjunct in a harmonic chart.

"3 planet patterns OK, 4 is better = behaviour. The tighter the orb, the stronger." Score 1 counts 4-planet
patterns (a 5-planet group contains five of them); score 2 sums pair weights × tightness.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from itertools import combinations
from typing import Any

from astrolog_skills.analysis.aspects import separation
from astrolog_skills.analysis.harmonics import harmonic_lon
from astrolog_skills.analysis.method import Method


@dataclass
class Pattern:
    bodies: list[str]
    span: float  # widest pairwise separation in the harmonic chart
    strength: float  # 1 − span/orb

    @property
    def size(self) -> int:
        return len(self.bodies)


@dataclass
class HarmonicScore:
    harmonic: int
    patterns: list[Pattern] = field(default_factory=list)
    score1: int = 0  # number of 4-planet patterns
    score2: float = 0.0  # weighted pairs × tightness

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "patterns": [{**asdict(p), "size": p.size} for p in self.patterns]}


def _cliques(nodes: list[str], adjacent: dict[str, set[str]]) -> list[set[str]]:
    """All maximal cliques (Bron–Kerbosch with pivoting) — at most ~20 bodies, so this is instant."""
    out: list[set[str]] = []

    def expand(r: set[str], p: set[str], x: set[str]) -> None:
        if not p and not x:
            out.append(r)
            return
        pivot = max(p | x, key=lambda v: len(adjacent[v] & p))
        for v in list(p - adjacent[pivot]):
            expand(r | {v}, p & adjacent[v], x & adjacent[v])
            p = p - {v}
            x = x | {v}

    expand(set(), set(nodes), set())
    return out


def find_patterns(
    lons: dict[str, float], orb: float, min_size: int = 3, excluded: set[frozenset[str]] | None = None
) -> list[Pattern]:
    """Maximal groups (≥ min_size) whose members are all within `orb` of each other. Tightest first.
    `excluded` pairs never count as connected (see lower-harmonic exclusion)."""
    keys = list(lons)
    excluded = excluded or set()
    adjacent = {
        k: {j for j in keys if j != k and separation(lons[k], lons[j]) <= orb and frozenset((k, j)) not in excluded}
        for k in keys
    }
    patterns = []
    for group in _cliques(keys, adjacent):
        if len(group) < min_size:
            continue
        ordered = [k for k in keys if k in group]
        span = max(separation(lons[a], lons[b]) for a, b in combinations(ordered, 2))
        patterns.append(Pattern(ordered, round(span, 4), round(1 - span / orb, 4)))
    return sorted(patterns, key=lambda p: (-p.size, p.span))


def group_score(patterns: list[Pattern]) -> float:
    """Planet groups as one number: each group's strength × the planet pairs it holds (a 4-planet group has 6, a
    3-planet group 3), so bigger and tighter groups weigh more."""
    return sum(p.strength * p.size * (p.size - 1) / 2 for p in patterns)


def lower_harmonic_pairs(natal: dict[str, float], h: int, orb: float) -> set[frozenset[str]]:
    """Pairs conjunct in H only because they are already conjunct in a lower harmonic d that divides H
    (e.g. a quintile — H5 — reappears as a conjunction in H10). An "exclude lower harmonics" option."""
    divisors = [d for d in range(1, h) if h % d == 0]
    out: set[frozenset[str]] = set()
    for a, b in combinations(natal, 2):
        if any(separation(harmonic_lon(natal[a], d), harmonic_lon(natal[b], d)) <= orb for d in divisors):
            out.add(frozenset((a, b)))
    return out


def score_harmonic(natal: dict[str, float], h: int, method: Method) -> HarmonicScore:
    """Patterns and the two vibrational scores for one harmonic of one chart."""
    natal = {k: v for k, v in natal.items() if k in method.pattern_bodies}
    bodies = {k: harmonic_lon(v, h) for k, v in natal.items()}
    orb = method.pattern_orb
    excluded = lower_harmonic_pairs(natal, h, orb) if method.exclude_lower_harmonics else set()
    patterns = find_patterns(bodies, orb, method.pattern_min_size, excluded)
    strong = method.pattern_strong_size
    quads: set[frozenset[str]] = set()
    for p in patterns:
        if p.size >= strong:
            quads.update(frozenset(c) for c in combinations(p.bodies, strong))
    score2 = 0.0
    for a, b in combinations(bodies, 2):
        sep = separation(bodies[a], bodies[b])
        if sep <= orb and frozenset((a, b)) not in excluded:
            score2 += method.weight(a, b) * (1 - sep / orb)
    return HarmonicScore(h, patterns, len(quads), round(score2, 4))


def harmonic_profile(
    natal: dict[str, float], method: Method, low: int | None = None, high: int | None = None
) -> list[HarmonicScore]:
    low = low or method.harmonic_range[0]
    high = high or method.harmonic_range[1]
    return [score_harmonic(natal, h, method) for h in range(low, high + 1)]
