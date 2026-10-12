#!/usr/bin/env python3
"""tools/web_grounder.py
----------------------
Lightweight, zero-dependency real-time grounding engine for /adaptive-workflow.

Queries live upstream registries (PyPI API, GitHub API via gh.exe) and local CLI
binaries to discover authoritative flags, package versions, and syntax contracts.
Caches verified discoveries atomically into orchestrator-state/grounding_cache.json
to enforce INV-REALTIME-GROUNDING without polluting intent routing exemplars.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
CACHE_FILE = ROOT / "orchestrator-state" / "grounding_cache.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("web_grounder")

PKG_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+$")


def load_grounding_cache() -> Dict[str, Any]:
    """Loads grounding cache safely; returns empty structure on missing/corrupt file."""
    if not CACHE_FILE.exists():
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "version": "1.0.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "packages": {},
            "cli_tools": {},
        }
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        logger.warning(f"Failed to read grounding cache: {e}. Reinitializing.")
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "version": "1.0.0",
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "packages": {},
        "cli_tools": {},
    }


def atomic_save_cache(cache: Dict[str, Any]) -> bool:
    """Atomically writes cache to disk on Windows using tempfile + os.replace."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        cache["last_updated"] = datetime.now(timezone.utc).isoformat()
        tmp_file = CACHE_FILE.with_suffix(f".tmp.{os.getpid()}")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
        os.replace(tmp_file, CACHE_FILE)
        return True
    except Exception as e:
        logger.error(f"Failed to atomically persist grounding cache: {e}")
        return False


def query_pypi(package_name: str, timeout: int = 5) -> Dict[str, Any]:
    """Queries official PyPI JSON API for latest package metadata and release version."""
    pkg = package_name.strip()
    if not PKG_REGEX.match(pkg):
        return {"error": f"Invalid package name format: '{pkg}'", "package": pkg}

    url = f"https://pypi.org/pypi/{pkg}/json"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Fleet-Orchestrator-Grounder/3.10 (+https://github.com/Aaradhya-Dev-Tamrakar/Fleet-Orchestrator)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            info = data.get("info", {})
            result = {
                "package": pkg,
                "latest_version": info.get("version"),
                "summary": (info.get("summary") or "")[:200],
                "requires_python": info.get("requires_python"),
                "project_url": info.get("project_url"),
                "source": "pypi_api",
                "last_verified": datetime.now(timezone.utc).isoformat(),
            }

            # Known package syntax augmentations
            if pkg == "google-genai":
                result["import_syntax"] = "from google import genai"
                result["client_init"] = "client = genai.Client()"
                result["deprecated_packages"] = ["google.generativeai", "genai.GenerativeModel"]

            # Cache discovery
            cache = load_grounding_cache()
            cache.setdefault("packages", {})[pkg] = result
            atomic_save_cache(cache)
            return result
    except urllib.error.HTTPError as e:
        return {"package": pkg, "error": f"HTTP {e.code}: {e.reason}", "source": "pypi_error"}
    except Exception as e:
        return {"package": pkg, "error": str(e), "source": "pypi_network_error"}


def query_github_release(repo: str, timeout: int = 5) -> Dict[str, Any]:
    """Queries GitHub release tag using gh api when available or public api.github.com."""
    repo = repo.strip()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Priority 1: gh.exe with authenticated token
    if shutil.which("gh"):
        try:
            cmd = ["gh", "api", f"repos/{repo}/releases/latest", "--jq", "{tag_name: .tag_name, name: .name, published_at: .published_at}"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout.strip())
                data["repo"] = repo
                data["source"] = "gh_cli_api"
                data["last_verified"] = now_iso
                return data
        except Exception as e:
            logger.debug(f"gh api query failed for {repo}: {e}")

    # Priority 2: public HTTP request
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Fleet-Orchestrator-Grounder/3.10"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {
                "repo": repo,
                "tag_name": data.get("tag_name"),
                "name": data.get("name"),
                "published_at": data.get("published_at"),
                "source": "github_public_api",
                "last_verified": now_iso,
            }
    except Exception as e:
        return {"repo": repo, "error": str(e), "source": "github_error"}


