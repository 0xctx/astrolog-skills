"""A tradition's calculation rules (method.toml): aspects, orbs, harmonics, patterns, pair weights, chart settings."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from astrolog_skills.analysis.aspects_registry import BY_KEY, AspectType
from astrolog_skills.analysis.doctrine import Doctrine, parse_doctrine
from astrolog_skills.engine.objects import BY_KEY as OBJECTS
from astrolog_skills.engine.profile import ChartSettings, parse_chart_settings
from astrolog_skills.errors import AstroError

GROUPS: dict[str, set[str]] = {
    "personal": {"sun", "moon", "mercury", "venus", "mars"},
    "luminaries": {"sun", "moon"},
    "social": {"jupiter", "saturn"},
    "outer": {"uranus", "neptune", "pluto"},
}
TEN_PLANETS = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto")
DEFAULT_HARMONIC_CHART_ORBS = {"conjunction": 16.0, "opposition": 8.0, "square": 8.0, "trine": 6.0, "sextile": 6.0}


@dataclass(frozen=True)
class WeightRule:
    a: str
    b: str
    weight: float

    def _matches(self, token: str, key: str) -> bool:
        return token == "*" or token == key or key in GROUPS.get(token, set())

    def matches(self, x: str, y: str) -> bool:
        return (self._matches(self.a, x) and self._matches(self.b, y)) or (
            self._matches(self.a, y) and self._matches(self.b, x)
        )


@dataclass(frozen=True)
class Method:
    name: str
    label: str = ""
    aspects: tuple[str, ...] = ("conjunction", "opposition", "trine", "square", "sextile")
    orb_rule: str = "fixed"  # fixed | harmonic (orb = base / aspect harmonic)
    orb_base: float = 16.0  # harmonic rule: orb = base / aspect harmonic
    orbs: dict[str, float] = field(default_factory=dict)  # fixed orbs, or per-aspect overrides under the harmonic rule
    harmonic_chart_orbs: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_HARMONIC_CHART_ORBS))
    harmonic_range: tuple[int, int] = (1, 32)
    harmonic_max: int = 180
    pattern_orb: float = 16.0  # degrees, measured in the harmonic chart
    pattern_min_size: int = 3
    pattern_strong_size: int = 4
    pattern_bodies: tuple[str, ...] = TEN_PLANETS
    exclude_lower_harmonics: bool = False
    weight_rules: tuple[WeightRule, ...] = ()
    weight_default: float = 1.0
    transit_aspects: tuple[str, ...] = ()  # empty = the natal aspect set
    transit_orbs: dict[str, float] = field(default_factory=dict)  # per aspect; default below
    midpoint_choice: tuple[str, ...] | None = None  # [midpoints] aspects; None = "all" (the pack's aspect set)
    midpoint_orb: float = 1.5  # old method: the conjunction/opposition orb in the harmonic chart; others in proportion
    midpoint_method: str = "old"  # old (midpoints inside the harmonic chart) | new (the natal angle × H)
    midpoint_new_orb: float = 3.0  # new method: the conjunction orb; others = this ÷ the aspect's harmonic
    doctrine: Doctrine | None = (
        None  # traditional doctrine sections, when the pack has them (analysis/doctrine/rules.py)
    )
    chart: ChartSettings | None = None  # [chart]: the zodiac, houses, node and objects the tradition uses

    @property
    def midpoint_aspects(self) -> tuple[str, ...]:
        return self.aspects if self.midpoint_choice is None else self.midpoint_choice

    @property
    def aspect_types(self) -> list[AspectType]:
        return [BY_KEY[k] for k in self.aspects]

    def orb_for(self, aspect: AspectType) -> float:
        """Orb in natal (harmonic-1) degrees."""
        if aspect.key in self.orbs:
            return self.orbs[aspect.key]
        if self.orb_rule == "harmonic":
            return self.orb_base / aspect.harmonic
        raise AstroError(
            f"method '{self.name}': no orb for {aspect.key}.", fix=f"add {aspect.key} = <degrees> under [orbs]"
        )

    def transit_types(self) -> list[AspectType]:
        return [BY_KEY[k] for k in (self.transit_aspects or self.aspects)]

    def transit_orb(self, aspect: AspectType) -> float:
        """Transit orb: [transits] orbs if set, else min(natal orb, 2°) for H ≤ 4 aspects and 1° for the rest."""
        if aspect.key in self.transit_orbs:
            return self.transit_orbs[aspect.key]
        natal = self.orbs.get(aspect.key, self.orb_base / aspect.harmonic if self.orb_rule == "harmonic" else 2.0)
        return min(natal, 2.0 if aspect.harmonic <= 4 else 1.0)

    def weight(self, a: str, b: str) -> float:
        for rule in self.weight_rules:
            if rule.matches(a, b):
                return rule.weight
        return self.weight_default


# ── parsing ──────────────────────────────────────────────────────────────────


def merge(base: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    """`extends`: tables merge key by key (child wins); lists and values are replaced."""
    out = copy.deepcopy(base)
    for key, value in child.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _num(where: str, key: str, value: Any, low: float, high: float) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool) or not low <= value <= high:
        raise AstroError(f"{where}: {key} must be a number between {low:g} and {high:g}, not {value!r}.")
    return float(value)


def _aspect_keys(where: str, key: str, values: list[str]) -> tuple[str, ...]:
    unknown = [a for a in values if a not in BY_KEY]
    if unknown:
        raise AstroError(
            f"{where}: {key} has unknown aspect(s) {', '.join(unknown)}.", fix="known: " + ", ".join(BY_KEY)
        )
    return tuple(values)


MIDPOINT_METHODS = ("old", "new")


def _midpoint_method(where: str, value: Any) -> str:
    if value not in MIDPOINT_METHODS:
        raise AstroError(f"{where}: midpoints.method must be 'old' or 'new', not {value!r}.")
    return str(value)


def parse(raw: dict[str, Any], where: str) -> Method:
    aspects_t = raw.get("aspects", {})
    orbs_t = raw.get("orbs", {})
    harm_t = raw.get("harmonics", {})
    pat_t = raw.get("patterns", {})
    w_t = raw.get("weights", {})
    tr_t = raw.get("transits", {})
    mp_t = raw.get("midpoints", {})

    aspects = tuple(aspects_t.get("set", Method.aspects))
    unknown = [a for a in aspects if a not in BY_KEY]
    if unknown:
        raise AstroError(f"{where}: unknown aspect(s) {', '.join(unknown)}.", fix="known: " + ", ".join(BY_KEY))
    rule = orbs_t.get("rule", "fixed")
    if rule not in ("fixed", "harmonic"):
        raise AstroError(f"{where}: orbs.rule must be 'fixed' or 'harmonic', not {rule!r}.")
    orbs = {k: _num(where, f"orbs.{k}", v, 0, 30) for k, v in orbs_t.items() if k not in ("rule", "base")}
    bad = [k for k in orbs if k not in BY_KEY]
    if bad:
        raise AstroError(f"{where}: orbs for unknown aspect(s) {', '.join(bad)}.")
    if rule == "fixed":
        missing = [a for a in aspects if a not in orbs]
        if missing:
            raise AstroError(f"{where}: fixed orbs need a value for {', '.join(missing)}.", fix="add them under [orbs]")
    hc = {
        k: _num(where, f"harmonic_chart_orbs.{k}", v, 0, 30)
        for k, v in raw.get("harmonic_chart_orbs", DEFAULT_HARMONIC_CHART_ORBS).items()
    }
    rng = harm_t.get("range", [1, 32])
    if not (isinstance(rng, list) and len(rng) == 2 and all(isinstance(x, int) for x in rng) and 1 <= rng[0] <= rng[1]):
        raise AstroError(f"{where}: harmonics.range must be [low, high], e.g. [1, 32].")
    bodies = tuple(pat_t.get("bodies", TEN_PLANETS))
    bad_bodies = [b for b in bodies if b not in OBJECTS]
    if bad_bodies:
        raise AstroError(f"{where}: patterns.bodies has unknown object(s) {', '.join(bad_bodies)}.")
    rules: list[WeightRule] = []
    for i, r in enumerate(w_t.get("rules", [])):
        pair = r.get("pair", [])
        tokens_ok = all(t == "*" or t in GROUPS or t in OBJECTS for t in pair)
        if len(pair) != 2 or not tokens_ok:
            raise AstroError(f"{where}: weights.rules[{i}].pair must be two objects/groups ({', '.join(GROUPS)}, *).")
        rules.append(WeightRule(pair[0], pair[1], _num(where, f"weights.rules[{i}].weight", r.get("weight"), 0, 100)))
    method = Method(
        name=str(raw.get("name", "")),
        label=str(raw.get("label", "")),
        aspects=aspects,
        orb_rule=rule,
        orb_base=_num(where, "orbs.base", orbs_t.get("base", 16.0), 0.1, 60),
        orbs=orbs,
        harmonic_chart_orbs=hc,
        harmonic_range=(int(rng[0]), int(rng[1])),
        harmonic_max=int(_num(where, "harmonics.max", harm_t.get("max", 180), 1, 10000)),
        pattern_orb=_num(where, "patterns.orb", pat_t.get("orb", 16.0), 0.1, 60),
        pattern_min_size=int(_num(where, "patterns.min_size", pat_t.get("min_size", 3), 2, 12)),
        pattern_strong_size=int(_num(where, "patterns.strong_size", pat_t.get("strong_size", 4), 2, 12)),
        pattern_bodies=bodies,
        exclude_lower_harmonics=bool(harm_t.get("exclude_lower", False)),
        weight_rules=tuple(rules),
        weight_default=_num(where, "weights.default", w_t.get("default", 1.0), 0, 100),
        transit_aspects=_aspect_keys(where, "transits.aspects", tr_t.get("aspects", [])),
        transit_orbs={k: _num(where, f"transits.orbs.{k}", v, 0, 10) for k, v in tr_t.get("orbs", {}).items()},
        # "all" (the default) = every aspect in the pack's [aspects] set, minor ones included
        midpoint_choice=None
        if mp_t.get("aspects", "all") == "all"
        else _aspect_keys(where, "midpoints.aspects", mp_t["aspects"]),
        midpoint_orb=_num(where, "midpoints.orb", mp_t.get("orb", Method.midpoint_orb), 0.05, 5),
        midpoint_method=_midpoint_method(where, mp_t.get("method", Method.midpoint_method)),
        midpoint_new_orb=_num(where, "midpoints.new_orb", mp_t.get("new_orb", Method.midpoint_new_orb), 0.1, 10),
        doctrine=parse_doctrine(raw, where),
        chart=parse_chart_settings(raw.get("chart"), where),
    )
    bad_tr = [k for k in method.transit_orbs if k not in BY_KEY]
    if bad_tr:
        raise AstroError(f"{where}: transits.orbs for unknown aspect(s) {', '.join(bad_tr)}.")
    for a in method.aspect_types:
        method.orb_for(a)  # every aspect resolves to an orb
    return method
