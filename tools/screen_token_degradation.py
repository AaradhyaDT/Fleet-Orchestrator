#!/usr/bin/env python3
"""
Token Degradation & AI-Slop Screening Engine (Fleet-Orchestrator).

Audits markdown documentation, agent transcripts, and prompt templates for:
1. Decorative emoji pollution (⚡, ✨, 🚀, 🧠, 💡, 🔥, etc.)
2. Canonical AI-slop vocabulary (delve, testament, beacon, tapestry, evolving landscape, etc.)
3. Thinking trace residue (<think>...</think>)
4. Excessive raw stdout / tool output dumps exceeding token safety thresholds.

Enforces zero-drift context SNR across the ecosystem.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import unicodedata

# Canonical AI-slop vocabulary & syntactic markers
CANONICAL_SLOP_PATTERNS = [
    (r"\bdelve\b", "delve"),
    (r"\bdelving into\b", "delving into"),
    (r"\btestament to\b", "testament to"),
    (r"\bbeacon of\b", "beacon of"),
    (r"\btapestry\b", "tapestry"),
    (r"\bevolving landscape\b", "evolving landscape"),
    (r"\bdynamic landscape\b", "dynamic landscape"),
    (r"\bnot only\b.*?\bbut also\b", "not only... but also"),
    (r"\brobust synergy\b", "robust synergy"),
    (r"\bparadigm shift\b", "paradigm shift"),
    (r"\bholistic approach\b", "holistic approach"),
    (r"\bfoster(?:ing)? innovation\b", "foster innovation"),
]

THINKING_TRACE_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

# Dangerous zero-width & invisible formatting characters that split tokenizer BPE merges
INVISIBLE_FORMATTING_CHARS = {
    "\u200B": "Zero-Width Space",
    "\u200C": "Zero-Width Non-Joiner",
    "\u200D": "Zero-Width Joiner",
    "\u2060": "Word Joiner",
    "\uFEFF": "Byte Order Mark (BOM/ZWNBSP)",
    "\u200E": "Left-to-Right Mark",
    "\u200F": "Right-to-Left Mark",
}

# Variation selectors that cause 3-byte composite emoji fragmentation
VARIATION_SELECTOR_PATTERN = re.compile(r"[\uFE00-\uFE0F\U000E0100-\U000E01EF]")

# Involuntary Markdown Syntax Malformations that cause broken rendering and glyph artifacts
# e.g., broken GitHub alerts `> [! NOTE]`, dangling unescaped HTML tags `<foo>`, broken task checkboxes `- [ ]text`
MARKDOWN_SYNTAX_GLITCHES = [
    (re.compile(r"^>\s*\[!\s+(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]", re.MULTILINE), r"> [!\1]"),  # broken alert space
    (re.compile(r"^-\s*\[([ xX])\]([^\s])", re.MULTILINE), r"- [\1] \2"),  # checkbox missing space
    (re.compile(r"<!--\s*slide\s*-->", re.IGNORECASE), "<!-- slide -->"),  # normalize carousel slide markers
]


@dataclass
class AuditReport:
    file_path: Path
    emoji_count: int
    invisible_char_count: int
    variation_selector_count: int
    slop_matches: list[str]
    thinking_traces_found: int
    syntax_glitches_found: int
    long_codeblocks_count: int
    clean: bool

    def summary(self) -> str:
        status = "[PASS]" if self.clean else "[FAIL]"
        details = []
        if self.emoji_count > 0:
            details.append(f"{self.emoji_count} decorative glyphs/emojis")
        if self.invisible_char_count > 0:
            details.append(f"{self.invisible_char_count} invisible zero-width chars")
        if self.variation_selector_count > 0:
            details.append(f"{self.variation_selector_count} emoji variation selectors")
        if self.syntax_glitches_found > 0:
            details.append(f"{self.syntax_glitches_found} malformed markdown syntax tags")
        if self.slop_matches:
            details.append(f"{len(self.slop_matches)} slop phrases ({', '.join(set(self.slop_matches))})")
        if self.thinking_traces_found > 0:
            details.append(f"{self.thinking_traces_found} unstripped <think> blocks")
        if self.long_codeblocks_count > 0:
            details.append(f"{self.long_codeblocks_count} stdout blocks > 60 lines")
        
        detail_str = "; ".join(details) if details else "Zero degradation detected"
        return f"{status} {self.file_path.name}: {detail_str}"


def scan_unicode_glyphs(content: str) -> tuple[int, int, int]:
    """Scan content for decorative emojis, invisible formatting chars, and variation selectors."""
    emoji_count = 0
    invisible_count = 0
    
    # Check invisible formatting
    for char in INVISIBLE_FORMATTING_CHARS:
        invisible_count += content.count(char)

    # Variation selectors
    var_selectors = len(VARIATION_SELECTOR_PATTERN.findall(content))

    # Comprehensive Unicode categorization
    for ch in content:
        cat = unicodedata.category(ch)
        cp = ord(ch)
        # Exclude box drawing characters (0x2500 - 0x257F) and geometric block elements (0x2580 - 0x259F)
        if 0x2500 <= cp <= 0x259F:
            continue
        # Exclude standard ASCII / Latin / basic punctuation / math
        if cp < 0x2600 and cat != "So":
            continue
        # Check if in standard emoji or dingbat blocks
        if (cat in ("So",) and cp >= 0x2600) or (0x1F300 <= cp <= 0x1F9FF) or (0x2600 <= cp <= 0x27BF):
            # Skip technical math, arrows, and currency symbols
            if ch not in ("±", "×", "÷", "≠", "≤", "≥", "∑", "∏", "√", "∞", "∫", "≈", "→", "←", "↔", "•", "·", "°", "µ", "©", "®"):
                emoji_count += 1

    return emoji_count, invisible_count, var_selectors


def audit_content(content: str, file_path: Path) -> AuditReport:
    emoji_count, invisible_count, var_selectors = scan_unicode_glyphs(content)

    slop_matches = []
    for pattern, name in CANONICAL_SLOP_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            slop_matches.extend([name] * len(matches))

    thinking_traces = len(THINKING_TRACE_PATTERN.findall(content))

    # Scan for markdown syntax glitches
    syntax_glitches = 0
    for pattern, _ in MARKDOWN_SYNTAX_GLITCHES:
        syntax_glitches += len(pattern.findall(content))

    # Audit for excessively large raw stdout / tool blocks (> 60 lines in a single code block)
    long_codeblocks = 0
    codeblocks = re.findall(r"```(?:[a-zA-Z0-9_\-]+)?\n(.*?)```", content, re.DOTALL)
    for block in codeblocks:
        line_count = len(block.strip().splitlines())
        if line_count > 60:
            long_codeblocks += 1

    clean = (
        emoji_count == 0
        and invisible_count == 0
        and var_selectors == 0
        and syntax_glitches == 0
        and len(slop_matches) == 0
        and thinking_traces == 0
    )

    return AuditReport(
        file_path=file_path,
        emoji_count=emoji_count,
        invisible_char_count=invisible_count,
        variation_selector_count=var_selectors,
        slop_matches=slop_matches,
        thinking_traces_found=thinking_traces,
        syntax_glitches_found=syntax_glitches,
        long_codeblocks_count=long_codeblocks,
        clean=clean,
    )


def sanitize_content(content: str) -> str:
    """Sanitize content by stripping glyphs, invisible chars, thinking traces, and fixing markdown syntax."""
    sanitized = content
    
    # Strip thinking traces
    sanitized = THINKING_TRACE_PATTERN.sub("", sanitized)
    
    # Strip invisible zero-width chars
    for char in INVISIBLE_FORMATTING_CHARS:
        sanitized = sanitized.replace(char, "")

    # Strip variation selectors
    sanitized = VARIATION_SELECTOR_PATTERN.sub("", sanitized)

    # Strip decorative symbols (Unicode category 'So') and emoji ranges
    clean_chars = []
    for ch in sanitized:
        cat = unicodedata.category(ch)
        cp = ord(ch)
        # Exclude box drawing characters (0x2500 - 0x257F) and geometric block elements (0x2580 - 0x259F)
        if 0x2500 <= cp <= 0x259F:
            clean_chars.append(ch)
            continue
        # Exclude standard ASCII / Latin / basic punctuation / math
        if cp < 0x2600 and cat != "So":
            clean_chars.append(ch)
            continue
        # Check if in standard emoji or dingbat blocks
        if (cat in ("So",) and cp >= 0x2600) or (0x1F300 <= cp <= 0x1F9FF) or (0x2600 <= cp <= 0x27BF):
            # Preserve technical math, arrows, and currency symbols
            if ch in ("±", "×", "÷", "≠", "≤", "≥", "∑", "∏", "√", "∞", "∫", "≈", "→", "←", "↔", "•", "·", "°", "µ", "©", "®"):
                clean_chars.append(ch)
            continue
        clean_chars.append(ch)
    sanitized = "".join(clean_chars)

    # Repair involuntary markdown formatting glitches
    for pattern, replacement in MARKDOWN_SYNTAX_GLITCHES:
        sanitized = pattern.sub(replacement, sanitized)

    return sanitized


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and screen files for Token Degradation & AI-Slop.")
    parser.add_argument("--file", type=Path, help="Specific file to audit.")
    parser.add_argument("--dir", type=Path, help="Specific directory/repository root to audit.")
    parser.add_argument("--all", action="store_true", help="Audit all markdown and transcript files in workspace.")
    parser.add_argument("--fix", action="store_true", help="Automatically sanitize detected emojis and thinking traces.")
    args = parser.parse_args()

    files_to_check: list[Path] = []
    target_root = args.dir.resolve() if args.dir else Path.cwd()

    if args.file:
        files_to_check.append(args.file)
    elif args.all or args.dir:
        for ext in ("*.md", "*.jsonl"):
            for p in target_root.rglob(ext):
                # Skip git, venvs, cache, datasets, and runtime session state
                if any(part.startswith(".") or part in ("node_modules", "venv", ".venv", "build", "dist", "dataset", "datasets", "events", "transcripts", "orchestrator-state") for part in p.parts):
                    continue
                files_to_check.append(p)

    if not files_to_check:
        print("No files targeted for screening. Use --file <path> or --all.")
        return 0

    total_failures = 0
    print(f"--- Screening {len(files_to_check)} files for Token Degradation Factors ---")

    for p in files_to_check:
        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        report = audit_content(content, p)
        if not report.clean:
            total_failures += 1
            print(report.summary())

            if args.fix:
                sanitized = sanitize_content(content)
                p.write_text(sanitized, encoding="utf-8")
                print(f"  -> Fixed {p.name} (stripped emojis & thinking traces).")
        else:
            if not args.all:
                print(report.summary())

    print("\n--- Screening Complete ---")
    if total_failures > 0:
        print(f"Detected token degradation markers in {total_failures} file(s).")
        return 1 if not args.fix else 0
    else:
        print("All audited files satisfy strict token density & zero-slop invariants.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
