"""Harmonic sweeps over a chart set, with a control baseline ("expected by chance").

Each harmonic is measured three ways (the same ones `astro harmonics` ranks one chart by): midpoint structures by the
new method (each structure counted at its own vibration) and by the old method (direct contacts in the harmonic
chart), and two-planet aspects (the pack's pair score). Comparing a set's measures with its controls shows which
harmonics stand out — and which method separates the set from chance better.

Baseline = recombined control charts: new birth moments recombined from the set's own components (year from one
person, month and day from another, time of day from a third, place from a fourth), cast by Astrolog. The control skies
are real skies — Mercury stays within 28° of the Sun, Venus within 47°, outer planets keep their generational
clustering and the Sun its seasonal spread — but no longer belong to the people in the set. So "above chance" means
"stronger than real skies at comparable moments", not "stronger than planets scattered at random" (shuffling positions
independently would break the astronomy and make low harmonics look falsely significant).
"""

from __future__ import annotations

import calendar
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import numpy as np

from astrolog_skills.analysis.chance import sums as midpoint_sums
from astrolog_skills.charts import chartlist, sets
from astrolog_skills.charts.records import SetRecord
from astrolog_skills.engine.batch import BatchChart, batch
from astrolog_skills.engine.profile import Profile
from astrolog_skills.errors import AstroError
from astrolog_skills.packs.loader import Pack
from astrolog_skills.paths import data_dir
from astrolog_skills.research.vector import F, pair_weights, scores

MEASURES = ("new", "old", "aspects")
LABELS = {
    "new": "midpoint structures, new method",
    "old": "midpoint structures, old method",
    "aspects": "two-planet aspects (pair score)",
}


@dataclass
class HarmonicStat:
    harmonic: int
    observed: float  # the set's mean
    expected: float  # the control groups' mean
    ratio: float  # observed / expected
    z: float  # (observed − expected) / spread of the control-group means
    p_family: float  # chance of a |z| this large anywhere in the tested range, from the control groups (max-statistic)
    control_mean: float | None = None  # another set's mean (--control)
    top: list[dict[str, Any]] = field(default_factory=list)  # strongest charts in this harmonic


@dataclass
class SweepResult:
    set_name: str
    count: int
    measures: dict[str, list[HarmonicStat]]
    charts: list[dict[str, Any]]  # per chart: id, name, rating, strongest harmonics (first measure)
    params: dict[str, Any]

    def ranked(self, measure: str = "new", key: str = "z") -> list[HarmonicStat]:
        return sorted(self.measures[measure], key=lambda s: -float(getattr(s, key)))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def matrix(pairs: list[tuple[SetRecord, BatchChart]], bodies: list[str]) -> tuple[F, list[SetRecord]]:
    """(N, B) longitudes for the charts that have every body."""
    rows, kept = [], []
    for record, chart in pairs:
        if all(b in chart.points for b in bodies):
            rows.append([chart.lon(b) for b in bodies])
            kept.append(record)
    return np.array(rows, dtype=float).reshape(len(rows), len(bodies)), kept


def _values(
    lons: F, bodies: list[str], pack: Pack, harmonics: range, measures: tuple[str, ...]
) -> dict[str, np.ndarray]:
    """Per measure, an (H, N) array: each chart's value in each harmonic."""
    out: dict[str, np.ndarray] = {}
    m = pack.method
    if "new" in measures or "old" in measures:
        new, old = midpoint_sums(lons, harmonics.stop - 1, m.midpoint_new_orb, m.midpoint_orb)
        cols = list(harmonics)
        if "new" in measures:
            out["new"] = new[:, cols].T
        if "old" in measures:
            out["old"] = old[:, cols].T
    if "aspects" in measures:
        w = pair_weights(bodies, m)
        out["aspects"] = np.array([scores(lons, bodies, m, h, w)[1] for h in harmonics]).reshape(len(harmonics), -1)
    return out


def control_records(records: list[SetRecord], shuffles: int, sample: int, seed: int) -> list[list[SetRecord]]:
    """Recombined controls: each control chart takes its year, month-and-day, time of day and place from four
    different (random) members of the set. Groups are as large as the set (up to `sample`), so the spread of their
    means is the right yardstick for the set's own mean."""
    rng = np.random.default_rng(seed)
    size = min(sample, len(records))
    out: list[list[SetRecord]] = []
    for s in range(shuffles):
        pick = [rng.integers(0, len(records), size) for _ in range(4)]
        group = []
        for k in range(size):
            y, md, tod, pl = (records[int(p[k])] for p in pick)
            day = min(md.utc.day, calendar.monthrange(y.utc.year, md.utc.month)[1])  # 29 Feb in a common year → 28
            when = datetime(
                y.utc.year, md.utc.month, day, tod.utc.hour, tod.utc.minute, tod.utc.second, tzinfo=tod.utc.tzinfo
            )
            group.append(SetRecord(f"c{s}-{k}", f"control {s}-{k}", when, pl.lat, pl.lon, source="control"))
        out.append(group)
    return out


@dataclass
class Baseline:
    expected: np.ndarray  # per harmonic: the control groups' mean
    spread: np.ndarray  # per harmonic: the spread of the control-group means
    null_max: np.ndarray  # per control group: its largest |z| across the range (for family-wise p)


