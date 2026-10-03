"""The chart model every other part of the toolkit reads: plain dataclasses ↔ JSON."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from astrolog_skills.engine.zodiac import degree_in_sign, format_position, norm, sign_of

SCHEMA = 1


@dataclass
class Point:
    key: str
    name: str
    glyph: str
    lon: float
    lat: float = 0.0
    speed: float = 0.0
    house: int | None = None
    retrograde: bool = False
    sign: str = ""
    degree_in_sign: float = 0.0
    text: str = ""

    def __post_init__(self) -> None:
        self.lon = round(norm(self.lon), 6)
        self.sign = sign_of(self.lon)
        self.degree_in_sign = round(degree_in_sign(self.lon), 6)
        self.text = format_position(self.lon, seconds=True)
        self.retrograde = self.speed < 0


@dataclass
class ChartModel:
    name: str
    moment: dict[str, Any]
    profile: dict[str, Any]
    points: list[Point]
    cusps: list[float]
    angles: dict[str, float]
    astrolog: dict[str, Any] = field(default_factory=dict)
    harmonic: int = 1
    schema: int = SCHEMA

    def point(self, key: str) -> Point:
        for p in self.points:
            if p.key == key:
                return p
        raise KeyError(key)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChartModel:
        points = [
            Point(**{k: v for k, v in p.items() if k in ("key", "name", "glyph", "lon", "lat", "speed", "house")})
            for p in data["points"]
        ]
        return cls(
            name=data["name"],
            moment=data["moment"],
            profile=data["profile"],
            points=points,
            cusps=list(data["cusps"]),
            angles=dict(data["angles"]),
            astrolog=dict(data.get("astrolog", {})),
            harmonic=int(data.get("harmonic", 1)),
            schema=int(data.get("schema", SCHEMA)),
        )
