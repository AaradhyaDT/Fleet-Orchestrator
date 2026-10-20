#!/usr/bin/env python3
"""tools/incubator_gemini_worker.py
-----------------------------------
Autonomous Background Incubator Worker powered by Gemini API Fleet Key Rotator.

Lifecycle:
1. Receives raw thought text and metadata as arguments.
2. Acquires healthy key from GeminiKeyRotator (30-key fleet).
3. Queries Gemini (gemini-2.5-flash) to structure the raw idea into a formal BRL Incubator RFC:
   - Target Ecosystem Module & Universe Lobe (SPARK, BiasAperture, Fleet, Brainstorm, U7, U14, etc.)
   - Theoretical Invariant / Mathematical Formulation
   - Empirical Falsifiable Hypothesis
   - Boundary Conditions & Failure Modes
   - 1-Line Immediate Next Step
4. Saves structured RFC markdown to `orchestrator-state/incubator/`
5. Dispatches a tracked GitHub Issue to `Aaradhya-Dev-Tamrakar/brainstorm` via `gh issue create --body-file`
   adhering to canonical /github-workflow patterns.
6. Updates `orchestrator-state/cognitive_vault.jsonl` with the structured card and issue URL.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "orchestrator-state"
INCUBATOR_DIR = STATE_DIR / "incubator"
VAULT_PATH = STATE_DIR / "cognitive_vault.jsonl"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [Incubator-Worker] %(message)s")
logger = logging.getLogger("incubator_worker")

# Ensure Fleet root is on sys.path for rotator import
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from client.adapters.gemini_fleet_rotator import GeminiKeyRotator

SYSTEM_PROMPT = """You are the Chief Research Architect of the Brainstorm Research Lab (BRL) and Fleet-Orchestrator ecosystem.
Your job is to transform a raw, fleeting thought captured by Aaradhya during a rest break into a high-agency, instructor-grade Research & Development Incubator RFC.

Structure your response strictly in the following GitHub Markdown format:

## 1. Executive Summary & Problem Formulation
[Concise summary of the breakthrough idea and what inefficiency or technical challenge it resolves]

## 2. Target Ecosystem Module & Universe Mapping
- **Primary Repository / Module**: [e.g. SPARK, BiasAperture, Fleet-Orchestrator, Brainstorm, Cyber-Forensics]
- **Universe Lobe**: [e.g. U0-U14, such as U7 Cyber Resilience, U10 Edge AI, U14 Frontier ATS]
- **Architectural Layer**: [e.g. Hardware/ISR, SMT Solver Invariant, Multi-Agent Consensus, Evaluation Gate]

## 3. Theoretical Invariant & Mathematical Model
[State the exact invariant, state-space equations, Control Barrier Function h(x)>=0, or formal SMT logic constraint]

## 4. Falsifiable Hypothesis & Empirical Benchmark
- **Hypothesis**: [Clear falsifiable statement adhering to BRL standards]
- **Verification Metric**: [Quantitative success threshold, e.g. latency < 5ms, recall >= 0.95, 0 deadlocks]
- **Baseline Comparison**: [Existing status quo vs. proposed upgrade]

## 5. Failure Modes & Boundary Conditions
- [Edge case 1: e.g. floating point quantization on microcontrollers]
- [Edge case 2: e.g. network latency or token degradation]

## 6. Immediate Next Step
- [ ] [Single concise, actionable task to execute once the break finishes]
"""


async def generate_incubator_rfc(raw_thought: str) -> str:
    """Uses Gemini Key Rotator to synthesize structured RFC."""
    rotator = GeminiKeyRotator()
    slot = await rotator.get_next_slot()
    logger.info("Acquired Gemini key slot: %s", slot.masked_key)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={slot.api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"SYSTEM GUIDANCE:\n{SYSTEM_PROMPT}\n\nUSER RAW THOUGHT CAPTURED DURING BREAK:\n\"{raw_thought}\""}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 2048
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def dispatch_github_issue(title: str, body_path: Path) -> str | None:
    """Dispatches a tracked issue to Aaradhya-Dev-Tamrakar/brainstorm using --body-file."""
    cmd = [
        "gh", "issue", "create",
        "--repo", "Aaradhya-Dev-Tamrakar/brainstorm",
        "--title", f"[Incubator] {title}",
        "--body-file", str(body_path),
        "--label", "enhancement",
        "--assignee", "AaradhyaDT"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if res.returncode == 0:
            url = res.stdout.strip()
            logger.info("Successfully created issue in brainstorm: %s", url)
            return url
        else:
            logger.warning("Failed to create issue in brainstorm: %s", res.stderr.strip() or res.stdout.strip())
    except Exception as e:
        logger.error("Exception creating GitHub issue: %s", e)
    return None


async def main_async(raw_thought: str, create_issue: bool = True) -> int:
    timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    INCUBATOR_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("  AZMUTH INCUBATOR: AUTONOMOUS GEMINI FLEET SYNTHESIS")
    print("=" * 80)
    print(f"Raw Thought: '{raw_thought}'")
    print(f"Timestamp:   {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}")
    print("=" * 80)

    # 1. Synthesize RFC via Gemini Fleet
    rfc_content = await generate_incubator_rfc(raw_thought)

    # Extract clean title from thought
    clean_title = raw_thought.split("\n")[0][:70].strip()

    # 2. Save RFC markdown file
    rfc_file = INCUBATOR_DIR / f"RFC_{timestamp_slug}.md"
    full_markdown = f"# Incubator RFC: {clean_title}\n\n> **Raw Thought**: *\"{raw_thought}\"*\n> **Captured At**: `{datetime.now(timezone.utc).isoformat()}`\n\n---\n\n{rfc_content}\n"
    with open(rfc_file, "w", encoding="utf-8") as f:
        f.write(full_markdown)
    print(f"[+] Saved structured RFC artifact to: {rfc_file}")

    # 3. Dispatch GitHub Issue if requested
    issue_url = None
    if create_issue:
        issue_url = dispatch_github_issue(clean_title, rfc_file)

    # 4. Update cognitive_vault.jsonl entry
    vault_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "local_time": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
        "raw_thought": raw_thought,
        "rfc_file": str(rfc_file),
        "issue_url": issue_url
    }
    with open(VAULT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(vault_record) + "\n")

    print(f"[+] Incubator workflow complete. Issue: {issue_url or 'Local RFC only'}\n")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous Incubator Worker via Gemini Fleet")
    parser.add_argument("thought", type=str, nargs="+", help="The raw thought to process")
    parser.add_argument("--no-issue", action="store_true", help="Skip remote GitHub issue dispatch")
    args = parser.parse_args()

    raw_thought = " ".join(args.thought).strip()
    if not raw_thought:
        sys.exit(1)

    sys.exit(asyncio.run(main_async(raw_thought, create_issue=not args.no_issue)))


if __name__ == "__main__":
    main()
