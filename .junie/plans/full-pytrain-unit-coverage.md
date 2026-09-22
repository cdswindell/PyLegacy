---
sessionId: session-260922-123626-u58x
---

# Requirements

### Goal
Continue the completed `pytrain.py` coverage work by fixing the Python 3.11 failures in `tests/cli/test_pytrain_commands.py::test_parse_errors`. Preserve the existing test expansion rather than repeat its five completed stages.

### Acceptance Criteria
- `PyTrain.parse_cli("unknown")` and `PyTrain.parse_cli("s")` return informative error strings instead of raising `SystemExit`, consistently across Python 3.11–3.14.
- Retain real argument parsing, meaningful error assertions, and no-send guarantees; do not skip, xfail, or weaken the tests based on Python version.
- Preserve successful command parsing, command-specific parser restoration, and normal interactive help (`SystemExit(0)`).
- Pass focused regressions, the full unit suite, the existing interpreter matrix, and required formatting checks after implementation. Report missing interpreters as unverified, not passing.

### Approved Scope
The user explicitly approved one production change: in `src/pytrain/cli/pytrain.py`, retain the initial command parser locally in `_handle_command()` and call its existing `clear_exit_on_error()` before parsing **only when `parse_only=True`**. Supporting changes are limited to `tests/cli/test_pytrain_commands.py` and `tests/README.md`.

Every additional production change still requires prior review. Do not modify `src/pytrain/utils/argument_parser.py`, normalize interactive error handling, perform dead-code cleanup, or alter dependencies, Python support, or coverage exclusions. Leave `src/pytrain/comm/comm_buffer.py` and the user's changes untouched; their presence is not a blocker.

### Current Status
- Earlier implementation/review reported 756 CLI tests and 7,077 full-suite tests passing on Python 3.13, with 99.75% line and 99.00% branch coverage. The documented unreachable gaps remain review-gated.
- The user's newer matrix result reports two failures on Python 3.11 (7,075 passing), with Python 3.12–3.14 and lint passing. Earlier single-interpreter success did not establish matrix compatibility.
- Only this plan is changed during planning. No tests were rerun and no production or test files were modified.

# Technical Design

### Root Cause
- `PyTrain._command_parser()` (`src/pytrain/cli/pytrain.py`, currently around line 1653) creates a `PyTrainArgumentParser` with argparse's public `exit_on_error=False`.
- `PyTrainArgumentParser.__init__()` independently initializes its private `_exit_on_error=True`; its `error()` and `exit()` use that private flag through `is_exit_on_error`.
- In the supplied Python 3.11 traceback, unknown and ambiguous options invoke those overrides and exit with status 2. `_handle_command()` catches `ArgumentError`, not `SystemExit`.
- `_handle_command()` currently clears the private flag only on the command-specific parser, after initial command selection. The failing inputs never reach that code. `parse_cli()` explicitly documents returning an error message for invalid input.
- The `_started_at` error displayed in the fixture representation is incidental: `bare_pytrain` deliberately bypasses initialization. It is not the cause of either failure.

### Approved Local Fix
Replace the initial chained parser call inside `_handle_command()`'s existing `try` block with:

```python
command_parser = self._command_parser()
if parse_only:
    command_parser.clear_exit_on_error()
args = command_parser.parse_args(["-" + ui_parts[0]])
```

Use the existing `ArgumentError` handler to return the message. Do not catch `SystemExit` broadly, change parser-constructor defaults, or patch the parser in fixtures to conceal the defect. `_command_parser()` creates a fresh parser per invocation, so this local flag change does not leak into future interactive calls. Leave command-specific cleanup in the existing `finally` block unchanged.

