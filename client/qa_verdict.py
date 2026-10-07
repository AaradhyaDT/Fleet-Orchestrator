from __future__ import annotations

import re

VERDICT_PASS = "pass"
VERDICT_REVISION = "revision_needed"

DEFAULT_REVISION_REASON = "QA checks requested revision"
_MAX_REASON_CHARS = 500

# Explicit marker: "QA_VERDICT: PASS" / "QA_VERDICT: REVISE" (tolerates **bold**, `code`, extra spaces).
_MARKER_RE = re.compile(
    r"QA_VERDICT[\s*`_]*:[\s*`_]*(PASS|REVISE)(?![A-Za-z0-9_])",
    re.IGNORECASE,
)


def _reason_after(text: str, end: int) -> str:
    """Revision reason = remainder of the marker line, else the following non-empty lines."""
    tail = text[end:]
    first_line, _, rest = tail.partition("\n")
    inline = first_line.strip(" \t*`_-—–:|")
    if inline:
        return inline[:_MAX_REASON_CHARS]
    following = "\n".join(ln.strip() for ln in rest.splitlines() if ln.strip()).strip()
    return following[:_MAX_REASON_CHARS] if following else DEFAULT_REVISION_REASON


def parse_qa_verdict(text: str) -> tuple[str, str | None]:
    """
    Parse QA reviewer output into (verdict, reason).

    verdict is "pass" or "revision_needed". reason is None for "pass".
    - If one or more explicit 'QA_VERDICT: PASS|REVISE' markers exist, the LAST one wins
      and the free-text body (e.g. "no fail conditions found") is ignored.
    - Only when no marker is present, fall back to the legacy keyword heuristic
      ("fail" / "revision_needed" anywhere in the text => revision_needed).
    """
    if not isinstance(text, str):
        text = "" if text is None else str(text)

    last = None
    for last in _MARKER_RE.finditer(text):
        pass
    if last is not None:
        if last.group(1).upper() == "PASS":
            return VERDICT_PASS, None
        return VERDICT_REVISION, _reason_after(text, last.end())

    lowered = text.lower()
    if "fail" in lowered or "revision_needed" in lowered:
        return VERDICT_REVISION, DEFAULT_REVISION_REASON
    return VERDICT_PASS, None
