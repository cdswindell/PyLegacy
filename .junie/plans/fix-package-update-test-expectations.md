---
sessionId: session-260923-172402-hfsb
---

# Diagnosis & Fix

### Cause
Both cases of `test_package_update_fallback_and_failed_commands` (`returncode=0` and `returncode=1`) share an incorrect expectation in `tests/cli/test_pytrain_update.py`: the comprehension adds `--no-cache-dir` to **both** subprocess calls.

`PyTrain.update()` in `src/pytrain/cli/pytrain.py` intentionally uses it only when upgrading the PyTrain distribution—not when upgrading `pip`. The existing `test_api_update_upgrades_pip_before_exit` and `UPDATE_SUBPROCESS_WAITS` already reflect that distinction.

### Exact fix
Replace the `assert run.call_args_list == ...` block with two explicit calls:

```python
    assert run.call_args_list == [
        call(
            [sys.executable, "-m", "pip", "install", "-U", "pip"],
            cwd=mod.os.getcwd(),
            check=False,
        ),
        call(
            [sys.executable, "-m", "pip", "install", "-U", "--no-cache-dir", PROGRAM_PACKAGE],
            cwd=mod.os.getcwd(),
            check=False,
        ),
    ]
```

Keep the return-code parameterization and `obj.relaunch.assert_called_once_with(PyTrainExitStatus.UPDATE)` unchanged. This preserves command ordering, fallback package selection, and behavior after nonzero subprocess exits. No production-code or shutdown changes are needed.

# Validation

### After implementation
- Confirm both return-code cases expect the ordinary `pip` upgrade first and the cache-free fallback distribution upgrade second.
- Preserve the existing API, distribution-selection, source-update, and interruption tests.
- Run `../bin/python -m ruff format --check tests/cli/test_pytrain_update.py`. If it fails, format that file and repeat the check.
- Run the full suite with `../bin/python -m pytest`.

No files were changed or tests executed during this planning session. The diagnosis comes from the supplied code; recent IDE test results were unavailable.

# Delivery Steps

### ✓ Step 1: Correct the pip upgrade expectation
The fallback test expects the unchanged pip bootstrap command without `--no-cache-dir`.
- In `tests/cli/test_pytrain_update.py`, replace the shared command comprehension with explicit ordered `call(...)` entries.
- Make the first entry use `[sys.executable, "-m", "pip", "install", "-U", "pip"]`.
- Retain `cwd=mod.os.getcwd()` and `check=False`.

### ✓ Step 2: Pin the cache-free fallback package expectation
Both return-code cases preserve the cache-free PyTrain upgrade and relaunch contract.
- Make the second explicit entry target `PROGRAM_PACKAGE` with `--no-cache-dir`, preserving `cwd` and `check=False`.
- Keep the missing-installed-package mock, return codes 0 and 1, and the single-relaunch assertion unchanged.
- Leave `src/pytrain/cli/pytrain.py` unchanged.
- Run the required Ruff format check, format and recheck if needed, then run the full pytest suite.