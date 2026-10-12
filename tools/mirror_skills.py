#!/usr/bin/env python3
r"""tools/mirror_skills.py
----------------------
SSOT Skill Mirroring Engine for /adaptive-workflow.

Enforces INV-SSOT-ADAPTIVE:
- Authoritative SSOT: Fleet-Orchestrator/.agents/skills/adaptive-workflow
- Mirrors:
  1. ~/.gemini/config/skills/adaptive-workflow (unconditional)
  2. F:\Aaradhya-Dev-Tamrakar\brainstorm\.agents\skills\adaptive-workflow (safe git check)

Normalizes text line endings (CRLF -> LF) before computing SHA-256 hashes
to eliminate false Windows line-ending drift.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Tuple

ROOT = Path(__file__).resolve().parent.parent
SSOT_DIR = ROOT / ".agents" / "skills" / "adaptive-workflow"
GLOBAL_MIRROR = Path.home() / ".gemini" / "config" / "skills" / "adaptive-workflow"
BRAINSTORM_MIRROR = Path(r"F:\Aaradhya-Dev-Tamrakar\brainstorm\.agents\skills\adaptive-workflow")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mirror_skills")

TEXT_EXTENSIONS = {".md", ".json", ".yaml", ".yml", ".txt", ".py", ".ps1", ".bat", ".sh"}


def normalize_and_hash_file(file_path: Path) -> str:
    """Compute a normalized SHA-256 hash for a file.

    Text files are normalized to standard ``\\n`` line endings before hashing.

    Args:
        file_path: Path to the file to hash.

    Returns:
        The SHA-256 digest as a hexadecimal string.
    """
    if file_path.suffix.lower() in TEXT_EXTENSIONS:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            normalized = content.replace("\r\n", "\n").replace("\r", "\n")
            return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        except Exception:
            pass

    # Fallback to binary hash
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def compute_tree_hashes(base_dir: Path) -> Dict[str, str]:
    """Compute normalized SHA-256 hashes for files in a directory tree.

    Args:
        base_dir: Root directory whose files should be hashed.

    Returns:
        A mapping from relative POSIX file paths to their SHA-256 digests.
    """
    tree: Dict[str, str] = {}
    if not base_dir.exists():
        return tree

    for root, _, files in os.walk(base_dir):
        for f in files:
            fp = Path(root) / f
            rel = fp.relative_to(base_dir).as_posix()
            tree[rel] = normalize_and_hash_file(fp)
    return tree


def compare_trees(ssot: Dict[str, str], mirror: Dict[str, str]) -> Dict[str, Any]:
    """Compare the hashes in an SSOT tree and its mirror.

    Args:
        ssot: Relative file paths and hashes from the authoritative tree.
        mirror: Relative file paths and hashes from the mirror tree.

    Returns:
        A report containing synchronization status and missing, extra, and
        modified file paths.
    """
    ssot_keys = set(ssot.keys())
    mirror_keys = set(mirror.keys())

    missing_in_mirror = sorted(list(ssot_keys - mirror_keys))
    extra_in_mirror = sorted(list(mirror_keys - ssot_keys))
    modified = sorted([k for k in (ssot_keys & mirror_keys) if ssot[k] != mirror[k]])

    is_synced = not (missing_in_mirror or extra_in_mirror or modified)
    return {
        "is_synced": is_synced,
        "missing": missing_in_mirror,
        "extra": extra_in_mirror,
        "modified": modified,
    }


def copy_tree(src: Path, dst: Path) -> int:
    """Mirror a source tree to a destination, removing obsolete files.

    Args:
        src: Source directory to mirror.
        dst: Destination directory to update.

    Returns:
        The number of files copied to the destination.
    """
    copied = 0
    dst.mkdir(parents=True, exist_ok=True)

    src_hashes = compute_tree_hashes(src)
    dst_hashes = compute_tree_hashes(dst)

    # 1. Remove extra files in dst
    for rel in set(dst_hashes.keys()) - set(src_hashes.keys()):
        p = dst / Path(rel)
        if p.exists():
            p.unlink(missing_ok=True)

    # 2. Copy missing or modified files
    for rel, s_hash in src_hashes.items():
        if rel not in dst_hashes or dst_hashes[rel] != s_hash:
            src_file = src / Path(rel)
            dst_file = dst / Path(rel)
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)
            copied += 1

    return copied


def is_brainstorm_git_clean(brainstorm_root: Path) -> Tuple[bool, str]:
    """Check whether the brainstorm repository is clean.

    Args:
        brainstorm_root: Path to the brainstorm Git repository.

    Returns:
        A tuple containing whether the repository is clean and the branch name
        or reason it could not be verified.
    """
    if not brainstorm_root.exists():
        return False, "Brainstorm repo directory not found"

    try:
        status_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(brainstorm_root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if status_res.returncode != 0:
            return False, "Git status failed"
        diff_lines = [l for l in status_res.stdout.splitlines() if l.strip()]
        if diff_lines:
            return False, f"Working tree has {len(diff_lines)} uncommitted changes"

        branch_res = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(brainstorm_root),
            capture_output=True,
            text=True,
            timeout=5,
        )
        branch = branch_res.stdout.strip()
        return True, branch
    except Exception as e:
        return False, str(e)


def main() -> int:
    """Run the skill-mirroring command-line interface.

    Returns:
        The process exit code, where zero indicates success.
    """
    parser = argparse.ArgumentParser(description="SSOT Skill Mirroring Engine for adaptive-workflow")
    parser.add_argument("--check", action="store_true", help="Audit drift without copying files")
    parser.add_argument("--fix", action="store_true", help="Mirror SSOT to mirrors")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = parser.parse_args()

    if not SSOT_DIR.exists():
        logger.error(f"SSOT directory not found: {SSOT_DIR}")
        return 1

    ssot_hashes = compute_tree_hashes(SSOT_DIR)
    global_hashes = compute_tree_hashes(GLOBAL_MIRROR)
    brainstorm_hashes = compute_tree_hashes(BRAINSTORM_MIRROR)

    diff_global = compare_trees(ssot_hashes, global_hashes)
    diff_brainstorm = compare_trees(ssot_hashes, brainstorm_hashes)

    overall_synced = diff_global["is_synced"] and diff_brainstorm["is_synced"]

    report = {
        "ssot_dir": str(SSOT_DIR),
        "ssot_file_count": len(ssot_hashes),
        "mirrors": {
            "global_config": {
                "path": str(GLOBAL_MIRROR),
                "synced": diff_global["is_synced"],
                "missing": diff_global["missing"],
                "modified": diff_global["modified"],
                "extra": diff_global["extra"],
            },
            "brainstorm": {
                "path": str(BRAINSTORM_MIRROR),
                "synced": diff_brainstorm["is_synced"],
                "missing": diff_brainstorm["missing"],
                "modified": diff_brainstorm["modified"],
                "extra": diff_brainstorm["extra"],
            },
        },
        "all_synced": overall_synced,
    }

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if overall_synced else 1

    if args.check:
        print("=" * 65)
        print("  SSOT SKILL MIRROR DRIFT AUDIT (INV-SSOT-ADAPTIVE)")
        print("=" * 65)
        print(f"  SSOT Root        : {SSOT_DIR}")
        print(f"  Tracked Files    : {len(ssot_hashes)}")
        print(f"  Global Mirror    : {'SYNCED' if diff_global['is_synced'] else 'DRIFT DETECTED'}")
        if not diff_global["is_synced"]:
            print(f"    Missing: {len(diff_global['missing'])} | Modified: {len(diff_global['modified'])} | Extra: {len(diff_global['extra'])}")
        print(f"  Brainstorm Mirror: {'SYNCED' if diff_brainstorm['is_synced'] else 'DRIFT DETECTED'}")
        if not diff_brainstorm["is_synced"]:
            print(f"    Missing: {len(diff_brainstorm['missing'])} | Modified: {len(diff_brainstorm['modified'])} | Extra: {len(diff_brainstorm['extra'])}")
        print("=" * 65)
        return 0 if overall_synced else 1

    # Default action or --fix: Mirror files
    print("[SYNC] Mirroring SSOT skills to destinations...")

    # 1. Global config mirror (unconditional)
    copied_global = copy_tree(SSOT_DIR, GLOBAL_MIRROR)
    print(f"  [+] Global Mirror updated: {copied_global} files copied to {GLOBAL_MIRROR}")

    # 2. Brainstorm mirror (safe git check)
    brainstorm_root = Path(r"F:\Aaradhya-Dev-Tamrakar\brainstorm")
    is_clean, info = is_brainstorm_git_clean(brainstorm_root)
    if is_clean:
        copied_bs = copy_tree(SSOT_DIR, BRAINSTORM_MIRROR)
        print(f"  [+] Brainstorm Mirror updated (branch '{info}'): {copied_bs} files copied")
    else:
        print(f"  [!] Brainstorm Mirror SKIPPED: {info}. Run .\\sync.bat -CrossSync once clean.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
