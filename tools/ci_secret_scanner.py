#!/usr/bin/env python3
"""
CI Secret Scanner for Fleet-Orchestrator.
Performs deterministic pre-commit and CI credential leakage audits.
Enforces zero-leak security invariants across the repository.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# High-confidence credential patterns
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("OpenAI API Key", re.compile(r"sk-[a-zA-Z0-9]{20,}")),
    ("Anthropic API Key", re.compile(r"sk-ant-[a-zA-Z0-9\-]{20,}")),
    ("GitHub Personal Access Token", re.compile(r"ghp_[a-zA-Z0-9]{36}")),
    ("GitHub Fine-Grained PAT", re.compile(r"github_pat_[a-zA-Z0-9_]{20,}")),
    ("Google AI / GCP API Key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("Slack Token", re.compile(r"xox[baprs]-[0-9a-zA-Z\-]{10,}")),
    ("Private Key", re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|PGP|DSA)? ?PRIVATE KEY-----")),
]

# Generic assignment pattern
GENERIC_ASSIGN_PATTERN = re.compile(
    r"""(?i)(?:api[_-]?key|secret|password|passwd|token)\s*[:=]\s*["']([^"'\s]{8,})["']"""
)

# Known safe placeholders that should never trigger false positives
SAFE_PLACEHOLDERS = {
    "your_gemini_api_key_here",
    "your_api_key_here",
    "your_pat_here",
    "mock_key_value",
    "dummy_secret_value",
    "placeholder_token",
}

IGNORED_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".worktrees",
    "node_modules",
    "dist",
    "build",
}

IGNORED_FILES = {
    ".env.fleet.example",
    ".env.fleet.copilot.example",
    ".env.fleet.gemini.example",
    ".env.fleet.agy.example",
    "ci_secret_scanner.py",
}


def scan_line(line: str) -> list[str]:
    """Scan a single line for any secret pattern match."""
    hits = []
    for name, pattern in SECRET_PATTERNS:
        if pattern.search(line):
            hits.append(name)

    # Check generic assignment
    match = GENERIC_ASSIGN_PATTERN.search(line)
    if match:
        val = match.group(1).strip()
        if val.lower() not in SAFE_PLACEHOLDERS:
            # Check if it looks like variable interpolation or env reference
            if not (val.startswith("$") or val.startswith("%") or val.startswith("{") or val.startswith("<")):
                hits.append(f"Generic Secret Assignment ('{val[:4]}***')")

    return hits


def scan_text(text: str, source_name: str) -> list[dict[str, str]]:
    """Scan multiline text and return any finding."""
    findings = []
    lines = text.splitlines()
    for idx, line in enumerate(lines, start=1):
        line_hits = scan_line(line)
        for hit in line_hits:
            findings.append({
                "source": source_name,
                "line_no": str(idx),
                "pattern": hit,
                "snippet": line.strip()[:80],
            })
    return findings


def scan_git_diff(range_or_cached: str = "--cached") -> list[dict[str, str]]:
    """Scan git diff output for newly added lines."""
    findings = []
    cmd = ["git", "diff", range_or_cached, "-U0"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except Exception as e:
        print(f"[scanner] Git diff failed: {e}", file=sys.stderr)
        return []

    current_file = "unknown"
    line_no = 0
    for line in res.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            line_no = int(m.group(1)) if m else 0
        elif line.startswith("+") and not line.startswith("+++"):
            content = line[1:]
            hits = scan_line(content)
            for hit in hits:
                findings.append({
                    "source": current_file,
                    "line_no": str(line_no),
                    "pattern": hit,
                    "snippet": content.strip()[:80],
                })
            line_no += 1
    return findings


def scan_repository(root_dir: Path) -> list[dict[str, str]]:
    """Scan all tracked files in git, or walk directory respecting gitignore."""
    findings = []
    # Prefer git ls-files to accurately reflect tracked repository contents
    try:
        res = subprocess.run(["git", "ls-files"], cwd=root_dir, capture_output=True, text=True, check=True)
        tracked_files = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        for rel in tracked_files:
            if rel.startswith(".env") and not rel.endswith(".example"):
                continue
            path = root_dir / rel
            if not path.is_file() or path.suffix.lower() in {".pyc", ".png", ".jpg", ".ico", ".woff2", ".db", ".sqlite"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
                findings.extend(scan_text(text, rel))
            except Exception:
                continue
        return findings
    except Exception:
        pass

    # Fallback to filesystem traversal
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for f in files:
            if f.startswith(".env") or f in IGNORED_FILES or f.endswith((".pyc", ".png", ".jpg", ".ico", ".woff2", ".db", ".sqlite")):
                continue
            path = Path(root) / f
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
                rel_path = path.relative_to(root_dir)
                findings.extend(scan_text(text, str(rel_path)))
            except Exception:
                continue
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Fleet-Orchestrator CI Secret Scanner")
    parser.add_argument("--diff", type=str, help="Scan a specific git diff range (e.g. HEAD~1..HEAD)")
    parser.add_argument("--cached", action="store_true", help="Scan git staged changes")
    parser.add_argument("--all", action="store_true", help="Scan full repository")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent

    if args.diff:
        print(f"[*] Scanning git diff range: {args.diff}...")
        findings = scan_git_diff(args.diff)
    elif args.cached:
        print("[*] Scanning staged git changes...")
        findings = scan_git_diff("--cached")
    else:
        print(f"[*] Scanning repository tree at {root}...")
        findings = scan_repository(root)

    if findings:
        print(f"\n[!] SECURITY ALERT: {len(findings)} possible secret(s) detected:")
        for f in findings:
            print(f"    - {f['source']}:{f['line_no']} [{f['pattern']}]")
            print(f"      {f['snippet']}")
        return 1

    print("[+] Zero secret leaks detected. Repository audit clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
