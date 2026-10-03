from __future__ import annotations

import copy
import json
import tomllib
from pathlib import Path
from typing import Any

import pytest

from astrolog_skills.analysis.doctrine import check_doctrine, parse_doctrine
from astrolog_skills.analysis.method import parse
from astrolog_skills.errors import AstroError
from astrolog_skills.packs import loader
from tests.conftest import run_cli

FIXTURE = Path(__file__).parent / "fixtures" / "doctrine_pack.toml"


def raw() -> dict[str, Any]:
    return tomllib.loads(FIXTURE.read_text())


def test_parse_every_section() -> None:
    d = parse_doctrine(raw(), "t")
    assert d is not None
    assert d.sect and d.sect.diurnal == ("sun", "jupiter", "saturn") and d.sect.rejoicing.by_sign == "gender"
    g = d.dignities
    assert g and g.domicile["aquarius"] == "saturn" and g.exaltation["sun"] == ("aries", 19.0)
    assert g.triplicity["water"] == ("venus", "mars", "moon") and g.bounds_scheme == "egyptian"
    assert g.bounds["egyptian"]["aries"][0] == ("jupiter", 6.0) and g.decan_scheme == "chaldean"
    assert g.twelfth_parts == 12
    eros = d.lots["eros"]
    assert eros.version == "early" and set(eros.versions) == {"early", "later"}
    assert eros.effective().points == ("lot:fortune", "lot:spirit") and eros.effective().reverse
    assert d.lots["father"].fallback and d.lots["father"].fallback.when == "saturn_under_beams"
    assert d.lots["death"].project_from == "saturn" and d.lots["foundation"].distance == "shortest"
    assert d.lots["exaltation"].day == ("sun", "sign:aries") and d.lots["fortune"].variants == {
        "never_reversed": "p. 3"
    }
    assert d.phase and d.phase.under_beams == 15 and d.phase.heliacal_days == 7 and "bounds" in d.phase.chariot
    ray = d.conditions["striking_with_a_ray"]
    assert ray.kind == "degree_aspect" and ray.orb == 3.0 and ray.cite == "p. 6" and ray.direction == "backward"
    assert (
        ray.maltreat == ("square",)
        and d.conditions["engagement"].moon_orb == 13
        and d.conditions["engagement"].applying
    )
    assert d.conditions["counteraction"].maltreat_places == (6, 12)
    assert d.scoring and "bonified" in d.scoring.good and "lord_maltreated" in d.scoring.lot_bad
    assert d.places and d.places.joys["saturn"] == 12
    assert d.profections and d.releasing and d.releasing.periods["capricorn"] == 27 and d.transits and d.scoring
    assert d.summary()["lots"] == sorted(d.lots)
    assert check_doctrine(d) == []


def test_no_doctrine_sections_means_none() -> None:
    assert parse_doctrine({"aspects": {}}, "t") is None
    assert parse({"orbs": {"rule": "harmonic"}}, "t").doctrine is None
    assert parse(raw(), "t").doctrine is not None


def mutate(path: str, value: Any) -> dict[str, Any]:
    r = copy.deepcopy(raw())
    node = r
    *parents, leaf = path.split(".")
    for p in parents:
        node = node[p]
    if value is None:
        del node[leaf]
    else:
        node[leaf] = value
    return r


