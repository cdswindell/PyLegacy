---
sessionId: session-260923-133427-1hck
---

# Requirements

### Best-effort shutdown on every exit path
An ordinary cache shutdown failure must not prevent PyTrain or its API host from exiting. Preserve the user's `Cache sync cleanup is incomplete` warnings in both `PyTrain.run()` and `PyTrain.__call__()`. This revision supersedes the previous callback-only scope and closes the remaining final-cleanup exception path rather than merely weakening tests.

- Cover local/interactive, headless, queued API, and callback-driven exits in server and client roles.
- Attempt remaining subsystem cleanup, then allow the selected deferred action or API handoff despite incomplete cache cleanup. Publish the selected `exit_status` before exactly one host notification.
- Retain failed cache ownership for an explicit retry; never pretend cleanup succeeded, clear ownership prematurely, or allow retry/late callbacks to repeat the exit action or notification.
- Treat ordinary subsystem exceptions as warning-and-continue. Preserve genuine `KeyboardInterrupt`/`SystemExit` cancellation and unrelated runtime or deferred-action errors; do not catch `BaseException` or report a failed update as successful.
- Add a durable project rule: **Subsystem shutdown must be best effort and must never impede PyTrain shutdown or PyTrainApi handoff; log ordinary cleanup failures and continue remaining teardown.**

### Scope and preserved behavior
Use the existing per-subsystem exception handling in `PyTrain.shutdown()` as the pattern. The only behavioral source adjustment is at the final-cleanup boundary in `src/pytrain/cli/pytrain.py`; document the policy and align lightweight unit tests.

Preserve the first-exit guard, late-echo suppression, deferred actions outside `finally`, API update ownership, retryable cache lifecycle, and successful-cleanup behavior. Cache ownership remains exclusively in PyTrain. Do not redesign singleton construction, cache workers, signal handling, or shutdown timeouts, and do not add unbounded cleanup retries.

Leave the external API checkout, dependencies, and `tests/requirements.txt` unchanged. Existing API integration tests remain opt-in, use an existing checkout, and never download code or launch children during a normal unit-test run. No new integration subprocess matrix is needed for this follow-up.

# Technical Design

### Current implementation and remaining gap
- `src/pytrain/cli/pytrain.py:425–427`: `run()` now warns when ownership remains, but the preceding `shutdown_cache()` call can still raise before reaching that warning. The preceding `shutdown_service()` is also unguarded.
- `PyTrain.shutdown()` already isolates ordinary subsystem exceptions with individual `try`/`except Exception` blocks and warning logs, then proceeds to queue disposal, disconnect, and component cleanup.
- `shutdown_cache()` deliberately clears `_cache_sync_manager` only after `CacheSyncManager.stop()` succeeds. Keep this strict low-level contract and its retry/lock-release tests unchanged.
- Existing callback warning tests in `tests/cli/test_pytrain_admin.py` already cover status-before-notification, retained ownership, late callbacks, and genuine interruption. Reuse their assertions rather than rebuilding the test harness.

### Close the final-cleanup gap locally
In `PyTrain.run()`, protect final `shutdown_service()` and `shutdown_cache()` calls independently using the same `except Exception` and subsystem-specific warning messages as `shutdown()`. A service failure must not skip cache cleanup, and a cache failure must not skip the closing log, selected deferred action, or API notification.

Preserve the user's incomplete-cleanup warning and deferred dispatch after the `finally` block. Do not wrap the whole run loop or deferred actions in a catch-all, and do not move action dispatch back into `finally`. An original runtime error must remain the propagated error even when final cache cleanup also fails.

Do not change the exception behavior of direct `shutdown_cache()` or `CacheSyncManager.stop()` calls. Failure remains observable to explicit cleanup callers; only application-exit orchestration is best effort. Preserve both manager references on failure and clear them only through successful cleanup.

### Document the invariant
- Add the subsystem-shutdown rule to root `AGENTS.md`, including the distinction between ordinary cleanup failures and genuine process cancellation.
- Add a brief `PyTrain.shutdown()` docstring and final-cleanup comment explaining best-effort teardown and why retained ownership must not gate application exit.
- Correct `_notify_api_exit()`'s obsolete docstring: notification follows attempted teardown and any applicable deferred action, not necessarily successful cache release.
- Update `tests/integration/README.md` to remove the queued-exit blocking limitation. State accurately that queued failure coverage is in fast unit tests; the existing integration failure cases remain callback-specific, while successful queued handoff and real-signal coverage are unchanged.

