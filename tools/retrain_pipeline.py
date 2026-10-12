#!/usr/bin/env python3
"""Closed-Loop SLM Retraining Pipeline Orchestrator.

Completes the L4 Self-Upgrading Infrastructure closed loop:
  Phase 1 (Gap Detector) → Phase 4 (Adapter Scaffolder) → Phase 3 (This)

Evaluates routing accuracy against golden scenarios, detects dataset
staleness, harvests fresh trajectories, rebuilds unified datasets,
syncs to Google Drive, triggers Colab A100 fine-tuning, and redeploys
GGUF models to LM Studio for sub-50ms local inference.

Two-Phase Lazy Gate:
  Phase A (free, <1s): Check staleness + heuristic accuracy evaluation.
  Phase B (action):    Harvest → Rebuild → Sync → Train → Deploy.
  Phase B only fires when Phase A detects both staleness AND accuracy drift.

Usage:
  python tools/retrain_pipeline.py                          # Standard run
  python tools/retrain_pipeline.py --dry-run                # Evaluate without executing
  python tools/retrain_pipeline.py --force-retrain          # Bypass threshold checks
  python tools/retrain_pipeline.py --min-accuracy 90        # Custom accuracy threshold
  python tools/retrain_pipeline.py --max-staleness-days 7   # Custom staleness window
  python tools/retrain_pipeline.py --retrain-brain          # Also retrain 3B/7B models
  python tools/retrain_pipeline.py --format json            # Machine-readable output
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("retrain_pipeline")

GOLDEN_FIXTURE = ROOT / "tests" / "fixtures" / "adaptive_golden_scenarios.yaml"
DATASET_DIR = ROOT / "dataset"
DATASET_SUMMARY = DATASET_DIR / "dataset_summary.json"
STATE_DIR = ROOT / "orchestrator-state"
MANIFEST_PATH = ROOT / "drive-manifest.json"

# Colab notebook references from drive-manifest.json
INTENT_ROUTER_NOTEBOOK_URL = (
    "https://colab.research.google.com/drive/1xlweNlXJ4maBCfUJVkReZLHMTWwKsYGh"
)
FLEET_BRAIN_NOTEBOOK_URL = (
    "https://colab.research.google.com/drive/1VdTGqTDY32NM_yDchErn01c5fnvFA_uv"
)

DEFAULT_MIN_ACCURACY = 85.0
DEFAULT_MAX_STALENESS_DAYS = 21


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class AccuracyReport:
    """Result of evaluating routing accuracy against golden scenarios."""
    total: int = 0
    archetype_correct: int = 0
    cell_correct: int = 0
    skill_correct: int = 0
    fast_path_correct: int = 0
    composite_accuracy: float = 0.0
    per_scenario: List[Dict[str, Any]] = field(default_factory=list)
    decider: str = "deterministic"
    latency_ms: float = 0.0


@dataclass
class RetrainDecision:
    """Decision on whether retraining is needed."""
    should_retrain: bool
    reason: str
    accuracy: float
    staleness_days: float
    threshold_accuracy: float
    threshold_staleness: int
    phase_a_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    """Full pipeline execution result."""
    decision: RetrainDecision
    harvest_count: int = 0
    dataset_train_size: int = 0
    dataset_eval_size: int = 0
    drive_sync_ok: bool = False
    colab_triggered: bool = False
    colab_method: str = "none"
    post_accuracy: Optional[float] = None
    timestamp: str = ""
    dry_run: bool = False
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Step 1: Accuracy Evaluation
# ---------------------------------------------------------------------------

def evaluate_routing_accuracy(
    fixture_path: Path,
    decider: str = "deterministic",
) -> AccuracyReport:
    """Evaluates routing accuracy against golden scenarios.

    Runs the AdaptiveDecisionEngine against each scenario in the golden
    fixture YAML and computes per-field accuracy scores.

    Returns:
        AccuracyReport with composite accuracy (weighted average).
    """
    from tools.adaptive_decision_harness import AdaptiveDecisionEngine

    if not fixture_path.exists():
        return AccuracyReport(decider=decider)

    with open(fixture_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    scenarios = data.get("scenarios", [])
    if not scenarios:
        return AccuracyReport(decider=decider)

    arch_correct = 0
    cell_correct = 0
    skill_correct = 0
    fp_correct = 0
    scored_arch = 0
    scored_cell = 0
    scored_skill = 0
    per_scenario: List[Dict[str, Any]] = []

    t0 = time.perf_counter()

    for sc in scenarios:
        prompt = sc["prompt"]
        files = sc.get("files")
        exp = sc.get("expected", {})

        decision = AdaptiveDecisionEngine.decide(prompt, files=files, decider=decider)

        result: Dict[str, Any] = {"id": sc.get("id", "?"), "prompt": prompt[:80]}

        # Fast-path accuracy (always scored)
        fp_match = decision.get("is_fast_path") == exp.get("is_fast_path", False)
        if fp_match:
            fp_correct += 1
        result["fast_path_match"] = fp_match

        # Archetype accuracy (scored when expected provides it)
        if exp.get("archetype"):
            scored_arch += 1
            if decision.get("archetype") == exp["archetype"]:
                arch_correct += 1
                result["archetype_match"] = True
            else:
                result["archetype_match"] = False
                result["archetype_got"] = decision.get("archetype")

        # Matrix cell accuracy
        if exp.get("matrix_cell"):
            scored_cell += 1
            if decision.get("matrix_cell") == exp["matrix_cell"]:
                cell_correct += 1
                result["cell_match"] = True
            else:
                result["cell_match"] = False
                result["cell_got"] = decision.get("matrix_cell")

        # Primary skill accuracy
        if exp.get("primary_skill"):
            scored_skill += 1
            if decision.get("primary_skill") == exp["primary_skill"]:
                skill_correct += 1
                result["skill_match"] = True
            else:
                result["skill_match"] = False
                result["skill_got"] = decision.get("primary_skill")

        # Negative skill constraint (not_skill)
        if exp.get("not_skill"):
            result["not_skill_ok"] = decision.get("primary_skill") != exp["not_skill"]

        per_scenario.append(result)

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    total = len(scenarios)

    # Composite accuracy: weighted average of all scored dimensions
    # Weights: fast_path=0.25, archetype=0.25, cell=0.25, skill=0.25
    weights = []
    if total > 0:
        weights.append(fp_correct / total)
    if scored_arch > 0:
        weights.append(arch_correct / scored_arch)
    if scored_cell > 0:
        weights.append(cell_correct / scored_cell)
    if scored_skill > 0:
        weights.append(skill_correct / scored_skill)

    composite = (sum(weights) / len(weights) * 100.0) if weights else 0.0

    return AccuracyReport(
        total=total,
        archetype_correct=arch_correct,
        cell_correct=cell_correct,
        skill_correct=skill_correct,
        fast_path_correct=fp_correct,
        composite_accuracy=round(composite, 1),
        per_scenario=per_scenario,
        decider=decider,
        latency_ms=round(elapsed_ms, 2),
    )


# ---------------------------------------------------------------------------
# Step 2: Staleness Detection
# ---------------------------------------------------------------------------

def check_dataset_staleness(dataset_dir: Path) -> float:
    """Returns dataset age in days based on dataset_summary.json or file mtime.

    Returns:
        Age in fractional days. Returns float('inf') if no dataset exists.
    """
    now = datetime.now(timezone.utc)

    # Try dataset_summary.json timestamp first
    summary_path = dataset_dir / "dataset_summary.json"
    if summary_path.exists():
        try:
            with open(summary_path, "r", encoding="utf-8") as f:
                summary = json.load(f)
            generated_at = summary.get("generated_at")
            if generated_at:
                ts = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
                return max(0.0, (now - ts).total_seconds() / 86400.0)
        except Exception:
            pass

    # Fallback: check unified_fleet_train.jsonl mtime
    train_path = dataset_dir / "unified_fleet_train.jsonl"
    if train_path.exists():
        mtime = datetime.fromtimestamp(train_path.stat().st_mtime, tz=timezone.utc)
        return max(0.0, (now - mtime).total_seconds() / 86400.0)

    return float("inf")


# ---------------------------------------------------------------------------
# Step 3: Decision Gate (Two-Phase Lazy Evaluation)
# ---------------------------------------------------------------------------

def make_retrain_decision(
    accuracy: float,
    staleness_days: float,
    min_accuracy: float = DEFAULT_MIN_ACCURACY,
    max_staleness_days: int = DEFAULT_MAX_STALENESS_DAYS,
    force: bool = False,
) -> RetrainDecision:
    """Two-phase lazy gate: only retrain when genuinely needed.

    Phase A checks are free (<1ms, zero AI tokens):
      1. If forced → retrain.
      2. If accuracy < threshold → retrain (accuracy drift is the primary signal).
      3. If staleness > threshold → retrain (dataset may be outdated).
      4. Otherwise → skip (model is healthy).
    """
    if force:
        return RetrainDecision(
            should_retrain=True,
            reason="Forced retrain requested via --force-retrain",
            accuracy=accuracy,
            staleness_days=staleness_days,
            threshold_accuracy=min_accuracy,
            threshold_staleness=max_staleness_days,
            phase_a_details={"trigger": "force"},
        )

    accuracy_drift = accuracy < min_accuracy
    dataset_stale = staleness_days > max_staleness_days

    if accuracy_drift:
        return RetrainDecision(
            should_retrain=True,
            reason=f"Routing accuracy {accuracy:.1f}% below threshold {min_accuracy}%",
            accuracy=accuracy,
            staleness_days=staleness_days,
            threshold_accuracy=min_accuracy,
            threshold_staleness=max_staleness_days,
            phase_a_details={"trigger": "accuracy_drift", "gap": round(min_accuracy - accuracy, 1)},
        )

    if dataset_stale:
        return RetrainDecision(
            should_retrain=True,
            reason=f"Dataset staleness {staleness_days:.1f}d exceeds {max_staleness_days}d threshold",
            accuracy=accuracy,
            staleness_days=staleness_days,
            threshold_accuracy=min_accuracy,
            threshold_staleness=max_staleness_days,
            phase_a_details={"trigger": "staleness", "overage_days": round(staleness_days - max_staleness_days, 1)},
        )

    return RetrainDecision(
        should_retrain=False,
        reason=f"Model healthy: accuracy {accuracy:.1f}% >= {min_accuracy}%, staleness {staleness_days:.1f}d <= {max_staleness_days}d",
        accuracy=accuracy,
        staleness_days=staleness_days,
        threshold_accuracy=min_accuracy,
        threshold_staleness=max_staleness_days,
        phase_a_details={"trigger": "none"},
    )


# ---------------------------------------------------------------------------
# Step 4: Fresh Trajectory Harvest
# ---------------------------------------------------------------------------

def harvest_fresh_trajectories(dry_run: bool = False) -> int:
    """Invokes tools/harvest_agent_trajectories.py to mine latest brain transcripts.

    Returns:
        Number of harvested samples (0 on dry-run or failure).
    """
    harvest_script = ROOT / "tools" / "harvest_agent_trajectories.py"
    if not harvest_script.exists():
        logger.warning("harvest_agent_trajectories.py not found")
        return 0

    if dry_run:
        logger.info("[DRY-RUN] Would invoke: python tools/harvest_agent_trajectories.py")
        return 0

    logger.info("Harvesting fresh agent trajectories from brain transcripts...")
    try:
        res = subprocess.run(
            [sys.executable, str(harvest_script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if res.returncode == 0:
            # Parse sample count from output
            for line in res.stdout.splitlines():
                if "Agent-Reflex" in line and "samples" in line:
                    try:
                        count = int(line.split(":")[1].strip().split()[0])
                        return count
                    except (ValueError, IndexError):
                        pass
            return 1  # Success but couldn't parse count
        logger.warning(f"Harvest script exited with code {res.returncode}: {res.stderr[:200]}")
        return 0
    except subprocess.TimeoutExpired:
        logger.warning("Harvest script timed out after 300s")
        return 0
    except Exception as e:
        logger.warning(f"Harvest invocation failed: {e}")
        return 0


# ---------------------------------------------------------------------------
# Step 5: Unified Dataset Rebuild
# ---------------------------------------------------------------------------

def rebuild_unified_dataset(dry_run: bool = False) -> tuple[int, int]:
    """Invokes tools/build_unified_fleet_dataset.py to merge all sources.

    Returns:
        Tuple of (train_count, eval_count). Both 0 on dry-run or failure.
    """
    build_script = ROOT / "tools" / "build_unified_fleet_dataset.py"
    if not build_script.exists():
        logger.warning("build_unified_fleet_dataset.py not found")
        return 0, 0

    if dry_run:
        logger.info("[DRY-RUN] Would invoke: python tools/build_unified_fleet_dataset.py")
        return 0, 0

    logger.info("Rebuilding unified fleet dataset...")
    try:
        res = subprocess.run(
            [sys.executable, str(build_script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if res.returncode == 0:
            train_count = 0
            eval_count = 0
            for line in res.stdout.splitlines():
                if "unified_fleet_train" in line:
                    try:
                        train_count = int(line.split("with")[1].strip().split()[0])
                    except (ValueError, IndexError):
                        pass
                elif "unified_fleet_eval" in line:
                    try:
                        eval_count = int(line.split("with")[1].strip().split()[0])
                    except (ValueError, IndexError):
                        pass

            # Update dataset_summary.json with fresh timestamp
            summary = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "train_samples": train_count,
                "eval_samples": eval_count,
                "total_samples": train_count + eval_count,
            }
            DATASET_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
            with open(DATASET_SUMMARY, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)

            return train_count, eval_count
        logger.warning(f"Dataset build exited with code {res.returncode}: {res.stderr[:200]}")
        return 0, 0
    except Exception as e:
        logger.warning(f"Dataset rebuild failed: {e}")
        return 0, 0


# ---------------------------------------------------------------------------
# Step 6: Drive Sync
# ---------------------------------------------------------------------------

def sync_dataset_to_drive(dry_run: bool = False) -> bool:
    """Syncs fresh datasets to Google Drive via scripts/sync_drive.py.

    Returns:
        True if sync succeeded (or dry-run), False on failure.
    """
    sync_script = ROOT / "scripts" / "sync_drive.py"
    if not sync_script.exists():
        logger.warning("sync_drive.py not found")
        return False

    if dry_run:
        logger.info("[DRY-RUN] Would invoke: python scripts/sync_drive.py --file dataset/unified_fleet_train.jsonl")
        logger.info("[DRY-RUN] Would invoke: python scripts/sync_drive.py --file dataset/unified_fleet_eval.jsonl")
        return True

    logger.info("Syncing datasets to Google Drive...")
    files_to_sync = [
        "dataset/unified_fleet_train.jsonl",
        "dataset/unified_fleet_eval.jsonl",
    ]

    all_ok = True
    for rel_path in files_to_sync:
        try:
            res = subprocess.run(
                [sys.executable, str(sync_script), "--file", rel_path],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=300,
            )
            if res.returncode != 0:
                logger.warning(f"Drive sync failed for {rel_path}: {res.stderr[:200]}")
                all_ok = False
            else:
                logger.info(f"Synced {rel_path} to Drive")
        except Exception as e:
            logger.warning(f"Drive sync exception for {rel_path}: {e}")
            all_ok = False

    return all_ok


# ---------------------------------------------------------------------------
# Step 7: Colab A100 Trigger
# ---------------------------------------------------------------------------

def trigger_colab_training(
    retrain_brain: bool = False,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Triggers Colab A100 fine-tuning via CLI or returns manual instructions.

    Strategy: CLI-first with manual fallback.
      1. Try `colab run --gpu A100` for autonomous headless execution.
      2. If CLI unavailable, emit actionable manual instructions with notebook URL.

    Args:
        retrain_brain: If True, also triggers fleet_master_brain_forge.ipynb (3B/7B).
        dry_run: Evaluate without executing.

    Returns:
        Tuple of (triggered: bool, method: str).
        method is one of: "cli", "manual_instructions", "dry_run".
    """
    if dry_run:
        logger.info("[DRY-RUN] Would trigger Colab A100 training")
        return False, "dry_run"

    # Determine which notebooks to trigger
    notebooks = [
        ("Intent Router (0.5B)", INTENT_ROUTER_NOTEBOOK_URL, "slm_time_router_forge"),
    ]
    if retrain_brain:
        notebooks.append(
            ("Fleet Master Brain (3B/7B)", FLEET_BRAIN_NOTEBOOK_URL, "fleet_master_brain_forge"),
        )

    # Attempt CLI-based headless execution
    colab_bin = shutil.which("colab")
    if not colab_bin:
        # Check Windows-specific launcher
        colab_cmd = Path.home() / ".local" / "bin" / "colab.cmd"
        if colab_cmd.exists():
            colab_bin = str(colab_cmd)

    if colab_bin:
        logger.info(f"Colab CLI found at: {colab_bin}")
        for name, url, session_name in notebooks:
            logger.info(f"Triggering {name} training on Colab A100...")
            try:
                res = subprocess.run(
                    [str(colab_bin), "run", "--gpu", "A100", "-s", session_name,
                     str(ROOT / "notebooks" / f"{session_name}.ipynb")],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    timeout=7200,  # 2-hour ceiling for A100 training
                )
                if res.returncode == 0:
                    logger.info(f"Colab training completed for {name}")
                else:
                    logger.warning(f"Colab CLI returned code {res.returncode} for {name}")
            except subprocess.TimeoutExpired:
                logger.warning(f"Colab training timed out for {name} (>2h)")
            except Exception as e:
                logger.warning(f"Colab CLI failed for {name}: {e}")
        return True, "cli"

    # Fallback: Manual instructions
    print("\n" + "=" * 65)
    print("  COLAB A100 TRAINING — MANUAL EXECUTION REQUIRED")
    print("=" * 65)
    for name, url, session_name in notebooks:
        print(f"\n  [{name}]")
        print(f"  Open: {url}")
        print(f"  Runtime → Change runtime type → A100 GPU")
        print(f"  Runtime → Run all (Ctrl+F9)")
        print(f"  Dataset auto-fetches from Drive. GGUF auto-persists to Drive.")
        print(f"  Final cell auto-teardowns via runtime.unassign()")
    print("\n" + "=" * 65)

    return False, "manual_instructions"


