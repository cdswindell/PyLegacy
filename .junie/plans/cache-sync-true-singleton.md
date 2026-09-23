---
sessionId: session-260923-133427-1hck
---

# Requirements

### Updated cache shutdown policy
Cache ownership belongs exclusively to `PyTrain`; `PyTrainApi` does not create an independent cache server. The user's clarification supersedes the previous requirement to block API handoff when cache cleanup is incomplete: ordinary cache-stop failures should be logged without preventing the remaining PyTrain shutdown or API notification.

The current follow-up is **test and test-documentation changes** for the user's production warning change. `src/pytrain/cli/pytrain.py:673` already logs `Cache sync cleanup is incomplete` in `PyTrain.__call__()`. Do not overwrite the user's production edits or change the external API checkout.

### Acceptance criteria for the callback change
- An ordinary cache-stop error produces warning diagnostics, but the accepted API callback continues through status publication and exactly one host notification in both server and client roles.
- Other shutdown work still runs. The selected admin action remains unchanged and its `exit_status` is visible before the mocked `SIGINT` send.
- Failed cache cleanup retains the same manager for an explicit retry; notification does not imply that cache resources were successfully released. Retrying cleanup or receiving late callbacks must not produce another notification or host action.
- A genuine `KeyboardInterrupt` remains cancellation, not an ordinary cache error; retain propagation and no-notification coverage for that path.
- Existing no-error shutdown, duplicate suppression, update/relaunch mappings, and low-level cache ownership protections remain intact.

### Remaining queued-exit gap
The callback edit does not yet satisfy the broader warning-only goal for all exit paths. `PyTrain.run()` still calls `shutdown_cache()` unguarded at line 425 and raises for retained ownership at lines 426–427. Replacing that explicit raise alone would still allow an ordinary cache-stop exception to escape final cleanup.

This test-only follow-up must report that gap, not silently change production behavior or weaken current queued-path assertions. Completing warning-only queued exits requires a corresponding production adjustment at the final-cleanup boundary, followed by updating the affected runtime tests. Until then, do not claim cache failures are nonfatal for every exit route.

### Preserved prior work and scope
The original issue was a shutdown race, not evidence of duplicate cache managers. Keep the implemented first-exit guard, late-echo suppression, deferred-action ordering, one-shot API notification, retryable cache ownership, and isolated receiver tests. Constructor-level singleton hardening remains deferred.

Previous implementation validation recorded **7,333 passing tests**, including **34 opt-in integration cases**; that predates the current warning change and is not validation of this revision.

Leave `tests/requirements.txt`, production dependencies, and the external API checkout unchanged. Integration tests remain opt-in through `PYTRAIN_API_CHECKOUT`, use an existing local checkout, and never clone, fetch, pull, install dependencies, or start API children in a normal unit-test run.

# Technical Design

### Callback unit tests
In `tests/cli/test_pytrain_admin.py`, replace the combined `test_api_callback_cache_failure_blocks_handoff_and_allows_retry` expectations with separate ordinary-failure and interruption scenarios. Reuse the existing server/client `admin` fixture, real `PyTrain.shutdown()` and `shutdown_cache()`, mocked resource boundaries, and controlled `CacheSyncManager.stop()` failure followed by success.

- For `RuntimeError`, expect the callback to return normally. Capture the `WARNING` record containing `Cache sync cleanup is incomplete` with `caplog`; allow the existing detailed warning from `shutdown()` as well.
- Check API queue disposal, remaining component cleanup, client disconnect when applicable, unchanged selected action, and retained manager identity. Use a mocked `os.kill` side effect to assert the expected `exit_status` and `_api_exit_notified` before the signal is recorded.
- Cover UPDATE plus inexpensive RESTART and QUIT cases in the unit test, with the corresponding status for each action. Require exactly one signal throughout callback completion, duplicate/late requests, and explicit successful cache retry.
- Keep the `KeyboardInterrupt` case separate: the interrupt propagates before notification, the manager and selected action remain available for retry, and no success status is published. Do not change genuine cancellation into warning-only behavior.
- Keep successful-cleanup tests and low-level ownership/error tests in `tests/cli/test_cache_sync_service.py` and `tests/db/test_cache_sync.py`; the warning changes high-level exit policy, not whether a failed `stop()` actually released resources.

### Existing API receiver integration
Update the two existing server/client cache-failure cases in `tests/integration/test_pytrain_api_exit.py` and `tests/integration/_pytrain_api_exit_child.py`; do not add a new integration subsystem or routinely expand the slow matrix.

