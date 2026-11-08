---
sessionId: session-260925-141630-1bw4
---

# Requirements

### Goal
Make `get_ip_address()` work on Steam Deck when the native `hostname` executable is missing, using the existing `hostname.sh`.

- Support both pip installations and source-tree execution, independent of the working directory.
- Keep native `hostname -I` as the preferred Linux command.
- Preserve the existing first-address return behavior, network wait, socket fallback, retries, and non-Linux behavior.
- Limit changes to `src/pytrain/utils/ip_tools.py` and `tests/utils/test_ip_tools.py`; leave the script and packaging configuration unchanged.

# Technical Design

### Existing implementation
- `get_ip_address()` in `src/pytrain/utils/ip_tools.py:74–113` directly executes `hostname -I`; a missing executable currently raises `FileNotFoundError` before socket fallback.
- `src/pytrain/installation/hostname.sh` accepts `-I` and prints whitespace-separated IPv4 addresses.
- `pyproject.toml:91–92` already installs the script through setuptools `script-files`.
- `src/pytrain/cli/make_base.py` provides reference patterns: module-relative installation paths and explicit `/bin/bash` invocation for shell scripts.

### Proposed changes
1. Add a private `_find_hostname_script() -> Path | None` helper in `ip_tools.py`. Check these locations in order, returning the first existing file:
   - `shutil.which("hostname.sh")` for an installed script on `PATH`.
   - `Path(sysconfig.get_path("scripts")) / "hostname.sh"` for the active Python installation, including an unactivated virtual environment.
   - `Path(__file__).resolve().parents[1] / "installation" / "hostname.sh"` for source-tree execution.
2. Keep the existing native command invocation. Only on `FileNotFoundError`, locate and execute the script as `["/bin/bash", str(script_path), "-I"]`, with `capture_output=True` and `text=True`. This avoids depending on source-file executable permissions and safely handles paths containing spaces.
3. Apply the existing successful-output parsing to either command. If the script is absent, cannot launch due to `OSError`, exits unsuccessfully, or produces blank output, continue to the existing socket fallback.
4. Preserve native nonzero/blank-output behavior: proceed directly to socket fallback rather than invoking the replacement. Do not catch cancellation exceptions.

No new dependencies, public APIs, or cross-module changes are needed.

# Testing

### Regression coverage
Extend `tests/utils/test_ip_tools.py` using its existing `monkeypatch`, `DummyCompleted`, and mocked network-wait conventions:
- Native command success remains preferred and returns only the first address.
- Missing native command finds the pip-installed script on `PATH`.
- Installed script is found in the active Python scripts directory when absent from `PATH`.
- Source-tree fallback works from an unrelated working directory, including a path with spaces and a script without executable permission.
- Missing script, script launch failure, nonzero exit, and blank output reach socket fallback.
- Native nonzero/blank output and existing non-Linux behavior remain unchanged.

Mock subprocesses and network calls so new tests require neither Steam Deck hardware nor actual network access.

### Validation after implementation
- Run `../bin/python -m ruff format --check src/pytrain/utils/ip_tools.py tests/utils/test_ip_tools.py`; if needed, format those files and rerun the check.
- Run `../bin/python -m pytest`.

No files have been modified or tests run during planning.

# Delivery Steps

### ✓ Step 1: Add installed and source-tree script discovery
A private helper locates `hostname.sh` without depending on the current working directory.

- Add `_find_hostname_script()` in `src/pytrain/utils/ip_tools.py`.
- Search `PATH`, the active Python scripts directory, and the module-relative installation directory in that order.
- Add deterministic discovery tests in `tests/utils/test_ip_tools.py`, including missing files and source-tree paths.

### ✓ Step 2: Integrate the missing-hostname fallback
Linux IP discovery uses `hostname.sh` when the native executable is missing while retaining existing fallback behavior.

- Catch `FileNotFoundError` from native `hostname -I` and invoke the discovered script through `/bin/bash`.
- Reuse first-address parsing and continue to socket resolution when the replacement is unavailable or unsuccessful.
- Extend regression tests for command preference, installed/source execution, failure paths, and unchanged non-Linux behavior.
- Run the required Ruff format check, apply formatting if necessary, and run the full pytest suite.