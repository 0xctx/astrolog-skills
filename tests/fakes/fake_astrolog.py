"""A stand-in for the Astrolog binary: just enough behaviour for unit tests.

Mimics: the `-Hc` version banner; `-Yq<n>` cast + AstroExpression lines (values on stderr); `-R0` object
restriction (restricted objects return 0.0, like the real program); sidereal `-s <name>` shifting longitudes;
`_s1`; `Cusp n`; `-5e` chart-list listings (from FAKE_ASTROLOG_BATCH); anything else echoes its argv.

Env knobs: FAKE_ASTROLOG_VERSION (default 8.00), FAKE_ASTROLOG_BROKEN=1 (prints nothing),
FAKE_ASTROLOG_SUN (override Einstein's Sun), FAKE_ASTROLOG_S1 (override the applied sidereal offset),
FAKE_ASTROLOG_BATCH (file printed for -5e), FAKE_ASTROLOG_EXIT (exit code for echo mode).
"""

import os
import re
import sys

# code: (lon, lat, speed, house) — Einstein, from the real Astrolog 7.80
EINSTEIN = {
    "Sun": (353.507748, 0.0, 0.995957, 10),
    "Moo": (254.525911, -3.8288, 13.918897, 6),
    "Mer": (3.143611, -0.3897, 1.951887, 10),
    "Ven": (16.985, -0.6853, 1.231764, 10),
    "Mar": (296.914167, -0.8517, 0.728654, 7),
    "Jup": (327.483889, -0.7536, 0.227366, 9),
    "Sat": (4.189722, -2.1506, 0.123574, 10),
    "Ura": (151.288333, 0.7842, -0.039558, 3),
    "Nep": (37.871667, -1.7372, 0.028808, 11),
    "Plu": (54.725564, -13.6858, 0.012071, 11),
    "Chi": (35.54469, 1.0, 0.052489, 11),
    "Nor": (302.731276, 0.0, -0.019327, 8),
    "Lil": (27.976722, 2.0, 0.111593, 10),
    "Cer": (47.331976, 3.0, 0.25, 11),
    "Pal": (10.0, 4.0, 0.2, 10),
    "Jun": (20.0, 5.0, 0.21, 10),
    "Ves": (30.0, 6.0, 0.22, 11),
    "For": (2.664558, 0.0, 0.0, 10),
    "Ver": (237.905049, 0.0, 0.0, 5),
    "Asc": (101.646405, 0.0, 297.4418, 1),
    "Mid": (342.839865, 0.0, 388.07619, 10),
}
NOW = {"Sun": (186.77, 0.0, 0.98, 7), "Moo": (48.38, 2.0, 12.5, 2), "Asc": (103.85, 0.0, 300.0, 1)}
DEFAULT_ENABLED = {"Sun", "Moo", "Mer", "Ven", "Mar", "Jup", "Sat", "Ura", "Nep", "Plu", "Nor"}
AYANAMSA = {
    "Fagan": 0.0,
    "Lahiri": 0.883208,
    "Krishnamurti": 0.98006,
    "Raman": 2.329509,
    "Yukteshwar": 2.261497,
    "DeLuce": -3.075453,
    "Djwhal": -3.619379,
    "Usha-Shasi": 4.682759,
    "Galactic": -2.105736,
}
FAGAN_1879 = 23.0  # any consistent shift: sidereal longitude = tropical − (FAGAN_1879 + offset)


def _enabled(tokens: list[str]) -> set[str]:
    if "-R0" not in tokens:
        return set(DEFAULT_ENABLED)
    start = tokens.index("-R0") + 1
    names = []
    for tok in tokens[start:]:
        if tok[:1] in "-=_":
            break
        names.append(tok)
    return set(names)


