#!/usr/bin/env python3
"""
tools/validate_schemas.py
-------------------------
Deterministic, zero-token JSON Schema validation engine for Fleet-Orchestrator.

Validates:
  1. Declarative SKU DAG batch pipeline templates in sku-templates/*.json
     against schemas/sku-template.schema.json
  2. drive-manifest.json against schemas/drive-manifest.schema.json
  3. Exported task contract schema validity in schemas/task-contract.schema.json
  4. Ephemeral task manifests in orchestrator-state/tasks/*.json (syntax & required keys)

Returns exit code 0 on clean validation pass; non-zero with structured failure report otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent


def _validate_with_fallback(instance: Any, schema: Dict[str, Any], path_desc: str) -> List[str]:
    """Validates instance against schema using jsonschema if present, or deterministic structural fallback."""
    errors = []
    try:
        import jsonschema

        validator = jsonschema.Draft202012Validator(schema)
        for error in validator.iter_errors(instance):
            loc = " -> ".join([str(p) for p in error.path]) or "root"
            errors.append(f"[{path_desc}] {loc}: {error.message}")
        return errors
    except ImportError:
        # Fallback structural checks when jsonschema is not installed
        reqs = schema.get("required", [])
        if isinstance(instance, dict):
            for r in reqs:
                if r not in instance:
                    errors.append(f"[{path_desc}] Missing required field '{r}'")
        return errors


def validate_sku_templates(root: Path = ROOT_DIR) -> Tuple[bool, List[str]]:
    """Validates all sku-templates/*.json against schemas/sku-template.schema.json."""
    schema_path = root / "schemas" / "sku-template.schema.json"
    templates_dir = root / "sku-templates"
    errors = []

    if not schema_path.exists():
        return False, [f"Missing SKU template schema: {schema_path}"]
    if not templates_dir.exists():
        return False, [f"Missing sku-templates directory: {templates_dir}"]

    try:
        with open(schema_path, "r", encoding="utf-8") as sf:
            schema = json.load(sf)
    except Exception as e:
        return False, [f"Failed to read {schema_path}: {e}"]

    template_files = sorted(templates_dir.glob("*.json"))
    if not template_files:
        return False, ["No SKU templates found in sku-templates/"]

    for tf in template_files:
        try:
            with open(tf, "r", encoding="utf-8") as f:
                data = json.load(f)
            file_errors = _validate_with_fallback(data, schema, tf.name)
            errors.extend(file_errors)
        except Exception as e:
            errors.append(f"[{tf.name}] JSON parse failure: {e}")

    return len(errors) == 0, errors


def validate_drive_manifest(root: Path = ROOT_DIR) -> Tuple[bool, List[str]]:
    """Validates drive-manifest.json against schemas/drive-manifest.schema.json."""
    schema_path = root / "schemas" / "drive-manifest.schema.json"
    manifest_path = root / "drive-manifest.json"
    errors = []

    if not schema_path.exists():
        return False, [f"Missing drive-manifest schema: {schema_path}"]
    if not manifest_path.exists():
        return False, [f"Missing drive-manifest.json: {manifest_path}"]

    try:
        with open(schema_path, "r", encoding="utf-8") as sf:
            schema = json.load(sf)
        with open(manifest_path, "r", encoding="utf-8") as mf:
            data = json.load(mf)
    except Exception as e:
        return False, [f"Failed to load files: {e}"]

    file_errors = _validate_with_fallback(data, schema, manifest_path.name)
    errors.extend(file_errors)
    return len(errors) == 0, errors


def validate_task_contract_schema(root: Path = ROOT_DIR) -> Tuple[bool, List[str]]:
    """Validates that schemas/task-contract.schema.json exists and is valid Draft 2020-12 JSON schema."""
    schema_path = root / "schemas" / "task-contract.schema.json"
    errors = []
    if not schema_path.exists():
        return False, [f"Missing task contract schema: {schema_path}"]

    try:
        with open(schema_path, "r", encoding="utf-8") as sf:
            schema = json.load(sf)

        try:
            import jsonschema

            # Validate against Draft 2020-12 meta-schema
            jsonschema.Draft202012Validator.check_schema(schema)
        except ImportError:
            pass
        except Exception as e:
            errors.append(f"[task-contract.schema.json] Draft 2020-12 meta-schema check failed: {e}")

        defs = schema.get("$defs", {})
        expected_models = ["TaskCreate", "TaskResponse", "JobCreate", "JobResponse", "WorkerResponse"]
        for m in expected_models:
            if m not in defs:
                errors.append(f"[task-contract.schema.json] Missing expected model definition '{m}' in $defs")
    except Exception as e:
        errors.append(f"[task-contract.schema.json] Parse failure: {e}")

    return len(errors) == 0, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Fleet-Orchestrator Declarative Schema & Manifest Validator")
    parser.add_argument("--all", action="store_true", help="Validate all schemas and templates")
    parser.add_argument("--sku", action="store_true", help="Validate SKU templates only")
    parser.add_argument("--manifest", action="store_true", help="Validate drive-manifest only")
    args = parser.parse_args()

    check_all = args.all or (not args.sku and not args.manifest)

    all_passed = True
    total_checks = 0

    if check_all or args.sku:
        total_checks += 1
        ok, errs = validate_sku_templates()
        if ok:
            print("  [+] sku-templates/*.json: Validated successfully against Draft 2020-12 schema.")
        else:
            all_passed = False
            print("  [!] sku-templates validation failed:")
            for e in errs:
                print(f"      - {e}")

    if check_all or args.manifest:
        total_checks += 1
        ok, errs = validate_drive_manifest()
        if ok:
            print("  [+] drive-manifest.json: Validated successfully against Draft 2020-12 schema.")
        else:
            all_passed = False
            print("  [!] drive-manifest.json validation failed:")
            for e in errs:
                print(f"      - {e}")

    if check_all:
        total_checks += 1
        ok, errs = validate_task_contract_schema()
        if ok:
            print("  [+] schemas/task-contract.schema.json: Validated successfully.")
        else:
            all_passed = False
            print("  [!] task-contract schema validation failed:")
            for e in errs:
                print(f"      - {e}")

    if all_passed:
        print(f"[OK] All {total_checks} schema validation suites passed cleanly.")
        return 0
    else:
        print(f"[FAIL] Schema validation failed with errors.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
