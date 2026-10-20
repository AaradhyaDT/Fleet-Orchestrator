#!/usr/bin/env python3
"""tools/incubator_gemini_worker.py
-----------------------------------
Autonomous Background Incubator Worker powered by Gemini API Fleet Key Rotator
with Copilot CLI (GitHub PAT) Tier-2 fallback.

Tiered Synthesis Pipeline:
  Tier 1: Gemini API Fleet (30-key round-robin, multi-model candidate list).
  Tier 2: GitHub Copilot CLI via PAT pool (31 accounts from .env.fleet.copilot),
          invoked headlessly when all Gemini keys are exhausted or throttled.

Lifecycle:
1. Receives raw thought text and metadata as arguments.
2. Tier 1: Acquires healthy key from GeminiKeyRotator (30-key fleet).
3. Queries Gemini (gemini-flash-lite-latest / gemini-2.5-flash) with auto-retry and
   multi-slot rotation to structure the raw idea into a formal BRL Incubator RFC.
4. Tier 2 Fallback: If all Gemini fleet keys fail, discovers Copilot PATs from
   .env.fleet.copilot and invokes `copilot -p` headlessly to synthesize the RFC
   via GPT-4o / Claude 3.7 Sonnet / o3-mini (GitHub Copilot model catalog).
5. Saves structured RFC markdown to `orchestrator-state/incubator/`
6. Dispatches a tracked GitHub Issue to `Aaradhya-Dev-Tamrakar/brainstorm` via `gh issue create --body-file`
   adhering to canonical /github-workflow patterns.
7. Updates `orchestrator-state/cognitive_vault.jsonl` with the structured card and issue URL.
"""

from __future__ import annotations
import re

import argparse
import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "orchestrator-state"
INCUBATOR_DIR = STATE_DIR / "incubator"
VAULT_PATH = STATE_DIR / "cognitive_vault.jsonl"
COPILOT_ENV_PATH = ROOT / ".env.fleet.copilot"

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
    """Uses Gemini Key Rotator with auto-retry and multi-slot rotation to synthesize structured RFC.

    Models prioritized:
      1. gemini-3.5-flash-lite (Ultra-fast low-latency tier, 500 RPD, 15 RPM)
      2. gemini-3.1-flash-lite (High-capacity tier, 500 RPD, 15 RPM)
      3. gemini-3.6-flash (Active frontier flash, 20 RPD, 5 RPM)
      4. gemini-3.8-flash (High-capability reasoning flash, 20 RPD, 5 RPM)
      5. gemini-2.5-flash (Legacy fallback)
    """
    rotator = GeminiKeyRotator()
    candidate_models = [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.8-flash",
        "gemini-2.5-flash",
    ]

    max_attempts = max(rotator.total_keys * 2, 6)
    last_err = None

    for attempt in range(max_attempts):
        slot = await rotator.get_next_slot()
        logger.info("Attempt %d/%d: Acquired Gemini key slot: %s", attempt + 1, max_attempts, slot.masked_key)

        slot_success = False
        for model_name in candidate_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={slot.api_key}"
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

            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read())
                    text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    slot.total_calls += 1
                    logger.info("Successfully synthesized RFC using slot %s with model %s", slot.masked_key, model_name)
                    return text
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code == 429:
                    logger.warning("Slot %s hit 429 on %s, checking next candidate model on same slot", slot.masked_key, model_name)
                    # Quotas in Google AI Studio free tier are per-model. Attempt remaining candidate models first.
                    continue
                elif e.code == 403:
                    logger.debug("Slot %s returned 403 PERMISSION_DENIED on %s, marking daily exhausted", slot.masked_key, model_name)
                    rotator.mark_daily_exhausted(slot.key_id, error_msg="403 Project Denied Access")
                    break  # Key project disabled across all models, skip to next slot immediately
                elif e.code == 404:
                    logger.debug("Model %s returned 404 for slot %s, falling back to next model", model_name, slot.masked_key)
                    continue  # Try next model candidate on the same slot
                elif e.code == 503:
                    logger.warning("Model %s returned 503 on slot %s, trying next candidate model", model_name, slot.masked_key)
                    continue
                else:
                    logger.warning("HTTP %d error on slot %s: %s", e.code, slot.masked_key, e)
                    break
            except Exception as e:
                last_err = e
                logger.warning("Error with slot %s on %s: %s", slot.masked_key, model_name, e)
                break
        else:
            # All candidate models failed on this slot; trigger burst cooldown before next attempt
            rotator.mark_burst_cooldown(slot.key_id, cooldown_seconds=60.0, error_msg=f"All candidate models failed: {last_err}")

    raise RuntimeError(f"All Gemini fleet slots failed to synthesize RFC. Last error: {last_err}")


