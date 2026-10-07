from __future__ import annotations

import contextlib
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCRATCHPAD_DIR = Path(
    os.getenv("SCRATCHPAD_DIR") or (REPO_ROOT / "orchestrator-state" / "scratchpads")
)

SECTION_TITLES: dict[int, str] = {
    1: "## 1. Architectural Plan & WBS Specs",
    2: "## 2. Worktree Diffs & Test Passes",
    3: "## 3. Adversarial QA Verdict",
}
SECTION_AUTHORS: dict[int, str] = {
    1: "Claude Architect",
    2: "Copilot CLI workers",
    3: "Claude Reviewer",
}
_HEADER_RE = re.compile(r"^## ([123])\. .*$", re.MULTILINE)
_JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ScratchpadError(RuntimeError):
    """Raised on invalid job ids, lock timeouts, or invalid section numbers."""


class ScratchpadManager:
    """
    Persistent Markdown state shared by every stage of a job.

    File: <base_dir>/<job_id>_scratchpad.md with three fixed sections
    (plan / worktree results / QA verdict). Writes are serialised through an
    exclusive lock file and published with an atomic os.replace().
    """

    def __init__(
        self,
        base_dir: Path | str | None = None,
        lock_timeout: float = 10.0,
        stale_lock_seconds: float = 60.0,
    ):
        self.base_dir = Path(base_dir) if base_dir else DEFAULT_SCRATCHPAD_DIR
        self.lock_timeout = lock_timeout
        self.stale_lock_seconds = stale_lock_seconds

    # ── paths ───────────────────────────────────────────────────────
    def path_for(self, job_id: str) -> Path:
        if not isinstance(job_id, str) or not _JOB_ID_RE.match(job_id):
            raise ScratchpadError(f"Invalid job id for scratchpad: {job_id!r}")
        return self.base_dir / f"{job_id}_scratchpad.md"

    def exists(self, job_id: str) -> bool:
        return self.path_for(job_id).exists()

    # ── locking ─────────────────────────────────────────────────────
    @contextlib.contextmanager
    def _lock(self, job_id: str) -> Iterator[None]:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        lock_path = self.path_for(job_id).with_suffix(".md.lock")
        deadline = time.monotonic() + self.lock_timeout
        fd: int | None = None
        while fd is None:
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
            except FileExistsError:
                try:
                    age = time.time() - lock_path.stat().st_mtime
                    if age > self.stale_lock_seconds:
                        lock_path.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise ScratchpadError(f"Timed out acquiring scratchpad lock for {job_id}")
                time.sleep(0.02)
        try:
            yield
        finally:
            os.close(fd)
            with contextlib.suppress(FileNotFoundError):
                lock_path.unlink()

    def _atomic_write(self, path: Path, text: str) -> None:
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            os.replace(tmp, path)
        except BaseException:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(tmp)
            raise

    # ── parsing / rendering ─────────────────────────────────────────
    @staticmethod
    def _template(job_id: str) -> str:
        parts = [f"# Shared Scratchpad — {job_id}\n"]
        for n in (1, 2, 3):
            parts.append(f"\n{SECTION_TITLES[n]}\n\n_(pending)_\n")
        return "".join(parts)

    @staticmethod
    def _split(text: str) -> tuple[str, dict[int, str]]:
        matches = list(_HEADER_RE.finditer(text))
        preamble = text[: matches[0].start()] if matches else text
        bodies: dict[int, str] = {}
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[m.end():end].strip("\n")
            bodies[int(m.group(1))] = body.strip()
        return preamble, bodies

    @staticmethod
    def _join(preamble: str, bodies: dict[int, str]) -> str:
        out = preamble.rstrip("\n") + "\n"
        for n in (1, 2, 3):
            body = bodies.get(n) or "_(pending)_"
            out += f"\n{SECTION_TITLES[n]}\n\n{body.strip()}\n"
        return out

    @staticmethod
    def _check_section(section: int) -> None:
        if section not in SECTION_TITLES:
            raise ScratchpadError(f"Invalid scratchpad section: {section!r} (expected 1, 2 or 3)")

    # ── public API ──────────────────────────────────────────────────
    def ensure(self, job_id: str) -> Path:
        path = self.path_for(job_id)
        with self._lock(job_id):
            if not path.exists():
                self._atomic_write(path, self._template(job_id))
        return path

    def read(self, job_id: str) -> str:
        path = self.path_for(job_id)
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def read_section(self, job_id: str, section: int) -> str:
        self._check_section(section)
        _, bodies = self._split(self.read(job_id))
        body = bodies.get(section, "")
        return "" if body == "_(pending)_" else body

    def write_section(self, job_id: str, section: int, content: str) -> Path:
        """Replace the body of a section (read-modify-write under the lock)."""
        self._check_section(section)
        path = self.path_for(job_id)
        with self._lock(job_id):
            text = path.read_text(encoding="utf-8") if path.exists() else self._template(job_id)
            preamble, bodies = self._split(text)
            bodies[section] = content.strip()
            self._atomic_write(path, self._join(preamble, bodies))
        return path

    def append_section(self, job_id: str, section: int, content: str) -> Path:
        """Append to a section body, keeping earlier entries (e.g. QA revision history)."""
        self._check_section(section)
        path = self.path_for(job_id)
        with self._lock(job_id):
            text = path.read_text(encoding="utf-8") if path.exists() else self._template(job_id)
            preamble, bodies = self._split(text)
            existing = bodies.get(section, "")
            existing = "" if existing == "_(pending)_" else existing
            bodies[section] = (existing + "\n\n" + content.strip()).strip()
            self._atomic_write(path, self._join(preamble, bodies))
        return path

    def render_context(
        self,
        job_id: str,
        exclude_text: str = "",
        max_chars: int = 60_000,
    ) -> str:
        """
        Prompt-ready context. Sections already contained verbatim in `exclude_text`
        (typically the task spec) are skipped to avoid duplicated payloads.
        """
        if not self.exists(job_id):
            return ""
        _, bodies = self._split(self.read(job_id))
        chunks: list[str] = []
        for n in (1, 2, 3):
            body = bodies.get(n, "")
            if not body or body == "_(pending)_":
                continue
            if exclude_text and body in exclude_text:
                continue
            chunks.append(f"{SECTION_TITLES[n]}  (author: {SECTION_AUTHORS[n]})\n{body}")
        text = "\n\n".join(chunks)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n…[scratchpad truncated]"
        return text


def build_task_context(task_info: dict, manager: ScratchpadManager | None = None) -> dict:
    """Context dict handed to adapters: always carries job_id, plus scratchpad text when one exists."""
    ctx: dict = {}
    job_id = task_info.get("job_id")
    if not job_id:
        return ctx
    ctx["job_id"] = job_id
    try:
        text = (manager or ScratchpadManager()).render_context(job_id, exclude_text=task_info.get("spec", ""))
    except ScratchpadError:
        text = ""
    if text:
        ctx["scratchpad"] = text
    return ctx
