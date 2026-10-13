# Fleet-Orchestrator repository evaluation

Date: 2026-10-13 (Asia/Katmandu)
Local commit inspected: `1bc9f49`
Scope: Aaradhya's personal, private tool ecosystem. Evaluation only; no publishing, task dispatch, visibility change, or runtime repair.
Evidence labels: EMPIRICALLY_VERIFIED denotes executed checks; HEURISTIC_HYPOTHESIS denotes assessment or recommended design.

## Assessment

HEURISTIC_HYPOTHESIS: This is a substantial personal automation workbench with useful provider adapters, account isolation, checkpoint persistence, quota accounting, and a tested coordination backend. Its main engineering priority is making execution boundaries and task state dependable before increasing capability breadth. Enterprise product requirements are outside this evaluation.

## Executed verification

EMPIRICALLY_VERIFIED:

- `python -m pytest tests/ -q --tb=short`: 335 passed, one dependency deprecation warning, 68.91 seconds. Local interpreter was Python 3.14; remote CI was not checked.
- `python -m ruff check .`: passed. The configured rules are a narrow crash/syntax/undefined-name subset, not a comprehensive maintainability review.
- `python tools/validate_schemas.py --all`: all three validation suites passed.
- Repository secret scanner, invoked through `scan_repository` with aggregate-only output: zero matches in currently tracked files. This does not establish that history or generated/private local files contain no secrets.
- `gh repo view --json nameWithOwner,visibility`: `AaradhyaDT/Fleet-Orchestrator` reports PUBLIC. This conflicts with the requested private posture; visibility was not changed.
- Local runtime check: no matching fleet processes or listener on the expected backend port; localhost backend health request failed.

## Priority findings

### 1. Public repository visibility conflicts with private intent

EMPIRICALLY_VERIFIED: GitHub reports PUBLIC. Ignoring runtime credentials prevents some accidental commits but does not make tracked source, documentation, or archived conversations private. Resolve the intended hosting visibility before synchronizing private ecosystem material. This review makes no finding about the sensitivity of every tracked document.

### 2. Headless file tools do not enforce their workspace boundary

Source: `client/adapters/copilot_headless.py:163-213`.

EMPIRICALLY_VERIFIED: A temporary workspace and a dummy file in its parent directory were created. Calling `_execute_tool('read_file', {'path': '../outside.txt'})` returned success. `_resolve_safe_path` resolves paths without verifying containment; both read and write tools use it. The shell tool sets a working directory but does not provide an OS sandbox.

HEURISTIC_HYPOTHESIS: Enforce containment after resolution for file tools, including absolute paths and links. Treat arbitrary shell execution as an explicit trusted capability; a working directory alone cannot confine it. Add negative tests for traversal, absolute paths, and links.

### 3. MCP authentication disagrees with REST authentication

Source: `server/main.py:64-96`; comparison: `server/core/auth.py:15-22`.

EMPIRICALLY_VERIFIED: A dummy ASGI handler received an anonymous HTTP request through `MCPAuthMiddleware` with an empty API key and `ALLOW_ANONYMOUS_DEV=False`. The middleware only checks credentials when a key exists. REST explicitly rejects the same configuration. Production startup requires a sufficiently long key, which mitigates the normal production path.

HEURISTIC_HYPOTHESIS: Share one authentication policy between REST and MCP. Verify that anonymous-disabled mode refuses requests on both transports. Docker Compose already binds its published backend port to loopback and requires a key; those are useful controls to preserve.

### 4. Dashboard readiness and busy state can be stale

Source: `tools/copilot_fleet.py:143-188`.

EMPIRICALLY_VERIFIED: Local status reports 27 ready accounts and one busy worker while all recorded heartbeats are from October 12 and no matching fleet runtime was detected on October 13. Readiness counts configured token presence. Heartbeats are returned but their age is not used to invalidate worker status.

HEURISTIC_HYPOTHESIS: Distinguish configured credentials, provider-verified credentials, and online workers. Report expired heartbeat state as stale/offline; preserve recorded credit usage independently of liveness.

### 5. Claimed file tasks without owner PID cannot be recovered by the scanner

Source: `tools/copilot_queue_worker.py:391-403`.

EMPIRICALLY_VERIFIED: Both existing claimed tasks were last updated October 9, have an `owner_account`, and have `owner_pid=null`. A temporary equivalent task remained claimed and produced no pending candidate after `find_pending_code_tasks()`. Recovery requires a truthy dead PID. The earlier status check looked for `assigned_to`, which is not the ownership field for this file queue; these tasks do have account ownership.

HEURISTIC_HYPOTHESIS: Define an expiry/recovery policy for missing PID and legacy tasks. Re-read and update under the claim lock so recovery cannot overwrite a concurrent claim. Specify a consistent lifecycle across the JSON queue and SQLite backend; SQLite supervision does not automatically repair the JSON task directory.

## Secondary observations

- EMPIRICALLY_VERIFIED: README advertises 332 tests; this checkout executes 335. README says operational state never triggers CI, but `.github/workflows/ci.yml` explicitly includes `orchestrator-state/**`.
- EMPIRICALLY_VERIFIED: The inspected pipeline engine advances through an ordered stage list. General fan-in/fan-out DAG guarantees were not established by this evaluation.
- EMPIRICALLY_VERIFIED: Hardware status combines detected device names with fixed CPU/platform/power specifications. Those fixed values are not live performance measurements.
- EMPIRICALLY_VERIFIED: The Graphify report is built from `f213b196`, while the inspected checkout is `1bc9f49`. Graph traversal was used for orientation and findings were checked against current source.
- EMPIRICALLY_VERIFIED: Tests changed two tracked cache files. Their contents were restored byte-for-byte from HEAD and checked for equality. Git still reports modification markers for those files despite no content diff; no synchronization or commit was performed.

## Falsifiable follow-up criteria

HEURISTIC_HYPOTHESIS:

1. A private-intent installation has verified matching repository visibility and explicit choices for external sync/tunneling.
2. Headless file tools reject access outside the configured workspace in deterministic negative tests.
3. REST and MCP reject unauthenticated requests whenever anonymous access is disabled.
4. Stale heartbeats never count as online/busy workers, even when credentials are configured.
5. Missing-PID claimed tasks expire safely, and concurrent recovery/claim tests prove no active claim is overwritten.
6. A finite end-to-end job is completed with bounded execution, expected checkpoints, and no stranded claims after worker restart.

Live provider canaries, benchmarks, remote CI, Git history scanning, and real workload dispatch were not executed. Passing the local suite does not establish these untested properties.
