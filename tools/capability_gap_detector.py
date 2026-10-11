"""Autonomous Capability Gap Detector — 6th Fleet Sentinel.

Audits repository capabilities across 4 dimensions:
1. Untested adapters: client/adapters/*.py without matching tests.
2. Routing misses & fallthroughs: tasks/queries resulting in STRICT_INTERLOCK.
3. Stale or undocumented skills: declared skills lacking SKILL.md.
4. Dead or broken adapters: adapters failing syntax/import integrity.

Produces structured gap reports in orchestrator-state/gap_report.json and
supports --auto-issue generation for GitHub tracking.
"""

from __future__ import annotations

import argparse
import ast
import datetime
import json
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class Severity(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Gap:
    category: str  # "untested_adapter" | "routing_miss" | "stale_skill" | "dead_adapter"
    severity: Severity
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)
    auto_fixable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity.name,
            "summary": self.summary,
            "details": self.details,
            "auto_fixable": self.auto_fixable,
        }


def _find_imported_adapters(tests_dir: Path) -> set[str]:
    """Find all adapter module names imported anywhere in tests."""
    imported: set[str] = set()
    if not tests_dir.exists():
        return imported

    for test_file in tests_dir.glob("test_*.py"):
        try:
            content = test_file.read_text(encoding="utf-8")
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and "client.adapters" in node.module:
                        parts = node.module.split(".")
                        if len(parts) > 2:
                            imported.add(parts[2])
                        for alias in node.names:
                            imported.add(alias.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if "client.adapters" in alias.name:
                            parts = alias.name.split(".")
                            if len(parts) > 2:
                                imported.add(parts[2])
        except Exception:
            # Fallback to simple string searching if AST fails
            content = test_file.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                if "client.adapters" in line:
                    for token in line.replace(",", " ").split():
                        imported.add(token.strip())
    return imported


def detect_untested_adapters(repo_root: Path) -> List[Gap]:
    """Identify adapters in client/adapters/ lacking unit test coverage."""
    gaps: List[Gap] = []
    adapters_dir = repo_root / "client" / "adapters"
    tests_dir = repo_root / "tests"

    if not adapters_dir.exists():
        return gaps

    imported_in_tests = _find_imported_adapters(tests_dir)

    for adapter_file in sorted(adapters_dir.glob("*.py")):
        stem = adapter_file.stem
        if stem.startswith("__") or stem == "base_adapter":
            continue

        # Check direct test naming variants
        direct_tests = [
            f"test_{stem}.py",
            f"test_{stem}_adapter.py",
            f"test_{stem.replace('_adapter', '')}.py",
            f"test_{stem.replace('_adapter', '')}_adapter.py",
        ]
        has_direct_test = any((tests_dir / t).exists() for t in direct_tests)
        has_import = stem in imported_in_tests

        if not (has_direct_test or has_import):
            gaps.append(
                Gap(
                    category="untested_adapter",
                    severity=Severity.HIGH,
                    summary=f"Adapter '{adapter_file.name}' lacks test coverage",
                    details={
                        "adapter": adapter_file.name,
                        "expected_test": f"test_{stem}.py",
                        "path": str(adapter_file.relative_to(repo_root)),
                    },
                    auto_fixable=True,
                )
            )

    return gaps


def detect_routing_misses(repo_root: Path, days: int = 7) -> List[Gap]:
    """Scan benchmark reports and logs for queries triggering fallthroughs or interlocks."""
    gaps: List[Gap] = []
    bench_dir = repo_root / "orchestrator-state" / "bench"
    if not bench_dir.exists():
        return gaps

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)

    for report_file in sorted(bench_dir.glob("*.json")):
        try:
            mtime = datetime.datetime.fromtimestamp(
                report_file.stat().st_mtime, tz=datetime.timezone.utc
            )
            if mtime < cutoff:
                continue

            data = json.loads(report_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue

            decision = data.get("decision", {})
            if decision.get("policy") == "STRICT_INTERLOCK":
                gaps.append(
                    Gap(
                        category="routing_miss",
                        severity=Severity.MEDIUM,
                        summary=f"Routing trigger required STRICT_INTERLOCK in {report_file.name}",
                        details={
                            "file": report_file.name,
                            "prompt": str(data.get("prompt", ""))[:120],
                            "cell": decision.get("matrix_cell", "(V2, R2)"),
                        },
                        auto_fixable=False,
                    )
                )
        except Exception:
            continue

    return gaps


def detect_stale_skills(repo_root: Path) -> List[Gap]:
    """Verify that skills defined in skills directories contain valid SKILL.md."""
    gaps: List[Gap] = []
    skills_dir = repo_root / ".agents" / "skills"
    if not skills_dir.exists():
        return gaps

    for skill_path in sorted(skills_dir.iterdir()):
        if skill_path.is_dir() and not skill_path.name.startswith("."):
            skill_md = skill_path / "SKILL.md"
            if not skill_md.exists():
                gaps.append(
                    Gap(
                        category="stale_skill",
                        severity=Severity.MEDIUM,
                        summary=f"Skill '{skill_path.name}' is missing SKILL.md specification",
                        details={"skill_dir": skill_path.name},
                        auto_fixable=True,
                    )
                )
    return gaps


def detect_dead_adapters(repo_root: Path) -> List[Gap]:
    """Audit client/adapters/ for Python syntax errors or broken AST."""
    gaps: List[Gap] = []
    adapters_dir = repo_root / "client" / "adapters"
    if not adapters_dir.exists():
        return gaps

    for adapter_file in sorted(adapters_dir.glob("*.py")):
        if adapter_file.name.startswith("__"):
            continue
        try:
            source = adapter_file.read_text(encoding="utf-8")
            ast.parse(source)
        except SyntaxError as e:
            gaps.append(
                Gap(
                    category="dead_adapter",
                    severity=Severity.CRITICAL,
                    summary=f"Syntax error in adapter '{adapter_file.name}': {e.msg}",
                    details={
                        "adapter": adapter_file.name,
                        "line": e.lineno,
                        "offset": e.offset,
                    },
                    auto_fixable=False,
                )
            )
        except Exception as e:
            gaps.append(
                Gap(
                    category="dead_adapter",
                    severity=Severity.HIGH,
                    summary=f"Unreadable adapter file '{adapter_file.name}': {e}",
                    details={"adapter": adapter_file.name},
                    auto_fixable=False,
                )
            )
    return gaps


def generate_gap_report(repo_root: Path, write_output: bool = True) -> Dict[str, Any]:
    """Execute 4-dimension audit and compile structured gap report."""
    gaps: List[Gap] = []
    gaps.extend(detect_dead_adapters(repo_root))
    gaps.extend(detect_untested_adapters(repo_root))
    gaps.extend(detect_routing_misses(repo_root))
    gaps.extend(detect_stale_skills(repo_root))

    # Rank by severity descending
    sorted_gaps = sorted(gaps, key=lambda g: g.severity.value, reverse=True)

    report = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_gaps": len(sorted_gaps),
        "critical": sum(1 for g in sorted_gaps if g.severity == Severity.CRITICAL),
        "high": sum(1 for g in sorted_gaps if g.severity == Severity.HIGH),
        "medium": sum(1 for g in sorted_gaps if g.severity == Severity.MEDIUM),
        "low": sum(1 for g in sorted_gaps if g.severity == Severity.LOW),
        "auto_fixable_count": sum(1 for g in sorted_gaps if g.auto_fixable),
        "gaps": [g.to_dict() for g in sorted_gaps],
    }

    if write_output:
        state_dir = repo_root / "orchestrator-state"
        state_dir.mkdir(parents=True, exist_ok=True)
        out_file = state_dir / "gap_report.json"
        out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report