@pytest.mark.parametrize(
    ("path", "value", "where"),
    [
        ("dignities.domicile.pisces", None, "dignities.domicile"),
        ("dignities.bounds.egyptian.aries", [["jupiter", 6], ["venus", 12], ["mercury", 20], ["mars", 30]], "aries"),
        (
            "dignities.bounds.egyptian.aries",
            [["jupiter", 12], ["venus", 6], ["mercury", 20], ["mars", 25], ["saturn", 30]],
            "aries",
        ),
        (
            "dignities.bounds.egyptian.aries",
            [["jupiter", 6], ["venus", 12], ["mercury", 20], ["mars", 25], ["saturn", 29]],
            "aries",
        ),
        ("dignities.bounds.egyptian.pisces", None, "dignities.bounds.egyptian"),
        ("dignities.triplicity.fire", ["sun", "sun", "saturn"], "triplicity.fire"),
        ("dignities.decans", {"scheme": "table", "aries": ["mars", "sun", "venus"]}, "dignities.decans"),
        ("lots.eros.early", {"points": ["lot:nowhere", "lot:spirit"]}, "lots.eros"),
        ("lots.fortune.points", ["lot:foundation", "moon"], "lots."),
        ("lots.death.points", ["moon", "place:13"], "lots.death"),
        ("lots.eros.version", "missing", "lots.eros.version"),
        ("timing.releasing.periods.pisces", None, "timing.releasing.periods"),
        ("places.good", [0, 13], "places.good"),
        ("sect.nocturnal", ["moon", "venus", "mars", "saturn"], "sect"),
        ("phase.weak_within", 20, "phase.weak_within"),
        ("phase.weak_within", 0.5, "phase.heart"),
        ("conditions.overcoming.maltreat", ["opposition"], "conditions.overcoming"),
        ("conditions.overcoming.kind", "counteraction", "conditions.overcoming"),
        ("lots.father.fallback", {"when": "never", "points": ["mars", "jupiter"]}, "lots.father.fallback"),
        ("scoring.bad", ["of_sect"], "scoring"),
    ],
)
def test_check_finds_errors(path: str, value: Any, where: str) -> None:
    d = parse_doctrine(mutate(path, value), "t")
    assert d is not None
    errors = [p for p in check_doctrine(d) if p.level == "error"]
    assert errors and any(where in p.where for p in errors), [p.where for p in check_doctrine(d)]


def test_warnings_for_citations_and_egyptian_totals() -> None:
    r = mutate("sect.cite", None)
    r["dignities"]["bounds"]["egyptian"]["aries"] = [
        ["jupiter", 7],
        ["venus", 12],
        ["mercury", 20],
        ["mars", 25],
        ["saturn", 30],
    ]
    d = parse_doctrine(r, "t")
    assert d is not None
    problems = check_doctrine(d)
    assert all(p.level == "warn" for p in problems)
    assert any(p.where == "sect" and "citation" in p.message for p in problems)
    assert any("classical years" in p.message and "jupiter 80" in p.message for p in problems)


@pytest.mark.parametrize(
    ("path", "value", "text"),
    [
        ("dignities.domicile.aries", "uranus", "traditional planet"),
        ("sect.mercury", "sometimes", "sect.mercury"),
        ("conditions.striking_with_a_ray.kind", "wobble", "kind"),
        ("conditions.striking_with_a_ray.maltreat", ["trine", "wobble"], "maltreat"),
        ("conditions.striking_with_a_ray.effect", "by_nature", "unknown key"),
        ("conditions.counteraction.maltreat_places", [6, 13], "maltreat_places"),
        ("scoring.good", ["of_sect", "lucky"], "scoring.good"),
        ("lots.fortune.points", ["sun"], "two points"),
        ("lots.foundation.distance", "longest", "distance"),
        ("dignities.bounds_scheme", "ptolemaic", "no table"),
        ("dignities.triplicity.aether", ["sun", "moon", "mars"], "element"),
        ("timing.releasing.year_days", 10, "year_days"),
        ("lots.fortune.revers", True, "unknown key"),
        ("phase.chariot", ["domicile", "joy"], "phase.chariot"),
        ("phase.under_beam", 15, "unknown key"),
        ("dignities.twelfth_parts", {"multiplier": 10}, "12 or 13"),
    ],
)
def test_structural_errors_raise(path: str, value: Any, text: str) -> None:
    with pytest.raises(AstroError) as err:
        parse_doctrine(mutate(path, value), "pack 'x'")
    assert text in str(err.value) and "pack 'x'" in str(err.value)


def test_packs_check_cli_and_show() -> None:
    pack = loader.user_dir() / "doctrine-test"
    pack.mkdir(parents=True)
    (pack / "method.toml").write_text(FIXTURE.read_text())
    assert run_cli("packs", "check", "doctrine-test").returncode == 0
    shown = json.loads(run_cli("--json", "packs", "show", "doctrine-test").stdout)
    assert "dignities" in shown["doctrine"]["sections"] and "fortune" in shown["doctrine"]["lots"]
    everything = json.loads(run_cli("--json", "packs", "check").stdout)
    assert everything["ok"] and {p["pack"] for p in everything["packs"]} >= {
        "psychological",
        "vibrational",
        "doctrine-test",
    }
    good = '["mars", 28], ["saturn", 30]]'
    assert good in FIXTURE.read_text()
    (pack / "method.toml").write_text(FIXTURE.read_text().replace(good, '["mars", 28], ["saturn", 29]]'))
    broken = run_cli("--json", "packs", "check", "doctrine-test")
    assert broken.returncode == 1 and json.loads(broken.stdout)["errors"] >= 1
