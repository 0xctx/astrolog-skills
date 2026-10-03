"""SetRecord: one chart in a research set, already resolved to UT (whatever its source)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SetRecord:
    id: str
    name: str
    utc: datetime
    lat: float
    lon: float
    place: str = ""
    rating: str = ""
    gender: str = ""
    datatype: str = ""
    categories: list[str] = field(default_factory=list)
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["utc"] = self.utc.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SetRecord:
        return cls(**{**d, "utc": datetime.fromisoformat(d["utc"])})