def _discover_copilot_pats() -> list[dict[str, str]]:
    """Discovers Copilot PATs from .env.fleet.copilot environment file.

    Returns list of dicts with keys: name, token, index.
    """
    accounts: list[dict[str, str]] = []
    if not COPILOT_ENV_PATH.exists():
        return accounts

    env_vars: dict[str, str] = {}
    try:
        with open(COPILOT_ENV_PATH, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env_vars[k.strip()] = v.strip().strip('"').strip("'")
    except Exception as e:
        logger.debug("Could not parse %s: %s", COPILOT_ENV_PATH, e)
        return accounts

    for i in range(1, 65):
        name_key = f"COPILOT_ACCOUNT_{i}_NAME"
        token_key = f"COPILOT_ACCOUNT_{i}_TOKEN"
        name = env_vars.get(name_key, "").strip()
        token = env_vars.get(token_key, "").strip()
        if token and not token.startswith("REPLACE_"):
            accounts.append({"name": name or f"copilot-{i}", "token": token, "index": str(i)})

    return accounts


def _copilot_generate_rfc(raw_thought: str, token: str, account_name: str) -> str | None:
    """Synthesizes RFC via GitHub Copilot CLI headless non-interactive execution.

    Uses the given PAT for authentication via GITHUB_TOKEN env override.
    Returns the trimmed text output or None on failure.
    """
    copilot_bin = shutil.which("copilot")
    if not copilot_bin:
        logger.warning("copilot binary not found on PATH")
        return None

    prompt = (
        f"You are the Chief Research Architect of the BRL.\n"
        f"Transform this raw thought into a structured BRL Incubator RFC using "
        f"the exact markdown format with sections: "
        f"1. Executive Summary, 2. Target Ecosystem Module & Universe Mapping, "
        f"3. Theoretical Invariant & Mathematical Model, "
        f"4. Falsifiable Hypothesis & Empirical Benchmark, "
        f"5. Failure Modes & Boundary Conditions, 6. Immediate Next Step.\n\n"
        f"Raw thought: \"{raw_thought}\""
    )

    cmd = [
        copilot_bin,
        "-p", prompt,
        "-s",
        "--allow-all-tools",
        "--no-ask-user",
        "--no-color",
        "--no-custom-instructions",
        "--max-ai-credits", "15",
        "--max-autopilot-continues", "3",
    ]

    env = {**dict(__import__("os").environ), "GITHUB_TOKEN": token}

    try:
        logger.info("[Tier-2] Invoking Copilot CLI via PAT account: %s", account_name)
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=90,
            env=env,
            creationflags=flags,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
        else:
            logger.warning("[Tier-2] Copilot CLI returned code %d for account %s: %s",
                           proc.returncode, account_name, (proc.stderr or "")[:200])
    except subprocess.TimeoutExpired:
        logger.warning("[Tier-2] Copilot CLI timed out for account %s", account_name)
    except Exception as e:
        logger.warning("[Tier-2] Copilot CLI error for account %s: %s", account_name, e)

    return None


async def generate_incubator_rfc_tiered(raw_thought: str) -> str:
    """Tiered RFC synthesis: Gemini Fleet (Tier 1) -> Copilot CLI PAT Pool (Tier 2)."""
    # Tier 1: Gemini Fleet
    try:
        return await generate_incubator_rfc(raw_thought)
    except RuntimeError:
        logger.warning("[Tier-1] All Gemini fleet slots exhausted. Falling back to Tier-2 Copilot CLI.")

    # Tier 2: Copilot CLI via GitHub PAT pool
    pats = _discover_copilot_pats()
    if not pats:
        raise RuntimeError(
            "Tier-1 (Gemini) exhausted and Tier-2 (Copilot) unavailable: "
            "no PATs found in .env.fleet.copilot"
        )

    logger.info("[Tier-2] Discovered %d Copilot PAT accounts for fallback", len(pats))

    for account in pats[:5]:  # Try up to 5 accounts before giving up
        result = _copilot_generate_rfc(raw_thought, account["token"], account["name"])
        if result:
            logger.info("[Tier-2] Successfully synthesized RFC via Copilot account: %s", account["name"])
            return result

    raise RuntimeError("Both Tier-1 (Gemini Fleet) and Tier-2 (Copilot CLI) failed to synthesize RFC.")


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


async def main_async(raw_thought: str, create_issue: bool = True, vault_id: str | None = None) -> int:
    timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
    INCUBATOR_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("  AZMUTH INCUBATOR: AUTONOMOUS GEMINI FLEET SYNTHESIS")
    print("=" * 80)
    print(f"Raw Thought: '{raw_thought}'")
    print(f"Timestamp:   {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}")
    print("=" * 80)

    # 1. Synthesize RFC via Tiered Pipeline (Gemini Fleet -> Copilot CLI PAT)
    rfc_content = await generate_incubator_rfc_tiered(raw_thought)

    # Extract clean title and slug from thought
    clean_title = raw_thought.split("\n")[0][:70].strip()
    slug_text = re.sub(r"[^a-zA-Z0-9]+", "_", clean_title.lower()).strip("_")[:40]

    # 2. Save RFC markdown file (Primary local copy in Fleet-Orchestrator)
    rfc_file = INCUBATOR_DIR / f"RFC_{timestamp_slug}_{slug_text}.md"
    full_markdown = (
        f"# Incubator RFC: {clean_title}\n\n"
        f"> **Raw Thought**: *\"{raw_thought}\"*\n"
        f"> **Captured At**: `{datetime.now(timezone.utc).isoformat()}`\n"
        f"> **Vault ID**: `{vault_id or 'UNKNOWN'}`\n\n"
        f"---\n\n"
        f"{rfc_content}\n"
    )
    with open(rfc_file, "w", encoding="utf-8") as f:
        f.write(full_markdown)
    print(f"[+] Saved structured RFC artifact to: {rfc_file}")

    # Dual-Sync: Mirror offline Markdown copy into brainstorm/research/incubator/
    brainstorm_incubator = ROOT.parent / "brainstorm" / "research" / "incubator"
    try:
        brainstorm_incubator.mkdir(parents=True, exist_ok=True)
        brainstorm_rfc_file = brainstorm_incubator / f"RFC_{timestamp_slug}_{slug_text}.md"
        brainstorm_rfc_file.write_text(full_markdown, encoding="utf-8")
        print(f"[+] Mirrored offline RFC copy to brainstorm: {brainstorm_rfc_file}")
    except Exception as e:
        logger.warning("Could not mirror RFC to brainstorm/research/incubator: %s", e)

    # 3. Dispatch GitHub Issue if requested
    issue_url = None
    if create_issue:
        issue_url = dispatch_github_issue(clean_title, rfc_file)

    # 4. Update cognitive_vault.jsonl in-place (Unify thought and RFC into single entity)
    updated_records = []
    matched = False
    clean_raw = raw_thought.strip().lower()

    if VAULT_PATH.exists():
        try:
            with open(VAULT_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    # Match by vault_id or matching thought text
                    rec_id = rec.get("vault_id")
                    rec_thought = (rec.get("thought") or rec.get("raw_thought", "")).strip().lower()

                    if (vault_id and rec_id == vault_id) or (not matched and rec_thought == clean_raw):
                        rec["rfc_file"] = str(rfc_file)
                        rec["issue_url"] = issue_url
                        if "thought" not in rec:
                            rec["thought"] = raw_thought
                        if vault_id and "vault_id" not in rec:
                            rec["vault_id"] = vault_id
                        matched = True
                    updated_records.append(rec)
        except Exception as e:
            logger.warning("Error reading cognitive vault during in-place update: %s", e)

    if not matched:
        updated_records.append({
            "vault_id": vault_id or f"VLT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "local_time": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
            "thought": raw_thought,
            "rfc_file": str(rfc_file),
            "issue_url": issue_url
        })

    with open(VAULT_PATH, "w", encoding="utf-8") as f:
        for rec in updated_records:
            f.write(json.dumps(rec) + "\n")

    # 5. Formatted Executive Synthesis Display for CLI completion
    print("\n" + "=" * 80)
    print("  AZMUTH INCUBATOR: DECODED RESEARCH SYNTHESIS")
    print("=" * 80)
    print(f"[*] Raw Input Thought : \"{raw_thought}\"")
    print(f"[*] Captured At       : {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')} Local")
    if issue_url:
        print(f"[*] Tracked GitHub PR : {issue_url}")
    print(f"[*] Local RFC File    : {rfc_file}")
    print("-" * 80)
    print(rfc_content.strip())
    print("=" * 80)
    print(f"[+] Issue live: {issue_url or 'Local RFC only'}")
    print("[*] Return to rest, or execute with fresh focus!\n")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous Incubator Worker via Gemini Fleet")
    parser.add_argument("thought", type=str, nargs="+", help="The raw thought to process")
    parser.add_argument("--no-issue", action="store_true", help="Skip remote GitHub issue dispatch")
    parser.add_argument("--vault-id", type=str, default=None, help="Associated vault ID to update in-place")
    args = parser.parse_args()

    raw_thought = " ".join(args.thought).strip()
    if not raw_thought:
        sys.exit(1)

    sys.exit(asyncio.run(main_async(raw_thought, create_issue=not args.no_issue, vault_id=args.vault_id)))


if __name__ == "__main__":
    main()
