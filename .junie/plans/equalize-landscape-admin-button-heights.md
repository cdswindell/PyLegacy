---
sessionId: session-260810-214807-1rqv
---

# Requirements

### Goal
Use the available landscape vertical space so every Admin section and all three Admin Operations rows render cleanly without clipping or crowding.

### Image Findings
- The buttons now have consistent row dimensions, and all three Admin Operations pairs are present.
- The section legends sit too close to the first control row because each compact `TitleBox` reserves only `12` pixels beyond its `44`-pixel control row.
- The three-row `Hold for 3 seconds` section has the same undersized allowance: `compact_admin_actions_height` is only `144` pixels (`3 * 44 + 12`), leaving `Quit` and `Shutdown` crowded against or clipped by the lower border.
- There is unused vertical space between the Admin content and `Close`, so the panel can grow rather than shrinking buttons or unrelated sections again.

### Acceptance Criteria
- Give landscape `TitleBox` legends and borders enough dedicated vertical allowance that they do not intrude on controls.
- Show `Restart`/`Reboot`, `Update PyTrain`/`Upgrade Pi OS`, and `Quit`/`Shutdown` at their full, uniform `44`-pixel row height with consistent spacing.
- Keep `Close` visible and separate from the expanded Admin content.
- Render the landscape `Logging` and `Debugging` options fully within the `Logging & Debugging` box, without truncating their labels or controls.
- Preserve equal control widths, visible `Local` and `All` Scope options, Network content, version title, and existing action behavior.
- Do not change portrait mode or `src/pytrain/cli/pytrain.py`.

# Technical Design

### Current Implementation
- `AdminPanel.compact_control_height` at `src/pytrain/gui/controller/admin_panel.py:66–68` defines the shared `44`-pixel landscape control allocation.
- `compact_section_height` at lines `74–76` adds only `12` pixels for a section legend and border; `compact_admin_actions_height` at lines `82–84` applies that same allowance to the three-row action section.
- `_titlebox()` at lines `547–597` disables grid propagation and fixes compact containers to those computed heights, so an undersized allowance clips or crowds their children rather than growing naturally.
- The `Logging & Debugging` box at lines `245–271` uses the same default compact section height; its `Logging` option is truncated because the shared legend/border allowance is too small for the decorated checkbox row.
- The fixed action rows at lines `307–317` and compact widget sizing at lines `624–627` already establish uniform control geometry and should remain intact.
- `PopupManager.create_popup()` adds `Close` separately below the body in `src/pytrain/gui/controller/popup_manager.py:141–172`; the image shows enough space to enlarge the body without changing that footer behavior.

### Proposed Changes
- Introduce a named landscape title/border allowance larger than the current implicit `12` pixels, sized to the rendered legend font and frame border.
- Derive both `compact_section_height` and `compact_admin_actions_height` from that shared allowance so one-row and three-row sections follow the same geometry rule.
- Let the resulting taller `TitleBox` values grow the Admin body into the available vertical space, including the `Logging & Debugging` box so both decorated checkbox options render fully; do not reduce `compact_control_height`, remove fixed row sizing, or alter control padding.
- Keep the existing landscape-only guards, shared `compact_control_width`, three-column Scope span, and all portrait branches unchanged.

### Why This Works
The row allocations already guarantee equal button heights. Adding vertical space outside those rows addresses the actual remaining constraint—the legend and border overhead—while preserving all three action rows and the behavior that is now correct.

### Files
- Modify `src/pytrain/gui/controller/admin_panel.py`.
- Update `tests/gui/controller/test_admin_panel_layout.py`.
- Leave `src/pytrain/gui/components/hold_button.py`, `src/pytrain/gui/controller/popup_manager.py`, and attached `src/pytrain/cli/pytrain.py` unchanged.

# Testing

### Validation
- Assert the expanded landscape title allowance and the resulting one-row and three-row section heights.
- Verify all six Admin Operations controls remain in three consecutive fixed-height rows.
- Assert the landscape `Logging & Debugging` box receives the expanded section height and still contains complete `Logging` and `Debugging` controls.
- Retain checks for shared widths, uniform padding, Scope spanning, version title, and compact native widget constraints.
- Retain portrait assertions proving it still uses natural geometry and receives no compact sizing changes.
- Run the required Ruff format check on changed Python files and the complete pytest suite.

# Delivery Steps

### ✓ Step 1: Expand landscape section framing
Landscape Admin sections reserve enough height for their legends, borders, and full-size control rows.

- Add a named compact title/border allowance in `src/pytrain/gui/controller/admin_panel.py`.
- Recalculate standard compact section height from one `compact_control_height` plus that allowance.
- Recalculate Admin Operations height from three `compact_control_height` rows plus the same allowance.
- Preserve the existing `44`-pixel rows, shared widths, padding, Scope layout, callbacks, and portrait branches.

### ✓ Step 2: Protect the complete landscape layout
Regression coverage proves the expanded panel keeps every control visible and preserves established behavior.

- Update `tests/gui/controller/test_admin_panel_layout.py` with the new derived height expectations.
- Verify the `Logging & Debugging` section uses the expanded landscape height and constructs both `Logging` and `Debugging` controls without changing portrait geometry.
- Verify all three action pairs remain constructed in fixed consecutive rows and `Close` retains space below the body.
- Retain portrait-isolation and existing compact geometry assertions.
- Run Ruff format checking on changed Python files and execute the full pytest suite.

### ✓ Step 3: Equalize checkbox geometry and rebalance landscape heights
The Logging and Debugging controls render at the same size, while landscape-only control heights gain two pixels and Network uses half its current height.

- Correct the compact Logging checkbox sizing without disturbing Debugging or other landscape geometry.
- Increase compact control height allocations by two pixels and reduce the compact WiFi/Network block height by 50%.
- Leave portrait dimensions and natural geometry unchanged.
- Preserve Scope visibility, all three Admin Operations rows, Close separation, callbacks, and CLI behavior.

### ✓ Step 4: Extend regression coverage and verify
Automated checks protect checkbox parity, the landscape-only two-pixel height increase, the reduced Network block, and portrait isolation.

- Update `tests/gui/controller/test_admin_panel_layout.py` with focused landscape and portrait geometry assertions.
- Run Ruff format checking on changed Python files.
- Run the complete pytest suite.

### ✓ Step 5: Align tests with manual landscape sizing
Regression expectations reflect the user-adjusted compact button and Network heights without changing production code.

- Update `tests/gui/controller/test_admin_panel_layout.py` for the current derived landscape dimensions.
- Preserve checkbox parity, action-row, Scope, and portrait-isolation assertions.

### ✓ Step 6: Verify the updated expectations
Formatting and the complete test suite confirm the manual landscape geometry is covered correctly.

- Run Ruff format checking on the changed Python test file.
- Run the complete pytest suite.

### ✓ Step 7: Revert incorrect Scope alignment changes
Restore the Scope controls to their behavior before the latest width and alignment change.

- Remove the shared option-width property and direct Scope child repositioning.
- Restore the landscape-only three-column Scope span and portrait grid behavior.
- Restore the prior Logging, Debugging, and Scope width expressions.
- Revert the corresponding layout test changes.

### ✓ Step 8: Verify the reversion
Formatting and the complete test suite confirm the previous behavior is restored safely.

- Run Ruff format checking on the changed Python files.
- Run the complete pytest suite.