# Fleet telemetry review receipt

## Scope

Reviewed the copied candidate against Git HEAD in:

- `tools/copilot_fleet.py`
- `tests/test_copilot_fleet_dashboard.py`
- `tests/test_quota_reconciliation.py`

Only the listed source/test files and this receipt were changed. No provider
credential verification is inferred from token presence; telemetry reports
`credential_verification: "unknown"`. No MCP/REST call, claim lock, PID
recovery, or completion fencing path exists in this dashboard surface, so those
behaviors were not changed.

## Findings and fix

The candidate accepted negative, NaN, and infinite `credits_used` values,
which could inflate remaining quota or poison aggregate burn-rate telemetry.
`get_fleet_quota_metrics` now accepts only finite non-negative values and treats
other values as zero. Regression coverage was added for negative, non-numeric,
NaN, and infinite values. Existing stale, missing, and malformed heartbeat
tests preserve usage while reporting workers offline.

The baseline intentionally reports persisted cooldown state even without a
heartbeat; that behavior was retained rather than weakening existing tests.

## Verification

- Before patch: targeted candidate tests `19 passed`; direct repro showed
  `credits_used=-5.0`, `remaining=205.0`.
- After patch: targeted tests `23 passed`; full suite `346 passed`.
- `python -m compileall` passed.
- Ruff passed for all changed Python files.
- `git diff --check` passed.

Limitations: tests use temporary state and mocked account discovery/providers;
no live provider authentication or multi-process OS-lock behavior was
exercised because those paths are outside the allowed telemetry scope.
