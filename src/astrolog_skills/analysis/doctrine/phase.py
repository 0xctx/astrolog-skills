"""Solar phase: distance from the Sun, under the beams, in the heart, chariot, morning/evening, heliacal, speed."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from astrolog_skills.analysis.doctrine.dignities import PlanetDignities
from astrolog_skills.analysis.doctrine.rules import Phase
from astrolog_skills.analysis.doctrine.sect import morning_star

# Mean daily motions (°/day), astronomical facts; the inner planets' mean motion is the Sun's.
MEAN_MOTION = {
    "sun": 0.9856,
    "moon": 13.1764,
    "mercury": 0.9856,
    "venus": 0.9856,
    "mars": 0.5240,
    "jupiter": 0.0831,
    "saturn": 0.0335,
}
STARS = ("mercury", "venus", "mars", "jupiter", "saturn")


def separation(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


@dataclass(frozen=True)
class PlanetPhase:
    distance: float | None  # from the Sun, shortest arc; None for the Sun
    under_beams: bool = False
    weak: bool = False  # inside the stricter "especially within" zone
    in_heart: bool = False
    chariot: tuple[str, ...] = ()  # the dignities that make its own chariot
    star: str = ""  # "morning" | "evening"
    visible: bool = False  # beyond the visibility distance
    heliacal: str = ""  # "emerging" | "sinking" within the pack's days
    speed_ratio: float | None = None
    speed: str = ""  # "additive" | "subtractive" | "stationary"
    retrograde: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def labels(self) -> list[str]:
        out = []
        if self.in_heart:
            out.append("in the heart")
        elif self.under_beams:
            out.append("under the beams" + (" (close)" if self.weak else ""))
        if self.chariot:
            out.append("in its chariot")
        if self.star:
            out.append(f"{self.star} {'riser' if self.visible else 'star'}")
        if self.heliacal:
            out.append(f"heliacal: {self.heliacal}")
        if self.retrograde:
            out.append("retrograde")
        elif self.speed:
            out.append(self.speed)
        return out


def planet_phase(
    planet: str,
    lon: float,
    speed: float,
    sun: float,
    rules: Phase,
    dignities: PlanetDignities | None,
    later: tuple[float, float] | None = None,  # (planet, sun) longitudes rules.heliacal_days later
) -> PlanetPhase:
    mean = rules.mean_motion.get(planet, MEAN_MOTION.get(planet, 0.0))
    ratio = abs(speed) / mean if mean else None
    pace = ""
    if ratio is not None:
        if rules.stationary_ratio and ratio < rules.stationary_ratio:
            pace = "stationary"
        else:
            pace = "additive" if ratio >= 1 else "subtractive"
    if planet == "sun":
        return PlanetPhase(None, speed_ratio=ratio, speed=pace)
    dist = separation(lon, sun)
    beams = dist <= rules.under_beams
    chariot: tuple[str, ...] = ()
    if beams and dignities is not None:
        held = {
            "domicile": dignities.domicile,
            "exaltation": dignities.exaltation,
            "bounds": dignities.bounds,
            "triplicity": bool(dignities.triplicity),
        }
        chariot = tuple(d for d in rules.chariot if held[d])
    star = ""
    if planet in STARS:
        star = "morning" if morning_star(lon, sun) else "evening"
    heliacal = ""
    if later is not None and rules.heliacal_days and planet in STARS:
        beams_later = separation(*later) <= rules.under_beams
        heliacal = "emerging" if beams and not beams_later else "sinking" if beams_later and not beams else ""
    return PlanetPhase(
        dist,
        under_beams=beams,
        weak=bool(rules.weak_within) and dist <= rules.weak_within,
        in_heart=bool(rules.heart) and dist <= rules.heart,
        chariot=chariot,
        star=star,
        visible=bool(star) and dist > rules.visible_beyond,
        heliacal=heliacal,
        speed_ratio=ratio,
        speed=pace,
        retrograde=speed < 0,
    )
