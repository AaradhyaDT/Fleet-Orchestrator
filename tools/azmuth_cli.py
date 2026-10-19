#!/usr/bin/env python3
"""tools/azmuth_cli.py
---------------------
Global CLI entrypoint for the Azmuth Neuromorphic & Foresight Ecosystem.

Behavior:
- Running `azmuth` with zero arguments directly launches the native desktop
  Azmuth Command Center GUI (tools/azmuth_gui.py).
- Running `azmuth <subcommand>` executes headless CLI diagnostics:
  * sweep    : Run 12-universe 81-node multi-universe sweep
  * cbf      : Run Control Barrier Function (CBF) audit & mitigation check
  * live     : Query real-time hardware telemetry (CPU temp, RAM, power, SPARK queue)
  * sde      : Run stratified continuous-time Euler-Maruyama risk horizon trajectories
  * gate     : Arbitrate high-stakes motion via Celestialsapien Gate (Alien X)
  * trigger  : Run closed-loop autonomic mitigation check
  * gui      : Explicitly launch GUI
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

# Ensure Fleet-Orchestrator root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def launch_gui() -> int:
    """Launches the Azmuth Command Center GUI."""
    gui_script = ROOT / "tools" / "azmuth_gui.py"
    if not gui_script.exists():
        print(f"[Error] GUI script not found at {gui_script}", file=sys.stderr)
        return 1

    # On Windows, prefer launching pythonw or python detached
    cmd = [sys.executable, str(gui_script)]
    try:
        # Spawn detached so it opens cleanly without blocking terminal if invoked directly
        if sys.platform == "win32":
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            subprocess.Popen(
                cmd,
                cwd=str(ROOT),
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
            )
        else:
            subprocess.Popen(cmd, cwd=str(ROOT), start_new_session=True)
        print("[+] Azmuth Command Center GUI launched successfully.")
        return 0
    except Exception as e:
        print(f"[Error] Failed to launch Azmuth GUI: {e}", file=sys.stderr)
        return 1


def handle_sweep(args: argparse.Namespace) -> int:
    """Executes the multi-universe sweep."""
    from tools.azmuth_macro_graph import sweep_all_universes

    results = sweep_all_universes()
    print("=" * 80)
    print("  AZMUTH MULTI-UNIVERSE 81-NODE SWEEP")
    print("=" * 80)
    print(f"- Total Universes Mounted: {results.get('total_cartridges', 12)}")
    print(f"- Systemic Spikes Found:   {len(results.get('systemic_spikes', []))}")
    print(f"- Critical Chokepoints:    {len(results.get('critical_chokepoints', []))}")
    print("=" * 80)
    return 0


def handle_cbf(args: argparse.Namespace) -> int:
    """Executes the CBF Governor evaluation."""
    from tools.azmuth_cbf_governor import run_cbf_governor_cli
    run_cbf_governor_cli(argv=[])
    return 0


def handle_live(args: argparse.Namespace) -> int:
    """Queries live hardware sensors."""
    from tools.azmuth_live_sensors import AzmuthLiveSensors
    sensors = AzmuthLiveSensors()
    snap = sensors.read_hardware_snapshot()
    print("=" * 80)
    print("  AZMUTH LIVE HARDWARE & TELEMETRY STREAM")
    print("=" * 80)
    print(f"- CPU Temp (Est):        {snap.cpu_package_temp_c} °C")
    print(f"- CPU Utilization:       {snap.cpu_load_pct}%")
    print(f"- Host RAM Saturation:   {snap.ram_saturation_pct}%")
    print(f"- Power Draw (Est):      {snap.estimated_power_mw} mW")
    print(f"- Battery / Plugged:     {snap.battery_pct}% (Plugged: {snap.power_plugged})")
    print(f"- SPARK IMU Rate:        {snap.spark_imu_rate_hz} Hz")
    print(f"- SPARK Queue Watermark: {snap.spark_freertos_watermark} slots")
    print("=" * 80)
    return 0


def handle_sde(args: argparse.Namespace) -> int:
    """Runs multi-scale SDE horizon projections."""
    from tools.azmuth_multiscale_sde import run_multiscale_cli
    run_multiscale_cli()
    return 0


def handle_gate(args: argparse.Namespace) -> int:
    """Arbitrates a high-stakes action through Alien X consensus."""
    from tools.celestialsapien_gate import CelestialsapienGate
    gate = CelestialsapienGate()
    decision = gate.arbitrate(action_type=args.action, target_payload=args.payload)
    print("=" * 80)
    print("  CELESTIALSAPIEN CONSENSUS GATE (ALIEN X)")
    print("=" * 80)
    print(f"- Action:            {decision.action_type}")
    print(f"- Consensus Granted: {decision.consensus_granted}")
    print(f"- Rationale:         {decision.reason}")
    print(f"- Bellicus Vote:     {decision.bellicus.approved} (Conf: {decision.bellicus.confidence:.2f})")
    print(f"- Serena Vote:       {decision.serena.approved} (Conf: {decision.serena.confidence:.2f})")
    print("=" * 80)
    return 0 if decision.consensus_granted else 1


def handle_trigger(args: argparse.Namespace) -> int:
    """Executes closed-loop autonomic mitigation check."""
    from tools.azmuth_autonomic_trigger import AzmuthAutonomicTrigger
    trigger = AzmuthAutonomicTrigger(dry_run=args.dry_run)
    verdict = trigger.evaluate_and_dispatch(force_dispatch=args.force)
    print("=" * 80)
    print("  AZMUTH AUTONOMIC MITIGATION TRIGGER")
    print("=" * 80)
    print(f"- Summary:             {verdict.summary}")
    print(f"- Mitigation Required: {verdict.mitigation_required}")
    print(f"- Action Type:         {verdict.action_type}")
    print(f"- Target Node:         {verdict.target_node}")
    print(f"- Dispatch Success:    {verdict.dispatch_success}")
    print("=" * 80)
    return 0 if verdict.dispatch_success else 1


def main() -> int:
    # If no arguments provided in CLI/PowerShell, default directly to opening GUI
    if len(sys.argv) == 1:
        return launch_gui()

    parser = argparse.ArgumentParser(
        prog="azmuth",
        description="Azmuth Neuromorphic & Foresight CLI (Defaults to launching GUI when called with no arguments).",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # GUI
    subparsers.add_parser("gui", help="Explicitly launch the Azmuth Command Center GUI")

    # Sweep
    subparsers.add_parser("sweep", help="Run 12-universe 81-node multi-universe sweep")

    # CBF
    subparsers.add_parser("cbf", help="Run Control Barrier Function (CBF) invariance evaluation")

    # Live Sensors
    subparsers.add_parser("live", help="Query live hardware sensor streams (CPU, RAM, SPARK)")

    # SDE
    subparsers.add_parser("sde", help="Run multi-scale continuous Euler-Maruyama SDE risk projections")

    # Gate
    gate_parser = subparsers.add_parser("gate", help="Arbitrate action via Celestialsapien consensus (Alien X)")
    gate_parser.add_argument("action", type=str, help="Action type (e.g. EXECUTE_REFACTOR, DISPATCH_BURST)")
    gate_parser.add_argument("payload", type=str, nargs="?", default="System Inspection", help="Target description")

    # Autonomic Trigger
    trigger_parser = subparsers.add_parser("trigger", help="Run closed-loop autonomic mitigation trigger")
    trigger_parser.add_argument("--dry-run", action="store_true", help="Simulate mitigation")
    trigger_parser.add_argument("--force", action="store_true", help="Force mitigation evaluation")

    args = parser.parse_args()

    if args.subcommand == "gui":
        return launch_gui()
    elif args.subcommand == "sweep":
        return handle_sweep(args)
    elif args.subcommand == "cbf":
        return handle_cbf(args)
    elif args.subcommand == "live":
        return handle_live(args)
    elif args.subcommand == "sde":
        return handle_sde(args)
    elif args.subcommand == "gate":
        return handle_gate(args)
    elif args.subcommand == "trigger":
        return handle_trigger(args)
    else:
        return launch_gui()


if __name__ == "__main__":
    sys.exit(main())
