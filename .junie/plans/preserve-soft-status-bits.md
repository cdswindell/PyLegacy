---
sessionId: session-260919-095051-siw2
---

# Requirements

### Goal
Enable direction updates without overwriting unknown `soft_status` bits.

- **Confirmed convention:** `FORWARD_DIRECTION` clears bit 0; `REVERSE_DIRECTION` sets bit 0.
- Preserve bits 1–7 exactly, without assigning meanings to them.
- Support both `request_to_updates` and `field_to_updates`, for engines and trains.
- Make the helper reusable for other bit positions later.
- Skip the update when the current status byte is unavailable rather than inventing a value.

### Scope
Modify `src/pytrain/db/comp_data.py` and `tests/db/test_comp_data.py`. Keep direction readers, existing `RESET` behavior, and Base request/refresh handling unchanged.

# Technical Design

### Current logic
In `src/pytrain/db/comp_data.py`:
- `soft_status` occupies one byte at `0x0B`, shared by engine and train layouts.
- Both update entry points delegate to `_create_update_pkg`.
- Ordinary transforms receive command `data`, **not the current field value**. Consequently, `lambda x: x | 1` would modify the wrong value.
- The RPM/labor branch already demonstrates the required pattern: look up existing state with `get_state(scope, address, False)` and read it under `state.synchronizer`.

### Recommended helper
Add a small immutable callable, `BitUpdate(bit: int, enabled: bool)`, alongside the existing helpers. Its type explicitly identifies transforms that need the stored field value; no tuple-format change or callable-signature guessing is required.

Its calculation is:
```python
def __call__(self, current: int) -> int:
    mask = 1 << self.bit
    return current | mask if self.enabled else current & ~mask
```
Validate bit positions `0–7` and byte values `0–255`. Treat `0xFF` as a valid status byte, as the existing direction tests do. Repeated application is idempotent; it never toggles a bit.

### Shared integration
Add a distinct `isinstance(transform, BitUpdate)` branch in `_create_update_pkg`, before the existing transform handling:
1. Retrieve existing component state without creating a component record.
2. Under `state.synchronizer`, read the mapped field from `state.comp_data` and apply the helper.
3. If state, component data, or a valid byte is unavailable, return `None` with an appropriate diagnostic, following the existing missing-state logging convention.
4. Serialize the result through the existing `CompDataHandler` and return the normal `UpdatePkg`.

Package construction remains nonmutating. Ordinary transforms still receive command data, speed encoding retains its special handling, and `RESET` still writes its explicit zero without requiring a previous status byte.

Enable the map entries:
```python
"FORWARD_DIRECTION": [("soft_status", BitUpdate(bit=0, enabled=False))],
"REVERSE_DIRECTION": [("soft_status", BitUpdate(bit=0, enabled=True))],
```
Neither public update method needs a signature change. `BaseReq.update_eng`, `do_update_field`, and `updates_to_reqs` continue using their existing transport and refresh paths.

### Boundary
This preserves the other bits in the **cached byte**; it is not an atomic read-modify-write on the Base 3. Retain the existing refresh strategy rather than introducing a query/retry subsystem or silently defaulting missing status to zero.

# Testing

### Automated coverage
Extend `tests/db/test_comp_data.py` using its existing `isolated_state_store`, mocking, and parameterization patterns.

- Exercise all byte values and bit positions: only the selected bit changes, set/clear is idempotent, and invalid inputs are rejected.
- Verify both update entry points produce one `soft_status` package at `0x0B`, length `1`, for TMCC1/TMCC2 engine and train commands.
- Include `0x00`, `0x01`, mixed high bits, and `0xFF`; confirm packet generation does not mutate cached state.
- Verify missing state, missing component data, and unavailable status produce no write; confirm reads occur under the state lock.
- Exercise existing Base-memory and D4 serialization using representative addresses.
- Preserve direction-reader tests and regression coverage for `RESET`, speed, smoke, and RPM/labor.

### Required checks during implementation
Run `../bin/python -m ruff format --check <changed Python files>`; format and recheck if needed. Then run `../bin/python -m pytest`.

This planning session does not modify files or run tests.

# Delivery Steps

### ✓ Step 1: Add a reusable bit-update callable
`BitUpdate` can set or clear any status-byte bit without changing the others.

- Add the immutable callable in `src/pytrain/db/comp_data.py` with `bit` and `enabled` parameters.
- Implement mask-based set/clear logic and byte/bit validation.
- Add focused tests in `tests/db/test_comp_data.py` for preservation, all bit positions, idempotence, and invalid inputs.

### ✓ Step 2: Connect direction mappings to stored status
Both update entry points generate direction packages from the current status byte.

- Add explicit `BitUpdate` handling to `_create_update_pkg`, using the existing state lookup and synchronization pattern.
- Skip unsafe writes when the current byte is unavailable; do not mutate cached state while constructing packages.
- Enable forward-clear and reverse-set entries in `REQUEST_TO_UPDATES_MAP` while preserving existing transform behavior.
- Add integration coverage for both entry points, command syntaxes, scopes, missing-state handling, and Base-memory/D4 serialization.
- Run the required formatting checks and full unit suite.