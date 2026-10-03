"""The whole user journey, through the real CLI and the real Astrolog: `uv run pytest -m astrolog tests/e2e`.

doctor → save a chart → view it → aspects/patterns → transits → report data → HTML export → a research set from a CSV →
harmonic sweep. Every step as a user (or Claude) would run it, reading --json.
"""

from __future__ import annotations

import json
import os
import pwd
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.astrolog


def astro(*args: str) -> dict:
    res = subprocess.run(
        [sys.executable, "-m", "astrolog_skills", "--json", *args],
        capture_output=True,
        text=True,
        cwd=REPO,
        env=os.environ.copy(),
        check=False,
    )
    assert res.returncode == 0, f"astro {' '.join(args)} failed: {res.stdout}{res.stderr}"
    return json.loads(res.stdout)


@pytest.fixture
def real(monkeypatch: pytest.MonkeyPatch) -> Path:
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    for candidate in (os.environ.get("REAL_ASTROLOG", ""), str(home / "astrolog" / "astrolog")):
        if candidate and Path(candidate).is_file():
            monkeypatch.setenv("ASTROLOG_BIN", candidate)
            return Path(candidate)
    pytest.skip("no real Astrolog found")


def test_user_journey(real: Path, tmp_path: Path) -> None:
    doctor = astro("doctor")
    assert doctor["ok"] and doctor["first_light"]["sun"]["text"]

    astro("config", "set", "location", "48N24 10E00", "--name", "Ulm")
    saved = astro(
        "chart",
        "add",
        "Einstein",
        "--date",
        "1879-03-14",
        "--time",
        "11:30",
        "--place",
        "Ulm, Germany",
        "--rating",
        "AA",
    )
    assert saved["chart"]["tz"] == "Europe/Berlin"

    shown = astro("view", "--chart", "Einstein", "--show", "chart,aspects,patterns")
    sun = next(p for p in shown["chart"]["points"] if p["key"] == "sun")
    assert sun["text"].startswith("23°30′") and sun["house"] == 10

    patterns = astro("patterns", "--chart", "Einstein", "--pack", "vibrational", "-H", "7")
    assert patterns["harmonics"][0]["patterns"][0]["bodies"] == ["mercury", "saturn", "pluto"]

    transits = astro("transits", "--chart", "Einstein", "--on", "1908-10-01", "--days", "60")
    saturn_return = [w for w in transits["window"] if (w["transit"], w["natal"]) == ("saturn", "saturn")]
    assert saturn_return and saturn_return[0]["exact"] == "1908-11-06"

    report = astro("report-data", "--chart", "Einstein", "--pack", "vibrational", "--pack", "psychological")
    assert Path(report["packs"][0]["files"]["process.md"]).exists()

    exported = astro("export", "html", "--chart", "Einstein", "--out", str(tmp_path / "einstein.html"))
    assert Path(exported["path"]).stat().st_size > 20_000

    rows = ["name,date,time,tz,lat,lon"] + [
        f"P{i},19{10 + i}-0{1 + i % 9}-1{i % 9},{i % 24:02d}:30,UTC,48.4,10.0" for i in range(40)
    ]
    (tmp_path / "people.csv").write_text("\n".join(rows) + "\n")
    astro("set", "create", "people", "--csv", str(tmp_path / "people.csv"))
    sweep = astro("research", "sweep", "people", "--range", "1-12", "--shuffles", "6")
    assert sweep["count"] == 40 and all(len(v) == 12 for v in sweep["measures"].values()) and sweep["run"]
    assert astro("research", "list")["runs"][0]["id"] == sweep["run"]
