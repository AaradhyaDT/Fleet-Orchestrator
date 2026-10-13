# Local/private background jobs

`fleet.bat job` (or `python -m tools.fleet_jobs`) starts an explicitly requested
local Copilot CLI job with durable state, separately from the shared Fleet queue.
The bridge currently supports automatic intelligence-tier selection only; model
selection is left to the installed CLI and account configuration:

```powershell
.\fleet.bat job start --spec-file .\job-spec.json --auto-tier intelligence
.\fleet.bat job status job-<32 lowercase hex characters> --json
.\fleet.bat job list --json
.\fleet.bat job cancel job-<32 lowercase hex characters>
.\fleet.bat job result job-<32 lowercase hex characters> --json
.\fleet.bat job resume job-<32 lowercase hex characters>
```

When invoking the module directly, omit the `job` word, for example:
`python -m tools.fleet_jobs status job-<id> --json`.

`resume` is intentionally explicit and allows one retry after a failed,
timed-out, or interrupted attempt, but never after completion or cancellation.
It verifies the immutable spec and original deadline, and refuses to proceed
while any recorded supervisor, worker, or verified descendant remains alive.
The retry preserves the original scope, deadline, and worktree and includes the
prior failure as feedback. `status` and `list` are read-only: they never restart
or resubmit a job. A controller restart does not duplicate or automatically
resume execution.

## Spec format

The UTF-8 JSON spec accepts exactly these fields. `allowed_files` entries are
relative POSIX paths, matched exactly; directory-wide scope is not supported.
Optional test commands are argv arrays (executed without a shell) in the
isolated worktree and supply verification evidence. Do not put credentials,
tokens, or secret material in the spec.

```json
{
  "specification": "Implement a narrowly scoped change.",
  "allowed_files": ["src/module.py", "tests/test_module.py"],
  "repo_path": "C:\\absolute\\path\\to\\git-repository",
  "timeout_seconds": 900,
  "overall_deadline": 1791895000,
  "worker_id": "copilot-w1",
  "test_commands": [["python", "-m", "pytest", "tests/test_module.py", "-q"]]
}
```

`timeout_seconds` must be in `(0, 1800]`; `overall_deadline` must be a future
UNIX timestamp no more than two hours away. `worker_id` is optional; without
it, the bridge selects an available configured Copilot account using an OS
lock. Explicit account selection is also exclusive. No credit or entitlement
assumptions are made. Credentials are loaded internally and never written to
job state/specs.
The sample deadline is illustrative; generate a current timestamp plus the
desired duration when creating a real spec.

Each job has an immutable spec, atomic state, lock, heartbeat, redacted log,
binary patch (including base64-encoded untracked file contents), test evidence,
and a concise manifest under ignored `orchestrator-state/jobs/<job-id>/`.
If bounded Git inspection fails during finalization, the job records a failed
verification and preserves scoped file contents in `recovery_files_base64`
alongside `artifact_error`. These recovery contents are an incomplete patch;
review the retained worktree before applying them. The job still records its
terminal state, including cancellation or timeout when applicable.
When provisioned, the worktree and `codex/job-<id>` branch are preserved under
the repository's `.worktrees/` directory for inspection, regardless of
outcome. No commits are created. Copilot execution uses a per-job
`COPILOT_HOME` and selected token, strips all account-pool and other
secret-bearing environment variables from
the worker and test processes, disables remote/export and built-in MCP access,
and redacts all configured account tokens from output. As inherent to Copilot
use, the selected inference provider receives the prompt and relevant code.
The bridge performs no separate sharing, upload, or export of job contents.

By default, three OS-locked active slots bound concurrent execution; additional
jobs wait in the queue. Set `FLEET_JOB_MAX_WORKERS` consistently for all
controllers and supervisors to an integer from 1 to 27 to change the local
limit. Account locks remain exclusive and each job retains its own execution
budget. Heartbeats are written every 15 seconds, and stale heartbeats
older than 120 seconds are reported as unresponsive only while the recorded
supervisor identity is still live. Status includes the execution phase,
heartbeat age, and artifact paths. PID, process creation time, exact command,
and job association are checked before a process is signalled; descendant
identity and ancestry snapshots are captured while processes are alive.
Cancellation is cooperative first, followed by a bounded verified
process-tree termination.

Worker success is not itself acceptance: lifecycle `status` is separate from
`verification` (`unverified`, `passed`, or `failed`). Verification is `passed`
only when configured test commands complete successfully. Actual model,
token, and credit values are taken only from provider usage data; unavailable
values remain `null`. The bridge does not infer account entitlements or credits.

This is local orchestration, not an OS sandbox. The worker can execute local
commands with the current user's permissions inside its worktree and may read
other accessible local files; secret-bearing environment variables are
stripped. Prompts and relevant repository source are sent to the configured
inference provider. Fleet does not separately upload or export job specs,
patches, logs, or test evidence. Use trusted specs/repositories and inspect the
preserved patch and test evidence before applying changes elsewhere.

## Verification manifest

- Regression tests use temporary Git repositories/state, a real hidden
  supervisor startup path where useful, and a mocked provider. They never
  contact a provider or submit a live job.
- `python -m pytest tests/test_fleet_jobs.py -q`: regression suite.
- `python -m ruff check tools/fleet_jobs.py tools/fleet_job_supervisor.py tests/test_fleet_jobs.py`: lint.
