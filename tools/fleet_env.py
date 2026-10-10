#!/usr/bin/env python3
"""
Unified Fleet Environment Loader (tools/fleet_env.py).
Provides zero-friction cascading discovery and parsing across:
  1. .env.fleet.copilot (GitHub Copilot 27-account pool)
  2. .env.fleet.gemini  (Google AI Studio Gemini API keys)
  3. .env.fleet.agy     (Antigravity CLI headless worker pool)
  4. .env.fleet / .env  (Consolidated legacy fallback)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


def parse_env_file(path: Path | str) -> dict[str, str]:
    """Parses a KEY=VALUE environment file ignoring comments and blank lines."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return {}

    env_vars: dict[str, str] = {}
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                env_vars[k] = v
    except Exception:
        pass
    return env_vars


def get_fleet_file_paths(repo_root: Path | None = None) -> dict[str, Path]:
    """Returns the standard file paths for each fleet module."""
    root = repo_root or REPO_ROOT
    return {
        "copilot": root / ".env.fleet.copilot",
        "gemini": root / ".env.fleet.gemini",
        "agy": root / ".env.fleet.agy",
        "legacy": root / ".env.fleet",
        "env": root / ".env",
    }


def load_all_fleet_env(
    repo_root: Path | None = None,
    inject_os_environ: bool = True,
) -> dict[str, Any]:
    """
    Cascading loader that merges provider-specific fleet configs with legacy fallbacks.
    Returns structured dictionary with per-fleet variables and merged namespace.
    """
    root = repo_root or REPO_ROOT
    paths = get_fleet_file_paths(root)

    # 1. Base legacy environment
    legacy_env = {}
    if paths["legacy"].exists():
        legacy_env.update(parse_env_file(paths["legacy"]))
    elif paths["env"].exists():
        legacy_env.update(parse_env_file(paths["env"]))

    # 2. Provider-specific overrides
    copilot_env = dict(legacy_env)
    if paths["copilot"].exists():
        copilot_env.update(parse_env_file(paths["copilot"]))

    gemini_env = dict(legacy_env)
    if paths["gemini"].exists():
        gemini_env.update(parse_env_file(paths["gemini"]))

    agy_env = dict(legacy_env)
    if paths["agy"].exists():
        agy_env.update(parse_env_file(paths["agy"]))

    # 3. Merged dictionary (specific provider files take precedence)
    merged = {**legacy_env, **copilot_env, **gemini_env, **agy_env}

    if inject_os_environ:
        for k, v in merged.items():
            if v:
                os.environ[k] = v

    return {
        "copilot": copilot_env,
        "gemini": gemini_env,
        "agy": agy_env,
        "merged": merged,
        "paths": paths,
    }


if __name__ == "__main__":
    fleet_config = load_all_fleet_env()
    paths = fleet_config["paths"]
    print("=== Fleet-Orchestrator Environment Audit ===")
    for name, p in paths.items():
        status = "[EXISTS]" if p.exists() else "[MISSING]"
        print(f"  - {name.ljust(8)} : {status} {p.name}")
    print(f"Total merged configuration keys: {len(fleet_config['merged'])}")
