# Fleet background bridge and self-repair experiment

Related: [[Fleet-Orchestrator]], [[Worker Session Runtime]], [[Background Jobs]].

## Scope and execution

EMPIRICALLY_VERIFIED: Fleet Copilot CLI workers implemented the local background
bridge, four repairs, and independent review refinements. Codex supplied bounded
specifications, reviewed and integrated patches, updated the obsolete locking
fixture, and made small bridge configuration/finalization follow-ups. No commits,
pushes, merges, synchronization, hosting, or separate artifact uploads occurred.
Repository privacy was accepted from the maintainer's confirmation.

The resumed run started at 2026-10-13 14:04:27 UTC with a hard deadline of
15:34:27 UTC. Four isolated implementation jobs and four independent review jobs
used disjoint file scopes and exclusive accounts after authorization to expand
concurrency. The default bridge limit remains three; this run used four. Provider
selection was automatic intelligence throughout. Reported models were
`gpt-6-luna`; configured credentials were never treated as proof of paid capacity.

## Verified outcomes

EMPIRICALLY_VERIFIED:

- `fleet.bat job start/status/list/cancel/result/resume` uses durable ignored
  state, retained worktrees, atomic writes, OS locks, immutable job specifications,
  verified process identities, separate verification status, and explicit retries.
  Mock-provider regression coverage includes timeout, cancellation, interrupted
  controllers, stale heartbeat reporting, artifact retention, and result isolation.
- File tools reject traversal, outside absolute paths, and escaping symlinks.
  Shell execution is trusted execution with the current user's permissions;
  worktree containment is not an OS sandbox.
- REST and MCP share the configured authentication policy, including disabled
  anonymous access and repeated credential-header precedence.
- Dashboard telemetry distinguishes configured and online accounts. Missing,
  stale, future, malformed, and timezone-free heartbeats cannot report an online
  or busy worker. Invalid credit values cannot inflate or poison quota totals.
- Missing-PID claims expire after their timeout and grace period. Claim recovery,
  checkpoints, and completion use locks and ownership fencing. Tests cover stale
  writes, concurrent recovery, PID reuse, unsafe lock paths, symlinked locks, and
  non-finite legacy timeouts.

Regression evidence was obtained against original source before acceptance.
The independent baseline checkout reproduced six failures and one passing control
for workspace escape, anonymous MCP access, and missing-PID recovery. Fleet
reported seven telemetry regressions failing before its fix; independent review
added reproducing authentication, quota, and claim edge-case tests. Receipts are
in `fleet-review-workspace.md`, `fleet-review-authentication.md`,
`fleet-review-telemetry.md`, and `fleet-review-claim-recovery.md`.

Final combined validation in `.worktrees/fleet-validation` passed **425 tests**
in 73.97 seconds, Ruff, all three schema validation suites, and `git diff --check`.
The complete snapshot included concurrent local provider changes; those changes
were not authored by this repair run. A subsequent redaction-fixture expression
change preserves its synthetic credential behavior and was checked separately.
Secret scanning covers tracked and new source/document files with credential
snippets suppressed. Tracked caches changed by isolated tests are restored within
the validation checkout; concurrent root cache changes are preserved.

Two bounded live jobs completed with verification passed and retained patches:
`job-c82e656611a948c1b2bd037752042d5f` and
`job-43ff3fcf643346e99181a047825d0ae0`. Each wrote only its allowed smoke marker,
passed its configured assertion, and reported automatic `gpt-6-luna` usage.

The local AST knowledge graph was refreshed without LLM inference or uploads.

## Retained failures and limits

EMPIRICALLY_VERIFIED: Some implementation/review controllers failed Git metadata
finalization; one reviewer was rejected for test-generated cache changes outside
its allowed scope. Their original failed/interrupted states remain unchanged.
Lead acceptance is supported by retained patches, independent review, and the
combined suite; it does not relabel those jobs as successful.

The bridge now retries bounded read-only Git inspection and records its redacted
diagnostic. If patch capture still fails, terminal state and scoped recovery file
contents are preserved with `artifact_error`; verification fails. This behavior
has an injected-failure regression test. Such recovery contents are incomplete
patch evidence and require review of the retained worktree before integration.

HEURISTIC_HYPOTHESIS: The cause of the earlier Git inspection failures remains
unconfirmed. The second live smoke passed after bounded Git inspection was added;
that result does not prove the intermittent failure cannot recur. No native Codex
task-card integration or dashboard was implemented, as specified.

Exact implementation/reviewer IDs and the deadline remain in ignored
`orchestrator-state/logs/resumed-run.json`; job artifacts are under
`orchestrator-state/jobs/`. Worktrees and partial results remain resumable where
their original deadline and retry allowance permit. No automatic resubmission
occurs. The completion heartbeat is disabled when this run ends.
