"""Batch: read Astrolog's chart-list listing (`-5e -b0`) into light chart records for research.

One Astrolog run prints thousands of charts (3,825 in 0.9 s, measured); rows carry arc-second positions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from astrolog_skills.astrolog.run import run
from astrolog_skills.engine.cast import binary_or_raise
from astrolog_skills.engine.objects import BY_BATCH_LABEL
from astrolog_skills.engine.profile import Profile, active, pins
from astrolog_skills.engine.zodiac import SIGN_ABBR

BATCH_TIMEOUT = 600
ANGLE_LABELS = {"Asce": "asc", "Midh": "mc"}

_HEADER = re.compile(r"^Astrolog \d+\.\d+(?: chart for (?P<name>.*)|: (?P<when>.*))$")
_ROW = re.compile(
    r"^(?P<label>\w{3,4}) ?:\s*(?P<deg>\d+)(?P<sign>[A-Z][a-z]{2})(?P<min>\d+)'(?P<sec>\d+)\"\s+(?P<retro>R?)\s*"
    r"(?P<latsign>[+-])\s*(?P<latd>\d+):(?P<latm>\d+)'(?P<lats>\d+)\"\s+(?:\(.\)\s+)?"
    r"\[\s*(?P<house>\d+)\w\w house\]\s+(?:\[.\]\s+)?(?P<speed>[+-]\d+(?:\.\d+)?)"
)


@dataclass
class BatchChart:
    name: str
    header: str = ""
    points: dict[str, dict[str, Any]] = field(default_factory=dict)
    angles: dict[str, float] = field(default_factory=dict)

    def lon(self, key: str) -> float:
        return float(self.points[key]["lon"])


def _row(m: re.Match[str]) -> dict[str, Any]:
    lon = SIGN_ABBR.index(m["sign"]) * 30 + int(m["deg"]) + int(m["min"]) / 60 + int(m["sec"]) / 3600
    lat = int(m["latd"]) + int(m["latm"]) / 60 + int(m["lats"]) / 3600
    return {
        "lon": round(lon, 6),
        "lat": round(-lat if m["latsign"] == "-" else lat, 6),
        "speed": float(m["speed"]),
        "retrograde": m["retro"] == "R",
        "house": int(m["house"]),
    }


def parse(text: str) -> list[BatchChart]:
    charts: list[BatchChart] = []
    current: BatchChart | None = None
    expect_header_line = False
    for line in text.splitlines():
        if h := _HEADER.match(line):
            current = BatchChart(name=(h["name"] or "").strip(), header=(h["when"] or "").strip())
            charts.append(current)
            expect_header_line = h["name"] is not None
            continue
        if current is None:
            continue
        if expect_header_line and line.strip():
            current.header = line.strip()
            expect_header_line = False
            continue
        if (m := _ROW.match(line)) and m["sign"] in SIGN_ABBR:
            row = _row(m)
            if m["label"] in ANGLE_LABELS:
                current.angles[ANGLE_LABELS[m["label"]]] = row["lon"]
            elif obj := BY_BATCH_LABEL.get(m["label"]):
                current.points[obj.key] = row
    for chart in charts:
        north = chart.points.get("north_node")
        if north:
            chart.points["south_node"] = {
                **north,
                "lon": round((north["lon"] + 180) % 360, 6),
                "lat": -north["lat"],
                "house": (north["house"] + 5) % 12 + 1,
            }
    return charts


def batch(list_args: list[str], profile: Profile | None = None, binary: Path | None = None) -> list[BatchChart]:
    """Run Astrolog over a chart list (e.g. `["-Y5i", ">AA<", "-i", "file.xml"]`) with the profile pinned."""
    profile = profile or active()
    argv = [*pins(profile, extra_codes=("Asc", "Mid")), *list_args, "-5e", "-b0"]  # angles get their own rows
    done = run(binary or binary_or_raise(), argv, timeout=BATCH_TIMEOUT)
    return parse(done.stdout)
