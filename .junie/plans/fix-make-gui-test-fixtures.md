---
sessionId: session-260924-215447-iksn
---

# Diagnosis

### Likely cause
Three cases in `tests/cli/test_make_gui.py` construct `MakeGui` with `__new__`, bypassing initialization, but then call `make_shell_script()` without setting `_template_dir`:
- `test_make_gui_shell_script_includes_cache_sync_switch_only_when_disabled`
- Both parameterizations of `test_shell_script_exports_the_platform_it_was_generated_for`

The call chain is `MakeGui.make_shell_script()` (`src/pytrain/cli/make_gui.py:659`) → `_MakeBase.find_installation_file()` → `template_dir` (`src/pytrain/cli/make_base.py:182–187`). Accessing the missing attribute should raise `AttributeError` before any rendering assertions run. Normal construction initializes it at `make_base.py:75`.

The cache-sync test also omits `___PLATFORM___`, leaving an unresolved launcher token once template lookup succeeds.

### Confidence and scope
This diagnosis comes from static inspection; no recent IDE failure output was available, and tests were not rerun. Plan a localized test-fixture repair, not a production fallback for incompletely initialized objects. Leave installer behavior, service generation, and shutdown logic unchanged.

# Fix and Validation

### Proposed changes
- Add a function-scoped launcher factory fixture in `tests/cli/test_make_gui.py`, following its existing `__new__`-based test setup and `_installable` helper pattern.
- Initialize `_template_dir` using `Path(mod.__file__).resolve().parents[1] / "installation"`, matching production construction. Keep output under `tmp_path`.
- Supply `_gui_class`, `_launch_path`, and a complete rendering configuration, including `___PLATFORM___` from `mg.platform`.
- Migrate the cache-sync and platform-export tests to this fixture while exercising the real lookup and `src/pytrain/installation/launch_pytrain.bash.template`; do not mock the behavior under test.
- Extend cache-sync assertions to reject unresolved placeholders and verify the empty platform export. Preserve Steam Deck and ordinary-GUI platform coverage.
- Add a regression that changes the working directory to a temporary directory and still resolves and renders the packaged template. Make the existing template-placeholder check use an explicit package-relative location rather than recursive working-directory discovery.

### Validation after implementation
- Verify both cache-sync settings, platform exports, complete substitutions, and working-directory-independent lookup without launching a GUI or running an installation.
- Consult the Python environment guidance before executing Python commands.
- Run `../bin/python -m ruff format --check tests/cli/test_make_gui.py`; if necessary, format that file and repeat the check.
- Run the required full suite with `../bin/python -m pytest`, distinguishing any unrelated failures from this repair.

# Delivery Steps

### ✓ Step 1: Repair launcher test object initialization
The three affected launcher cases use complete, isolated `MakeGui` test objects.
- Add a function-scoped launcher factory fixture in `tests/cli/test_make_gui.py`.
- Initialize the package-relative `_template_dir`, temporary output path, GUI class, and full substitution configuration.
- Migrate both shell-generation test functions to the fixture without bypassing real template lookup or rendering.
- Preserve the existing cache-sync and platform assertions.

### ✓ Step 2: Protect launcher rendering against fixture drift
Launcher regressions verify complete substitutions and lookup independent of the working directory.
- Strengthen the cache-sync test to assert an empty platform export and no unresolved placeholders for both flag settings.
- Add a temporary-working-directory regression using the real launcher template.
- Anchor the existing template-placeholder test to the package-relative template location.
- Perform the required formatting checks and full unit-test validation after implementation; report any remaining failures separately.