def create_issue_for_gap(gap: Dict[str, Any], repo_root: Path, dry_run: bool = False) -> Optional[str]:
    """Create a tracked GitHub issue for a high/critical gap."""
    if gap.get("severity") not in ("HIGH", "CRITICAL"):
        return None

    title = f"[Auto-Detected] {gap.get('summary')}"
    body_lines = [
        "## Auto-Generated Capability Gap Report",
        f"- **Category**: `{gap.get('category')}`",
        f"- **Severity**: `{gap.get('severity')}`",
        f"- **Auto-Fixable**: `{'Yes' if gap.get('auto_fixable') else 'No'}`",
        "",
        "## Details",
        "```json",
        json.dumps(gap.get("details", {}), indent=2),
        "```",
        "",
        "## Acceptance Tasks",
    ]

    category = gap.get("category")
    if category == "untested_adapter":
        adapter = gap.get("details", {}).get("adapter", "adapter.py")
        expected_test = gap.get("details", {}).get("expected_test", "test_adapter.py")
        body_lines.extend([
            f"- [ ] Scaffold unit tests in `tests/{expected_test}`",
            f"- [ ] Verify branch coverage for `client/adapters/{adapter}`",
            f"- [ ] Ensure full test suite passes with `pytest tests/`",
            f"- [ ] Synchronize via `.\\sync.bat -m \"test(adapters): add coverage for {adapter}\"`",
        ])
    elif category == "dead_adapter":
        adapter = gap.get("details", {}).get("adapter", "adapter.py")
        body_lines.extend([
            f"- [ ] Fix syntax / AST errors in `client/adapters/{adapter}`",
            "- [ ] Run `pytest tests/` to confirm resolution",
            f"- [ ] Synchronize via `.\\sync.bat -m \"fix(adapters): resolve syntax error in {adapter}\"`",
        ])
    else:
        body_lines.extend([
            "- [ ] Review and resolve capability gap",
            "- [ ] Re-run capability gap detector",
            "- [ ] Synchronize via `.\\sync.bat`",
        ])

    body = "\n".join(body_lines)

    if dry_run:
        print(f"--- [DRY-RUN] WOULD CREATE ISSUE: {title} ---")
        print(body)
        return "https://github.com/dry-run/issue"

    try:
        res = subprocess.run(
            [
                "gh",
                "issue",
                "create",
                "--assignee",
                "@me",
                "--label",
                "auto-generated,self-upgrade,enhancement",
                "--title",
                title,
                "--body",
                body,
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception as e:
        print(f"[-] Failed to create GitHub issue: {e}", file=sys.stderr)
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Fleet Capability Gap Detector")
    parser.add_argument("--repo-root", default=".", help="Root path of Fleet-Orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Print report without writing to disk")
    parser.add_argument("--auto-issue", action="store_true", help="Auto-create GitHub issues for HIGH/CRITICAL gaps")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve()
    report = generate_gap_report(repo, write_output=not args.dry_run)

    if args.format == "json":
        print(json.dumps(report, indent=2))
    else:
        print("=" * 65)
        print("  FLEET CAPABILITY GAP DETECTOR — 6TH SENTINEL AUDIT")
        print("=" * 65)
        print(f"  Generated at      : {report['generated_at']}")
        print(f"  Total Gaps        : {report['total_gaps']}")
        print(f"  Critical          : {report['critical']}")
        print(f"  High              : {report['high']}")
        print(f"  Medium            : {report['medium']}")
        print(f"  Low               : {report['low']}")
        print(f"  Auto-Fixable      : {report['auto_fixable_count']}")
        print("-" * 65)

        if report["gaps"]:
            for i, g in enumerate(report["gaps"], 1):
                print(f"  [{i}] [{g['severity']}] ({g['category']}) {g['summary']}")
        else:
            print("  [+] No capability gaps detected. System fully healthy and covered.")
        print("=" * 65)

    if args.auto_issue and report["high"] + report["critical"] > 0:
        for g in report["gaps"]:
            if g["severity"] in ("HIGH", "CRITICAL"):
                created = create_issue_for_gap(g, repo, dry_run=args.dry_run)
                if created:
                    print(f"[+] Tracked issue: {created}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
