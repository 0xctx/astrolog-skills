"""The built-in packs must cover everything the toolkit can report, and must be original writing."""

from __future__ import annotations

import re

from astrolog_skills.analysis.aspects_registry import BY_KEY
from astrolog_skills.engine.objects import OBJECTS
from astrolog_skills.engine.zodiac import SIGNS
from astrolog_skills.packs import loader

SOURCED = {5, 7, 8, 9, 11, 13, 17, 19, 23, 29, 31}  # named in the pack's sources


def _text(pack: str, name: str) -> str:
    path = loader.load(pack).file(name)
    assert path is not None, f"{pack}/{name} missing"
    return path.read_text(encoding="utf-8")


def test_psychological_covers_every_object_sign_house_and_aspect() -> None:
    text = _text("psychological", "meanings.md")
    for o in OBJECTS:
        assert f"**{o.name}" in text or o.name.split()[0] in text, o.key
    for sign in SIGNS:
        assert f"**{sign}**" in text, sign
    for house in range(1, 13):
        assert re.search(rf"\b{house}\. \w", text), house
    for aspect in loader.load("psychological").method.aspects:
        assert BY_KEY[aspect].name.capitalize() in text, aspect


def test_vibrational_covers_h1_to_h32_with_provenance() -> None:
    text = _text("vibrational", "meanings.md")
    for h in range(1, 33):
        m = re.search(rf"^- \*\*H{h}\*\* — .+\[(source|theory|derived)\]$", text, re.M)
        assert m, f"H{h} missing or unlabelled"
        assert (m[1] == "source") == (h in SOURCED), f"H{h} labelled {m[1]}"


def test_process_files_have_steps_and_rules() -> None:
    for pack in ("psychological", "vibrational"):
        text = _text(pack, "process.md")
        assert "## " in text and "Writing rules" in text and "medical" in text


def test_no_long_quotations() -> None:
    """Original writing only: nothing longer than a short phrase between quotation marks."""
    for pack in ("psychological", "vibrational"):
        for name in ("meanings.md", "process.md"):
            for quote in re.findall(r"[\"“]([^\"”]{60,})[\"”]", _text(pack, name)):
                raise AssertionError(f"{pack}/{name} quotes a long passage: {quote[:40]}…")


def test_review_flags_derived_meanings() -> None:
    assert "Derived harmonic meanings" in _text("vibrational", "REVIEW.md")
