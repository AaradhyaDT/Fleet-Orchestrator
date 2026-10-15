"""Unit and governance tests for Skills Registry & Capability Inventory."""

import json
import os
from pathlib import Path

import pytest

from tools.build_skills_registry import scan_all_skills, build_and_save_registry
from tools.fast_intent_router import DynamicSkillManifest

ROOT = Path(__file__).resolve().parent.parent
REGISTRY_FILE = ROOT / "tools" / "skills_registry.json"


def test_skills_registry_file_exists_and_valid():
    """Asserts that skills_registry.json exists, is valid JSON, and catalogs all distinct skills."""
    if not REGISTRY_FILE.exists():
        build_and_save_registry(REGISTRY_FILE)

    assert REGISTRY_FILE.exists()
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "version" in data
    assert "total_distinct_skills" in data
    assert data["total_distinct_skills"] >= 90, f"Expected at least 90 distinct skills, found {data['total_distinct_skills']}"
    assert "skills" in data
    assert len(data["skills"]) == data["total_distinct_skills"]


def test_skills_registry_entry_schema_and_integrity():
    """Asserts that each registered skill adheres to the required metadata schema and verified SSOT path."""
    with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    required_keys = {"name", "domain", "availability_tier", "ssot_path", "mirrors", "triggers"}
    valid_tiers = {"INSTALLED", "ACCESSIBLE", "VERIFIED"}

    is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
    for skill_name, skill_meta in data["skills"].items():
        assert required_keys.issubset(skill_meta.keys()), f"Skill {skill_name} missing required schema keys"
        assert skill_meta["availability_tier"] in valid_tiers
        if not is_ci:
            assert Path(skill_meta["ssot_path"]).exists(), f"SSOT path for {skill_name} not found on disk: {skill_meta['ssot_path']}"


def test_dynamic_skill_manifest_reads_from_registry():
    """Asserts that DynamicSkillManifest successfully leverages skills_registry.json."""
    DynamicSkillManifest._MANIFEST_CACHE = None
    triggers = DynamicSkillManifest.get_skill_triggers()

    assert isinstance(triggers, dict)
    assert len(triggers) > 0
    # Core ecosystem skills should have triggers present
    assert "adaptive-workflow" in triggers or "github-workflow" in triggers
