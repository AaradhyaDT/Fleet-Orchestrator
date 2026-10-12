#!/usr/bin/env python3
"""
Credit Ledger: Single authoritative thread/process-safe accounting engine for GitHub Copilot Fleet.
Enforces per-worker sidecars, OS file locking, and atomic live-status updates with automatic month rollover.
Strictly a leaf module: ZERO imports from the repository.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import threading
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

logger = logging.getLogger("credit_ledger")

# Global in-memory cache for (file_size, mtime) to avoid re-reading unchanged event logs
_EVENT_FILE_CACHE: dict[str, tuple[int, float, int, str]] = {}


def resolve_state_dir(orch_state: Path | str | None = None) -> Path:
    """
    Resolve and create the orchestrator state directory.

    The directory is selected in this order: an explicit argument, the
    ``ORCHESTRATOR_STATE_DIR`` environment variable, an existing
    ``orchestrator-state`` directory under the current or parent directory,
    and finally the configured project default.

    Args:
        orch_state: Optional explicit path to the state directory.

    Returns:
        The resolved state directory path.

    Raises:
        OSError: If the selected directory cannot be created.
        RuntimeError: If path resolution fails.
    """
    if orch_state:
        p = Path(orch_state).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    env_dir = os.getenv("ORCHESTRATOR_STATE_DIR")
    if env_dir:
        p = Path(env_dir).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    # Probe current directory and parents
    cwd = Path.cwd().resolve()
    for candidate in [cwd, cwd.parent]:
        target = candidate / "orchestrator-state"
        if target.exists() and target.is_dir():
            return target

    # Default project root fallback
    default_p = Path("F:/Aaradhya-Dev-Tamrakar/Fleet-Orchestrator/orchestrator-state")
    default_p.mkdir(parents=True, exist_ok=True)
    return default_p


def parse_iso_utc(ts_val: Any) -> datetime | None:
    """Parse a timestamp value as an aware UTC datetime.

    ISO-formatted strings and epoch milliseconds are supported. Naive
    timestamps are interpreted as UTC; malformed or unsupported values return
    ``None``.

    Args:
        ts_val: ISO timestamp string, epoch milliseconds, or another value to
            parse.

    Returns:
        The timestamp normalized to UTC, or ``None`` when parsing fails.

    Raises:
        None. Conversion and parsing errors are caught and represented by
        ``None``.
    """
    if not ts_val:
        return None
    try:
        if isinstance(ts_val, (int, float)):
            # Epoch milliseconds
            return datetime.fromtimestamp(ts_val / 1000.0, timezone.utc)
        if isinstance(ts_val, str):
            clean = ts_val.strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
    except Exception:
        return None
    return None


def next_billing_reset(now: datetime | None = None) -> datetime:
    """Compute midnight UTC on the first day of the next calendar month.

    Args:
        now: Optional reference datetime. When omitted, the current UTC time
            is used.

    Returns:
        An aware UTC datetime for the next monthly billing reset.

    Raises:
        OverflowError: If ``now`` is in December of the maximum datetime year.
    """
    dt = now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)
    if dt.month == 12:
        return datetime(dt.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    return datetime(dt.year, dt.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)


class FileLock:
    """Manage an exclusive cross-platform operating-system file lock.

    Use this class as a context manager to acquire the lock on entry and
    release it on exit. Windows uses ``msvcrt``; POSIX platforms use ``fcntl``.

    Args:
        lock_path: Filesystem path of the lock file. Its parent directory is
            created when the lock is acquired.

    Returns:
        A ``FileLock`` context manager for the specified lock file.

    Raises:
        OSError: If opening or acquiring the lock file fails.
    """

    def __init__(self, lock_path: Path):
        """Initialize a lock manager for ``lock_path``.

        Args:
            lock_path: Path to the file used for interprocess locking.

        Returns:
            None.

        Raises:
            TypeError: If ``lock_path`` is not a valid filesystem path.
            The file is not opened until the context manager is entered.
        """
        self.lock_path = Path(lock_path)
        self.file_obj: Any = None

    def __enter__(self) -> FileLock:
        """Open the lock file and acquire its exclusive lock.

        Args:
            None.

        Returns:
            This lock manager, allowing use in a ``with`` statement.

        Raises:
            OSError: If the lock file cannot be opened or the lock cannot be
                acquired.
        """
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.file_obj = open(self.lock_path, "a+b")
        if sys.platform == "win32":
            for _ in range(50):
                try:
                    self.file_obj.seek(0)
                    msvcrt.locking(self.file_obj.fileno(), msvcrt.LK_NBLCK, 1)
                    return self
                except OSError:
                    time.sleep(0.05)
            # Fallback to blocking lock
            self.file_obj.seek(0)
            msvcrt.locking(self.file_obj.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(self.file_obj.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Release the lock and close its file handle.

        Args:
            exc_type: Exception type raised inside the context, if any.
            exc_val: Exception value raised inside the context, if any.
            exc_tb: Traceback for the exception raised inside the context, if
                any.

        Returns:
            None.

        Raises:
            OSError: If closing the lock file fails. Unlock errors are
                suppressed so the handle is still closed.
        """
        if self.file_obj:
            try:
                self.file_obj.seek(0)
                if sys.platform == "win32":
                    msvcrt.locking(self.file_obj.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(self.file_obj.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            finally:
                self.file_obj.close()
                self.file_obj = None


def atomic_write_json(target_path: Path, data: dict[str, Any], max_attempts: int = 5) -> None:
    """Atomically write a JSON object to a file.

    The data is serialized to a unique temporary file beside the target, then
    moved into place with ``os.replace``. Permission failures during replacement
    are retried before a final uncaught attempt.

    Args:
        target_path: Destination path for the JSON file.
        data: JSON-serializable mapping to write.
        max_attempts: Number of replacement attempts before the final attempt.

    Returns:
        None.

    Raises:
        OSError: If creating or writing the temporary file fails, or if the
            final replacement attempt fails.
        TypeError: If ``data`` contains a value that cannot be serialized as
            JSON.
        ValueError: If ``data`` contains a circular reference that cannot
            be serialized as JSON.
    """
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tid = threading.get_ident()
    u = uuid.uuid4().hex[:6]
    tmp_path = target_path.with_name(f"{target_path.name}.tmp.{os.getpid()}.{tid}.{u}")

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    for attempt in range(max_attempts):
        try:
            os.replace(tmp_path, target_path)
            return
        except PermissionError:
            time.sleep(0.05 * (2 ** attempt))

    # Final attempt before error
    os.replace(tmp_path, target_path)


def harvest_worker_sessions(
    worker_home: Path,
    month_prefix: str | None = None,
) -> dict[str, int]:
    """
    Collect Copilot usage totals from a worker's session event logs.

    The function scans ``session-state/*/events.jsonl``, extracts the greatest
    recorded ``totalNanoAiu`` value from shutdown events, and caches results
    using each event file's size and modification time. Only sessions matching
    the requested month are included.

    Args:
        worker_home: Worker home directory containing ``session-state``.
        month_prefix: Billing month in ``YYYY-MM`` format. Defaults to the
            current UTC month.

    Returns:
        A mapping from session ID to its usage in nano-AIU units. Missing
        session-state directories produce an empty mapping.

    Raises:
        OSError: If the worker home path cannot be inspected. Errors reading
            individual event files are logged and skipped.
        TypeError: If ``worker_home`` cannot be converted to a filesystem path.
    """
    worker_home = Path(worker_home)
    s_dir = worker_home / "session-state"
    if not s_dir.exists():
        return {}

    now_period = month_prefix or datetime.now(timezone.utc).strftime("%Y-%m")
    sessions: dict[str, int] = {}

    for sess_dir in s_dir.glob("*"):
        sess_id = sess_dir.name
        events_file = sess_dir / "events.jsonl"
        if not events_file.exists():
            continue

        try:
            stat = events_file.stat()
            file_key = str(events_file)
            cached = _EVENT_FILE_CACHE.get(file_key)

            if cached and cached[0] == stat.st_size and cached[1] == stat.st_mtime:
                # Cache hit: size and mtime match
                nano, period = cached[2], cached[3]
                if period == now_period and nano > 0:
                    sessions[sess_id] = nano
                continue

            best_nano = 0
            event_period = ""

            with open(events_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip() or "session.shutdown" not in line:
                        continue
                    try:
                        evt = json.loads(line)
                        ts_raw = evt.get("timestamp")
                        if not ts_raw and "sessionStartTime" in evt.get("data", {}):
                            ts_raw = evt["data"]["sessionStartTime"]

                        dt = parse_iso_utc(ts_raw)
                        if dt:
                            event_period = dt.strftime("%Y-%m")

                        data = evt.get("data", {})
                        nano = data.get("totalNanoAiu", 0)
                        if not nano and "accountingSnapshot" in data:
                            nano = data["accountingSnapshot"].get("totalNanoAiu", 0)

                        if nano > best_nano:
                            best_nano = int(nano)
                    except Exception:
                        continue

            _EVENT_FILE_CACHE[file_key] = (stat.st_size, stat.st_mtime, best_nano, event_period)

            if event_period == now_period and best_nano > 0:
                sessions[sess_id] = best_nano
        except Exception as e:
            logger.debug(f"Could not read events from {events_file}: {e}")
            continue

    return sessions


def sync_worker_ledger(
    orch_state: Path | str | None,
    account: dict[str, Any],
    provisional_credits: float = 0.0,
    current_period: str | None = None,
    force_cooldown: bool = False,
    cooldown_until: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """
    Synchronize one worker's authoritative credit ledger and live status.

    This operation locks the worker ledger, harvests session metrics, merges
    provisional credits, resets the ledger when the billing period changes,
    computes quota status, and atomically updates both ledger and live-status
    files.

    Args:
        orch_state: Optional orchestrator state directory. If omitted, the
            standard state-directory resolution rules are used.
        account: Worker configuration. Must include ``worker_id`` and may
            include ``state_dir``, ``monthly_credits``, ``has_token``, and
            ``name``.
        provisional_credits: Additional credits to record for this
            synchronization; non-positive values are ignored.
        current_period: Billing period in ``YYYY-MM`` format. Defaults to the
            current UTC month.
        force_cooldown: Whether to mark the worker as cooling down unless its
            quota is exhausted or it already has an active task.
        cooldown_until: Optional ISO timestamp for the cooldown expiry.
        note: Optional status note, taking precedence over the existing note
            and generated default.

    Returns:
        The live-status payload written for the worker, including usage,
        remaining credits, quota state, and worker status.

    Raises:
        KeyError: If ``account`` does not contain ``worker_id``.
        OSError: If the lock, ledger, or live-status files cannot be accessed
            or written.
        TypeError: If the account values or stored JSON data have incompatible
            types.
    """
    resolved_orch = resolve_state_dir(orch_state)
    ledger_dir = resolved_orch / "ledger"
    live_status_dir = resolved_orch / "live-status"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    live_status_dir.mkdir(parents=True, exist_ok=True)

    wid = account["worker_id"]
    limit = account.get("monthly_credits", 200)
    has_token = account.get("has_token", True)
    worker_home = Path(account.get("state_dir", ""))
    now_dt = datetime.now(timezone.utc)
    now_period = current_period or now_dt.strftime("%Y-%m")
    now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    lock_file = ledger_dir / f"{wid}.lock"
    ledger_file = ledger_dir / f"{wid}.json"
    status_file = live_status_dir / f"{wid}.json"

    with FileLock(lock_file):
        # 1. Load existing sidecar ledger
        ledger_data: dict[str, Any] = {
            "worker_id": wid,
            "period": now_period,
            "sessions": {},
            "provisional": [],
        }
        if ledger_file.exists():
            try:
                with open(ledger_file, "r", encoding="utf-8") as f:
                    ledger_data = json.load(f)
            except Exception:
                pass

        # 2. Handle Month Rollover on Sidecar Ledger
        if ledger_data.get("period") != now_period:
            ledger_data = {
                "worker_id": wid,
                "period": now_period,
                "sessions": {},
                "provisional": [],
            }

        # 3. Harvest fresh sessions from worker home
        if worker_home.exists():
            harvested = harvest_worker_sessions(worker_home, month_prefix=now_period)
            for sess_id, nano in harvested.items():
                existing = ledger_data["sessions"].get(sess_id, 0)
                if nano > existing:
                    ledger_data["sessions"][sess_id] = nano

        # 4. Handle provisional credits (from tests or manual calls without real session files)
        if provisional_credits > 0:
            ledger_data["provisional"].append({
                "timestamp": now_iso,
                "credits": round(float(provisional_credits), 2),
            })

        # Save updated sidecar ledger atomically
        atomic_write_json(ledger_file, ledger_data)

        # 5. Compute authoritative credit totals
        sessions_total_credits = sum(ledger_data["sessions"].values()) / 1_000_000_000.0
        provisional_total_credits = sum(p["credits"] for p in ledger_data.get("provisional", []))
        total_credits_used = round(sessions_total_credits + provisional_total_credits, 2)
        credits_remaining = max(0.0, round(float(limit) - total_credits_used, 2))
        quota_exhausted = (total_credits_used >= limit)

        # 6. Load pre-existing live-status to preserve active task or notes
        live_data: dict[str, Any] = {}
        if status_file.exists():
            try:
                with open(status_file, "r", encoding="utf-8") as f:
                    live_data = json.load(f)
            except Exception:
                pass

        # Check existing cooldown expiration
        cur_cd_until = cooldown_until or live_data.get("cooldown_until")
        if cur_cd_until:
            try:
                exp_dt = parse_iso_utc(cur_cd_until)
                if exp_dt and now_dt >= exp_dt:
                    cur_cd_until = None
            except Exception:
                cur_cd_until = None

        # Determine effective status
        worker_status = "idle" if has_token else "offline"
        if live_data.get("current_task_id"):
            worker_status = "busy"
        elif quota_exhausted:
            worker_status = "cooldown"
            cur_cd_until = next_billing_reset(now_dt).strftime("%Y-%m-%dT%H:%M:%SZ")
        elif force_cooldown or cur_cd_until:
            worker_status = "cooldown"

        default_note = "Ready" if has_token else "No Token"
        if quota_exhausted:
            default_note = f"Exhausted ({limit}/{limit} credits): Resets {next_billing_reset(now_dt).strftime('%Y-%m-%d')}"
        elif worker_status == "cooldown":
            default_note = f"Cooldown until {cur_cd_until[11:19] if cur_cd_until else 'later'}"

        status_payload = {
            "account": wid,
            "name": account.get("name", wid),
            "status": worker_status,
            "period": now_period,
            "current_task_id": live_data.get("current_task_id"),
            "credits_used": total_credits_used,
            "credits_remaining": credits_remaining,
            "monthly_credits": limit,
            "quota_exhausted": quota_exhausted,
            "cooldown_until": cur_cd_until,
            "heartbeat_at": now_iso,
            "note": note or live_data.get("note") or default_note,
        }

        # Write live-status atomically
        atomic_write_json(status_file, status_payload)
        return status_payload


def reconcile_all_workers(
    orch_state: Path | str | None,
    accounts: list[dict[str, Any]],
    month_prefix: str | None = None,
) -> dict[str, Any]:
    """
    Reconcile usage and quota status for all configured workers.

    Reconciliation is idempotent for a given set of on-disk usage data. When
    ``month_prefix`` names a period other than the current UTC month, the
    function reports harvested session usage without changing worker ledgers
    or live-status files.

    Args:
        orch_state: Optional orchestrator state directory. If omitted, the
            standard state-directory resolution rules are used.
        accounts: Worker configurations to reconcile. Each account must
            include ``worker_id`` and ``name``; ``state_dir`` and
            ``monthly_credits`` are optional.
        month_prefix: Billing period in ``YYYY-MM`` format. Defaults to the
            current UTC month.

    Returns:
        A summary containing the target period, report-only flag, per-worker
        results, total credits used, total monthly credits, and session count.

    Raises:
        KeyError: If a required account field is missing.
        OSError: If state or ledger files cannot be accessed or written.
        TypeError: If account data or persisted JSON has incompatible types.
    """
    resolved_orch = resolve_state_dir(orch_state)
    now_period = datetime.now(timezone.utc).strftime("%Y-%m")
    target_period = month_prefix or now_period
    is_report_only = (target_period != now_period)

    summary: dict[str, Any] = {
        "period": target_period,
        "report_only": is_report_only,
        "workers": {},
        "total_credits_used": 0.0,
        "total_monthly_credits": 0,
        "total_sessions": 0,
    }

    for acc in accounts:
        wid = acc["worker_id"]
        limit = acc.get("monthly_credits", 200)
        summary["total_monthly_credits"] += limit

        if is_report_only:
            # Report-only harvest from worker home without writing live-status
            worker_home = Path(acc.get("state_dir", ""))
            sessions = harvest_worker_sessions(worker_home, month_prefix=target_period)
            used = round(sum(sessions.values()) / 1_000_000_000.0, 2)
            summary["workers"][wid] = {
                "worker_id": wid,
                "name": acc["name"],
                "credits_used": used,
                "sessions_count": len(sessions),
            }
            summary["total_credits_used"] = round(summary["total_credits_used"] + used, 2)
            summary["total_sessions"] += len(sessions)
        else:
            # Synchronize live status and sidecar ledger
            res = sync_worker_ledger(resolved_orch, acc, current_period=target_period)
            used = res["credits_used"]
            summary["workers"][wid] = {
                "worker_id": wid,
                "name": acc["name"],
                "credits_used": used,
                "status": res["status"],
                "quota_exhausted": res["quota_exhausted"],
            }
            summary["total_credits_used"] = round(summary["total_credits_used"] + used, 2)

    return summary


def initialize_ledgers(
    orch_state: Path | str | None,
    accounts: list[dict[str, Any]],
) -> int:
    """Create live-status files for accounts that do not yet have one.

    Existing status files are left untouched, making repeated calls
    idempotent.

    Args:
        orch_state: Optional orchestrator state directory. If omitted, the
            standard state-directory resolution rules are used.
        accounts: Worker configurations to initialize. Each account must
            include ``worker_id`` and any fields required by
            :func:`sync_worker_ledger`.

    Returns:
        The number of live-status files created.

    Raises:
        KeyError: If an account is missing a required field.
        OSError: If the state directory or a live-status file cannot be
            accessed or written.
        TypeError: If an account contains incompatible values.
    """
    resolved_orch = resolve_state_dir(orch_state)
    live_status_dir = resolved_orch / "live-status"
    live_status_dir.mkdir(parents=True, exist_ok=True)
    created = 0

    for acc in accounts:
        wid = acc["worker_id"]
        status_file = live_status_dir / f"{wid}.json"
        if not status_file.exists():
            sync_worker_ledger(resolved_orch, acc)
            created += 1
    return created
