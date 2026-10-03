from __future__ import annotations

import json
import os
import tomllib

from astrolog_skills import __version__
from tests.conftest import REPO


def test_manifests_agree() -> None:
    plugin = json.loads((REPO / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text())
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text())
    entry = market["plugins"][0]
    assert plugin["name"] == entry["name"] == "astrolog-skills"
    assert plugin["version"] == entry["version"] == pyproject["project"]["version"] == __version__
    assert entry["source"] == "./"


def test_bin_astro_is_executable() -> None:
    wrapper = REPO / "bin" / "astro"
    assert os.access(wrapper, os.X_OK)
    text = wrapper.read_text()
    assert "UV_PROJECT_ENVIRONMENT" in text and "--frozen" in text and "ASTROLOG_SKILLS_PLUGIN_ROOT" in text


def test_skills_have_frontmatter() -> None:
    skills = sorted((REPO / "skills").glob("*/SKILL.md"))
    assert skills
    for skill in skills:
        head = skill.read_text().split("---")[1]
        assert f"name: {skill.parent.name}" in head
        assert "description:" in head


def test_uv_lock_committed() -> None:
    assert (REPO / "uv.lock").exists()
