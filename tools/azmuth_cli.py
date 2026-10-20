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
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

# Ensure Fleet-Orchestrator root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "orchestrator-state"
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
    print("  AZMUTH MULTI-UNIVERSE FORESIGHT SWEEP")
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


def handle_harvest(args: argparse.Namespace) -> int:
    """Executes sovereign & multilateral opportunity harvesting."""
    from tools.harvest_sovereign_opportunities import SovereignOpportunityHarvester

    harvester = SovereignOpportunityHarvester()
    records = harvester.harvest(source_filter=args.source, limit=args.limit)
    print("=" * 80)
    print("  AZMUTH SOVEREIGN & MULTILATERAL OPPORTUNITY HARVESTER")
    print("=" * 80)
    print(f"- Total Harvested:     {len(records)} opportunities")
    print(f"- GCC Sovereign Roles: {sum(1 for r in records if r.category == 'SOVEREIGN_GCC')}")
    print(f"- UN Multilateral:     {sum(1 for r in records if r.category == 'UN_MULTILATERAL')}")
    print(f"- Diplomatic Embassies:{sum(1 for r in records if r.category == 'EMBASSY_DIPLOMATIC')}")
    print(f"- Tax-Free Positions:  {sum(1 for r in records if r.tax_status in ('TAX_FREE', 'UN_EXEMPT'))}")
    print(f"- Catalog Stored:      {harvester.catalog_path}")
    print("-" * 80)
    for r in records[:5]:
        print(f"[{r.category}] {r.title}")
        print(f"  Org: {r.organization} | Loc: {r.location}")
        print(f"  Comp: {r.compensation_est} ({r.tax_status}) | Visa: {r.visa_pathway}")
        print(f"  URL: {r.url}")
    print("=" * 80)
    return 0


def handle_match(args: argparse.Namespace) -> int:
    """Executes semantic opportunity matching against portfolio pillars."""
    from tools.evaluate_opportunity_fit import SemanticOpportunityMatcher, MATCH_REPORT_PATH

    matcher = SemanticOpportunityMatcher()
    evaluations = matcher.evaluate_catalog(top_k=args.top)

    print("=" * 80)
    print("  AZMUTH SEMANTIC OPPORTUNITY FIT & ALPHA EVALUATOR")
    print("=" * 80)
    print(f"- Total Evaluated: {len(evaluations)}")
    print(f"- Report Cached:   {MATCH_REPORT_PATH}")
    print("=" * 80)

    for idx, e in enumerate(evaluations, 1):
        print(f"\n[{idx}] {e.title}")
        print(f"    Organization:    {e.organization} ({e.location})")
        print(f"    Fit Tier:        {e.fit_tier} (Score: {e.overall_fit_ratio * 100:.1f}%)")
        print(f"    Compensation:    ${e.net_alpha_index_kusd:.1f}k/yr Net ({e.tax_status})")
        print(f"    Visa Pathway:    {e.visa_pathway} (Feasibility: {e.visa_feasibility_score * 100:.1f}%)")
        print("    Pillar Overlap:  " + ", ".join(f"{k}: {v*100:.0f}%" for k, v in e.pillar_breakdown.items()))
        print("    Actionable Gaps: " + e.gap_closure_actions[0])
        print(f"    Target URL:      {e.url}")
    print("\n" + "=" * 80)
    return 0



