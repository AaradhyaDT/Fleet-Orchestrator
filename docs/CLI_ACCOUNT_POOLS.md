# CLI accounts and Windows process diagnostics

## Supported isolation

Codex profiles use a separate `CODEX_HOME` and file credential store. OpenCode profiles use separate XDG data, configuration, cache and state roots, including its native authentication data. Fleet removes inherited provider authentication overrides when launching a managed profile. Credentials stay in the native CLI store under `%USERPROFILE%\.fleet-orchestrator\profiles`; SQLite stores metadata and leases, not tokens. `FLEET_ACCOUNTS_HOME` overrides this root but cannot point inside this repository.

Sources: [Codex authentication](https://learn.chatgpt.com/docs/auth), [OpenCode configuration](https://dev.opencode.ai/docs/config/), [OpenCode directories](https://github.com/anomalyco/opencode/blob/dev/packages/core/src/global.ts).

AGY pooling is **unavailable**. Its OS keyring authentication has no verified per-profile namespace. Changing `AgyHome` alone does not establish credential isolation. The installed CLI starts authorization through normal launch, and Fleet does not invent an `agy login` command. Managed AGY login, verification and logout are blocked to protect the existing identity. Legacy AGY workers remain usable. Two-profile sign-in, refresh and logout isolation has not been demonstrated; separate Windows-user execution needs a later decision. See [AGY installation/authentication](https://www.antigravity.google/docs/cli/install/) and [upstream profile request](https://github.com/google-antigravity/antigravity-cli/issues/381).

## Enroll and authorize

Run from the Fleet repository in an interactive terminal:

```bat
fleet.bat accounts add --id plus-codex --provider codex_cli --pool plus --account-group my-plus
fleet.bat accounts login --id plus-codex
fleet.bat accounts verify --id plus-codex --identity-confirmed
fleet.bat accounts add --id plus-opencode --provider opencode_cli --pool plus --account-group my-plus
fleet.bat accounts login --id plus-opencode
fleet.bat accounts verify --id plus-opencode --canary --identity-confirmed
fleet.bat accounts status --json
```

The human completes native authorization and confirms the intended account. For OpenCode, choose the ChatGPT Plus/Pro authentication method offered by its native flow. Codex also supports `login --id plus-codex --device-auth`. `login --new-window` deliberately opens a usable console and retains it on error. No existing credentials are copied. Repeat enrollment for additional authorized accounts; these examples do not assume two subscriptions exist.

`--identity-confirmed` records human confirmation, not an independently measured email address. Codex `login status` establishes cached native login. OpenCode `auth list` establishes configured credentials; an explicit `verify --canary` is required before marking it ready. Canaries submit a small model prompt in a temporary workspace and can consume provider usage. Ordinary status checks only probe executable availability and display cached verification, leases and cooldowns. They do not submit prompts or prove that cached credentials remain valid remotely. Unknown quota remaining is `null`.

Other commands: `enable --id ID`, `disable --id ID`, `logout --id ID`. Logout requires an exclusive management lease and uses the native isolated environment. Cancelled login leaves the profile unverified. Administrative Codex policy can override file storage or authentication choices; a failed native login must be resolved before using that profile.

## Bind workers

Add exactly one of `AuthProfile` or `AccountPool` to an existing fleet entry:

```json
{"Account":"codex-worker","Provider":"codex_cli","AuthProfile":"plus-codex"}
```

```json
{"Account":"opencode-worker","Provider":"opencode_cli","AccountPool":"plus"}
```

Retain each adapter's task worktree setting. `Account` remains the worker ID. Legacy entries using `CodexHome` or `AgyHome` keep their existing behavior; combining a managed profile with a legacy home is rejected. Copilot and Gemini flows are unchanged.

Selection uses persistent round robin and transactional SQLite leases. Only enabled, ready profiles whose cooldown has elapsed are eligible. One executing task owns a credential profile. An account group is descriptive metadata: Codex and OpenCode may run concurrently on the same underlying Plus account, as requested. A running session never changes identity and a failed mutating prompt is never silently replayed under another profile.

Authentication errors require re-login. Rate limits start at 60 seconds and double up to 15 minutes unless an explicit provider retry interval is reported. Quota exhaustion without a reported reset requires explicit canary verification before reuse. CLI paths do not inherit Claude's five-hour cooldown assumption. Process and timeout failures remain task errors. After execution starts, failures block the task for inspection and save redacted partial outcomes under `task-attempts`; inspect the retained workspace before deliberately retrying. Dead-owner leases recover on restart; a recorded live CLI child prevents premature reuse. Lease heartbeat expiry alone does not revoke a live process.

## Windows flashing investigation

The original trigger is uncertain: task execution or polling. Inspection found missing window suppression in CLI probes/execution, background Git/verification commands, and the completion-notification PowerShell process. The background job launcher also combined `DETACHED_PROCESS` with `CREATE_NO_WINDOW`, a combination where Windows ignores the latter. These are plausible causes, not a reproduced attribution. [Microsoft process flags](https://learn.microsoft.com/en-us/windows/desktop/ProcThread/process-creation-flags).

Fleet-owned launches on these paths now share `CREATE_NO_WINDOW` and hidden startup options. OpenCode prefers its installed native executable over npm/PowerShell shims. Interactive login deliberately inherits a terminal or requests a new console. Output capture and tracked timeout/cancellation cleanup remain enabled.

To record sanitized executable, launch site, parent/child identifiers where available, time and exit status while observing the usual workload:

```powershell
$env:FLEET_PROCESS_TRACE = "$env:USERPROFILE\.fleet-orchestrator\diagnostics\processes.jsonl"
# Start the normal Fleet workload from this terminal; observe startup, polling,
# task execution, verification and shutdown separately.
python -m tools.fleet_process_diagnostics --output "$env:USERPROFILE\.fleet-orchestrator\diagnostics\window-launch.json"
```

Trace records omit arguments, environment and raw provider stderr. Synchronous probes do not expose a child PID; asynchronous launches and background controllers do. The diagnostic uses harmless processes, native help/version probes and Git; it does not authorize accounts or submit model prompts.

Controlled Windows checks demonstrated a background child without a console, timeout reaping, persistence after the submitting parent exited, and explicit interactive console allocation. The original flash did not reproduce in this host, even with an unsuppressed comparison child. Desktop visibility, a full live model task, and CLI-created descendants remain unverified. Hiding Fleet's CLI parent does not prove that provider-created tools stay hidden. Real two-account sign-in/refresh/logout checks also remain unverified until the human enrolls those accounts; automated pool and isolation tests use simulated identities.

## Implementation verification (2026-10-13)

- `python -m pytest tests/ -q`: 442 passed; one existing Google GenAI/Python deprecation warning.
- `python -m ruff check client tools tests server`: passed.
- `git diff --check`: passed.
- Native AGY help, Codex version, OpenCode version and Git verification probes: exit code zero.
- Account status JSON command: passed with an empty enrolled-profile list. No live accounts were added or authorized by implementation checks.
- Controlled Windows launch, timeout and persistence matrix: passed; results under `%USERPROFILE%\.fleet-orchestrator\diagnostics\window-launch.json`. This does not establish that the reported flashing problem is resolved on the real workload.
