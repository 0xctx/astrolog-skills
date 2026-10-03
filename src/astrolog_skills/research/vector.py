"""Vectorised vibrational scoring for many charts at once (numpy). Must equal analysis.patterns.score_harmonic."""

from __future__ import annotations

from functools import lru_cache
from itertools import combinations

import numpy as np
import numpy.typing as npt

from astrolog_skills.analysis.method import Method

F = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]


@lru_cache(maxsize=8)
def _structure(n_bodies: int, strong: int) -> tuple[IntArray, IntArray, IntArray]:
    """Pair index arrays (i, j) and, for every `strong`-sized subset of bodies, the indices of its pairs."""
    pairs = list(combinations(range(n_bodies), 2))
    index = {p: k for k, p in enumerate(pairs)}
    subsets = [[index[p] for p in combinations(q, 2)] for q in combinations(range(n_bodies), strong)]
    i, j = (np.array(x, dtype=np.int64) for x in zip(*pairs, strict=True))
    return i, j, np.array(subsets, dtype=np.int64).reshape(len(subsets), -1)


def pair_weights(bodies: list[str], method: Method) -> F:
    return np.array([method.weight(bodies[a], bodies[b]) for a, b in combinations(range(len(bodies)), 2)], dtype=float)


def separations(lons: F, h: int) -> F:
    """(N, P) harmonic-chart separations for every pair of bodies in every chart."""
    i, j, _ = _structure(lons.shape[1], 2)
    d = np.abs(lons[:, i] - lons[:, j]) * h % 360.0
    return np.minimum(d, 360.0 - d)


def scores(lons: F, bodies: list[str], method: Method, h: int, weights: F | None = None) -> tuple[IntArray, F]:
    """(score1, score2) per chart for harmonic h. `lons` is (N charts, B bodies) in natal degrees."""
    orb = method.pattern_orb
    weights = pair_weights(bodies, method) if weights is None else weights
    sep = separations(lons, h)
    close = sep <= orb
    if method.exclude_lower_harmonics:
        for d in (d for d in range(1, h) if h % d == 0):
            close &= separations(lons, d) > orb
    score2 = (close * weights * (1.0 - sep / orb)).sum(axis=1)
    strong = method.pattern_strong_size
    if lons.shape[1] < strong:
        return np.zeros(len(lons), dtype=np.int64), score2
    _, _, subsets = _structure(lons.shape[1], strong)
    score1 = close[:, subsets].all(axis=2).sum(axis=1).astype(np.int64)
    return score1, score2
