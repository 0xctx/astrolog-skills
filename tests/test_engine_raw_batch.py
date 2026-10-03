from __future__ import annotations

from pathlib import Path

import pytest

from astrolog_skills.engine import profile as P
from astrolog_skills.engine.batch import batch, parse
from astrolog_skills.engine.moment import Moment
from astrolog_skills.engine.raw import raw, raw_argv

SAMPLE = Path(__file__).parent / "fixtures" / "batch_sample.txt"


def test_raw_argv_order() -> None:
    m = Moment("1879-03-14", "11:30", "LMT", 48.4, 10.0)
    argv = raw_argv(["-v", "-c", "Koch"], m, P.load("default"))
    pins = P.pins(P.load("default"))
    assert argv[: len(pins)] == pins
    assert argv[len(pins) : len(pins) + 8] == m.cast_args()
    assert argv[-3:] == ["-v", "-c", "Koch"]  # the user's switches come last and win


def test_raw_runs_without_shell(fake_astrolog: Path) -> None:
    _argv, done = raw(["-zi", "a name; rm -rf /", "x"])
    assert done.returncode == 0
    assert "a name; rm -rf /" in done.stdout  # passed as one literal argument, never interpreted


def test_raw_exit_code_passthrough(fake_astrolog: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ASTROLOG_EXIT", "3")
    assert raw(["-v"])[1].returncode == 3


def test_parse_batch_sample() -> None:
    charts = parse(SAMPLE.read_text())
    assert [c.name for c in charts] == ["Test Person A", ""]
    a = charts[0]
    assert a.header.startswith("Tue Nov 29, 1825")
    assert a.lon("sun") == pytest.approx(247.334167, abs=1e-6)
    assert a.points["saturn"]["retrograde"] and not a.points["sun"]["retrograde"]
    assert a.points["pluto"]["lat"] == pytest.approx(-16.784444, abs=1e-6)
    assert a.points["chiron"]["house"] == 10
    assert a.angles == {"asc": pytest.approx(101.646389, abs=1e-6), "mc": pytest.approx(342.839722, abs=1e-6)}
    assert "Xyzw" not in a.points  # unknown labels are skipped
    assert a.points["south_node"]["lon"] == pytest.approx((a.lon("north_node") + 180) % 360)
    assert charts[1].header.startswith("Sun Jul  1, 1990") and set(charts[1].points) == {"sun", "moon"}


def test_batch_uses_pins_and_list_args(fake_astrolog: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_ASTROLOG_BATCH", str(SAMPLE))
    charts = batch(["-i", "list.as"], P.load("default"))
    assert len(charts) == 2 and charts[0].name == "Test Person A"
