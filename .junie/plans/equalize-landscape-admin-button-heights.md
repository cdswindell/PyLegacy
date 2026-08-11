---
sessionId: session-260810-214807-1rqv
---

# Requirements

### Goal
Correct the landscape regression introduced by the last height rebalance while ensuring all three Admin Operations rows are visible.

### Findings
- The last commit reduced `compact_control_height` from `44` to `36` and added `compact_auxiliary_height=44` to Network, Logging, and Scope (`src/pytrain/gui/controller/admin_panel.py:66–80`, `129–139`, `249–255`, and `284–290`). This compresses controls that previously rendered correctly.
- The change does not address the actual constraint: `grid_rowconfigure(..., minsize=...)` at `admin_panel.py:317–323` and `586–600` sets only a minimum. A Guizero `PushButton` or `HoldButton` can still request a taller row.
- `_fit_compact_control()` at `admin_panel.py:630–632` applies grid stretch and external padding but does not constrain the native Tk widget height.
- `HoldButton` delegates to Guizero `PushButton` in `src/pytrain/gui/components/hold_button.py:128–139`, so one compact native-height rule can cover `Loaded`, `Restart`, and the other action buttons.

### Acceptance Criteria
- Restore the pre-regression landscape heights for Network, Logging, Scope, and the shared action controls.
- Render `Restart`/`Reboot`, `Update PyTrain`/`Upgrade Pi OS`, and `Quit`/`Shutdown` together above `Close`.
- Preserve equal action-button width and height, uniform spacing, visible `Local` and `All` Scope options, the version title, and existing command behavior.
- Make no portrait-layout or `src/pytrain/cli/pytrain.py` changes.

# Technical Design

### Proposed Changes
- Revert the latest height rebalance in `AdminPanel`: restore `compact_control_height` to `max(44, int(button_size * 0.55))`, remove `compact_auxiliary_height`, restore Network to `compact_section_height`, and let compact Logging and Scope use `_titlebox()`'s standard compact section height.
- Retain the existing fixed, uniform action rows (`weight=0`, `minsize=compact_control_height`) and the `compact_admin_actions_height` allocation for three rows plus title allowance.
- Extend `_fit_compact_control()` only in compact mode to reduce the native Tk button/checkbutton height request and internal vertical padding before applying `sticky="nsew"`, `padx=2`, and `pady=2`. The shared `44`-pixel grid row then determines the rendered height instead of each widget's natural request.
- Keep `compact_control_width`, the three-column Scope span, and all portrait branches unchanged.

### Why This Works
The Admin Operations `TitleBox` already reserves `3 * compact_control_height + 12` pixels. Constraining each compact widget's requested height below the `44`-pixel row minimum allows all three rows to fit that existing allocation; shrinking unrelated sections is unnecessary.

### Files
- Modify `src/pytrain/gui/controller/admin_panel.py`.
- Update `tests/gui/controller/test_admin_panel_layout.py`.
- Leave `src/pytrain/gui/components/hold_button.py` and attached `src/pytrain/cli/pytrain.py` unchanged.

# Testing

### Validation
- Assert restored landscape section/control allocations and all three fixed Admin Operations rows.
- Assert compact controls receive the native height/padding constraint plus existing grid fill and spacing.
- Assert portrait controls do not receive compact-only geometry changes.
- Retain coverage for equal widths, Scope column span, version title, and visible third-row construction.
- Run the required Ruff format check on changed Python files and the complete pytest suite.

# Delivery Steps

### ✓ Step 1: Restore the pre-regression landscape section budget
Network, Logging, Scope, and shared compact controls regain their previously working heights.

- Revert the latest `compact_control_height` reduction in `src/pytrain/gui/controller/admin_panel.py`.
- Remove `compact_auxiliary_height` and its explicit use by Network, Logging, and Scope.
- Preserve fixed action rows, shared widths, Scope spanning, and every portrait branch.

### ✓ Step 2: Constrain compact controls to the shared row height
All landscape controls fit their uniform grid rows, allowing all three Admin Operations rows to render above `Close`.

- Update `_fit_compact_control()` to limit the native Tk height request and internal vertical padding only when `self._compact` is true.
- Keep the existing `44`-pixel row minimum, `sticky="nsew"`, and two-pixel inter-control spacing.
- Apply the shared behavior to `PushButton`, `HoldButton`, and decorated checkbox controls without changing command callbacks.

### ✓ Step 3: Update and run layout regression coverage
Automated validation protects the restored sections, uniform control geometry, third action row, and portrait behavior.

- Update `tests/gui/controller/test_admin_panel_layout.py` for restored height values and native compact-control constraints.
- Verify all three action row pairs are constructed inside the allocated Admin Operations section and portrait controls remain unconstrained.
- Run Ruff formatting checks on both changed Python files and execute the complete pytest suite.