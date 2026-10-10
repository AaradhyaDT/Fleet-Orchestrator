#!/usr/bin/env python3
"""
tools/harvest_cross_ide_transcripts.py
--------------------------------------
Harvests authentic developer-assistant interactions across all IDE environments on the machine:
  1. VS Code Copilot Chat (Code/User/globalStorage/github.copilot-chat/session-store.db)
  2. OpenCode Desktop (AppData/Roaming/ai.opencode.desktop/drafts.sqlite)
  3. Claude Markdown Exports (C:/Users/Aaradhya/Downloads/Markdown/Claude_export*.md)
  4. Brainstorm Research Transcripts (f:/Aaradhya-Dev-Tamrakar/brainstorm/research/transcripts/*.md)

Emits:
  - dataset/cross_ide_transcripts_train.jsonl
  - dataset/cross_ide_transcripts_eval.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
import random
import re
import sqlite3
import sys
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cross_ide_harvester")

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "dataset"

VSCODE_DB = (
    Path.home()
    / "AppData"
    / "Roaming"
    / "Code"
    / "User"
    / "globalStorage"
    / "github.copilot-chat"
    / "session-store.db"
)
OPENCODE_DB = Path.home() / "AppData" / "Roaming" / "ai.opencode.desktop" / "drafts.sqlite"
CLAUDE_EXPORTS_DIR = Path.home() / "Downloads" / "Markdown"
BRAINSTORM_TRANSCRIPTS_DIR = Path(r"F:\Aaradhya-Dev-Tamrakar\brainstorm\research\transcripts")

SYSTEM_PROMPT = (
    "You are the high-velocity Fleet-Master AI developer assistant for Aaradhya's software ecosystem. "
    "Provide concise, mathematically sound, invariant-preserving code diffs, architectural guidance, "
    "and zero-fluff explanations."
)


def harvest_vscode_copilot_chat() -> List[Dict[str, Any]]:
    """Extracts in-editor turns directly from VS Code Copilot Chat SQLite database."""
    samples = []
    if not VSCODE_DB.exists():
        logger.warning(f"VS Code Copilot Chat database not found at {VSCODE_DB}")
        return samples

    try:
        conn = sqlite3.connect(str(VSCODE_DB))
        cursor = conn.cursor()
        
        # Check available tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]

        # Query turns if available
        if "turns" in tables:
            cursor.execute("PRAGMA table_info(turns)")
            cols = [col[1] for col in cursor.fetchall()]
            
            user_col = "user_message" if "user_message" in cols else ("request" if "request" in cols else None)
            asst_col = "assistant_response" if "assistant_response" in cols else ("response" if "response" in cols else None)

            if user_col and asst_col:
                cursor.execute(f"SELECT {user_col}, {asst_col} FROM turns WHERE {user_col} IS NOT NULL AND {asst_col} IS NOT NULL")
                rows = cursor.fetchall()
                for u_msg, a_msg in rows:
                    if not u_msg or not a_msg or len(u_msg.strip()) < 5:
                        continue
                    samples.append({
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": str(u_msg).strip()},
                            {"role": "assistant", "content": str(a_msg).strip()},
                        ],
                        "source": "vscode_copilot_chat_sqlite",
                        "code_dense": "```" in str(a_msg),
                    })
        conn.close()
    except Exception as e:
        logger.error(f"Error querying VS Code SQLite: {e}")

    logger.info(f"Harvested {len(samples)} turns from VS Code Copilot Chat.")
    return samples


def harvest_opencode_drafts() -> List[Dict[str, Any]]:
    """Extracts developer prompt history from OpenCode Desktop drafts database."""
    samples = []
    if not OPENCODE_DB.exists():
        return samples

    try:
        conn = sqlite3.connect(str(OPENCODE_DB))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]

        if "document" in tables:
            cursor.execute("SELECT key, value FROM document WHERE value IS NOT NULL")
            for k, val in cursor.fetchall():
                text = str(val).strip()
                if len(text) > 20 and not text.startswith("{"):
                    samples.append({
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": text},
                            {"role": "assistant", "content": f"Understood. Analyzing requirements for: {text[:60]}"},
                        ],
                        "source": f"opencode_draft_{k}",
                    })
        conn.close()
    except Exception as e:
        logger.error(f"Error querying OpenCode SQLite: {e}")

    logger.info(f"Harvested {len(samples)} prompts from OpenCode Desktop.")
    return samples


def harvest_claude_markdown_exports() -> List[Dict[str, Any]]:
    """Parses multi-turn Claude Markdown exports into structured message pairs."""
    samples = []
    if not CLAUDE_EXPORTS_DIR.exists():
        return samples

    for f in CLAUDE_EXPORTS_DIR.glob("Claude_export*.md"):
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            # Split by markdown headers
            turns = re.split(r"\n(?=#{2,3}\s+(?:Human|User|Assistant|Claude))", content)
            current_user = None

            for turn in turns:
                t = turn.strip()
                if re.match(r"^#{2,3}\s+(?:Human|User)", t, re.IGNORECASE):
                    current_user = re.sub(r"^#{2,3}\s+(?:Human|User)[^\n]*\n", "", t).strip()
                elif re.match(r"^#{2,3}\s+(?:Assistant|Claude)", t, re.IGNORECASE) and current_user:
                    asst_msg = re.sub(r"^#{2,3}\s+(?:Assistant|Claude)[^\n]*\n", "", t).strip()
                    if current_user and asst_msg:
                        samples.append({
                            "messages": [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": current_user},
                                {"role": "assistant", "content": asst_msg},
                            ],
                            "source": f"claude_export_{f.stem}",
                            "code_dense": "```" in asst_msg,
                        })
                    current_user = None
        except Exception as e:
            logger.debug(f"Error parsing Claude export {f.name}: {e}")

    logger.info(f"Harvested {len(samples)} turns from Claude Markdown exports.")
    return samples


def harvest_brainstorm_transcripts() -> List[Dict[str, Any]]:
    """Parses architectural debates in brainstorm/research/transcripts/."""
    samples = []
    if not BRAINSTORM_TRANSCRIPTS_DIR.exists():
        return samples

    for f in BRAINSTORM_TRANSCRIPTS_DIR.glob("*.md"):
        try:
            content = f.read_text(encoding="utf-8", errors="replace")
            blocks = re.split(r"\n(?=#{2,3}\s+(?:User|Architect|Lead|Reviewer|Claude|Assistant))", content)
            current_user = None

            for blk in blocks:
                b = blk.strip()
                if re.match(r"^#{2,3}\s+(?:User|Lead)", b, re.IGNORECASE):
                    current_user = re.sub(r"^#{2,3}\s+[^\n]+\n", "", b).strip()
                elif re.match(r"^#{2,3}\s+(?:Architect|Reviewer|Claude|Assistant)", b, re.IGNORECASE) and current_user:
                    asst_msg = re.sub(r"^#{2,3}\s+[^\n]+\n", "", b).strip()
                    if current_user and asst_msg:
                        samples.append({
                            "messages": [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user", "content": current_user},
                                {"role": "assistant", "content": asst_msg},
                            ],
                            "source": f"brainstorm_transcript_{f.stem}",
                            "code_dense": "```" in asst_msg,
                        })
                    current_user = None
        except Exception as e:
            logger.debug(f"Error parsing transcript {f.name}: {e}")

    logger.info(f"Harvested {len(samples)} turns from Brainstorm research transcripts.")
    return samples


def main():
    parser = argparse.ArgumentParser(description="Harvest Multi-IDE Developer Transcripts.")
    parser.add_argument("--dry-run", action="store_true", help="Print sample count without writing files")
    args = parser.parse_args()

    vsc = harvest_vscode_copilot_chat()
    opencode = harvest_opencode_drafts()
    claude = harvest_claude_markdown_exports()
    brainstorm = harvest_brainstorm_transcripts()

    all_samples = vsc + opencode + claude + brainstorm
    logger.info(f"Total multi-IDE developer turns collected: {len(all_samples)}")

    if not all_samples:
        logger.warning("No samples harvested across IDE sources.")
        return

    random.seed(42)
    random.shuffle(all_samples)

    split = int(len(all_samples) * 0.8)
    train_samples = all_samples[:split]
    eval_samples = all_samples[split:]

    if not args.dry_run:
        DATASET_DIR.mkdir(parents=True, exist_ok=True)
        train_path = DATASET_DIR / "cross_ide_transcripts_train.jsonl"
        eval_path = DATASET_DIR / "cross_ide_transcripts_eval.jsonl"

        with open(train_path, "w", encoding="utf-8") as f:
            for s in train_samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")

        with open(eval_path, "w", encoding="utf-8") as f:
            for s in eval_samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")

        logger.info(f"Saved {len(train_samples)} samples to {train_path.name}")
        logger.info(f"Saved {len(eval_samples)} samples to {eval_path.name}")


if __name__ == "__main__":
    main()
