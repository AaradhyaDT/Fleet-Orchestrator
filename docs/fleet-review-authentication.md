# Fleet authentication review

Reviewed the copied authentication candidate against Git HEAD and exercised the REST and mounted MCP ASGI paths with temporary database state.

## Findings

- The candidate closes an MCP bypass present at HEAD: the middleware previously skipped authentication when `API_AUTH_KEY` was empty, even when production or development settings disallowed anonymous access. REST and MCP now share the same API-key policy.
- The candidate aligns credential precedence between REST and MCP when both supported headers are present.
- Review found an additional header-ambiguity defect: REST resolves repeated auth headers to the first value, while the MCP middleware's dictionary conversion selected the last. The middleware now selects the first matching `Authorization` and `X-API-Key` value, consistent with REST. Regression tests cover both header orders for both header names.
- No provider identity verification is performed; these paths enforce the configured shared API key only.

## Files reviewed

- `server/main.py`
- `server/core/auth.py`
- `tests/test_auth_enforcement.py`
- `tests/test_security_config.py`
- `docs/fleet-review-authentication.md`

## Verification

- Initial candidate-focused tests: 11 passed.
- Duplicate-header regression test before the fix: 4 failed, reproducing the REST/MCP decision mismatch.
- Focused tests after the fix: 15 passed.
- Full configured test suite: 343 passed.
- Ruff on the four changed Python files: passed.
- `git diff --check`: passed.

The checks exercise the application and ASGI middleware directly; they do not model header normalization by external proxies or verify identity with an upstream provider. The full suite emitted one third-party `google.genai` deprecation warning.