### Existing Patterns and Changes
- `tests/utils/test_argument_parser.py` already verifies `clear_exit_on_error()` turns both `error()` and `exit()` into `ArgumentError`; reuse this established mechanism without modifying the shared class.
- Extend `tests/cli/test_pytrain_commands.py`, using its `command_train` fixture and real parsers. The fixture already isolates `PyTrain._current` and blocks transport construction and background threads.
- Keep all seven invalid-input cases. Add focused assertions for unknown/ambiguous command diagnostics using stable substrings rather than exact version-dependent formatting, including no enqueued commands and no error output on stderr for these parse-only failures.
- Add mode-isolation regressions: an invalid parse-only call followed by a valid command and by normal interactive help on the same instance. Use spies around real parsers only when needed to verify that the initial custom flag is cleared exclusively for parse-only calls.
- Preserve `test_real_parse_only`, `test_parser_restored`, `test_normal_send`, and `test_help` as boundary coverage; retain ordinary help exits and command-specific parser reset behavior.
- Append a compatibility follow-up to `tests/README.md` documenting the cause, approved fix, interpreter-specific results, and remeasured coverage. Preserve historical results as historical; refresh affected current blocker references after line shifts without implementing their proposed cleanup.

# Testing

### Regression Scenarios
- Unknown command `unknown`: informative string containing `unrecognized arguments` and `-unknown`; no exit, stderr diagnostic, or transport activity.
- Ambiguous command `s`: informative string containing `ambiguous option` and `-s`; no exit, stderr diagnostic, or transport activity.
- Existing malformed engine/cache cases continue to return errors; valid engine/train commands still return real `CommandReq` objects without sending.
- Parse-only failures do not affect subsequent parsing or interactive help. Existing help inputs `?`, `help`, and `engine -h` still print usage and raise `SystemExit(0)` in normal mode.
- Command-specific parser flags are restored after success and failure. Both outcomes of the new `parse_only` guard are covered.

### Post-Implementation Validation
Consult the Python environment guidance before executing toolchain commands. Do not rerun the supplied failure merely to reproduce it during planning. After implementation, run:

```bash
../bin/python -m ruff format --check src/pytrain/cli/pytrain.py tests/cli/test_pytrain_commands.py
../bin/python -m tox -e py311 -- tests/cli/test_pytrain_commands.py tests/utils/test_argument_parser.py
../bin/python -m pytest tests/cli --cov=src.pytrain.cli.pytrain --cov-branch --cov-report=term-missing
../bin/python -m pytest
../bin/python -m tox -e py311,py312,py313,py314,lint
```

If formatting fails, format only the two changed Python files and repeat the check. Use the existing `tox.ini` matrix unchanged; it skips missing interpreters, so explicitly verify which environments actually ran. Record actual results in `tests/README.md`; do not infer Python 3.11 success from the configured Python 3.13 interpreter.

Remeasure line and branch coverage because the fix changes totals and line numbers. Ensure new paths are covered, preserve existing coverage, and retain the documented unreachable gaps without exclusions or an unattainable `--cov-fail-under=100` gate. Do not edit, revert, or format `comm_buffer.py`, and do not include generated coverage reports as source changes.

# Delivery Steps

### ✓ Step 1: Fix parse-only command selection on Python 3.11
Unknown and ambiguous commands return error strings through the existing exception handler instead of terminating parse-only callers.
- Apply only the approved local parser change in `src/pytrain/cli/pytrain.py::_handle_command()`; keep the shared parser class and interactive path unchanged.
- Strengthen unknown/ambiguous cases in `tests/cli/test_pytrain_commands.py` with meaningful diagnostic, stderr, and no-send assertions while retaining all other invalid-input cases.
- Reuse real parsers and existing isolated fixtures; do not introduce version-based skips, alternate expectations, or broad `SystemExit` handling.
- Check formatting and run the focused command/parser tests in the existing Python 3.11 tox environment after the change.

### ✓ Step 2: Protect parser-mode boundaries and document compatibility
Regression coverage protects interactive behavior and parser isolation, with actual supported-version and coverage results documented.
- Add same-instance parse-only failure followed by successful parsing and normal help cases in `tests/cli/test_pytrain_commands.py`.
- Verify both branches of the new guard using real parser behavior or narrowly scoped spies; preserve existing command-specific restoration and normal-send tests.
- Append the approved compatibility fix and measured results to `tests/README.md`, keeping prior validation historical and updating affected blocker references without dead-code cleanup.
- Run changed-file formatting checks, focused CLI branch coverage, the required full unit suite, and the existing Python 3.11–3.14/lint tox matrix; explicitly report unavailable environments.
- Preserve all earlier coverage deliverables and leave `comm_buffer.py`, unrelated production code, and generated report files untouched.