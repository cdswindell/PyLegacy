---
sessionId: session-260810-214807-1rqv
---

# Requirements

### Goal
Make `Loaded`, `Restart`, and every other Admin-panel action control render at the same height in landscape mode.

### Findings
- The image shows that `Loaded` is taller than `Restart`; their rendered heights are not equal.
- `Loaded` is a Guizero `PushButton` created at `src/pytrain/gui/controller/admin_panel.py:174–184`.
- `Restart` is created through `_hold_button()` at `admin_panel.py:318–323`. `HoldButton` subclasses Guizero `PushButton` in `src/pytrain/gui/components/hold_button.py:24` and delegates construction to it at lines `128–139`, so the differing subclasses are not the cause.
- The shared `compact_control_height` at `admin_panel.py:66–68` is only used as a grid `minsize`. The one-row `Loaded` section and three-row `Restart` section both use `weight=1`, so Tk expands their rows independently from differently sized containers (`admin_panel.py:311–317` and `580–594`).

### Scope
- Apply the correction only when `self._compact` is true (landscape mode).
- Preserve the existing 44-pixel shared control allocation, uniform widths, padding, Scope visibility, and Admin-panel vertical footprint.
- Do not alter portrait-mode layout or CLI restart behavior in `src/pytrain/cli/pytrain.py`.

# Technical Design

### Proposed Change
Treat compact action rows as fixed-size rows rather than expandable rows:

- In `AdminPanel._titlebox()`, configure compact row `0` with `weight=0` and `minsize=self.compact_control_height`.
- In the Admin Operations setup, configure rows returned by `admin_action_rows` with `weight=0`, the same `minsize`, and the existing `uniform="admin_actions"` grouping.
- Keep `_fit_compact_control()` using `sticky="nsew"` and two-pixel padding, so each control fills the same fixed row allocation.
- Keep `compact_section_height` and `compact_admin_actions_height` unchanged; their title allowance provides the remaining vertical space without allowing the button rows to absorb it.

### Why This Works
`minsize` alone does not impose an exact row height when a row has positive weight. Removing row expansion makes both the one-row Base 3 Database section and each row of the three-row Admin Operations section use the same allocation, independent of their containing `TitleBox` geometry.

### Files
- Modify `src/pytrain/gui/controller/admin_panel.py`.
- Update `tests/gui/controller/test_admin_panel_layout.py`.
- No change is required in attached `src/pytrain/cli/pytrain.py`.

# Testing

### Validation
- Update layout tests to assert non-expanding compact rows with the shared minimum height.
- Cover both a standard one-row compact `TitleBox` and all three Admin Operations rows.
- Retain portrait assertions to verify its natural-height grid behavior is unchanged.
- Run Ruff format checking on changed Python files and the complete pytest suite, as required by the project instructions.

# Delivery Steps

### ✓ Step 1: Fix compact row sizing
Landscape Admin controls use one fixed shared row allocation instead of independently expanding heights.

- Change compact row configuration in `src/pytrain/gui/controller/admin_panel.py` from expandable `weight=1` to fixed `weight=0`.
- Apply the same policy to all three Admin Operations rows containing `Restart`, `Reboot`, update/upgrade, `Quit`, and `Shutdown`.
- Preserve current width constraints, section heights, padding, Scope layout, and all portrait branches.

### ✓ Step 2: Strengthen layout regression coverage
Automated checks prove single-row and multi-row landscape controls receive identical height constraints.

- Update `tests/gui/controller/test_admin_panel_layout.py` expectations for the compact row weights.
- Assert every Admin Operations row uses the shared `compact_control_height` without expansion.
- Retain portrait-mode assertions and run Ruff format checking plus the full pytest suite.

### ✓ Step 3: Capture the compact vertical budget regression
Automated checks describe the smaller landscape-only allocations needed to keep all three Admin Operations rows visible.

- Add expectations for reduced compact control, WiFi/Network, Logging, and Scope heights.
- Retain portrait assertions proving natural-height behavior remains unchanged.

### ✓ Step 4: Rebalance landscape section heights
The landscape Admin panel reclaims enough vertical space to render `Quit` and `Shutdown` without clipping.

- Reduce the shared compact button height while preserving uniform button dimensions.
- Reduce only compact WiFi/Network, Logging, and Scope section allocations.
- Keep all portrait branches and CLI restart behavior unchanged.

### ✓ Step 5: Verify formatting and regressions
Formatting and the complete unit-test suite validate the landscape-only correction.

- Run Ruff format checking on changed Python files.
- Run the complete pytest suite.