def inspect_local_cli(binary_name: str) -> Dict[str, Any]:
    """Runs --version on local executable and updates grounding cache."""
    binary = binary_name.strip()
    path = shutil.which(binary)
    now_iso = datetime.now(timezone.utc).isoformat()
    if not path:
        return {"cli": binary, "installed": False, "source": "local_inspection"}

    version_str = "unknown"
    try:
        res = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5)
        raw = (res.stdout or res.stderr).strip()
        m = re.search(r"(\d+\.\d+[\.\d\w\-]*)", raw)
        if m:
            version_str = m.group(1)
        else:
            version_str = raw.split("\n")[0][:50]
    except Exception as e:
        version_str = f"error: {e}"

    result: Dict[str, Any] = {
        "installed": True,
        "path": path,
        "installed_version": version_str,
        "source": "host_binary",
        "last_verified": now_iso,
    }

    if binary == "copilot":
        result["flags"] = {
            "exec_prompt": "-p",
            "allow_all": "--allow-all",
            "yolo": "--yolo",
            "autopilot": "--autopilot",
            "plan": "--plan",
            "usage_json": "--usage-output-file",
            "win_powershell_safe": "--no-eager-powershell-resolution",
            "unattended": "--no-ask-user",
        }
        result["canonical_headless_exec"] = 'copilot -p "{prompt}" --allow-all --no-ask-user --no-eager-powershell-resolution'

    cache = load_grounding_cache()
    cache.setdefault("cli_tools", {})[binary] = result
    atomic_save_cache(cache)
    return result


def get_grounding_summary() -> str:
    """Returns a dense, high-signal summary of verified tools and packages (<150 tokens)."""
    cache = load_grounding_cache()
    lines = ["[REAL-TIME GROUNDING KNOWLEDGE BASE]"]

    pkgs = cache.get("packages", {})
    if pkgs:
        lines.append("  Verified Packages:")
        for name, data in pkgs.items():
            ver = data.get("latest_version", "unknown")
            syntax = data.get("import_syntax", "")
            lines.append(f"    - {name} (v{ver}){f': {syntax}' if syntax else ''}")

    tools = cache.get("cli_tools", {})
    if tools:
        lines.append("  Verified Host CLI Tools:")
        for name, data in tools.items():
            ver = data.get("installed_version", "unknown")
            cmd = data.get("canonical_headless_exec", "")
            lines.append(f"    - {name} (v{ver}){f' -> {cmd}' if cmd else ''}")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Real-Time Knowledge & Registry Grounder")
    parser.add_argument("--package", "-p", help="Package name to verify against PyPI")
    parser.add_argument("--cli", "-c", help="CLI binary name to inspect on host")
    parser.add_argument("--repo", "-r", help="GitHub repo (owner/repo) to query for latest release")
    parser.add_argument("--show-cache", action="store_true", help="Display cached grounding knowledge")
    parser.add_argument("--json", action="store_true", help="Output JSON format")

    args = parser.parse_args()

    if args.show_cache:
        cache = load_grounding_cache()
        if args.json:
            print(json.dumps(cache, indent=2))
        else:
            print(get_grounding_summary())
        return 0

    if args.package:
        res = query_pypi(args.package)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Package: {res.get('package')} | Version: {res.get('latest_version')} | Source: {res.get('source')}")
        return 0 if "error" not in res else 1

    if args.cli:
        res = inspect_local_cli(args.cli)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"CLI: {args.cli} | Version: {res.get('installed_version')} | Path: {res.get('path')}")
        return 0 if res.get("installed") else 1

    if args.repo:
        res = query_github_release(args.repo)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Repo: {res.get('repo')} | Latest Release: {res.get('tag_name')} ({res.get('name')})")
        return 0 if "error" not in res else 1

    # Default: print summary
    print(get_grounding_summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
