"""
Antigravity Context Bridge: Connects Antigravity App Scope to Fleet-Orchestrator.
Harvests live chat state, active conversation transcripts, approved plans,
and Antigravity customizations (skills, rules, invariants) to project them
directly into headless worker environments and Copilot CLI prompt payloads.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_ANTIGRAVITY_APP_DATA = Path.home() / ".gemini" / "antigravity"
DEFAULT_ANTIGRAVITY_CONFIG = Path.home() / ".gemini" / "config"


def get_brain_dir(app_data_dir: Path | None = None) -> Path:
    """Returns the path to Antigravity's brain directory."""
    base = app_data_dir or Path(os.getenv("ANTIGRAVITY_APP_DATA", str(DEFAULT_ANTIGRAVITY_APP_DATA)))
    return base / "brain"


def get_active_conversation_id(app_data_dir: Path | None = None) -> str | None:
    """
    Auto-detects the most recently active Antigravity conversation ID
    by inspecting directory modification timestamps in brain/.
    """
    brain_dir = get_brain_dir(app_data_dir)
    if not brain_dir.exists():
        return None

    candidate_dirs = [d for d in brain_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
    if not candidate_dirs:
        return None

    def get_latest_mtime(d: Path) -> float:
        transcript = d / ".system_generated" / "logs" / "transcript.jsonl"
        if transcript.exists():
            return transcript.stat().st_mtime
        return d.stat().st_mtime

    sorted_dirs = sorted(candidate_dirs, key=get_latest_mtime, reverse=True)
    return sorted_dirs[0].name


def harvest_chat_context(
    conversation_id: str | None = None,
    app_data_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Harvests active chat metadata, latest user prompt, and recent plans/artifacts
    from the target Antigravity conversation directory.
    """
    cid = conversation_id or get_active_conversation_id(app_data_dir)
    if not cid:
        return {}

    brain_dir = get_brain_dir(app_data_dir)
    conv_dir = brain_dir / cid
    if not conv_dir.exists():
        return {"conversation_id": cid}

    context: dict[str, Any] = {
        "conversation_id": cid,
        "session_goal": None,
        "recent_user_requests": [],
        "active_artifacts": [],
    }

    # 1. Harvest recent user requests from compact transcript
    transcript_path = conv_dir / ".system_generated" / "logs" / "transcript.jsonl"
    if transcript_path.exists():
        try:
            user_requests = []
            with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        step = json.loads(line)
                        if step.get("type") == "USER_INPUT" and step.get("content"):
                            raw_content = step["content"]
                            # Clean XML/tag framing if present
                            clean_text = raw_content
                            if "<USER_REQUEST>" in clean_text:
                                start = clean_text.find("<USER_REQUEST>") + len("<USER_REQUEST>")
                                end = clean_text.find("</USER_REQUEST>")
                                if end > start:
                                    clean_text = clean_text[start:end].strip()
                            clean_text = clean_text.split("<ADDITIONAL_METADATA>")[0].strip()
                            if clean_text:
                                user_requests.append(clean_text[:300])
                    except Exception:
                        continue
            if user_requests:
                context["recent_user_requests"] = user_requests[-3:]
                context["session_goal"] = user_requests[-1]
        except Exception as e:
            logger.debug(f"Error harvesting transcript for {cid}: {e}")

    # 2. Harvest recent artifacts (plans, walkthroughs)
    try:
        artifacts = []
        for f in conv_dir.glob("*.md"):
            name = f.name
            first_line = ""
            try:
                with open(f, "r", encoding="utf-8", errors="replace") as af:
                    for line in af:
                        s = line.strip()
                        if s.startswith("# "):
                            first_line = s.lstrip("# ").strip()
                            break
            except Exception:
                pass
            artifacts.append({
                "file": name,
                "title": first_line or name,
                "path": str(f.resolve()),
            })
        context["active_artifacts"] = artifacts
    except Exception as e:
        logger.debug(f"Error scanning artifacts for {cid}: {e}")

    return context


def harvest_antigravity_customizations(
    repo_root: Path | None = None,
    config_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Harvests Antigravity rules, active skills, and engineering invariants
    from repository root (AGENTS.md, GEMINI.md) and global config.
    """
    customizations: dict[str, Any] = {
        "rules": [
            "Commit Integrity: Never use synthetic or placeholder SHAs; authentic 7-40 hex git commit hashes only.",
            "Version Control: Worktree-local commits are authorized; root repository merges/pushes must run via sync.bat.",
            "Calm Authority Writing: Follow Anthropic Calm Authority Standard (declarative, zero hype superlatives).",
            "Verification Gate: Local test suite and linters must pass clean before completion.",
            "Worktree Isolation: Confine all file modifications strictly to the assigned git worktree.",
        ],
        "active_skills": [],
        "repo_rules_path": None,
    }

    # Discover repo-specific rules
    root = repo_root or Path.cwd()
    agents_md = root / "AGENTS.md"
    if agents_md.exists():
        customizations["repo_rules_path"] = str(agents_md.resolve())

    # Discover active global skills
    cfg = config_dir or DEFAULT_ANTIGRAVITY_CONFIG
    skills_dir = cfg / "skills"
    if skills_dir.exists():
        try:
            customizations["active_skills"] = [
                d.name for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
            ]
        except Exception:
            pass

    return customizations


def build_antigravity_scope(
    conversation_id: str | None = None,
    repo_root: Path | None = None,
    app_data_dir: Path | None = None,
    config_dir: Path | None = None,
) -> dict[str, Any]:
    """Assembles the complete unified Antigravity scope object."""
    chat = harvest_chat_context(conversation_id=conversation_id, app_data_dir=app_data_dir)
    customizations = harvest_antigravity_customizations(repo_root=repo_root, config_dir=config_dir)

    return {
        "chat_context": chat,
        "antigravity_customizations": customizations,
    }


def format_prompt_directives(antigravity_scope: dict[str, Any]) -> str:
    """
    Synthesizes a high-density, authoritative ASCII directives block
    to inject directly into the Copilot CLI prompt payload.
    """
    chat = antigravity_scope.get("chat_context", {})
    custom = antigravity_scope.get("antigravity_customizations", {})

    lines = [
        "======================================================================",
        " ANTIGRAVITY SESSION DIRECTIVES & LIVING CHAT CONTEXT",
        "======================================================================",
    ]

    cid = chat.get("conversation_id")
    if cid:
        lines.append(f"Conversation ID: {cid}")

    goal = chat.get("session_goal")
    if goal:
        lines.append(f"Session Goal:    {goal}")

    recent = chat.get("recent_user_requests", [])
    if recent and len(recent) > 1:
        lines.append("\nRecent User Directives:")
        for r in recent[:-1]:
            lines.append(f" - {r}")

    artifacts = chat.get("active_artifacts", [])
    if artifacts:
        lines.append("\nActive Session Artifacts & Plans:")
        for a in artifacts[:4]:
            lines.append(f" - {a['file']}: {a['title']}")

    rules = custom.get("rules", [])
    if rules:
        lines.append("\nGoverning Antigravity Invariants:")
        for r in rules:
            lines.append(f" * {r}")

    lines.append("======================================================================\n")
    return "\n".join(lines)


def project_worktree_context(worktree_dir: Path, antigravity_scope: dict[str, Any]) -> None:
    """
    Projects the harvested Antigravity scope into the isolated worktree filesystem:
    1. Writes TASK_CONTEXT.md at worktree root.
    2. Writes .github/copilot-instructions.md so copilot.exe natively ingests rules.
    """
    if not worktree_dir.exists():
        return

    chat = antigravity_scope.get("chat_context", {})
    custom = antigravity_scope.get("antigravity_customizations", {})

    # 1. Write TASK_CONTEXT.md
    context_md_lines = [
        "# Antigravity Task Context & Session Scope",
        "",
        f"**Conversation ID:** `{chat.get('conversation_id', 'unspecified')}`  ",
        f"**Session Goal:** {chat.get('session_goal', 'Task execution within Antigravity app scope')}  ",
        "",
        "## Governing Directives & Invariants",
        "",
    ]
    for r in custom.get("rules", []):
        context_md_lines.append(f"- {r}")

    if chat.get("active_artifacts"):
        context_md_lines.extend(["", "## Active Session Plans & Artifacts", ""])
        for a in chat["active_artifacts"]:
            context_md_lines.append(f"- **{a['file']}**: {a['title']} (`{a['path']}`)")

    projected_files = []

    context_file = worktree_dir / "TASK_CONTEXT.md"
    try:
        context_file.write_text("\n".join(context_md_lines) + "\n", encoding="utf-8")
        projected_files.append("TASK_CONTEXT.md")
        logger.debug(f"Projected TASK_CONTEXT.md into {worktree_dir}")
    except Exception as e:
        logger.warning(f"Could not write TASK_CONTEXT.md: {e}")

    # 2. Write .github/copilot-instructions.md (ephemeral within worktree)
    github_dir = worktree_dir / ".github"
    instructions_file = github_dir / "copilot-instructions.md"
    if not instructions_file.exists():
        try:
            github_dir.mkdir(parents=True, exist_ok=True)
            instructions_lines = [
                "# GitHub Copilot Task Instructions (Antigravity Runtime Projection)",
                "",
                "You are executing as an autonomous worker within Google Antigravity.",
                "",
                "## Core Execution Constraints",
                "- Confine all file changes strictly to this isolated repository worktree.",
                "- Ensure all modified code passes static analysis, typing, and local unit tests.",
                "- Do not introduce synthetic or placeholder Git commit SHAs.",
                "- Adhere to the Anthropic Calm Authority Standard (clear, factual, zero marketing fluff).",
                "",
                "## Task Context",
                f"Active Goal: {chat.get('session_goal', 'Autonomous implementation')}",
                "See `TASK_CONTEXT.md` in the workspace root for complete session details.",
                "",
            ]
            instructions_file.write_text("\n".join(instructions_lines), encoding="utf-8")
            projected_files.append(".github/copilot-instructions.md")
            logger.debug(f"Projected .github/copilot-instructions.md into {worktree_dir}")
        except Exception as e:
            logger.warning(f"Could not write .github/copilot-instructions.md: {e}")

    # Write marker file so teardown knows which files to prune before git commit
    if projected_files:
        marker = worktree_dir / ".antigravity_projected"
        try:
            marker.write_text("\n".join(projected_files) + "\n", encoding="utf-8")
        except Exception:
            pass


def cleanup_worktree_context(worktree_dir: Path) -> None:
    """
    Cleans up ephemeral Antigravity projected context files prior to committing
    changes inside the worktree so they do not pollute repository commit history.
    """
    if not worktree_dir.exists():
        return

    marker = worktree_dir / ".antigravity_projected"
    if marker.exists():
        try:
            lines = marker.read_text(encoding="utf-8").splitlines()
            for line in lines:
                fpath = line.strip()
                if fpath:
                    target = worktree_dir / fpath
                    if target.is_file():
                        target.unlink()
            marker.unlink()
        except Exception as e:
            logger.debug(f"Error cleaning projected context in {worktree_dir}: {e}")
    else:
        # Fallback cleanup for TASK_CONTEXT.md
        context_file = worktree_dir / "TASK_CONTEXT.md"
        if context_file.exists():
            try:
                context_file.unlink()
            except Exception:
                pass