def _evaluate(cast: str, expr: str) -> float:
    tokens = cast.split()
    table = dict(EINSTEIN if " 1879 " in f" {cast} " else NOW)
    if "FAKE_ASTROLOG_SUN" in os.environ:
        sun = table["Sun"]
        table["Sun"] = (float(os.environ["FAKE_ASTROLOG_SUN"]), *sun[1:])
    sidereal = "-s" in tokens
    offset = AYANAMSA.get(tokens[tokens.index("-s") + 1], 0.0) if sidereal else 0.0  # unknown names → Fagan
    if "FAKE_ASTROLOG_S1" in os.environ:
        offset = float(os.environ["FAKE_ASTROLOG_S1"])
    shift = FAGAN_1879 + offset if sidereal else 0.0
    enabled = _enabled(tokens) | {"Asc", "Mid"}
    parts = expr.split()
    if parts == ["_s1"]:
        return offset if sidereal else 0.0
    if parts[0] == "Cusp":
        asc = table.get("Asc", (0.0,))[0]
        return (asc - shift + 30 * (int(parts[1]) - 1)) % 360
    fn, obj = parts[0], parts[-1].removeprefix("O_")
    if obj not in table or obj not in enabled:
        return 0.0
    lon, lat, speed, house = table[obj]
    return {"ObjLon": (lon - shift) % 360, "ObjLat": lat, "ObjDir": speed, "ObjHouse": float(house)}.get(fn, 0.0)


SIGNS = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
LABELS = ["Sun ", "Moon", "Merc", "Venu", "Mars", "Jupi", "Satu", "Uran", "Nept", "Plut", "Chir", "Nort"]


def _positions(day: float) -> list[float]:
    """Toy astronomy, deterministic: rough mean motions, with Mercury and Venus tied to the Sun like the real sky."""
    import math

    sun = day * 0.9856
    return [
        sun,
        day * 13.176,
        sun + 22 * math.sin(day * 0.0712),
        sun + 44 * math.sin(day * 0.0161),
        day * 0.524,
        day * 0.0831,
        day * 0.0335,
        day * 0.0117,
        day * 0.006,
        day * 0.004,
        day * 0.0199,
        -day * 0.053,
    ]


def _row(label: str, lon: float) -> str:
    lon %= 360
    d, rest = divmod(lon, 30)
    deg = int(rest)
    minutes = int((rest - deg) * 60)
    seconds = int(((rest - deg) * 60 - minutes) * 60)
    tail = "   - 0:00'00\" (-) [ 1st house] [-] +1.0000000 +0.0000000"
    return f"{label}: {deg:2d}{SIGNS[int(d)]}{minutes:02d}'{seconds:02d}\"{tail}"


def _listing(path: str) -> str:
    """-5e over a chart list of -qcl lines → one listing per chart, positions from the date and time."""
    out = []
    with open(path, encoding="latin-1") as f:
        for line in f:
            m = re.match(r'-qcl (\d+) (\d+) (\d+) (\d+):(\d+):([\d.]+) \S+ \S+ \S+ \S+ "([^"]*)"', line)
            if not m:
                continue
            month, day, year, hh, mm, ss = (float(x) for x in m.groups()[:6])
            days = (year - 2000) * 365.25 + (month - 1) * 30.44 + day + (hh + mm / 60 + ss / 3600) / 24
            out.append(f"Astrolog 8.00 chart for {m[7]}\nheader\n")
            out.extend(_row(label, lon) + "\n" for label, lon in zip(LABELS, _positions(days), strict=True))
    return "".join(out)


def main(argv: list[str]) -> int:
    if os.environ.get("FAKE_ASTROLOG_BROKEN"):
        return 0
    if "-Hc" in argv:
        version = os.environ.get("FAKE_ASTROLOG_VERSION", "8.00")
        print("+" + "-" * 74 + "+")
        print(f"|                        ** Astrolog version {version} **                       |")
        return 0
    if argv and re.fullmatch(r"-Yq\d", argv[0]) and len(argv) >= 3:
        cast = argv[1]
        for line in argv[2:]:
            for expr in re.findall(r"-~ '([^']+)'", line):
                sys.stderr.write(f"Expression returned: {round(_evaluate(cast, expr), 6)}\n\n")
        return 0
    if "-5e" in argv and os.environ.get("FAKE_ASTROLOG_BATCH"):
        with open(os.environ["FAKE_ASTROLOG_BATCH"], encoding="latin-1") as f:
            sys.stdout.write(f.read())
        return 0
    if "-5e" in argv and "-i" in argv:
        sys.stdout.write(_listing(argv[argv.index("-i") + 1]))
        return 0
    print("FAKE ASTROLOG " + " ".join(argv))
    return int(os.environ.get("FAKE_ASTROLOG_EXIT", "0"))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
