"""Local metadata, native credential environments, and transactional account leases."""

from __future__ import annotations

import contextlib
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any
import uuid

import psutil

PROVIDERS = ("agy_cli", "codex_cli", "opencode_cli")
AGY_ISOLATION_NOTE = (
    "AGY uses the OS credential store. No supported per-profile credential selector "
    "was found in the installed CLI or official documentation. Home overrides do not "
    "prove isolation; pooled AGY login, logout, and execution are unavailable. "
    "Existing single-account AGY workers remain supported."
)


def account_root() -> Path:
    return Path(os.getenv("FLEET_ACCOUNTS_HOME", str(Path.home() / ".fleet-orchestrator"))).expanduser().resolve()


def valid_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value):
        raise ValueError("IDs must contain 1-64 letters, digits, underscores, dots or hyphens")
    value = value.lower()
    if value.endswith(".") or value.split(".")[0] in {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{i}" for i in range(1, 10)),
        *(f"lpt{i}" for i in range(1, 10)),
    }:
        raise ValueError("ID is a reserved Windows filename")
    return value


def profile_environment(profile: dict[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    root = Path(profile["credential_dir"])
    provider = profile["provider"]
    # Avoid ambient API keys silently selecting another identity or billing route.
    for name in (
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_AUTH_TOKEN",
        "CODEX_ACCESS_TOKEN",
        "CODEX_API_KEY",
        "CODEX_HOME",
        "OPENCODE_AUTH_FILE",
        "OPENCODE_TEST_HOME",
        "OPENCODE_CONFIG",
        "OPENCODE_CONFIG_CONTENT",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENCODE_API_KEY",
        "COPILOT_GITHUB_TOKEN",
    ):
        env.pop(name, None)
    if provider == "codex_cli":
        env["CODEX_HOME"] = str(root)
    elif provider == "opencode_cli":
        for kind in ("DATA", "CONFIG", "CACHE", "STATE"):
            env[f"XDG_{kind}_HOME"] = str(root / kind.lower())
        env["OPENCODE_CONFIG_DIR"] = str(root / "config" / "opencode")
    else:
        raise ValueError(AGY_ISOLATION_NOTE)
    return env


class AccountStore:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root).expanduser().resolve() if root else account_root()
        repo = Path(__file__).resolve().parent.parent
        if self.root.is_relative_to(repo):
            raise ValueError("Account storage must be outside the Fleet repository")
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "accounts.sqlite3"
        with contextlib.closing(self.connect()) as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY, provider TEXT NOT NULL, label TEXT NOT NULL,
                    pool TEXT NOT NULL, credential_dir TEXT NOT NULL, account_group TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1, auth_state TEXT NOT NULL DEFAULT 'unverified',
                    identity_verified INTEGER NOT NULL DEFAULT 0, last_verified REAL,
                    cooldown_until REAL NOT NULL DEFAULT 0, rate_failures INTEGER NOT NULL DEFAULT 0,
                    note TEXT NOT NULL DEFAULT '', binary TEXT
                );
                CREATE TABLE IF NOT EXISTS leases (
                    profile_id TEXT PRIMARY KEY REFERENCES profiles(id), token TEXT NOT NULL,
                    owner TEXT NOT NULL, pid INTEGER NOT NULL, process_started REAL NOT NULL,
                    expires REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cursors (pool_key TEXT PRIMARY KEY, last_id TEXT);
            """)
            if "children" not in {row[1] for row in db.execute("PRAGMA table_info(leases)")}:
                db.execute("ALTER TABLE leases ADD COLUMN children TEXT NOT NULL DEFAULT '[]'")
                db.commit()

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.db_path, timeout=15, isolation_level="IMMEDIATE")
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @contextlib.contextmanager
    def transaction(self):
        db = self.connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def add(
        self,
        profile_id: str,
        provider: str,
        *,
        label: str | None = None,
        pool: str = "default",
        account_group: str | None = None,
        binary: str | None = None,
    ) -> dict[str, Any]:
        profile_id = valid_id(profile_id)
        pool = valid_id(pool)
        if provider not in PROVIDERS:
            raise ValueError(f"Unsupported account provider: {provider}")
        directory = self.root / "profiles" / provider / profile_id
        state = "isolation_unverified" if provider == "agy_cli" else "unverified"
        note = AGY_ISOLATION_NOTE if provider == "agy_cli" else ""
        with self.transaction() as db:
            db.execute(
                "INSERT INTO profiles(id,provider,label,pool,credential_dir,account_group,auth_state,note,binary) VALUES(?,?,?,?,?,?,?,?,?)",
                (profile_id, provider, label or profile_id, pool, str(directory), account_group, state, note, binary),
            )
        directory.mkdir(parents=True, exist_ok=True)
        if provider == "codex_cli":
            config = directory / "config.toml"
            if not config.exists():
                config.write_text('cli_auth_credentials_store = "file"\n', encoding="utf-8")
        elif provider == "opencode_cli":
            for kind in ("data", "config", "cache", "state"):
                (directory / kind / "opencode").mkdir(parents=True, exist_ok=True)
        return self.get(profile_id)

    def get(self, profile_id: str) -> dict[str, Any]:
        profile_id = valid_id(profile_id)
        with contextlib.closing(self.connect()) as db:
            row = db.execute("SELECT * FROM profiles WHERE id=?", (profile_id,)).fetchone()
        if row is None:
            raise ValueError(f"Unknown auth profile: {profile_id}")
        return dict(row)

    def update(self, profile_id: str, **values: Any) -> None:
        profile_id = valid_id(profile_id)
        allowed = {
            "enabled",
            "auth_state",
            "identity_verified",
            "last_verified",
            "cooldown_until",
            "rate_failures",
            "note",
        }
        if not values or not set(values).issubset(allowed):
            raise ValueError("Invalid profile update")
        self.get(profile_id)
        with self.transaction() as db:
            # Refuse login/logout/administrative mutation while a task holds the profile.
            self._reap(db)
            if db.execute("SELECT 1 FROM leases WHERE profile_id=?", (profile_id,)).fetchone():
                raise ValueError("Profile is leased by an executing task")
            db.execute(
                f"UPDATE profiles SET {','.join(f'{k}=?' for k in values)} WHERE id=?", (*values.values(), profile_id)
            )

    def finish_management(
        self,
        profile_id: str,
        token: str,
        *,
        state: str,
        identity_verified: bool = False,
        note: str = "",
        error_kind: str | None = None,
        retry_after: float | None = None,
        reset_failure: bool = False,
    ) -> None:
        with self.transaction() as db:
            if not db.execute("DELETE FROM leases WHERE profile_id=? AND token=?", (profile_id, token)).rowcount:
                raise ValueError("Account management lease was lost")
            db.execute(
                "UPDATE profiles SET auth_state=?,identity_verified=?,last_verified=?,note=? WHERE id=?",
                (state, int(identity_verified), time.time(), note, profile_id),
            )
            if error_kind is not None or reset_failure:
                self._failure(db, profile_id, error_kind, retry_after)

    @staticmethod
    def _reap(db: sqlite3.Connection) -> None:
        for lease in db.execute("SELECT * FROM leases").fetchall():
            try:
                alive = abs(psutil.Process(lease["pid"]).create_time() - lease["process_started"]) < 0.01
            except psutil.NoSuchProcess:
                alive = False
            except psutil.AccessDenied:
                alive = True
            if not alive:
                for child in json.loads(lease["children"]):
                    try:
                        if abs(psutil.Process(child["pid"]).create_time() - child["started"]) < 0.01:
                            alive = True
                    except psutil.NoSuchProcess:
                        pass
                    except psutil.AccessDenied:
                        alive = True
            # Never revoke a still-running local process simply because its heartbeat paused.
            if not alive:
                db.execute("DELETE FROM leases WHERE profile_id=?", (lease["profile_id"],))

    def list(self) -> list[dict[str, Any]]:
        with self.transaction() as db:
            self._reap(db)
            rows = db.execute(
                "SELECT p.*, l.owner AS lease_owner FROM profiles p LEFT JOIN leases l ON l.profile_id=p.id ORDER BY p.id"
            ).fetchall()
        return [dict(r) for r in rows]

    def acquire(
        self,
        provider: str,
        owner: str,
        *,
        profile_id: str | None = None,
        pool: str | None = None,
        management: bool = False,
    ) -> tuple[dict[str, Any], str] | None:
        if bool(profile_id) == bool(pool):
            raise ValueError("Choose exactly one AuthProfile or AccountPool")
        profile_id = valid_id(profile_id) if profile_id else None
        pool = valid_id(pool) if pool else None
        with self.transaction() as db:
            self._reap(db)
            rows = db.execute("SELECT * FROM profiles WHERE provider=? ORDER BY id", (provider,)).fetchall()
            candidates = [dict(r) for r in rows if (r["id"] == profile_id if profile_id else r["pool"] == pool)]
            if management:
                candidates = [p for p in candidates if p["provider"] != "agy_cli"]
            else:
                candidates = [
                    p
                    for p in candidates
                    if p["enabled"] and p["auth_state"] == "ready" and p["cooldown_until"] <= time.time()
                ]
            key = f"{provider}:{pool or profile_id}"
            cursor = db.execute("SELECT last_id FROM cursors WHERE pool_key=?", (key,)).fetchone()
            if cursor:
                candidates.sort(key=lambda p: (p["id"] <= cursor[0], p["id"]))
            for profile in candidates:
                if db.execute("SELECT 1 FROM leases WHERE profile_id=?", (profile["id"],)).fetchone():
                    continue
                token = uuid.uuid4().hex
                db.execute(
                    "INSERT INTO leases(profile_id,token,owner,pid,process_started,expires) VALUES(?,?,?,?,?,?)",
                    (profile["id"], token, owner, os.getpid(), psutil.Process().create_time(), time.time() + 90),
                )
                db.execute(
                    "INSERT INTO cursors VALUES(?,?) ON CONFLICT(pool_key) DO UPDATE SET last_id=excluded.last_id",
                    (key, profile["id"]),
                )
                return profile, token
        return None

    def record_child(self, profile_id: str, token: str, pid: int) -> None:
        if not isinstance(pid, int):
            return
        try:
            identity = {"pid": pid, "started": psutil.Process(pid).create_time()}
        except psutil.NoSuchProcess:
            return
        with self.transaction() as db:
            row = db.execute(
                "SELECT children FROM leases WHERE profile_id=? AND token=?", (profile_id, token)
            ).fetchone()
            if row is None:
                raise ValueError("Account lease was lost before child launch")
            children = json.loads(row[0])
            if identity not in children:
                children.append(identity)
            db.execute(
                "UPDATE leases SET children=? WHERE profile_id=? AND token=?", (json.dumps(children), profile_id, token)
            )

    def renew(self, profile_id: str, token: str) -> None:
        with self.transaction() as db:
            changed = db.execute(
                "UPDATE leases SET expires=? WHERE profile_id=? AND token=?", (time.time() + 90, profile_id, token)
            ).rowcount
            if not changed:
                raise ValueError("Account lease was lost")

    def release(
        self, profile_id: str, token: str, *, error_kind: str | None = None, retry_after: float | None = None
    ) -> None:
        with self.transaction() as db:
            if not db.execute("DELETE FROM leases WHERE profile_id=? AND token=?", (profile_id, token)).rowcount:
                return
            self._failure(db, profile_id, error_kind, retry_after)

    @staticmethod
    def _failure(db: sqlite3.Connection, profile_id: str, error_kind: str | None, retry_after: float | None) -> None:
        if error_kind == "authentication":
            db.execute(
                "UPDATE profiles SET auth_state='reauth_required', identity_verified=0 WHERE id=?", (profile_id,)
            )
        elif error_kind in ("rate_limit", "quota_exhausted"):
            count = db.execute("SELECT rate_failures FROM profiles WHERE id=?", (profile_id,)).fetchone()[0] + 1
            if error_kind == "quota_exhausted" and retry_after is None:
                db.execute("UPDATE profiles SET auth_state='quota_exhausted' WHERE id=?", (profile_id,))
            else:
                delay = max(0, retry_after) if retry_after is not None else min(900, 60 * 2 ** min(count - 1, 4))
                db.execute(
                    "UPDATE profiles SET cooldown_until=?,rate_failures=? WHERE id=?",
                    (time.time() + delay, count, profile_id),
                )
        elif error_kind is None:
            db.execute("UPDATE profiles SET rate_failures=0,cooldown_until=0 WHERE id=?", (profile_id,))


def classify_failure(result: dict[str, Any]) -> str | None:
    if result.get("success"):
        return None
    if result.get("error_kind"):
        return result["error_kind"]
    message = str(result.get("error", "")).lower()
    if any(s in message for s in ("quota exhausted", "usage limit", "insufficient_quota", "quota exceeded")):
        return "quota_exhausted"
    if any(s in message for s in ("429", "rate limit", "too many requests", "resource_exhausted")):
        return "rate_limit"
    if any(
        s in message
        for s in (
            "unauthorized",
            "not logged in",
            "not signed in",
            "authentication",
            "401",
            "token expired",
            "login required",
        )
    ):
        return "authentication"
    if any(s in message for s in ("timed out", "timeout")):
        return "timeout"
    return "process"


def redact_message(value: str) -> str:
    value = re.sub(r"(?i)(bearer\s+)[^\s]+", r"\1[REDACTED]", value)
    return re.sub(r"\b(?:sk-[A-Za-z0-9_-]+|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b", "[REDACTED]", value)


def save_failed_attempt(worker_id: str, task_id: str, result: dict[str, Any], *, root: Path | None = None) -> Path:
    directory = (root or account_root()) / "task-attempts"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{uuid.uuid4().hex}.json"
    payload = {
        "task_id": task_id,
        "worker_id": worker_id,
        "time": time.time(),
        "auth_profile": result.get("auth_profile"),
        "workspace": result.get("workspace"),
        "error_kind": classify_failure(result),
        "error": redact_message(str(result.get("error", ""))),
        "result_text": redact_message(str(result.get("result_text", ""))),
        "execution_started": result.get("execution_started", True),
    }
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(target)
    return target


def reported_retry_after(output: str) -> float | None:
    """Read explicit seconds or standard HTTP Retry-After headers; never guess units."""

    def walk(value: Any) -> float | None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key.lower() in ("retry_after_seconds", "retry-after"):
                    try:
                        delay = float(item)
                    except (ValueError, TypeError):
                        try:
                            delay = parsedate_to_datetime(str(item)).timestamp() - time.time()
                        except (ValueError, TypeError, OverflowError):
                            continue
                    if 0 <= delay < float("inf"):
                        return delay
                found = walk(item)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = walk(item)
                if found is not None:
                    return found
        return None

    try:
        delay = walk(json.loads(output))
        if delay is not None:
            return delay
    except (json.JSONDecodeError, RecursionError):
        pass
    for line in output.splitlines():
        try:
            delay = walk(json.loads(line))
        except (json.JSONDecodeError, RecursionError):
            continue
        if delay is not None:
            return delay
    return None