- Replace the expected callback `RuntimeError` and early failure return with normal status publication and recorded host dispatch. Capture the incomplete-cleanup warning in the child.
- In `notify()`, allow the original retained manager only for the injected cache-failure scenario; keep the no-manager assertion for successful-cleanup cases. Preserve assertions for queue disposal, other cleanup, selected status, and one notification.
- Let the real `PyTrainApi` receiver consume UPDATE and follow the existing recorded update/relaunch path. Adjust `Relaunched` sentinel handling so this scenario is a terminal successful handoff, not a blocked exit. Keep destructive operations stubbed.
- After the controlled terminal boundary, verify the same retained manager can be explicitly cleaned up. Assert that late echoes and retry add neither host actions nor notifications and do not change the published status.
- Keep canonical import/enum identity checks, subprocess timeouts, the existing success action matrix, and real Uvicorn signal tests unchanged. No separate API cache is introduced or simulated.
- Update `tests/integration/README.md` to describe warning-and-continue with retained ownership, replacing the obsolete claim that a cache error blocks status publication and host action. Distinguish this callback coverage from the remaining queued-exit limitation.

### Runtime tests and unchanged behavior
`tests/cli/test_pytrain_runtime.py` currently includes `test_failed_cache_stop_blocks_update_until_retry_finishes`, `test_escaping_cleanup_error_never_dispatches_action`, and `test_queued_api_exit_skips_notification_when_cleanup_escapes`. These describe the still-blocking queued implementation, not the edited callback. Do not blindly invert all error assertions or remove cancellation/non-cache error coverage to accommodate a callback-only change. Any subsequent user edit to `run()` requires targeted changes for ordinary cache errors while preserving escaping non-cache errors, deferred-action failures, and genuine interrupts.

The existing first-request guard, `exit_status`/`SIGINT` contract, and API update ownership are unchanged. No production source changes are part of these delivery steps.

# Validation

### Regression checks
- Run the focused callback/admin tests: ordinary failure warns and notifies once; successful cleanup still works; interruption propagates; retry and echoes do not notify again.
- Retain runtime, update-method, and low-level cache tests to detect unintended changes outside the callback policy.
- Run the revised receiver cases using the existing local API checkout, then the existing integration group to check shared harness assertions and real-signal coverage. No live updates, networking, hardware, or host relaunches are permitted.
- With `PYTRAIN_API_CHECKOUT` unset, verify the integration group still skips before API imports or child startup. Do not add default-suite dependency probes or downloads.

### Required implementation commands
Consult the Python environment tooling before running Python commands. After Python edits, run `../bin/python -m ruff format --check <changed Python files>`; if needed, format those files and repeat the check. Run all unit tests with `../bin/python -m pytest`.

For the separate opt-in receiver run, use the existing checkout and interpreter:

```sh
PYTRAIN_API_CHECKOUT=/Users/davids/Documents/dev/PyTrainApiEnv/PyTrainApi \
PYTRAIN_API_PYTHON=/Users/davids/Documents/dev/PyTrainApiEnv/bin/python \
../bin/python -m pytest tests/integration/test_pytrain_api_exit.py
```

Report newly executed tests separately from skips and prior results. This planning revision edits only this plan file; it does not change Python files or run tests.

# Delivery Steps

### ✓ Step 1: Encode warning-only callback shutdown in unit tests
Server/client callback tests verify continued API notification after an ordinary cache failure without losing cancellation or retry coverage.
- Split the ordinary-failure and `KeyboardInterrupt` expectations in `tests/cli/test_pytrain_admin.py`, retaining real shutdown/cache-wrapper behavior.
- Assert warning severity/message, remaining cleanup, retained manager identity, and status-before-signal ordering for UPDATE, RESTART, and QUIT.
- Verify duplicate/late callbacks and explicit cache retry preserve the selected status and exactly one notification.
- Preserve existing low-level ownership and queued-path regressions; report the remaining queued production gap rather than changing source or concealing it.
- Run focused admin/cache tests and the required formatting check for changed Python files.

### ✓ Step 2: Align the opt-in API receiver harness with continued handoff
The existing cache-failure integration cases verify real API status dispatch despite a retained PyTrain cache manager.
- Update `tests/integration/test_pytrain_api_exit.py` and `_pytrain_api_exit_child.py` to expect the warning, one notification, normal recorded UPDATE/relaunch, and same-manager retry without another host action.
- Adjust only scenario-specific ownership and terminal-sentinel assertions; retain strict successful-cleanup checks, canonical imports, bounded child execution, and safe external-operation stubs.
- Revise `tests/integration/README.md` to distinguish best-effort callback shutdown from the remaining queued-exit limitation and keep opt-in instructions intact.
- Run the separate local-checkout integration group, verify opt-out skipping, run Ruff formatting checks, and run the complete normal unit suite with `../bin/python -m pytest`.
- Leave production files, API sources, requirements, and normal-test startup costs unchanged.