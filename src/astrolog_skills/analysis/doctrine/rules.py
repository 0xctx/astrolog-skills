"""Traditional doctrine as pack data: sect, dignities, lots, conditions, places, timing and scoring.

Every rule carries a `cite` (the source's printed pages). `parse_doctrine` raises on structural errors (wrong types,
unknown names); `check_doctrine` lists softer problems — a missing citation, a table that breaks its own invariants,
a lot formula pointing at nothing — so a whole pack can be reviewed at once (`astro packs check`).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields
from typing import Any

from astrolog_skills.analysis.aspects_registry import BY_KEY as ASPECTS
from astrolog_skills.engine.zodiac import ELEMENTS, SIGNS
from astrolog_skills.errors import AstroError

SEVEN = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn")
FIVE = ("mercury", "venus", "mars", "jupiter", "saturn")
SIGN_KEYS = tuple(s.lower() for s in SIGNS)
EGYPTIAN_TOTALS = {"mercury": 76, "venus": 82, "mars": 66, "jupiter": 79, "saturn": 57}  # the planets' years
MERCURY_RULES = ("morning_evening", "configured_with", "bounds_ruler", "neutral")
BY_SIGN = ("gender", "hemisphere", "domicile_lord", "none")
DAY_RULES = ("sun_above_horizon",)
DECAN_SCHEMES = ("chaldean", "table")
CONDITION_KINDS = (
    "overcoming",
    "sign_aspect",
    "degree_aspect",
    "adherence",
    "enclosure",
    "counteraction",
    "copresence",
    "containment",
    "custom",
)
CONDITION_KEYS = {
    "cite", "kind", "bonify", "maltreat", "orb", "moon_orb", "direction", "applying", "side", "rays", "body_orb",
    "maltreat_places", "bonify_places", "note",
}  # fmt: skip
SIDES = ("any", "right")
# Findings the summary can count as good or bad testimony ([scoring] good/bad/weights).
PLANET_TOKENS = (
    "of_sect", "contrary_to_sect", "rejoices_hemisphere", "rejoices_sign",
    "domicile", "exaltation", "triplicity_sect_ruler", "triplicity", "bounds", "decan", "adversity", "depression",
    "under_beams", "in_heart", "chariot", "morning_riser", "evening_riser", "heliacal_emerging", "heliacal_sinking",
    "retrograde", "additive", "subtractive", "stationary",
    "angular", "succedent", "declining", "good_place", "bad_place", "busy", "not_busy", "joy",
    "bonified", "maltreated", "bonified_by_sect_benefic", "maltreated_by_contrary_malefic", "reception", "exchange",
    "proper_face", "running_in_the_void", "busy_by_angle",
)  # fmt: skip
LOT_TOKENS = (
    "lot_good_place", "lot_bad_place", "benefic_copresent", "malefic_copresent", "benefic_configured",
    "malefic_configured", "malefic_in_aversion", "benefic_in_aversion", "lord_benefic", "lord_malefic",
    "lord_well_placed_by_sign", "lord_poorly_placed_by_sign", "lord_good_place", "lord_bad_place",
    "lord_configured", "lord_not_configured", "lord_configured_to_benefics", "lord_in_aversion_to_benefics",
    "lord_in_aversion_to_malefics", "lord_configured_to_malefics", "lord_bonified", "lord_not_bonified",
    "lord_not_maltreated", "lord_maltreated", "lord_not_under_beams", "lord_under_beams",
)  # fmt: skip
_FALLBACK_WHEN = re.compile(r"^(sun|moon|mercury|venus|mars|jupiter|saturn)_under_beams$")
DIRECTIONS = ("backward", "forward", "any")
DISTANCES = ("zodiacal", "shortest")
SCORING_MODES = ("testimonies", "weights")
CHARIOT_DIGNITIES = ("domicile", "exaltation", "bounds", "triplicity")
LOT_KEYS = {
    "cite", "points", "day", "night", "reverse", "project_from", "distance", "fallback", "version", "variants",
    "by_sex",
}  # fmt: skip
SEXES = ("male", "female")
MERCURY_ROLES = ("", "association")
QUADRANTS = ("", "porphyry")
_POINT = re.compile(r"^(lot:[a-z0-9_]+|sign:[a-z]+|place:\d{1,2}|ruler:place:\d{1,2}|asc|mc|[a-z_]+)$")


# ── models ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Rejoicing:
    by_hemisphere: bool = True
    by_sign: str = "gender"


@dataclass(frozen=True)
class SectRules:
    cite: str = ""
    day_rule: str = "sun_above_horizon"
    diurnal: tuple[str, ...] = ("sun", "jupiter", "saturn")
    nocturnal: tuple[str, ...] = ("moon", "venus", "mars")
    mercury: str = "morning_evening"
    benefics: tuple[str, ...] = ("jupiter", "venus")
    malefics: tuple[str, ...] = ("saturn", "mars")
    rejoicing: Rejoicing = field(default_factory=Rejoicing)
    mercury_role: str = ""  # "association": Mercury takes the role of the benefic or malefic it is closely joined to
    association_orb: float = 3.0  # degree range for Mercury's closest associations


@dataclass(frozen=True)
class Dignities:
    cite: str = ""
    domicile: dict[str, str] = field(default_factory=dict)  # sign → planet
    exaltation: dict[str, tuple[str, float]] = field(default_factory=dict)  # planet → (sign, degree)
    triplicity: dict[str, tuple[str, ...]] = field(default_factory=dict)  # element → (day, night, participating)
    bounds: dict[str, dict[str, tuple[tuple[str, float], ...]]] = field(default_factory=dict)  # scheme → sign → bounds
    bounds_scheme: str = ""
    decan_scheme: str = "chaldean"
    decans: dict[str, tuple[str, ...]] = field(default_factory=dict)  # sign → 3 planets (scheme "table")
    twelfth_parts: int = 0  # multiplier (12, or 13 in a variant); 0 = not used
    proper_face: bool = False  # the same sign relation to the Sun or Moon as in the domicile assignments


@dataclass(frozen=True)
class Phase:
    """Solar phase settings: orbs in degrees from the Sun, days for heliacal events (0 = not used)."""

    cite: str = ""
    under_beams: float = 15.0
    weak_within: float = 0.0
    heart: float = 0.0
    heliacal_days: int = 0
    visible_beyond: float = 15.0
    chariot: tuple[str, ...] = ()
    stationary_ratio: float = 0.0  # |speed| / mean motion below this = stationary; 0 = not used
    mean_motion: dict[str, float] = field(default_factory=dict)  # °/day overrides


@dataclass(frozen=True)
class Fallback:
    when: str
    points: tuple[str, ...]
    reverse: bool = False


@dataclass(frozen=True)
class LotRule:
    name: str
    cite: str = ""
    points: tuple[str, ...] = ()
    day: tuple[str, ...] = ()
    night: tuple[str, ...] = ()
    reverse: bool = False
    project_from: str = "asc"
    distance: str = "zodiacal"
    fallback: Fallback | None = None
    version: str = ""
    versions: dict[str, LotRule] = field(default_factory=dict)
    variants: dict[str, str] = field(default_factory=dict)  # named alternatives the source mentions (notes only)
    by_sex: dict[str, LotRule] = field(default_factory=dict)  # a version for each sex of the native (male, female)

    def effective(self, sex: str = "") -> LotRule:
        """The rule with its chosen version applied (or the native's sex's version)."""
        if self.by_sex:
            chosen = self.by_sex.get(sex)
            if chosen is None:
                return LotRule(self.name, self.cite)  # no points: needs the native's sex
        elif not self.version:
            return self
        else:
            chosen = self.versions[self.version]
        return LotRule(
            self.name,
            chosen.cite or self.cite,
            chosen.points,
            chosen.day,
            chosen.night,
            chosen.reverse,
            chosen.project_from,
            chosen.distance,
            chosen.fallback,
        )

    def all_points(self) -> tuple[str, ...]:
        rules = [self, *self.versions.values(), *self.by_sex.values()]
        out: list[str] = []
        for r in rules:
            out += [*r.points, *r.day, *r.night, r.project_from]
            if r.fallback:
                out += list(r.fallback.points)
        return tuple(out)


@dataclass(frozen=True)
class ConditionRule:
    """How a benefic bonifies or a malefic maltreats another planet (benefics and malefics from [sect])."""

    name: str
    kind: str
    cite: str = ""
    bonify: tuple[str, ...] = ()  # aspects by which a benefic bonifies
    maltreat: tuple[str, ...] = ()  # aspects by which a malefic maltreats
    orb: float = 3.0
    moon_orb: float = 0.0  # the Moon's own range (0 = same as orb)
    direction: str = "any"  # degree_aspect: "backward" = the actor is later and casts its ray back
    applying: bool = False  # the target must be applying
    side: str = "any"  # sign_aspect: "right" = the actor must be earlier in the zodiac
    rays: tuple[str, ...] = ()  # enclosure: the rays that enclose (besides bodies)
    body_orb: float = 0.0  # enclosure by body: range each side (0 = same as orb)
    maltreat_places: tuple[int, ...] = ()  # counteraction
    bonify_places: tuple[int, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class Places:
    cite: str = ""
    good: tuple[int, ...] = ()
    bad: tuple[int, ...] = ()
    busy: tuple[int, ...] = ()
    joys: dict[str, int] = field(default_factory=dict)
    angle_degrees: bool = False  # the Midheaven and IC degrees carry the 10th's and 4th's topics into their places
    busy_by_angle: tuple[
        str, ...
    ] = ()  # aspects to the Ascendant or Midheaven degree that make a declining planet busy
    busy_by_angle_orb: float = 3.0
    quadrant: str = ""  # "porphyry": each planet's quadrant house as information (no testimony)


@dataclass(frozen=True)
class Profections:
    cite: str = ""
    starts: tuple[str, ...] = ("asc",)  # asc, sect_light, contrary_light, a planet, lot:x or place:n
    step_signs: int = 1
    planets_in_sign: bool = False  # natal planets in the profected sign are activated too


@dataclass(frozen=True)
class Periods:
    cite: str = ""
    minor_years: dict[str, float] = field(default_factory=dict)  # planet → years


@dataclass(frozen=True)
class SectLightLords:
    cite: str = ""
    quality: dict[str, str] = field(default_factory=dict)  # angular/succedent/declining → good/middling/bad
    changeover: tuple[str, ...] = ()  # "minor_years", "ascensional_time"


@dataclass(frozen=True)
class Releasing:
    cite: str = ""
    lots: tuple[str, ...] = ("fortune", "spirit")
    year_days: float = 360.0
    periods: dict[str, float] = field(default_factory=dict)  # sign → years
    levels: int = 2
    peaks: tuple[int, ...] = ()  # places counted from Fortune that mark peak periods, strongest first
    loosing_of_bond: bool = False
    same_sign_shift: bool = False  # Spirit in Fortune's sign is released from the next sign
    ruler_sign: bool = False  # flag subperiods in the sign that holds the general period's ruler


@dataclass(frozen=True)
class TimingTransits:
    cite: str = ""
    kinds: tuple[str, ...] = ()  # ingress, sign_configurations, exact


@dataclass(frozen=True)
class Topic:
    """A topic of life judged by its three testimonies: its planet(s), its place(s) and ruler, its lot(s)."""

    name: str
    label: str
    cite: str = ""
    places: tuple[int, ...] = ()
    significators: tuple[str, ...] = ()
    lots: tuple[str, ...] = ()
    degrees: tuple[str, ...] = ()  # "mc", "ic": the place holding that degree joins the topic's places


@dataclass(frozen=True)
class Configs:
    """Degree-based configurations beyond the conditions: assembly, and the Moon running in the void."""

    cite: str = ""
    assembly: float = 0.0  # an applying conjunction beyond engagement but within this range; 0 = not used
    void_range: float = 0.0  # the Moon completes no exact aspect within this many degrees of its motion; 0 = not used


@dataclass(frozen=True)
class Scoring:
    cite: str = ""
    mode: str = "testimonies"
    good: tuple[str, ...] = ()  # planet finding tokens that count as good testimony
    bad: tuple[str, ...] = ()
    weights: dict[str, float] = field(default_factory=dict)
    lot_good: tuple[str, ...] = ()  # lot checklist tokens
    lot_bad: tuple[str, ...] = ()


@dataclass(frozen=True)
class Doctrine:
    sect: SectRules | None = None
    dignities: Dignities | None = None
    phase: Phase | None = None
    lots: dict[str, LotRule] = field(default_factory=dict)
    conditions: dict[str, ConditionRule] = field(default_factory=dict)
    places: Places | None = None
    profections: Profections | None = None
    releasing: Releasing | None = None
    transits: TimingTransits | None = None
    periods: Periods | None = None
    sect_light: SectLightLords | None = None
    scoring: Scoring | None = None
    topics: dict[str, Topic] = field(default_factory=dict)
    configs: Configs | None = None
    cited: bool = True  # False: a sample pack of the tradition's common doctrine, with no page citations

    def summary(self) -> dict[str, Any]:
        return {
            "sections": [
                name
                for name in (
                    "sect",
                    "dignities",
                    "phase",
                    "places",
                    "profections",
                    "releasing",
                    "transits",
                    "periods",
                    "sect_light",
                    "scoring",
                )
                if getattr(self, name) is not None
            ]
            + (["lots"] if self.lots else [])
            + (["conditions"] if self.conditions else [])
            + (["topics"] if self.topics else []),
            "lots": sorted(self.lots),
            "conditions": sorted(self.conditions),
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Problem:
    level: str  # "error" | "warn"
    where: str
    message: str
    fix: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


# ── parsing ───────────────────────────────────────────────────────────────────


def _err(where: str, msg: str, fix: str = "") -> AstroError:
    return AstroError(f"{where}: {msg}", fix=fix or None)


def _table(where: str, key: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _err(where, f"{key} must be a table")
    return value


def _names(where: str, key: str, value: Any, allowed: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise _err(where, f"{key} must be a list of names")
    bad = [v for v in value if v not in allowed]
    if bad:
        raise _err(where, f"{key}: unknown {', '.join(bad)}", fix="known: " + ", ".join(allowed))
    return tuple(value)


def _choice(where: str, key: str, value: Any, allowed: tuple[str, ...]) -> str:
    if value not in allowed:
        raise _err(where, f"{key} must be one of {', '.join(allowed)}, not {value!r}")
    return str(value)


def _number(where: str, key: str, value: Any, lo: float, hi: float) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool) or not lo <= value <= hi:
        raise _err(where, f"{key} must be a number from {lo:g} to {hi:g}, not {value!r}")
    return float(value)


def _cite(t: dict[str, Any]) -> str:
    return str(t.get("cite", ""))


def _sect(where: str, t: dict[str, Any]) -> SectRules:
    rj = _table(where, "sect.rejoicing", t.get("rejoicing", {}))
    return SectRules(
        cite=_cite(t),
        day_rule=_choice(where, "sect.day_rule", t.get("day_rule", "sun_above_horizon"), DAY_RULES),
        diurnal=_names(where, "sect.diurnal", t.get("diurnal", ["sun", "jupiter", "saturn"]), SEVEN),
        nocturnal=_names(where, "sect.nocturnal", t.get("nocturnal", ["moon", "venus", "mars"]), SEVEN),
        mercury=_choice(where, "sect.mercury", t.get("mercury", "morning_evening"), MERCURY_RULES),
        benefics=_names(where, "sect.benefics", t.get("benefics", ["jupiter", "venus"]), SEVEN),
        malefics=_names(where, "sect.malefics", t.get("malefics", ["saturn", "mars"]), SEVEN),
        rejoicing=Rejoicing(
            by_hemisphere=bool(rj.get("by_hemisphere", True)),
            by_sign=_choice(where, "sect.rejoicing.by_sign", rj.get("by_sign", "gender"), BY_SIGN),
        ),
        mercury_role=_choice(where, "sect.mercury_role", t.get("mercury_role", ""), MERCURY_ROLES),
        association_orb=_number(where, "sect.association_orb", t.get("association_orb", 3.0), 0, 30),
    )


def _bounds_table(where: str, scheme: str, t: dict[str, Any]) -> dict[str, tuple[tuple[str, float], ...]]:
    out: dict[str, tuple[tuple[str, float], ...]] = {}
    for sign, rows in t.items():
        if sign not in SIGN_KEYS:
            raise _err(where, f"dignities.bounds.{scheme}: unknown sign {sign!r}")
        if not isinstance(rows, list) or not all(isinstance(r, list) and len(r) == 2 for r in rows):
            raise _err(where, f"dignities.bounds.{scheme}.{sign} must be [[planet, end degree], …]")
        parsed = []
        for planet, end in rows:
            if planet not in SEVEN:
                raise _err(where, f"dignities.bounds.{scheme}.{sign}: unknown planet {planet!r}")
            parsed.append((str(planet), _number(where, f"dignities.bounds.{scheme}.{sign}", end, 0, 30)))
        out[sign] = tuple(parsed)
    return out


def _dignities(where: str, t: dict[str, Any]) -> Dignities:
    dom = _table(where, "dignities.domicile", t.get("domicile", {}))
    for sign, planet in dom.items():
        if sign not in SIGN_KEYS or planet not in SEVEN:
            raise _err(where, f"dignities.domicile: {sign} = {planet!r} isn't a sign and a traditional planet")
    exalt: dict[str, tuple[str, float]] = {}
    for planet, value in _table(where, "dignities.exaltation", t.get("exaltation", {})).items():
        if planet not in SEVEN or not isinstance(value, list) or len(value) != 2 or value[0] not in SIGN_KEYS:
            raise _err(where, f"dignities.exaltation.{planet} must be [sign, degree]")
        exalt[planet] = (value[0], _number(where, f"dignities.exaltation.{planet}", value[1], 0, 30))
    trip: dict[str, tuple[str, ...]] = {}
    for element, rulers in _table(where, "dignities.triplicity", t.get("triplicity", {})).items():
        if element not in ELEMENTS:
            raise _err(where, f"dignities.triplicity: unknown element {element!r}", fix="fire, earth, air, water")
        trip[element] = _names(where, f"dignities.triplicity.{element}", rulers, SEVEN)
    bounds = {
        scheme: _bounds_table(where, scheme, _table(where, f"dignities.bounds.{scheme}", table))
        for scheme, table in _table(where, "dignities.bounds", t.get("bounds", {})).items()
    }
    scheme = str(t.get("bounds_scheme", next(iter(bounds), "")))
    if bounds and scheme not in bounds:
        raise _err(where, f"dignities.bounds_scheme {scheme!r} has no table", fix="schemes: " + ", ".join(bounds))
    dec = _table(where, "dignities.decans", t.get("decans", {}))
    decan_scheme = _choice(where, "dignities.decans.scheme", dec.get("scheme", "chaldean"), DECAN_SCHEMES)
    decans = {
        sign: _names(where, f"dignities.decans.{sign}", rulers, SEVEN)
        for sign, rulers in dec.items()
        if sign != "scheme"
    }
    bad_signs = [s for s in decans if s not in SIGN_KEYS]
    if bad_signs:
        raise _err(where, f"dignities.decans: unknown sign(s) {', '.join(bad_signs)}")
    return Dignities(
        cite=_cite(t),
        domicile={str(k): str(v) for k, v in dom.items()},
        exaltation=exalt,
        triplicity=trip,
        bounds=bounds,
        bounds_scheme=scheme,
        decan_scheme=decan_scheme,
        decans=decans,
        twelfth_parts=_twelfth(where, t.get("twelfth_parts")),
        proper_face=bool(t.get("proper_face", False)),
    )


def _twelfth(where: str, value: Any) -> int:
    if value is None:
        return 0
    t = _table(where, "dignities.twelfth_parts", value)
    m = t.get("multiplier", 12)
    if m not in (12, 13):
        raise _err(where, f"dignities.twelfth_parts.multiplier must be 12 or 13, not {m!r}")
    return int(m)


def _phase(where: str, t: dict[str, Any]) -> Phase:
    unknown = set(t) - {f.name for f in fields(Phase)}
    if unknown:
        raise _err(where, f"phase: unknown key(s) {', '.join(sorted(unknown))}")
    motion = _table(where, "phase.mean_motion", t.get("mean_motion", {}))
    bad = [k for k in motion if k not in SEVEN]
    if bad:
        raise _err(where, f"phase.mean_motion: unknown planet(s) {', '.join(bad)}")
    return Phase(
        cite=_cite(t),
        under_beams=_number(where, "phase.under_beams", t.get("under_beams", 15), 0, 30),
        weak_within=_number(where, "phase.weak_within", t.get("weak_within", 0), 0, 30),
        heart=_number(where, "phase.heart", t.get("heart", 0), 0, 5),
        heliacal_days=int(_number(where, "phase.heliacal_days", t.get("heliacal_days", 0), 0, 60)),
        visible_beyond=_number(where, "phase.visible_beyond", t.get("visible_beyond", 15), 0, 30),
        chariot=_names(where, "phase.chariot", t.get("chariot", []), CHARIOT_DIGNITIES),
        stationary_ratio=_number(where, "phase.stationary_ratio", t.get("stationary_ratio", 0), 0, 1),
        mean_motion={k: _number(where, f"phase.mean_motion.{k}", v, 0, 20) for k, v in motion.items()},
    )


def _points(where: str, key: str, value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) != 2 or not all(isinstance(v, str) for v in value):
        raise _err(where, f'{key} must be two points, e.g. ["sun", "moon"]')
    return tuple(value)


def _lot_rule(where: str, name: str, t: dict[str, Any], top: bool = True) -> LotRule:
    key = f"lots.{name}"
    versions: dict[str, LotRule] = {}
    by_sex: dict[str, LotRule] = {}
    if top:
        for sex, v in _table(where, f"{key}.by_sex", t.get("by_sex", {})).items():
            if sex not in SEXES:
                raise _err(where, f"{key}.by_sex: {sex!r} isn't male or female")
            by_sex[sex] = _lot_rule(where, f"{name}.{sex}", _table(where, f"{key}.by_sex.{sex}", v), top=False)
        for k, v in t.items():
            if k not in LOT_KEYS:
                if not isinstance(v, dict):
                    raise _err(where, f"{key}: unknown key {k!r}", fix="keys: " + ", ".join(sorted(LOT_KEYS)))
                versions[k] = _lot_rule(where, f"{name}.{k}", v, top=False)
    fb = t.get("fallback")
    fallback = None
    if fb is not None:
        fbt = _table(where, f"{key}.fallback", fb)
        fallback = Fallback(
            str(fbt.get("when", "")),
            _points(where, f"{key}.fallback.points", fbt.get("points")),
            bool(fbt.get("reverse", False)),
        )
    has_points = "points" in t
    has_day_night = "day" in t or "night" in t
    if top and not t.get("version") and not by_sex and not (has_points or has_day_night):
        raise _err(where, f"{key} needs points (or day and night)")
    return LotRule(
        name=name,
        cite=_cite(t),
        points=_points(where, f"{key}.points", t["points"]) if has_points else (),
        day=_points(where, f"{key}.day", t["day"]) if "day" in t else (),
        night=_points(where, f"{key}.night", t["night"]) if "night" in t else (),
        reverse=bool(t.get("reverse", False)),
        project_from=str(t.get("project_from", "asc")),
        distance=_choice(where, f"{key}.distance", t.get("distance", "zodiacal"), DISTANCES),
        fallback=fallback,
        version=str(t.get("version", "")),
        versions=versions,
        variants={str(k): str(v) for k, v in _table(where, f"{key}.variants", t.get("variants", {})).items()},
        by_sex=by_sex,
    )


def _condition(where: str, name: str, t: dict[str, Any]) -> ConditionRule:
    key = f"conditions.{name}"
    unknown = set(t) - CONDITION_KEYS
    if unknown:
        raise _err(
            where,
            f"{key}: unknown key(s) {', '.join(sorted(unknown))}",
            fix="keys: " + ", ".join(sorted(CONDITION_KEYS)),
        )
    kind = _choice(where, f"{key}.kind", t.get("kind"), CONDITION_KINDS)

    def aspects(field_name: str) -> tuple[str, ...]:
        value = t.get(field_name, [])
        if not isinstance(value, list) or not all(isinstance(a, str) for a in value):
            raise _err(where, f"{key}.{field_name} must be a list of aspects")
        bad = [a for a in value if a not in ASPECTS]
        if bad:
            raise _err(where, f"{key}.{field_name}: unknown aspects {', '.join(bad)}")
        return tuple(value)

    def places(field_name: str) -> tuple[int, ...]:
        value = t.get(field_name, [])
        if not isinstance(value, list) or not all(isinstance(n, int) and 1 <= n <= 12 for n in value):
            raise _err(where, f"{key}.{field_name} must be a list of place numbers 1–12")
        return tuple(value)

    return ConditionRule(
        name=name,
        kind=kind,
        cite=_cite(t),
        bonify=aspects("bonify"),
        maltreat=aspects("maltreat"),
        orb=_number(where, f"{key}.orb", t.get("orb", 3), 0, 30),
        moon_orb=_number(where, f"{key}.moon_orb", t.get("moon_orb", 0), 0, 30),
        direction=_choice(where, f"{key}.direction", t.get("direction", "any"), DIRECTIONS),
        applying=bool(t.get("applying", False)),
        side=_choice(where, f"{key}.side", t.get("side", "any"), SIDES),
        rays=aspects("rays"),
        body_orb=_number(where, f"{key}.body_orb", t.get("body_orb", 0), 0, 30),
        maltreat_places=places("maltreat_places"),
        bonify_places=places("bonify_places"),
        note=str(t.get("note", "")),
    )


def _places(where: str, t: dict[str, Any]) -> Places:
    def ints(key: str) -> tuple[int, ...]:
        v = t.get(key, [])
        if not isinstance(v, list) or not all(isinstance(x, int) for x in v):
            raise _err(where, f"places.{key} must be a list of place numbers")
        return tuple(v)

    joys = _table(where, "places.joys", t.get("joys", {}))
    for planet, place in joys.items():
        if planet not in SEVEN or not isinstance(place, int):
            raise _err(where, f"places.joys: {planet} = {place!r} isn't a planet and a place number")
    busy_by = t.get("busy_by_angle", {})
    busy_t = _table(where, "places.busy_by_angle", busy_by) if busy_by else {}
    return Places(
        _cite(t), ints("good"), ints("bad"), ints("busy"), {str(k): int(v) for k, v in joys.items()},
        angle_degrees=bool(t.get("angle_degrees", False)),
        busy_by_angle=_names(where, "places.busy_by_angle.aspects", busy_t.get("aspects", []), tuple(ASPECTS))
        if busy_t
        else (),
        busy_by_angle_orb=_number(where, "places.busy_by_angle.orb", busy_t.get("orb", 3.0), 0, 15),
        quadrant=_choice(where, "places.quadrant", t.get("quadrant", ""), QUADRANTS),
    )  # fmt: skip


def _configs(where: str, t: dict[str, Any]) -> Configs:
    unknown = set(t) - {"cite", "assembly", "void_range"}
    if unknown:
        raise _err(where, f"configurations: unknown key(s) {', '.join(sorted(unknown))}")
    return Configs(
        _cite(t),
        _number(where, "configurations.assembly", t.get("assembly", 0), 0, 30),
        _number(where, "configurations.void_range", t.get("void_range", 0), 0, 60),
    )


TIMING_KEYS = {
    "profections": {"cite", "starts", "step_signs", "planets_in_sign"},
    "releasing": {
        "cite",
        "lots",
        "year_days",
        "periods",
        "levels",
        "peaks",
        "loosing_of_bond",
        "same_sign_shift",
        "ruler_sign",
    },
    "transits": {"cite", "kinds"},
    "periods": {"cite", "minor_years"},
    "sect_light": {"cite", "quality", "changeover"},
}
TRANSIT_KINDS = ("ingress", "sign_configurations", "exact")
CHANGEOVERS = ("minor_years", "ascensional_time")
ANGULARITY_QUALITY = ("good", "middling", "bad")
_START = re.compile(
    r"^(asc|sect_light|contrary_light|sun|moon|mercury|venus|mars|jupiter|saturn|lot:[a-z_]+|place:\d{1,2})$"
)


@dataclass(frozen=True)
class Timing:
    profections: Profections | None = None
    releasing: Releasing | None = None
    transits: TimingTransits | None = None
    periods: Periods | None = None
    sect_light: SectLightLords | None = None


def _timing(where: str, t: dict[str, Any]) -> Timing:
    unknown = set(t) - set(TIMING_KEYS)
    if unknown:
        raise _err(where, f"timing: unknown section(s) {', '.join(sorted(unknown))}", fix=", ".join(TIMING_KEYS))
    tables = {}
    for name, keys in TIMING_KEYS.items():
        if name in t:
            tables[name] = _table(where, f"timing.{name}", t[name])
            extra = set(tables[name]) - keys
            if extra:
                raise _err(where, f"timing.{name}: unknown key(s) {', '.join(sorted(extra))}")
    out: dict[str, Any] = {}
    if "profections" in tables:
        p = tables["profections"]
        starts = tuple(str(x) for x in p.get("starts", ["asc"]))
        bad = [x for x in starts if not _START.match(x)]
        if bad:
            raise _err(where, f"timing.profections.starts: unknown {', '.join(bad)}")
        out["profections"] = Profections(
            _cite(p),
            starts,
            int(_number(where, "timing.profections.step_signs", p.get("step_signs", 1), 1, 12)),
            bool(p.get("planets_in_sign", False)),
        )
    if "releasing" in tables:
        r = tables["releasing"]
        periods = _table(where, "timing.releasing.periods", r.get("periods", {}))
        bad = [s for s in periods if s not in SIGN_KEYS]
        if bad:
            raise _err(where, f"timing.releasing.periods: unknown sign(s) {', '.join(bad)}")
        peaks = r.get("peaks", [])
        if not isinstance(peaks, list) or not all(isinstance(n, int) and 1 <= n <= 12 for n in peaks):
            raise _err(where, "timing.releasing.peaks must be place numbers counted from Fortune, strongest first")
        out["releasing"] = Releasing(
            _cite(r),
            tuple(str(x) for x in r.get("lots", ["fortune", "spirit"])),
            _number(where, "timing.releasing.year_days", r.get("year_days", 360), 300, 400),
            {s: _number(where, f"timing.releasing.periods.{s}", v, 0, 1000) for s, v in periods.items()},
            int(_number(where, "timing.releasing.levels", r.get("levels", 2), 1, 4)),
            tuple(peaks),
            bool(r.get("loosing_of_bond", False)),
            bool(r.get("same_sign_shift", False)),
            bool(r.get("ruler_sign", False)),
        )
    if "transits" in tables:
        tr = tables["transits"]
        out["transits"] = TimingTransits(
            _cite(tr), _names(where, "timing.transits.kinds", tr.get("kinds", []), TRANSIT_KINDS)
        )
    if "periods" in tables:
        pe = tables["periods"]
        years = _table(where, "timing.periods.minor_years", pe.get("minor_years", {}))
        bad = [k for k in years if k not in SEVEN]
        if bad:
            raise _err(where, f"timing.periods.minor_years: unknown planet(s) {', '.join(bad)}")
        out["periods"] = Periods(
            _cite(pe), {k: _number(where, f"timing.periods.minor_years.{k}", v, 1, 200) for k, v in years.items()}
        )
    if "sect_light" in tables:
        sl = tables["sect_light"]
        quality = _table(where, "timing.sect_light.quality", sl.get("quality", {}))
        for k, v in quality.items():
            if k not in ("angular", "succedent", "declining") or v not in ANGULARITY_QUALITY:
                raise _err(
                    where,
                    f"timing.sect_light.quality: {k} = {v!r}",
                    fix="angular/succedent/declining = good/middling/bad",
                )
        out["sect_light"] = SectLightLords(
            _cite(sl),
            {str(k): str(v) for k, v in quality.items()},
            _names(where, "timing.sect_light.changeover", sl.get("changeover", []), CHANGEOVERS),
        )
    return Timing(**out)


TOPIC_KEYS = {"label", "cite", "places", "significators", "lots", "degrees"}


def _topic(where: str, name: str, t: dict[str, Any]) -> Topic:
    key = f"topics.{name}"
    unknown = set(t) - TOPIC_KEYS
    if unknown:
        raise _err(
            where, f"{key}: unknown key(s) {', '.join(sorted(unknown))}", fix="keys: " + ", ".join(sorted(TOPIC_KEYS))
        )
    places = t.get("places", [])
    if not isinstance(places, list) or not all(isinstance(n, int) and 1 <= n <= 12 for n in places):
        raise _err(where, f"{key}.places must be place numbers 1–12")
    return Topic(
        name,
        str(t.get("label", name.replace("_", " ").title())),
        _cite(t),
        tuple(places),
        _names(where, f"{key}.significators", t.get("significators", []), SEVEN),
        tuple(str(x) for x in t.get("lots", [])),
        _names(where, f"{key}.degrees", t.get("degrees", []), ("mc", "ic")),
    )


def parse_doctrine(raw: dict[str, Any], where: str) -> Doctrine | None:
    """The pack's doctrine sections, or None when it has none."""
    if not any(
        k in raw
        for k in ("sect", "dignities", "phase", "lots", "conditions", "places", "timing", "scoring", "topics",
                  "configurations")
    ):  # fmt: skip
        return None
    lots_t = _table(where, "lots", raw.get("lots", {}))
    lot_rules = {
        name: _lot_rule(where, name, _table(where, f"lots.{name}", t))
        for name, t in lots_t.items()
        if isinstance(t, dict)
    }
    conds = {
        name: _condition(where, name, _table(where, f"conditions.{name}", t))
        for name, t in _table(where, "conditions", raw.get("conditions", {})).items()
    }
    timing = _timing(where, _table(where, "timing", raw.get("timing", {})))
    scoring = None
    if "scoring" in raw:
        st = _table(where, "scoring", raw["scoring"])
        lots_t = _table(where, "scoring.lots", st.get("lots", {}))
        weights = _table(where, "scoring.weights", st.get("weights", {}))
        bad_weights = [k for k in weights if k not in PLANET_TOKENS]
        if bad_weights:
            raise _err(where, f"scoring.weights: unknown finding(s) {', '.join(bad_weights)}")
        scoring = Scoring(
            _cite(st),
            _choice(where, "scoring.mode", st.get("mode", "testimonies"), SCORING_MODES),
            _names(where, "scoring.good", st.get("good", []), PLANET_TOKENS),
            _names(where, "scoring.bad", st.get("bad", []), PLANET_TOKENS),
            {str(k): _number(where, f"scoring.weights.{k}", v, -100, 100) for k, v in weights.items()},
            _names(where, "scoring.lots.good", lots_t.get("good", []), LOT_TOKENS),
            _names(where, "scoring.lots.bad", lots_t.get("bad", []), LOT_TOKENS),
        )
    return Doctrine(
        cited=raw.get("cited", True) is not False,
        sect=_sect(where, _table(where, "sect", raw["sect"])) if "sect" in raw else None,
        dignities=_dignities(where, _table(where, "dignities", raw["dignities"])) if "dignities" in raw else None,
        phase=_phase(where, _table(where, "phase", raw["phase"])) if "phase" in raw else None,
        lots=lot_rules,
        conditions=conds,
        places=_places(where, _table(where, "places", raw["places"])) if "places" in raw else None,
        profections=timing.profections,
        releasing=timing.releasing,
        transits=timing.transits,
        periods=timing.periods,
        sect_light=timing.sect_light,
        scoring=scoring,
        topics={
            name: _topic(where, name, _table(where, f"topics.{name}", t))
            for name, t in _table(where, "topics", raw.get("topics", {})).items()
        },
        configs=_configs(where, _table(where, "configurations", raw["configurations"]))
        if "configurations" in raw
        else None,
    )


