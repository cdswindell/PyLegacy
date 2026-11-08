---
sessionId: session-261021-151905-6v6v
---

# Requirements

### Goals
- Audit every test module and its collected cases, including fixtures and parameter combinations—not just similarly named files.
- Remove proven duplicate coverage while retaining unique inputs, boundaries, failure paths, and regression assertions.
- Report the slowest tests and fixture phases with measured costs and prioritized efficiency recommendations.
- Add an opt-in smoke selection for frequent feedback; keep the full suite as the pre-check-in and CI default.

### Recommendation
**Yes, add smoke tests by selecting existing tests, not creating a duplicate suite.** Use smoke plus affected-module tests during development, then `../bin/python -m pytest` before check-in. Aim for roughly five seconds or less locally, subject to measured collection overhead; do not impose a flaky wall-clock assertion.

The reported **18.2 seconds is not yet a measured baseline for this review**. No tests were executed or files changed during planning. Current slowest-test rankings and achievable savings must be established during implementation.

Production behavior, dependencies, parallel execution, default exclusions, and CI coverage remain unchanged.

# Technical Design

### Findings from source review
| Area | Finding and proposed treatment |
|---|---|
| Validation tests | `tests/protocol/test_validations.py` overlaps with `tests/utils/test_validations.py`. Move float-to-int conversion and default rejection of `None` into the utility module before removing redundant coverage. Fix the utility test's always-truthy `or " is not an integer"` assertion. |
| Filesystem tests | `tests/utils/test_path_utils.py::test_non_default_places_are_fresh` searches `Path.cwd()` twice. `src/pytrain/utils/path_utils.py::_index_for` rebuilds indexes for nondefault roots. Replace that incidental repository traversal with a controlled temporary project root while preserving freshness semantics. |
| Similar filenames | The two path-utility modules cover distinct exclusion/indexing behavior. The listener modules distinguish lifecycle/queue behavior from decoding through a real worker. Do not delete files based on names or `_ai` suffixes. Audit the state-store pair similarly. |
| Process tests | `tests/utils/test_logging_multiprocessing.py::test_worker_import_does_not_rotate_main_log` runs three process-start methods; `tests/cli/test_routes.py::test_source_launcher_help_without_pythonpath` launches Python from two directories. Profile them individually; retain their distinct process-isolation guarantees in the full suite. |
| Optional integration | `tests/integration/test_pytrain_api_exit.py` runs only with `PYTRAIN_API_CHECKOUT`. Record whether it is enabled and report it separately; do not attribute default-suite time to skipped cases. |
| Existing efficiencies | GUI source-analysis caches already exist in `test_controller_view.py` and `test_lcs_imports.py`; `tests/test_base.py` provides `wait_until`; CLI fixtures already suppress startup side effects. Avoid redoing these optimizations. |

### Audit and optimization rules
- Inventory all collected cases and review their setup, exercised behavior, and assertions. Record every deletion against its surviving coverage; identical lines alone do not establish equivalence.
- Measure fresh-process wall time, collection, and setup/call/teardown separately. Rank both individual cases and aggregate module/parameter-family costs; broad loops in `tests/protocol/test_command_req.py` deserve attention even when represented by few test functions.
- Remove unnecessary fixture dependencies, starting with unused `tmpdir` in the listener cleanup fixture. Reuse immutable analysis only where profiling supports it; do not share mutable parsers, singleton state, or mocks across tests.
- Use controlled clocks or condition/event waits only when time or concurrency is incidental. Preserve real subprocess/thread coverage, reasonable failure timeouts, and cleanup assertions.
- Preserve best-effort shutdown, logging and continuation after ordinary cleanup failures, retryable failed ownership, and propagation of genuine `KeyboardInterrupt`/`SystemExit` cancellation.

### Smoke selection
Register `smoke` in `pytest.ini` and mark a small set of existing cases spanning protocol encoding/decoding, PDI requests, state updates, CLI startup/parsing, representative headless GUI logic, and critical shutdown failure behavior. Choose cases after timing; mark individual parameter cases when a whole parameter family is excessive.

Run `../bin/python -m pytest -m smoke`. Leave normal collection, `tox.ini`, and CI defaults unchanged. Exclude expensive subprocess matrices from smoke, not from the full suite. Measure selection overhead: `-m smoke` still imports and collects the suite, so disclose that floor rather than promising instantaneous runs.

