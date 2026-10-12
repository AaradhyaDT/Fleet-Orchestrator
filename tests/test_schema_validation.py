from __future__ import annotations

import json
from pathlib import Path
import pytest
from tools.validate_schemas import (
    validate_sku_templates,
    validate_drive_manifest,
    validate_task_contract_schema,
    _validate_with_fallback,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_sku_templates_schema_conformance():
    """All declarative SKU job templates must strictly conform to schemas/sku-template.schema.json."""
    ok, errors = validate_sku_templates(REPO_ROOT)
    assert ok, f"SKU template validation errors: {errors}"


def test_drive_manifest_schema_conformance():
    """drive-manifest.json must strictly conform to schemas/drive-manifest.schema.json."""
    ok, errors = validate_drive_manifest(REPO_ROOT)
    assert ok, f"Drive manifest validation errors: {errors}"


def test_task_contract_schema_defs():
    """schemas/task-contract.schema.json must provide definitions for core models."""
    ok, errors = validate_task_contract_schema(REPO_ROOT)
    assert ok, f"Task contract schema errors: {errors}"


def test_sku_template_invalid_rejected():
    """Malformed SKU template with missing required fields must be detected."""
    schema_path = REPO_ROOT / "schemas" / "sku-template.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    invalid_template = {
        "sku_id": "invalid_template",
        # Missing display_name, pipeline, etc.
    }
    errors = _validate_with_fallback(invalid_template, schema, "invalid_dummy.json")
    assert len(errors) > 0, "Expected validation errors for incomplete SKU template"


def test_drive_manifest_invalid_rejected():
    """Malformed drive manifest missing folder_id must be detected."""
    schema_path = REPO_ROOT / "schemas" / "drive-manifest.schema.json"
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    invalid_manifest = {
        "notebook_id": "dummy",
        "files": {}
    }
    errors = _validate_with_fallback(invalid_manifest, schema, "invalid_manifest.json")
    assert len(errors) > 0, "Expected validation errors for incomplete drive manifest"