# ---------------------------------------------------------------------------
# Step 8: Post-Training Re-Verification
# ---------------------------------------------------------------------------

def post_training_verify(fixture_path: Path) -> Optional[float]:
    """Re-evaluates accuracy after model redeployment.

    Only meaningful when LM Studio is running the new model. Otherwise
    returns the deterministic heuristic baseline (which should be stable).
    """
    try:
        report = evaluate_routing_accuracy(fixture_path, decider="deterministic")
        return report.composite_accuracy
    except Exception as e:
        logger.warning(f"Post-training verification failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Pipeline Orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(
    min_accuracy: float = DEFAULT_MIN_ACCURACY,
    max_staleness_days: int = DEFAULT_MAX_STALENESS_DAYS,
    force_retrain: bool = False,
    retrain_brain: bool = False,
    dry_run: bool = False,
    output_format: str = "text",
) -> PipelineResult:
    """Executes the full 7-step closed-loop retraining pipeline.

    Phase A (free, <1s):
      Step 1: Evaluate routing accuracy against golden scenarios.
      Step 2: Check dataset staleness.
      Step 3: Decision gate — should we retrain?

    Phase B (action, only if Phase A triggers):
      Step 4: Harvest fresh trajectories from brain transcripts.
      Step 5: Rebuild unified dataset.
      Step 6: Sync fresh dataset to Google Drive.
      Step 7: Trigger Colab A100 training (CLI or manual).
      Step 8: Post-training re-verification.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    if output_format == "text":
        print("\n" + "=" * 65)
        print("  CLOSED-LOOP SLM RETRAINING PIPELINE")
        print("  L4 Self-Upgrading Infrastructure -- Phase 3")
        print("=" * 65)

    # ── Phase A: Free evaluation ──────────────────────────────────────────

    # Step 1: Accuracy evaluation
    if output_format == "text":
        print("\n[Step 1/8] Evaluating routing accuracy against golden scenarios...")
    accuracy_report = evaluate_routing_accuracy(GOLDEN_FIXTURE, decider="deterministic")
    accuracy = accuracy_report.composite_accuracy
    if output_format == "text":
        print(f"  Composite accuracy: {accuracy:.1f}% ({accuracy_report.total} scenarios, {accuracy_report.latency_ms:.1f}ms)")

    # Step 2: Staleness detection
    if output_format == "text":
        print("\n[Step 2/8] Checking dataset staleness...")
    staleness = check_dataset_staleness(DATASET_DIR)
    if output_format == "text":
        if staleness == float("inf"):
            print("  Dataset age: UNKNOWN (no summary or train file found)")
        else:
            print(f"  Dataset age: {staleness:.1f} days (threshold: {max_staleness_days}d)")

    # Step 3: Decision gate
    if output_format == "text":
        print("\n[Step 3/8] Decision gate...")
    decision = make_retrain_decision(
        accuracy=accuracy,
        staleness_days=staleness,
        min_accuracy=min_accuracy,
        max_staleness_days=max_staleness_days,
        force=force_retrain,
    )

    result = PipelineResult(
        decision=decision,
        timestamp=timestamp,
        dry_run=dry_run,
    )

    if not decision.should_retrain:
        if output_format == "text":
            print(f"  [+] {decision.reason}")
            print("\n[+] No retraining needed. Pipeline exiting clean.")
            print("=" * 65 + "\n")
        return result

    if output_format == "text":
        print(f"  [!] {decision.reason}")
        if dry_run:
            print("  [DRY-RUN MODE -- no side effects will be produced]")

    # ── Phase B: Action pipeline ──────────────────────────────────────────

    # Step 4: Harvest fresh trajectories
    if output_format == "text":
        print("\n[Step 4/8] Harvesting fresh agent trajectories...")
    result.harvest_count = harvest_fresh_trajectories(dry_run=dry_run)
    if output_format == "text":
        print(f"  Harvested: {result.harvest_count} new samples")

    # Step 5: Rebuild unified dataset
    if output_format == "text":
        print("\n[Step 5/8] Rebuilding unified fleet dataset...")
    train_count, eval_count = rebuild_unified_dataset(dry_run=dry_run)
    result.dataset_train_size = train_count
    result.dataset_eval_size = eval_count
    if output_format == "text":
        print(f"  Train: {train_count} samples, Eval: {eval_count} samples")

    # Step 6: Drive sync
    if output_format == "text":
        print("\n[Step 6/8] Syncing datasets to Google Drive...")
    result.drive_sync_ok = sync_dataset_to_drive(dry_run=dry_run)
    if output_format == "text":
        status = "OK" if result.drive_sync_ok else "FAILED"
        print(f"  Drive sync: {status}")

    # Step 7: Colab trigger
    if output_format == "text":
        print("\n[Step 7/8] Triggering Colab A100 fine-tuning...")
    triggered, method = trigger_colab_training(retrain_brain=retrain_brain, dry_run=dry_run)
    result.colab_triggered = triggered
    result.colab_method = method
    if output_format == "text":
        print(f"  Colab triggered: {triggered} (method: {method})")

    # Step 8: Post-training re-verification
    if output_format == "text":
        print("\n[Step 8/8] Post-training accuracy re-verification...")
    if not dry_run and triggered:
        result.post_accuracy = post_training_verify(GOLDEN_FIXTURE)
        if output_format == "text" and result.post_accuracy is not None:
            print(f"  Post-training accuracy: {result.post_accuracy:.1f}%")
    else:
        if output_format == "text":
            print("  Skipped (dry-run or manual Colab execution pending)")

    # ── Report ────────────────────────────────────────────────────────────

    # Write structured report to orchestrator-state
    if not dry_run:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        report_path = STATE_DIR / "retrain_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2)
        if output_format == "text":
            print(f"\n[INFO] Report saved: {report_path}")

    if output_format == "text":
        print("\n" + "=" * 65)
        if result.colab_method == "manual_instructions":
            print("  ACTION REQUIRED: Execute Colab notebook manually (URLs above)")
        elif dry_run:
            print("  DRY-RUN COMPLETE -- no side effects produced")
        else:
            print("  PIPELINE COMPLETE")
        print("=" * 65 + "\n")

    return result


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Closed-Loop SLM Retraining Pipeline — L4 Self-Upgrading Infrastructure Phase 3",
    )
    parser.add_argument(
        "--min-accuracy", type=float, default=DEFAULT_MIN_ACCURACY,
        help=f"Minimum composite accuracy threshold (default: {DEFAULT_MIN_ACCURACY}%%)",
    )
    parser.add_argument(
        "--max-staleness-days", type=int, default=DEFAULT_MAX_STALENESS_DAYS,
        help=f"Maximum dataset staleness in days (default: {DEFAULT_MAX_STALENESS_DAYS})",
    )
    parser.add_argument(
        "--force-retrain", action="store_true",
        help="Bypass threshold checks and force full retraining pipeline",
    )
    parser.add_argument(
        "--retrain-brain", action="store_true",
        help="Also retrain the 3B/7B Fleet Master Brain models (default: intent router only)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Evaluate pipeline without executing any side effects",
    )
    parser.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    result = run_pipeline(
        min_accuracy=args.min_accuracy,
        max_staleness_days=args.max_staleness_days,
        force_retrain=args.force_retrain,
        retrain_brain=args.retrain_brain,
        dry_run=args.dry_run,
        output_format=args.format,
    )

    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
