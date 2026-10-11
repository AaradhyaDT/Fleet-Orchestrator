"""Unit tests for tools.adapter_scaffolder."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest
from tools.adapter_scaffolder import scaffold_adapter


def test_scaffold_adapter_creates_files(tmp_path: Path):
    created = scaffold_adapter(
        provider="mistral",
        model="mistral-large-latest",
        repo_root=tmp_path,
    )
    assert "adapter" in created
    assert "test" in created

    adapter_path = created["adapter"]
    test_path = created["test"]

    assert adapter_path.exists()
    assert test_path.exists()
    assert adapter_path.name == "mistral_adapter.py"
    assert test_path.name == "test_mistral_adapter.py"

    # Verify both files are valid Python syntax
    ast.parse(adapter_path.read_text(encoding="utf-8"))
    ast.parse(test_path.read_text(encoding="utf-8"))


def test_scaffold_adapter_no_overwrite_without_force(tmp_path: Path):
    created1 = scaffold_adapter(
        provider="cohere",
        model="command-r-plus",
        repo_root=tmp_path,
    )
    adapter_path = created1["adapter"]
    adapter_path.write_text("# manual edit", encoding="utf-8")

    created2 = scaffold_adapter(
        provider="cohere",
        model="command-r-plus",
        repo_root=tmp_path,
        force=False,
    )
    assert "adapter" not in created2
    assert adapter_path.read_text(encoding="utf-8") == "# manual edit"


def test_scaffold_adapter_force_overwrites(tmp_path: Path):
    created1 = scaffold_adapter(
        provider="cohere",
        model="command-r-plus",
        repo_root=tmp_path,
    )
    adapter_path = created1["adapter"]
    adapter_path.write_text("# manual edit", encoding="utf-8")

    created2 = scaffold_adapter(
        provider="cohere",
        model="command-r-plus",
        repo_root=tmp_path,
        force=True,
    )
    assert "adapter" in created2
    assert "BaseWorkerAdapter" in adapter_path.read_text(encoding="utf-8")


def test_scaffold_adapter_dry_run(tmp_path: Path):
    created = scaffold_adapter(
        provider="deepseek",
        model="deepseek-chat",
        repo_root=tmp_path,
        dry_run=True,
    )
    assert not created["adapter"].exists()
    assert not created["test"].exists()