# ── checks ────────────────────────────────────────────────────────────────────


def _check_point(point: str, lots: dict[str, LotRule]) -> str | None:
    """None if the point is resolvable, else what's wrong."""
    if not _POINT.match(point):
        return f"{point!r} isn't a point"
    if point.startswith("lot:"):
        return None if point[4:] in lots else f"lot {point[4:]!r} isn't defined"
    if point.startswith("sign:"):
        return None if point[5:] in SIGN_KEYS else f"unknown sign in {point!r}"
    if point.startswith(("place:", "ruler:place:")):
        n = int(point.rsplit(":", 1)[1])
        return None if 1 <= n <= 12 else f"place number out of range in {point!r}"
    return None if point in (*SEVEN, "asc", "mc", "north_node", "south_node") else f"unknown point {point!r}"


def _lot_cycles(lots: dict[str, LotRule]) -> list[str]:
    deps = {name: {p[4:] for p in rule.all_points() if p.startswith("lot:")} for name, rule in lots.items()}
    cyclic: list[str] = []
    for start in deps:
        stack, seen = list(deps[start]), set()
        while stack:
            node = stack.pop()
            if node == start:
                cyclic.append(start)
                break
            if node in seen or node not in deps:
                continue
            seen.add(node)
            stack.extend(deps[node])
    return cyclic