### Targeted runtime test changes
Use `runtime`, `real_exit_runtime`, and `_wire_api_deferred_methods` in `tests/cli/test_pytrain_runtime.py`, with real shutdown wrappers and mocked resource boundaries where ownership matters.

- Replace `test_failed_cache_stop_blocks_update_until_retry_finishes` with warning-and-continue coverage for persistent cache-stop errors. Verify downstream cleanup and the selected action occur before any successful explicit cache retry.
- Add the distinct retained-manager/no-exception scenario that directly exercises the user's changed warning. Assert warning severity/message and continued exit without clearing ownership artificially.
- Split `test_escaping_cleanup_error_never_dispatches_action` and `test_queued_api_exit_skips_notification_when_cleanup_escapes`: ordinary final service/cache exceptions now continue; genuine interrupts, unrelated escaping errors, and deferred-action failures retain their existing no-action/no-notification expectations.
- Extend queued API tests across server/client roles and the existing exit-action mappings. Inside mocked signal delivery, verify the selected status is already published, other cleanup was attempted, and only the failed manager remains retained. Retry and late echoes must not add notifications or actions.
- Exercise interactive/headless termination and standalone callback-driven shutdown through the same real final-cleanup boundary. Reuse existing role/mode fixtures and keep all external effects mocked.
- Preserve transient-failure-then-success cleanup coverage, successful-cleanup ordering, callback warning tests, genuine interrupt propagation, and low-level cache ownership tests. Add a paired runtime-error/cache-error regression proving cleanup does not mask the original error.

# Validation

### Fast regression coverage
- Check ordinary cache failures, retained-manager warnings, transient retries, and simultaneous service/cache failures without real networking, cache threads, updates, or signals.
- Verify all exit routes continue appropriately, selected actions/status remain stable, and notification occurs once even if ownership is retained.
- Confirm genuine cleanup interrupts and unrelated runtime/update failures still propagate without a false successful action or host notification.
- Run focused runtime/admin/update/cache tests, followed by the full normal unit suite. Keep API integration skipped by default; do not add dependencies, checkout operations, or child-process tests to the ordinary suite.

### Implementation checks
Consult the Python environment tooling before running Python commands. After editing Python files, run `../bin/python -m ruff format --check <changed Python files>`; if necessary, format those files and repeat the check. Run all unit tests with `../bin/python -m pytest`.

For a separate regression check of the existing opt-in receiver group, reuse the supplied checkout without installing anything:

```sh
PYTRAIN_API_CHECKOUT=/Users/davids/Documents/dev/PyTrainApiEnv/PyTrainApi \
PYTRAIN_API_PYTHON=/Users/davids/Documents/dev/PyTrainApiEnv/bin/python \
../bin/python -m pytest tests/integration/test_pytrain_api_exit.py
```

Do not expand the integration matrix. Report new validation separately from prior results and skips. This planning revision modifies only the plan file; no tests have been rerun or source files changed.

# Delivery Steps

### ✓ Step 1: Make final subsystem cleanup best effort and document the rule
Ordinary final service/cache cleanup exceptions no longer prevent PyTrain exit or its selected action.
- In `src/pytrain/cli/pytrain.py`, independently guard final service and cache cleanup using the existing `shutdown()` warning-and-continue pattern; preserve the user's warnings and dispatch outside `finally`.
- Keep `shutdown_cache()` and cache-manager ownership/error contracts unchanged.
- Add the shutdown policy to `AGENTS.md` and clarify the `shutdown()`/`_notify_api_exit()` documentation and final-cleanup comment.
- Revise runtime tests for persistent cache errors, retained ownership without an exception, and independent service/cache failures; preserve transient retry behavior.
- Check that ordinary cache errors do not mask an original runtime error, while genuine interrupts still propagate. Run focused tests and formatting checks.

### ✓ Step 2: Align exit-route and API handoff regressions with warning-only cleanup
Fast unit tests verify continued exit and exactly-once API handoff across roles and routes despite cache failure.
- Update the affected exception matrices and extend existing fixtures in `tests/cli/test_pytrain_runtime.py` for standalone, headless, callback-driven, and queued API exits.
- Verify selected status before notification, continued remaining cleanup, retained-manager retry, and suppression of late echoes and duplicate actions; keep existing callback, low-level ownership, and deferred-action-failure tests intact.
- Revise `tests/integration/README.md` to remove the obsolete queued-exit gap and distinguish unit failure coverage from unchanged opt-in receiver coverage.
- Run Ruff formatting checks, the full normal unit suite, and the existing receiver group separately with the supplied local checkout. Confirm default integration skips remain lightweight.
- Leave API sources, dependencies, requirements, and the integration case matrix unchanged.