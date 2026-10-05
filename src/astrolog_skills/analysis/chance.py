"""What a random chart scores in midpoint structures, per harmonic — the baseline a chart's strength is measured
against. Random charts: every body at an independent uniform longitude (fixed seed, so results repeat).

Computed with numpy once per set of rules and cached in `~/.astrolog-skills/cache/`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations

import numpy as np

from astrolog_skills.paths import data_dir

RUNS = 400  # random charts
SEED = 1
VERSION = 1  # bump when the scoring changes, so old caches are ignored


@dataclass(frozen=True)
class Chance:
    new_mean: float
    new_sd: float
    old_mean: float
    old_sd: float


def structures(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Index arrays (focus, a, b) for every body on the midpoint of every pair of the others."""
    rows = [(f, a, b) for f in range(n) for a, b in combinations([x for x in range(n) if x != f], 2)]
    arr = np.array(rows, dtype=int).reshape(-1, 3)
    return arr[:, 0], arr[:, 1], arr[:, 2]


def _sep(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    d = np.abs(a - b) % 360.0
    out: np.ndarray = np.minimum(d, 360.0 - d)
    return out


def _mid(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    diff = (b - a + 180.0) % 360.0 - 180.0
    out: np.ndarray = (a + diff / 2.0) % 360.0
    return out


def sums(lon: np.ndarray, highest: int, new_orb: float, old_orb: float) -> tuple[np.ndarray, np.ndarray]:
    """Per chart (rows of `lon`) and harmonic 1..highest: (new-method strength summed over the structures whose own
    vibration is that harmonic, old-method strength summed over direct contacts in that harmonic chart)."""
    f, a, b = structures(lon.shape[1])
    runs = lon.shape[0]
    new = np.zeros((runs, highest + 1))
    old = np.zeros((runs, highest + 1))
    # Both methods need only the natal angle x from each body to each midpoint: in harmonic chart n every midpoint of
    # the two positions is n × the natal midpoint + a multiple of 180°, so the old method's axis distance is x·n folded
    # to 0–90°, and the new method reads x·n itself.
    x = _sep(lon[:, f], _mid(lon[:, a], lon[:, b]))
    assigned = np.zeros(x.shape, dtype=bool)
    for n in range(1, highest + 1):
        y = (x * n) % 360.0
        c = np.minimum(y, 360.0 - y)
        hit = (c <= new_orb) & ~assigned
        new[:, n] = np.where(hit, 1.0 - c / new_orb, 0.0).sum(axis=1)
        assigned |= hit
        o = np.minimum(c, 180.0 - c)  # c is 0–180; the axis folds it to 0–90
        old[:, n] = np.where(o <= old_orb, 1.0 - o / old_orb, 0.0).sum(axis=1)
    return new, old


@lru_cache(maxsize=16)
def baseline(bodies: int, highest: int, new_orb: float, old_orb: float) -> dict[int, Chance]:
    """Mean and spread of random charts' midpoint strength for harmonics 1..highest."""
    path = data_dir() / "cache" / f"midpoint-chance-v{VERSION}-{bodies}-{highest}-{new_orb:g}-{old_orb:g}.json"
    try:
        raw = json.loads(path.read_text())
        return {int(k): Chance(*v) for k, v in raw.items()}
    except (OSError, ValueError, TypeError):
        pass
    rng = np.random.default_rng(SEED)
    new, old = sums(rng.uniform(0.0, 360.0, (RUNS, bodies)), highest, new_orb, old_orb)
    out = {
        n: Chance(
            round(float(new[:, n].mean()), 4),
            round(float(new[:, n].std(ddof=1)), 4),
            round(float(old[:, n].mean()), 4),
            round(float(old[:, n].std(ddof=1)), 4),
        )
        for n in range(1, highest + 1)
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({n: [c.new_mean, c.new_sd, c.old_mean, c.old_sd] for n, c in out.items()}))
    except OSError:
        pass  # a cache that can't be written is only slower
    return out


GROUP_RUNS = 2000


@lru_cache(maxsize=16)
def group_baseline(bodies: int, orb: float, min_size: int) -> tuple[float, float]:
    """Mean and spread of a random chart's planet-group score (patterns.group_score). The same in every harmonic: in
    a random chart, positions multiplied by H are still independent and uniform, so one baseline serves all."""
    from astrolog_skills.analysis.patterns import find_patterns, group_score

    path = data_dir() / "cache" / f"group-chance-v{VERSION}-{bodies}-{orb:g}-{min_size}.json"
    try:
        mean, sd = json.loads(path.read_text())
        return float(mean), float(sd)
    except (OSError, ValueError, TypeError):
        pass
    rng = np.random.default_rng(SEED)
    keys = [str(k) for k in range(bodies)]
    scores = [
        group_score(find_patterns(dict(zip(keys, row, strict=True)), orb, min_size))
        for row in rng.uniform(0.0, 360.0, (GROUP_RUNS, bodies))
    ]
    out = (round(float(np.mean(scores)), 4), round(float(np.std(scores)), 4))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    return out