def check_doctrine(d: Doctrine) -> list[Problem]:
    out: list[Problem] = []

    def err(where: str, msg: str, fix: str = "") -> None:
        out.append(Problem("error", where, msg, fix))

    def warn(where: str, msg: str, fix: str = "") -> None:
        out.append(Problem("warn", where, msg, fix))

    cite_fix = 'add cite = "p. …" with the source\'s printed pages'
    for name in (() if not d.cited else (
        "sect", "dignities", "phase", "places", "profections", "releasing", "transits", "periods", "sect_light",
        "scoring",
    )):  # fmt: skip
        part = getattr(d, name)
        if part is not None and not part.cite:
            warn(name, "no citation", cite_fix)
    for name, lot in d.lots.items():
        if d.cited and not lot.cite:
            warn(f"lots.{name}", "no citation", cite_fix)
    for name, cond in d.conditions.items():
        if d.cited and not cond.cite:
            warn(f"conditions.{name}", "no citation", cite_fix)

    if d.sect is not None:
        both = set(d.sect.diurnal) & set(d.sect.nocturnal)
        if both:
            err("sect", f"listed as both diurnal and nocturnal: {', '.join(sorted(both))}")

    g = d.dignities
    if g is not None:
        if g.domicile and set(g.domicile) != set(SIGN_KEYS):
            missing = [s for s in SIGN_KEYS if s not in g.domicile]
            err("dignities.domicile", f"missing {', '.join(missing)}", "every sign needs its domicile lord")
        for scheme, table in g.bounds.items():
            where = f"dignities.bounds.{scheme}"
            if set(table) != set(SIGN_KEYS):
                err(where, "must list all twelve signs")
            totals = dict.fromkeys(FIVE, 0.0)
            for sign, rows in table.items():
                planets = [p for p, _ in rows]
                ends = [e for _, e in rows]
                if sorted(planets) != sorted(FIVE):
                    err(f"{where}.{sign}", "needs each of Mercury, Venus, Mars, Jupiter and Saturn exactly once")
                if any(b <= a for a, b in zip([0.0, *ends], ends, strict=False)) or (ends and ends[-1] != 30):
                    err(f"{where}.{sign}", "end degrees must rise and finish at 30")
                prev = 0.0
                for planet, end in rows:
                    if planet in totals:
                        totals[planet] += end - prev
                    prev = end
            if scheme == "egyptian" and set(table) == set(SIGN_KEYS):
                off = {p: t for p, t in totals.items() if abs(t - EGYPTIAN_TOTALS[p]) > 1e-9}
                if off:
                    shown = ", ".join(f"{p} {t:g} (expected {EGYPTIAN_TOTALS[p]})" for p, t in off.items())
                    warn(where, f"planet totals differ from the classical years: {shown}", "re-check the transcription")
        for element, rulers in g.triplicity.items():
            if len(rulers) != 3 or len(set(rulers)) != 3:
                err(f"dignities.triplicity.{element}", "needs three different planets: day, night, participating")
        if g.triplicity and set(g.triplicity) != set(ELEMENTS):
            err("dignities.triplicity", "must list fire, earth, air and water")
        if g.decan_scheme == "table" and (
            set(g.decans) != set(SIGN_KEYS) or any(len(v) != 3 for v in g.decans.values())
        ):
            err("dignities.decans", "a decan table needs three planets for each of the twelve signs")

    if d.phase is not None:
        ph = d.phase
        if ph.weak_within and ph.weak_within > ph.under_beams:
            err("phase.weak_within", "must be inside the under-the-beams orb")
        if ph.heart and ph.heart > (ph.weak_within or ph.under_beams):
            err("phase.heart", "must be inside the under-the-beams orb")
        if "bounds" in ph.chariot and d.dignities is not None and not d.dignities.bounds:
            err("phase.chariot", "lists bounds but [dignities] has no bounds table")

    for name, lot in d.lots.items():
        for rule in (lot, *lot.versions.values()):
            if rule.fallback and not _FALLBACK_WHEN.match(rule.fallback.when):
                err(f"lots.{name}.fallback", f"unknown condition {rule.fallback.when!r}", 'use "<planet>_under_beams"')
        if lot.version and lot.version not in lot.versions:
            err(f"lots.{name}.version", f"no version called {lot.version!r}", "versions: " + ", ".join(lot.versions))
        for point in lot.all_points():
            problem = _check_point(point, d.lots)
            if problem:
                err(f"lots.{name}", problem)
    for name in _lot_cycles(d.lots):
        err(f"lots.{name}", "its formula depends on itself through other lots")

    for name, topic in d.topics.items():
        if not (topic.places or topic.significators or topic.lots):
            err(f"topics.{name}", "needs places, significators or lots")
        missing = [x for x in topic.lots if x not in d.lots]
        if missing:
            err(f"topics.{name}.lots", f"not defined in [lots]: {', '.join(missing)}")
        if d.cited and not topic.cite:
            warn(f"topics.{name}", "no citation", cite_fix)
    for name, cond in d.conditions.items():
        if cond.kind in ("overcoming", "sign_aspect", "degree_aspect") and not (cond.bonify or cond.maltreat):
            err(f"conditions.{name}", "needs bonify and/or maltreat aspects")
        if cond.kind == "overcoming":
            wrong = [a for a in (*cond.bonify, *cond.maltreat) if a not in ("sextile", "square", "trine")]
            if wrong:
                err(f"conditions.{name}", f"overcoming is only by sextile, square or trine, not {', '.join(wrong)}")
        if cond.kind == "counteraction" and not (cond.bonify_places or cond.maltreat_places):
            err(f"conditions.{name}", "needs maltreat_places and/or bonify_places")
    if d.scoring is not None and d.scoring.mode == "weights" and not d.scoring.weights:
        err("scoring.weights", 'mode "weights" needs weights')
    both = set(d.scoring.good) & set(d.scoring.bad) if d.scoring else set()
    if both:
        err("scoring", f"listed as both good and bad: {', '.join(sorted(both))}")

    if d.places is not None:
        for key in ("good", "bad", "busy"):
            bad = [n for n in getattr(d.places, key) if not 1 <= n <= 12]
            if bad:
                err(f"places.{key}", f"place numbers must be 1–12, not {bad}")
        bad_joys = {p: n for p, n in d.places.joys.items() if not 1 <= n <= 12}
        if bad_joys:
            err("places.joys", f"place numbers must be 1–12: {bad_joys}")

    needs_years = d.sect_light is not None and "minor_years" in d.sect_light.changeover
    if needs_years and (d.periods is None or set(d.periods.minor_years) != set(SEVEN)):
        err("timing.sect_light.changeover", "minor_years needs [timing.periods] minor_years for all seven planets")

    if d.releasing is not None:
        if set(d.releasing.periods) != set(SIGN_KEYS):
            err("timing.releasing.periods", "needs a period for each of the twelve signs")
        if d.releasing.peaks and len(set(d.releasing.peaks)) != len(d.releasing.peaks):
            err("timing.releasing.peaks", "lists a place twice")
        unknown = [lot for lot in d.releasing.lots if lot not in d.lots]
        if unknown and d.lots:
            err("timing.releasing.lots", f"not defined in [lots]: {', '.join(unknown)}")
    return out
