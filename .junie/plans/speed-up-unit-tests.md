---
sessionId: session-260922-150651-15nh
---

# Requirements

### Goal
Reduce the full suite’s reported ~15-second runtime without dropping tests, weakening assertions, or changing production behavior.

- Keep the normal `../bin/python -m pytest` workflow.
- Preserve test isolation and genuine concurrency checks.
- Treat `component_state.py` and the user's ongoing edits as out of scope: do not review its modifications, edit, revert, or format it.
- Prefer localized test improvements; do not add parallel execution dependencies or disable coverage/plugins to manufacture a speedup.
- Measure before and after on this computer. The current bottlenecks and achievable savings are not yet established; no files have been changed or tests run during planning.

# Technical Design

### Findings
- `tests/test_base.py::wait_until` already supports early completion; `tests/db/test_state_watcher.py` demonstrates event-based waits and explicit shutdown checks.
- Package fixtures in `tests/{comm,db,pdi}/conftest.py` already isolate network discovery and serial hardware.
- `tests/gui/test_controller_view.py` repeatedly reads and parses the same source in `_calls_to`, `_pack_calls_on`, `_box_call_for`, and `_grid_configure_calls_on`. `tests/gui/test_lcs_imports.py` similarly reparses each module across parametrized checks.
- `tests/pdi/test_base3_buffer.py` uses fixed sleeps even though `_CapturingBuffer.send` captures synchronously. Its keepalive test patches the shared `time.sleep`, potentially affecting unrelated threads.
- Two threaded tests in `tests/db/test_startup_state.py` each sleep before inspecting initialization.

### Changes
1. Measure collection and setup/call/teardown durations before editing; prioritize candidates that contribute measurable overhead.
2. Reuse read-only, module-scoped source/AST analysis in the two GUI test files. Retain every existing assertion and avoid caching mutable application objects or stale source in tests that intentionally change it.
3. Remove delays after synchronous buffer operations. Isolate unrelated buffer tests from keepalive scheduling; exercise the real `KeepAlive.run` logic separately with controlled time and termination, without modifying the shared `time` module.
4. Replace startup sleeps with bounded waits for the complete expected request set. Ensure thread cleanup occurs even when assertions fail, and verify termination.

Production timing, package imports, and module interfaces remain unchanged. Keep real-thread coverage where scheduling or lifecycle behavior is the subject of the test; do not shorten timeouts merely to run faster.

# Validation

### Performance and correctness
- Establish several fresh-process baseline runs using `../bin/python -m pytest --durations=25`; record overall wall time, slow phases, test count, and outcomes. Measure collection separately if it dominates.
- Run affected modules after each change. Repeat threaded tests to detect races, leaked workers, or order-dependent state.
- Check that cached analysis preserves all source checks and controlled keepalive tests still assert emitted packets and the requested two-second interval.
- Run `../bin/python -m ruff format --check <changed Python files>`. If needed, format those files and rerun the check.
- Run all unit tests with `../bin/python -m pytest` after changes. Repeat comparable timed runs with unchanged plugins and coverage settings; report median before/after times and retain optimizations that show a reproducible benefit.
- Do not exclude tests because the user is editing `component_state.py`. Report any validation blockers without changing that file; qualify timing comparisons if concurrent edits make before/after results noncomparable.

# Delivery Steps

### ✓ Step 1: Reuse repeated GUI source analysis
GUI source-check tests share parsed input without losing assertions.
- Establish baseline suite timings and inspect collection/setup/call/teardown costs before editing.
- Leave `component_state.py` and its user-owned modifications untouched and outside the optimization review.
- Add module-scoped, read-only source/AST reuse in `tests/gui/test_controller_view.py` and `tests/gui/test_lcs_imports.py` where profiling supports it.
- Update the existing helpers and parametrized checks to consume that analysis while preserving test independence.
- Run affected tests and formatting checks; compare their timings against baseline.

### ✓ Step 2: Make buffer and startup tests deterministic
Buffer and startup tests avoid incidental delays while preserving timing and lifecycle coverage.
- In `tests/pdi/test_base3_buffer.py`, remove waits after synchronous captures and isolate keepalive activity from unrelated cases.
- Replace the shared `time.sleep` patch with a controlled scheduling test of the real keepalive loop, including interval and packet assertions.
- In `tests/db/test_startup_state.py`, use the existing `wait_until` pattern or explicit events to detect completed initialization; guarantee cleanup and assert thread termination.
- Repeat affected threaded tests, perform required formatting checks, and run the full suite with `../bin/python -m pytest`.
- Compare equivalent repeated runs and report the measured runtime improvement with unchanged test coverage; note any validation blockers or timing uncertainty caused by concurrent edits without modifying `component_state.py`.