### File changes
- Add `doc/test-suite-audit.md`: complete review inventory, duplicate-to-survivor mappings, measured rankings, before/after results, and remaining recommendations.
- Update `tests/utils/test_validations.py`; remove `tests/protocol/test_validations.py` only after preserving its unique cases.
- Update `tests/utils/test_path_utils.py` and justified fixture/test hotspots identified by the audit, including `tests/comm/test_command_listener.py`.
- Add smoke marks to selected existing test modules; update `pytest.ini` and `tests/README.md` with commands, selection rationale, and maintenance guidance. Preserve historical results as historical.

# Testing

### Performance evidence
- Establish three comparable fresh-process baseline runs with `../bin/python -m pytest --durations=0 --durations-min=0`; record interpreter, plugins, coverage settings, environment, counts, skips, wall time, and phase durations. Measure collection separately with `--collect-only`.
- Report the top 25 individual cases/phases and aggregate hotspots. Compare before/after medians and ranges under unchanged settings; keep coverage-instrumented runs separate from ordinary timing runs.
- Validate smoke membership with `--collect-only -m smoke`, confirm it is nonempty and covers the intended areas, and measure its end-to-end runtime.

### Coverage and isolation
- Run all new or modified tests, related modules, and the full suite with `../bin/python -m pytest` after changes. Reconcile removed cases with the audit mapping rather than treating fewer tests as success.
- Compare focused line/branch coverage for consolidated behavior where available; assertion review remains necessary even if coverage is unchanged.
- Repeat changed threaded tests and run affected modules independently and together to detect leaked state or ordering dependencies. Retain process-start and shutdown regression matrices.

### Required checks
- Confirm the configured PyCharm interpreter before Python commands.
- Run `../bin/python -m ruff format --check <changed Python files>`; format failures and rerun the check.
- Inspect every new or modified test file in PyCharm, including warnings and weak warnings; fix findings and review American English in names, comments, docstrings, and assertion messages.
- Use only narrowly scoped, explained inspection suppressions where genuinely required, then rerun inspections. Report any unavailable validation, including opt-in API integration prerequisites.

# Delivery Steps

### ✓ Step 1: Produce the complete test audit and timing report
`doc/test-suite-audit.md` identifies coverage overlap and measured runtime hotspots across the entire suite.
- Inventory all test modules, collected cases, parameter families, and relevant fixtures.
- Review behavioral equivalence and record unique coverage, prioritizing the validation, path, listener, and state-store pairs without limiting the audit to them.
- Capture comparable baseline and collection timings; rank individual phases and aggregate costs.
- Separate optional integration tests from the default run and record profiling conditions.

### ✓ Step 2: Consolidate redundant validation and other proven duplicate cases
Duplicate cases are removed only after their unique regression coverage has a documented surviving home.
- Consolidate `tests/protocol/test_validations.py` into `tests/utils/test_validations.py`, preserving float conversion and `None` rejection.
- Replace the always-truthy exception-message assertion with a meaningful check.
- Apply additional removals only where the complete audit proves equivalence, preserving differing fixture and concurrency semantics.
- Update the coverage mapping; run affected tests, focused coverage comparisons, formatting checks, and PyCharm inspections.

### ✓ Step 3: Eliminate avoidable filesystem and fixture overhead
Measured test overhead is reduced without changing production behavior or weakening lifecycle checks.
- Replace repository-wide search roots in `test_non_default_places_are_fresh` with a small temporary tree.
- Remove the unused `tmpdir` dependency from the listener cleanup fixture.
- Address other demonstrated hotspots using isolated fixtures, immutable analysis reuse, or deterministic waits where appropriate; document expensive tests that should remain intact.
- Repeat affected tests independently and together, inspect changed files, and compare timings while preserving shutdown and cancellation guarantees.

### ✓ Step 4: Add the smoke selection and document the development workflow
Developers can run a curated smoke subset while the full-suite command and CI remain unchanged.
- Register `smoke` in `pytest.ini` and mark existing representative cases rather than duplicating tests.
- Document smoke, affected-module, profiling, and pre-check-in commands in `tests/README.md`, including collection overhead and selection-maintenance guidance.
- Verify smoke membership and runtime, run every modified test, complete formatting and PyCharm inspections, and run the full suite.
- Finalize the audit report with before/after timing medians, removed-case mappings, remaining efficiency recommendations, and any verification limitations.

### ✓ Step 5: Update / Follow-up
Please stage for commit files I should retain from your work and remove the others. Also, I run tests through tox; how can I run the smoke test via tox?