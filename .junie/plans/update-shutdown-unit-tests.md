---
sessionId: session-260923-130344-19jc
---

# Assessment

### Confirmed cause
`PyTrain.__init__()` now creates `_shutdown_lock` (`src/pytrain/cli/pytrain.py:170`), and `shutdown_cache()` acquires it before checking the manager (`:1164`). The shared `bare_pytrain` fixture constructs instances with `PyTrain.__new__()` (`tests/cli/conftest.py:54`), bypassing initialization. Neither derived fixture supplies the lock.

The latest available review reported **87 passed and 11 failed** in the two affected test files. Current source inspection confirms the same fixture mismatch:

| Test in `tests/cli/` | Affected cases |
|---|---:|
| `test_cache_sync_service.py::test_shutdown_cache_preserves_service_and_is_idempotent` | 2 |
| `test_cache_sync_service.py::test_shutdown_cache_retains_manager_on_failure_then_retries` | 1 |
| `test_pytrain_runtime.py::test_shutdown_real_helpers_isolate_failures_and_retry` | 6 |
| `test_pytrain_runtime.py::test_runtime_finalization_repeats_helpers_without_repeating_successful_cleanup` | 2 |

Direct helper/finalization calls raise `AttributeError`. Calls through `shutdown()` catch that error, producing an unexpected warning and missing cache-stop calls instead. These are setup failures, not reasons to weaken call-order or retry assertions.

### Scope
- Repair fixtures in the two test files; retain the already implemented helper, orchestration, and finalization coverage.
- Rename the unexpected-runtime-error test to reflect cleanup of both resources.
- Leave production files, including the user's concurrent edits, unchanged. Keep `tests/cli/conftest.py` unchanged; no broad fixture refactor, concurrency stress tests, or unrelated production cleanup.

Only this plan is being revised. No production/test files were changed and no tests were rerun during this assessment; the reported results above come from the prior review.

# Technical Design

### Fixture repair
- In `tests/cli/test_cache_sync_service.py::cache_service`, import `threading` and set `p._shutdown_lock = threading.Lock()` alongside the other instance state.
- In `tests/cli/test_pytrain_runtime.py::runtime`, initialize the same field using its existing `threading` import.
- Create a fresh real lock per fixture invocation, including no-manager cases. Do not use a shared lock, invoke the real constructor, remove production locking, or mock away the real helper in lifecycle tests.
- Keep initialization local to the fixtures that need it. This follows the constructor-bypass pattern in `tests/cli/test_pytrain_service_discovery.py::_pytrain`, which explicitly supplies its real `Event` dependency.

### Preserve and strengthen existing coverage
- Keep patching `module.CacheSyncManager.stop` as a class method, with real helpers restored/bound where already used. Networking, threads, GPIO, and process operations remain mocked.
- Preserve cache-helper success, absence, repeated-call, exception-identity, retained-manager, retry, and zeroconf-independence assertions. Add explicit unlocked-state assertions after direct helper calls, especially after the expected exception and before retry, to verify lock release without adding threads.
- Preserve service-before-cache ordering, distinct subsystem warnings, failure isolation within `shutdown()`, downstream disconnect/reset calls, and API queue accounting.
- Preserve duplicate-safe cleanup across `shutdown()` and `run()` finalization, including successful retry after transient cache-stop failure without repeated zeroconf cleanup.
- Rename `test_unexpected_runtime_errors_still_close_service` to `test_unexpected_runtime_errors_still_close_service_and_cache`; retain its existing exception-identity, cleanup-order, and `task_done()` assertions.

No new architecture or production interfaces are required. `run()` still has sequential, unguarded cleanup in `finally`; do not assert unconditional failure isolation there or expand this repair into production hardening.

# Validation

### Implementation checks
After the fixture repairs, run the targeted tests without weakening or skipping failing cases:

```bash
../bin/python -m pytest tests/cli/test_pytrain_runtime.py tests/cli/test_cache_sync_service.py
```

Check formatting for the changed Python files:

```bash
../bin/python -m ruff format --check tests/cli/test_pytrain_runtime.py tests/cli/test_cache_sync_service.py
```

If needed, run `../bin/python -m ruff format` with those two paths and repeat the check. Finally run the required complete suite:

```bash
../bin/python -m pytest
```

Allow 60 seconds for focused tests/formatting and 120 seconds for the full suite, based on prior runs. Success requires all 11 previously failing cases to pass, the lock to be released after helper success/no-op/failure, unchanged lifecycle guarantees, and a passing full suite. Report any additional failures separately rather than changing unrelated production behavior.

# Delivery Steps

### * Step 1: Repair direct cache-helper fixture and lock-release coverage
Direct cache-helper tests execute the locked production helper with valid fixture state.

- Add a `threading` import and a fresh `_shutdown_lock` to `cache_service` in `tests/cli/test_cache_sync_service.py`.
- Extend the existing idempotence and retry tests with unlocked-state assertions after success, no-manager calls, and the expected exception before retry.
- Retain exact stop-call counts, exception identity, manager retention/clearing, and untouched zeroconf resources.
- Run the file's tests and required format check; format and recheck if necessary.

### ✓ Step 2: Repair runtime lifecycle fixture and preserve finalization coverage
Orchestration and finalization tests run real cache cleanup without fixture-induced errors.

- Initialize a fresh `_shutdown_lock` in `runtime` in `tests/cli/test_pytrain_runtime.py`, keeping ordinary helper mocks and focused real-method bindings intact.
- Rename the unexpected-runtime-error test to include both service and cache cleanup without changing its assertions.
- Keep the existing failure matrices, warning attribution, cleanup order, retry/idempotence, deferred-action, and API accounting checks.
- Run both affected test files, check formatting on both files, and run the complete suite with `../bin/python -m pytest`; report actual results and any remaining failures.