"""Cast a chart: one Astrolog call (pinned settings + AstroExpressions) → ChartModel."""

from __future__ import annotations

from pathlib import Path

from astrolog_skills.astrolog import locate
from astrolog_skills.astrolog.run import INSTALL_FIX, expressions
from astrolog_skills.engine.model import ChartModel, Point
from astrolog_skills.engine.moment import Moment
from astrolog_skills.engine.objects import BY_KEY, Obj
from astrolog_skills.engine.profile import Profile, active, pins
from astrolog_skills.errors import AstroError

AYANAMSA_TOLERANCE = 0.01  # degrees between the expected and the applied sidereal offset
PER_OBJECT = ("ObjLon", "ObjLat", "ObjDir", "ObjHouse")


def binary_or_raise() -> Path:
    found = locate.find()
    if not found:
        raise AstroError("Astrolog isn't installed or configured.", fix=INSTALL_FIX)
    return found.path


def expression_list(objects: list[Obj]) -> list[str]:
    exprs = [f"{fn} O_{o.code}" for o in objects if o.code for fn in PER_OBJECT]
    exprs += [f"Cusp {n}" for n in range(1, 13)]
    exprs += ["ObjLon O_Asc", "ObjLon O_Mid", "_s1"]
    return exprs


def cast(moment: Moment, profile: Profile | None = None, binary: Path | None = None) -> ChartModel:
    profile = profile or active()
    binary = binary or binary_or_raise()
    objects = profile.object_list
    values = iter(expressions(binary, moment.cast_args() + pins(profile), expression_list(objects)))

    points: list[Point] = []
    for o in objects:
        if not o.code:
            continue
        lon, lat, speed, house = next(values), next(values), next(values), next(values)
        points.append(Point(o.key, o.name, o.glyph, lon, lat, speed, int(house) or None))
    cusps = [round(next(values) % 360, 6) for _ in range(12)]
    asc, mc, applied_offset = next(values), next(values), next(values)

    if any(o.key == "south_node" for o in objects):
        north = next(p for p in points if p.key == "north_node")
        south = BY_KEY["south_node"]
        south_house = ((north.house + 5) % 12) + 1 if north.house else None
        points.insert(
            points.index(north) + 1,
            Point(south.key, south.name, south.glyph, north.lon + 180, -north.lat, north.speed, south_house),
        )

    info = profile.ayanamsa_info()
    if info and abs(applied_offset - info[1]) > AYANAMSA_TOLERANCE:
        raise AstroError(
            f"Astrolog applied a sidereal offset of {applied_offset:+.6f}°, "
            f"not the {info[2]} ayanamsa ({info[1]:+.6f}°).",
            fix="please report this with `astro astrolog info`; meanwhile use a numeric ayanamsa in your profile",
        )

    version = locate.version(binary)
    return ChartModel(
        name=moment.name,
        moment=moment.to_dict(),
        profile=profile.to_dict(),
        points=points,
        cusps=cusps,
        angles={
            "asc": round(asc % 360, 6),
            "mc": round(mc % 360, 6),
            "dsc": round((asc + 180) % 360, 6),
            "ic": round((mc + 180) % 360, 6),
        },
        astrolog={"path": str(binary), "version": locate.version_text(version)},
    )