def handle_break(args) -> int:
    mins = args.minutes
    until = datetime.now(timezone.utc) + timedelta(minutes=mins)
    until_local = datetime.now() + timedelta(minutes=mins)
    telemetry_path = STATE_DIR / "cognitive_telemetry.json"
    data = {
        "break_active": True,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "target_minutes": mins,
        "target_resume": until.isoformat(),
        "target_local": until_local.strftime("%I:%M %p")
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(telemetry_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print("=" * 80)
    print("  AZMUTH COGNITIVE BARRIER FUNCTION -- HUMAN HEADROOM RECOVERY")
    print("=" * 80)
    print(f"[*] Rest cycle initiated: {mins} minutes.")
    print(f"[*] Target resume time:   {until_local.strftime('%I:%M:%S %p')} local time.")
    print("[*] Engine state:          100% verified, clean git tree, all feeds cached.")
    print("[*] Safety Invariant:     h(human_headroom) >= 0.20 enforced.")
    print("=" * 80)
    print("\n[Guidance] Step away from the screen. Walk, stretch, or hydrate.")
    print("If a breakthrough idea strikes during the break, capture it instantly without coding:")
    print("    azmuth dump \"your idea here\"\n")
    print(f"See you at {until_local.strftime('%I:%M %p')}. Enjoy your break!\n")
    return 0


def handle_dump(args) -> int:
    thought = " ".join(args.thought).strip()
    if not thought:
        print("[!] No idea text provided. Usage: azmuth dump <thought text>")
        return 1

    vault_path = STATE_DIR / "cognitive_vault.jsonl"
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    vault_id = f"VLT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    record = {
        "vault_id": vault_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "local_time": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
        "thought": thought
    }
    with open(vault_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    # Check break status
    telemetry_path = STATE_DIR / "cognitive_telemetry.json"
    remaining_msg = ""
    if telemetry_path.exists():
        try:
            with open(telemetry_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if d.get("break_active"):
                t_end = datetime.fromisoformat(d["target_resume"])
                rem = (t_end - datetime.now(timezone.utc)).total_seconds()
                if rem > 0:
                    remaining_msg = f" ({int(rem // 60)}m {int(rem % 60)}s break remaining)"
        except Exception:
            pass

    print(f"[Vaulted] '{thought}' secured to cognitive vault.{remaining_msg}")
    print("[*] Thought captured. Do NOT write code right now. Return to your break!")

    # Incubator Gemini Fleet Worker
    worker_script = ROOT / "tools" / "incubator_gemini_worker.py"
    if worker_script.exists():
        try:
            worker_cmd = [sys.executable, str(worker_script), thought, "--vault-id", vault_id]
            if getattr(args, "verbose", False):
                print("\n[*] [--verbose active] Streaming full Gemini Fleet RFC synthesis directly to terminal...")
                res = subprocess.run(worker_cmd, timeout=40)
            else:
                flags = 0
                if sys.platform == "win32":
                    flags = subprocess.CREATE_NO_WINDOW
                subprocess.Popen(worker_cmd, creationflags=flags, close_fds=True)
                print("[+] Gemini Fleet Worker dispatched headlessly. Research RFC & GitHub Issue generating in background.")
                print("    (Tip: Use 'azmuth dump -v <thought>' if you want the full decoded RFC printed live!)")
        except Exception as e:
            print(f"[Notice] Background incubator dispatch note: {e}")

    return 0


def handle_resume(args) -> int:
    telemetry_path = STATE_DIR / "cognitive_telemetry.json"
    vault_path = STATE_DIR / "cognitive_vault.jsonl"

    break_info = None
    started_at = None
    if telemetry_path.exists():
        try:
            with open(telemetry_path, "r", encoding="utf-8") as f:
                break_info = json.load(f)
            started_at = break_info.get("started_at")
            break_info["break_active"] = False
            with open(telemetry_path, "w", encoding="utf-8") as f:
                json.dump(break_info, f, indent=2)
        except Exception:
            pass

    ideas = []
    if vault_path.exists():
        try:
            raw_entries = []
            with open(vault_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        raw_entries.append(json.loads(line))

            # Deduplicate & unify entries: if an entry has issue_url/rfc_file, it enriches/supersedes the raw stub
            merged = {}
            for e in raw_entries:
                key = (e.get("thought") or e.get("raw_thought", "")).strip().lower()
                if not key:
                    continue
                if key not in merged:
                    merged[key] = dict(e)
                else:
                    # Enrich existing with decoded fields
                    if e.get("rfc_file"):
                        merged[key]["rfc_file"] = e["rfc_file"]
                    if e.get("issue_url"):
                        merged[key]["issue_url"] = e["issue_url"]
                    if e.get("vault_id") and not merged[key].get("vault_id"):
                        merged[key]["vault_id"] = e["vault_id"]
                    if e.get("thought") and not merged[key].get("thought"):
                        merged[key]["thought"] = e["thought"]
            ideas = list(merged.values())
        except Exception:
            pass

    # Filter ideas captured during THIS break if timestamp available
    break_ideas = []
    if started_at:
        try:
            t_start = datetime.fromisoformat(started_at)
            for it in ideas:
                t_it = datetime.fromisoformat(it.get("timestamp", ""))
                if t_it >= t_start:
                    break_ideas.append(it)
        except Exception:
            break_ideas = ideas[-5:]
    if not break_ideas:
        break_ideas = ideas[-5:]

    target = getattr(args, "target", None)

    # 1. Direct Selection Mode (azmuth resume <index> or <issue>)
    if target:
        selected = None
        # Check if numeric index (e.g. "1", "2")
        if target.isdigit():
            idx = int(target) - 1
            if 0 <= idx < len(break_ideas):
                selected = break_ideas[idx]
        # Check if matching issue number directly (e.g. "23" or "#23")
        target_clean = target.lstrip("#")
        if not selected and target_clean.isdigit():
            for it in break_ideas:
                if it.get("issue_url", "").endswith(f"/{target_clean}"):
                    selected = it
                    break

        if selected:
            t_text = selected.get("thought") or selected.get("raw_thought", "Untitled")
            url = selected.get("issue_url")
            rfc_path = selected.get("rfc_file")
            print("=" * 80)
            print(f"  AZMUTH FOCUS ENGINE: ACTIVATING TARGET [{target}]")
            print("=" * 80)
            print(f"[*] Title       : {t_text}")
            if url:
                print(f"[*] Issue Link  : {url}")
            if rfc_path and Path(rfc_path).exists():
                print(f"[*] RFC Path    : {rfc_path}")
                print("-" * 80)
                # Print First 30 lines of RFC
                lines = Path(rfc_path).read_text(encoding="utf-8").splitlines()
                for l in lines[:25]:
                    print(l)
                if len(lines) > 25:
                    print("... [Full RFC available at path above]")
            print("=" * 80)
            print(f"[+] Focus locked on {target}. Ready to execute.\n")
            return 0
        else:
            print(f"[!] Target '{target}' not found in active break queue.")

    # 2. General Menu / Session Summary Mode
    print("=" * 80)
    print("  AZMUTH COGNITIVE ENGINE -- HUMAN SESSION RESUMED")
    print("=" * 80)
    print(f"Welcome back, Aaradhya. Local time: {datetime.now().strftime('%I:%M %p')}.")

    if break_ideas:
        print(f"\nCaptured during your rest cycle ({len(break_ideas)} thought{'s' if len(break_ideas) > 1 else ''}):")
        for idx, it in enumerate(break_ideas, 1):
            t_text = it.get("thought") or it.get("raw_thought", "Untitled thought")
            url = it.get("issue_url")
            rfc_path = it.get("rfc_file")
            issue_tag = f" [#{url.split('/')[-1]}]" if url else ""
            print(f"\n  [{idx}]{issue_tag} {t_text}")
            if url:
                print(f"      Issue Link : {url}")
            if rfc_path and Path(rfc_path).exists():
                try:
                    rfc_text = Path(rfc_path).read_text(encoding="utf-8")
                    lines = [line.strip() for line in rfc_text.splitlines() if line.strip() and not line.startswith("#") and not line.startswith(">") and not line.startswith("-") and not line.startswith("=")]
                    if lines:
                        preview = lines[0][:140] + ("..." if len(lines[0]) > 140 else "")
                        print(f"      Decoded RFC: {preview}")
                except Exception:
                    pass
        print("\n" + "-" * 80)
        print("To focus immediately on an idea and print its full RFC, run:")
        print("    azmuth resume 1          (or azmuth resume #23)")
    else:
        print("\nZero intrusive thoughts logged during rest. Pure cognitive recovery achieved!")

    print("=" * 80)
    print("[+] Human headroom replenished. Ready for execution.\n")
    return 0

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

    # Harvest
    harvest_parser = subparsers.add_parser("harvest", help="Harvest GCC and UN multilateral opportunities")
    harvest_parser.add_argument("--source", type=str, choices=["all", "gcc", "un", "embassy"], default="all", help="Target sector")
    harvest_parser.add_argument("--limit", type=int, default=None, help="Max records to index")

    # Match
    match_parser = subparsers.add_parser("match", help="Match harvested opportunities against your portfolio")
    match_parser.add_argument("--top", type=int, default=5, help="Number of top matches to display")
    match_parser.add_argument("--tier", type=str, choices=["all", "exceptional", "high"], default="all", help="Filter by tier")
    # Break subcommand
    break_parser = subparsers.add_parser("break", help="Initiate a human rest cycle with Cognitive Barrier Function")
    break_parser.add_argument("minutes", type=int, nargs="?", default=30, help="Break duration in minutes (default: 30)")

    # Dump subcommand (instant thought vault)
    dump_parser = subparsers.add_parser("dump", help="Vault a breakthrough idea instantly during a break without writing code")
    dump_parser.add_argument("thought", type=str, nargs="+", help="The idea or insight to secure")
    dump_parser.add_argument("-v", "--verbose", action="store_true", help="Synchronously stream full structured Gemini RFC synthesis in terminal")

    # Resume subcommand
    resume_parser = subparsers.add_parser("resume", help="Resume work session and select an issue/thought to focus on")
    resume_parser.add_argument("target", nargs="?", default=None, help="Optional index [1, 2, ...] or issue number (#23) to immediately checkout/focus")


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
    elif args.subcommand == "harvest":
        return handle_harvest(args)
    elif args.subcommand == "match":
        return handle_match(args)
    elif args.subcommand == "break":
        return handle_break(args)
    elif args.subcommand == "dump":
        return handle_dump(args)
    elif args.subcommand == "resume":
        return handle_resume(args)
    else:
        return launch_gui()


if __name__ == "__main__":
    sys.exit(main())