def control_baseline(
    records: list[SetRecord],
    profile: Profile,
    bodies: list[str],
    pack: Pack,
    harmonics: range,
    shuffles: int,
    sample: int,
    seed: int,
    measures: tuple[str, ...],
) -> dict[str, Baseline]:
    """Per measure: the control groups' mean and spread per harmonic, and each group's largest |z| across the range
    (treating that group as if it were the set) — the null distribution for a family-wise p-value."""
    groups = control_records(records, shuffles, sample, seed)
    listing = chartlist.write([r for g in groups for r in g], data_dir() / "cache" / "controls.as")
    cast = {chartlist.id_of(c.name): c for c in batch(["-i", str(listing)], profile)}
    means = {m: np.zeros((shuffles, len(harmonics))) for m in measures}
    for s, group in enumerate(groups):
        lons, _ = matrix([(r, cast[r.id]) for r in group if r.id in cast], bodies)
        for m, v in _values(lons, bodies, pack, harmonics, measures).items():
            means[m][s] = v.mean(axis=1)
    out = {}
    for m, mm in means.items():
        spread = mm.std(axis=0, ddof=1) if shuffles > 1 else np.zeros(len(harmonics))
        null_max = np.zeros(shuffles)
        if shuffles > 2:
            for g in range(shuffles):
                others = np.delete(mm, g, axis=0)
                sd = others.std(axis=0, ddof=1)
                z = np.divide(mm[g] - others.mean(axis=0), sd, out=np.zeros(len(harmonics)), where=sd > 0)
                null_max[g] = np.abs(z).max()
        out[m] = Baseline(mm.mean(axis=0), spread, null_max)
    return out


def sweep(
    set_name: str,
    profile: Profile,
    pack: Pack,
    low: int = 1,
    high: int = 32,
    *,
    shuffles: int = 20,
    sample: int = 4000,
    seed: int = 1,
    control: str | None = None,
    top: int = 10,
    measures: tuple[str, ...] = MEASURES,
) -> SweepResult:
    if not 1 <= low <= high <= max(pack.method.harmonic_max, high):
        raise AstroError("Harmonic range must go from low to high, starting at 1.")
    unknown = [m for m in measures if m not in MEASURES]
    if unknown or not measures:
        raise AstroError(f"Unknown measure(s): {', '.join(unknown) or 'none'}.", fix="choose from new, old, aspects")
    bodies = list(pack.method.pattern_bodies)
    missing = [b for b in bodies if b not in {o.key for o in profile.object_list}]
    if missing:
        raise AstroError(
            f"The profile '{profile.name}' doesn't calculate {', '.join(missing)}, which the pack needs.",
            fix="use a profile with all ten planets, e.g. --profile vibrational",
        )
    lons, records = matrix(sets.cast_set(sets.load(set_name), profile), bodies)
    if len(records) < 10:
        raise AstroError(
            f"Only {len(records)} charts in '{set_name}' — too few to compare against chance.",
            fix="widen the set's filters (e.g. more Rodden ratings)",
        )
    harmonics = range(low, high + 1)
    values = _values(lons, bodies, pack, harmonics, measures)
    base = control_baseline(records, profile, bodies, pack, harmonics, shuffles, sample, seed, measures)
    other: dict[str, np.ndarray] = {}
    if control:
        c_lons, _ = matrix(sets.cast_set(sets.load(control), profile), bodies)
        if len(c_lons):
            other = {m: v.mean(axis=1) for m, v in _values(c_lons, bodies, pack, harmonics, measures).items()}

    results: dict[str, list[HarmonicStat]] = {}
    for m in measures:
        v, b = values[m], base[m]
        stats = []
        for k, h in enumerate(harmonics):
            observed, exp = float(v[k].mean()), float(b.expected[k])
            z = (observed - exp) / float(b.spread[k]) if b.spread[k] > 0 else 0.0
            p_family = (1 + int((b.null_max >= abs(z)).sum())) / (1 + len(b.null_max))
            order = np.argsort(-v[k])[:top]
            stats.append(
                HarmonicStat(
                    harmonic=h,
                    observed=round(observed, 4),
                    expected=round(exp, 4),
                    ratio=round(observed / exp, 4) if exp else 0.0,
                    z=round(z, 2),
                    p_family=round(p_family, 3),
                    control_mean=round(float(other[m][k]), 4) if m in other else None,
                    top=[
                        {"id": records[n].id, "name": records[n].name, "value": round(float(v[k][n]), 3)} for n in order
                    ],
                )
            )
        results[m] = stats

    # per chart: strongest harmonics (first measure) relative to what's typical for that harmonic in this set
    first = values[measures[0]]
    relative = first - first.mean(axis=1, keepdims=True)
    charts = []
    for n, record in enumerate(records):
        best = np.argsort(-relative[:, n])[:3]
        charts.append(
            {
                "id": record.id,
                "name": record.name,
                "rating": record.rating,
                "strongest": [{"harmonic": low + int(k), "value": round(float(first[k][n]), 3)} for k in best],
            }
        )
    return SweepResult(
        set_name=set_name,
        count=len(records),
        measures=results,
        charts=charts,
        params={
            "range": [low, high],
            "measures": list(measures),
            "baseline": "recombined controls",
            "shuffles": shuffles,
            "sample": sample,
            "seed": seed,
            "control": control,
            "bodies": bodies,
            "orbs": {
                "midpoints_new": pack.method.midpoint_new_orb,
                "midpoints_old": pack.method.midpoint_orb,
                "aspects": pack.method.pattern_orb,
            },
            "pack": pack.name,
            "profile": profile.name,
        },
    )
