---
sessionId: session-261020-175649-1ww9
---

# Requirements

### Goal
Resolve the harmless PyCharm warnings identified in `base_req.py` by correcting annotations and type inference, without changing runtime behavior. Leave missing-state and 4D-mapping risks untouched and provide concrete recommendations for a separate fix.

### Scope and Acceptance
- Correct misleading helper contracts, nullable numeric-field inference, and the types describing the existing mixed request/state refresh flow.
- Resolve the safe portion of the store-state and outbound-address warnings only under documented existing invariants; do not pretend this validates incomplete state or arbitrary scopes.
- Preserve packet bytes, lookup arguments, return values, rounding, defaults, callback order, refresh scheduling, and exception behavior. No new dependencies, new subsystem, or shutdown changes.
- Do not add guards, fallback addresses, new exceptions, or broad suppressions to hide the deferred runtime issues. Remaining risk warnings must be reported rather than treated as a failed cleanup requirement.
- Retain all completed target-speed and validity-helper regression tests without weakening assertions or adding skips/xfails.

### Completed Work Retained
The earlier parsing, serialization, validity-helper, and harmless-warning cleanup stages are complete. Coverage includes 2D/4D engines and trains, both directions of record-number/TMCC-ID lookup, `_set_valid()`/`_clear_valid()`, encoding defaults, numeric conversions, and mixed request/state dispatch. The last recorded full-suite result was **7,876 passed, 35 skipped, 0 failed**; this is historical, not verification of the user's subsequent guard changes. The current follow-up is an inspection-only reevaluation of `BaseReq.updates_to_reqs()` (called `update_to_requests` in the request); no new implementation is authorized by this review.

# Technical Design

### Current Reevaluation: `updates_to_reqs()`
Current PyCharm inspection reports two warnings in this method, at `base_req.py:268` (`tmcc_id`) and `:282` (`state.record_no`), plus a separate warning in `do_update_field()` at `:333`. No errors were reported. Source review confirms the `state.tmcc_id is not None` guard and the latest record assertion, `assert state.record_no is not None and 0 <= state.record_no < 0xFFFF` at line 278. For the declared integer-or-None contract, this now rejects `None`, negative values, the `0xFFFF` sentinel, and all oversized records; accepted values are `0` through `0xFFFE`. The previous upper-bound concern is resolved, consistent with `D4Req.as_bytes` encoding the record as two unsigned little-endian bytes at `d4_req.py:218`.

`ComponentState.tmcc_id` and `EngineState.record_no` correctly return `int | None`. The current code checks a property and then reads it again; PyCharm still treats the later value as nullable. Recommend checking and using the same local snapshot, following the existing pattern in `ComponentState.prev_link`/`next_link`:
- Preserve the empty-package/absent-state short circuit, then assign `tmcc_id = state.tmcc_id`; return `[]` if that local is `None`. Use the checked local in the existing `1 <= tmcc_id <= 100` routing and `BaseReq` constructor.
- Inside the existing D4 branch, assign `record_no = state.record_no`, apply the current assertion to that local, and pass the same local to `D4Req`. This removes repeated property reads without hiding optional values behind casts or suppressions.
- Preserve the special direct-address boundary `100`, the mapped record number rather than the 4D TMCC ID, package order, and optional refresh marker. Keep record validation within the D4 path so direct updates do not require a D4 mapping.
- Do not change the property return types to `int`, broaden constructor inputs to accept `None`, or add a blanket inspection suppression.

The tightened assertion now covers the full record encoding/sentinel range for stable integer state with assertions enabled. The remaining runtime-validation caveat is that assertions disappear under `python -O`; the range itself no longer needs tightening. As a separate runtime-hardening recommendation, use the same checked local with an explicit `if record_no is None or not 0 <= record_no < 0xFFFF: raise ValueError(...)`. This is an encoding/sentinel constraint, not proof that a mapping exists in the Base. Invalid TMCC IDs outside the intended address domain also still enter the D4 `else` branch; the method assumes a valid initialized engine/train state.

The guard here does not protect `do_update_field()`: that caller reads `state.tmcc_id` and evaluates `state.is_legacy` before invoking this method. Its warning remains a separate runtime-risk recommendation. The latest PyCharm inspection confirms that all three nullable-value warnings remain after the user's range edit; no errors were reported. Only review notes in this plan were changed; no production/test files were modified and no tests were run. The proposed local-variable cleanup has not been implemented or verified.

If these localized recommendations are implemented later, retain `test_updates_to_reqs_preserves_requests_and_refresh_marker()` for both scopes, addresses `7`, `100`, and `1234`, empty packages, and both refresh settings. Add focused missing-ID/invalid-record cases only alongside their corresponding behavior changes, then follow the verification requirements below.

### Pre-Cleanup Findings
The earlier audit reported 15 warnings and no errors. The following findings and implementation design record the rationale for the already-completed cleanup; the current reevaluation above supersedes the older assessment of `updates_to_reqs()`:
- `CompData.request_to_updates()` initializes and returns a list; `field_to_updates()` follows the same pattern.
- `PdiReq.encode_text()` already handles `None` and returns bytes on every successful path.
- `BaseReq.encode_throw_rate()` already handles `None` and always returns an integer, defaulting to `9`.
- Numeric fields start as `None` and later receive integers from parsed records. `EngineData.__init__()` already uses explicit `int | None` declarations, providing the local pattern to follow.
- `updates_to_reqs()` produces `BaseReq` or `D4Req` objects and optionally appends a state; both request classes share `PdiReq`. `process_sync_reqs()` already separates `ComponentState` refresh markers from sendable requests.
- The refresh manager's `StateT` is unnecessarily restricted to engine/train types, although existing GUI callers refresh other component states. Its type-only import pattern avoids circular runtime imports.

### File Scope
| File | Planned changes |
| --- | --- |
| `src/pytrain/pdi/base_req.py` | Helper annotations, four nullable numeric fields, documented local type narrowing, and mixed request/state annotations. |
| `src/pytrain/pdi/pdi_req.py` | Correct `encode_text()` annotations only. |
| `src/pytrain/db/comp_data.py` | Correct list-return annotations for the two update-package helpers. |
| `src/pytrain/pdi/base3_db_refresh_manager.py` | Correct the existing type-only `StateT` definition to represent `ComponentState`. |
| `tests/pdi/test_base_req.py` | Focused behavior-preservation coverage for helper defaults, numeric conversion/display, and mixed dispatch. |
| `tests/pdi/test_pdi_req.py` | Extend text-encoding cases and remove the now-unnecessary type-checker suppression from the normal encoding test. |

Reuse `tests/db/test_comp_data.py` for existing empty/nonempty package-list coverage; no new files or edits to the generic state store are planned.

### Helper and Numeric Contracts
Use these signatures without changing their implementations:
```python
CompData.request_to_updates(cls, req: R) -> list[UpdatePkg]
CompData.field_to_updates(
    cls, field: str, tmcc_id: int, scope: CommandScope = CommandScope.ENGINE,
    data: Any = None, legacy: bool = True,
) -> list[UpdatePkg]
PdiReq.encode_text(text: str | None, field_len: int) -> bytes
BaseReq.encode_throw_rate(data: float | None) -> int
```
This addresses the list-extension warnings near lines 191/201 and encoding warnings near lines 950/951 without widening missing-ID parameters to accept `None`.

Explicitly declare `_train_brake`, `_momentum`, `_fuel_level`, and `_water_level` as `int | None` in `BaseReq.__init__()`, splitting only the affected chained assignments. For the conversion warnings near lines 678/689, use a typed local value consistently for the guard and calculation if needed. Preserve `None`, zero, the existing multipliers, `round()`, and the cap of `7`. Keep fuel/water guards and percentage formatting near lines 870/871 unchanged; do not introduce float coercions or substitute zeros for absent data.

### Existing State and Request Contracts
- Annotate the request-producing methods `update_eng()`, `updates_to_reqs()`, `do_update_eng()`, and `do_update_field()` and their accumulators as lists of `PdiReq | ComponentState`. They return lists, including empty lists, rather than `None` on successful paths.
- Describe `process_sync_reqs()` input as `Sequence[PdiReq | ComponentState]` and its callback as `Callable[[PdiReq], Any]`. This read-only input contract accepts existing homogeneous request lists without list-invariance problems; dispatch logic remains untouched.
- In the refresh manager, bind `StateT` to `ComponentState` under `TYPE_CHECKING`, retaining its runtime fallback and the existing optional bucket state. Do not narrow refresh dispatch to engines or change debounce/thread behavior.
- At the `update_eng()` call near line 213, use a narrowly documented `cast(EngineState, cur_state)` for the established initialized engine/train store contract, following existing `cast(EngineState, state)` usage in `CompData._create_update_pkg()`. Keep `updates_to_reqs()`'s engine-state requirement; this annotation is not runtime validation and must not be described as making arbitrary scopes or incomplete states safe.
- At the outbound lookup near line 927, use a documented local `cast(int, self._record_no)` only after the original-bytes early return. Non-byte construction assigns `int(data)`; incoming requests return their original bytes. Keep the public nullable `record_no` contract, and do not cast the lookup result's optional record number or suppress the adjacent missing-mapping risks.
- Prefer truthful annotations over suppressions. Do not add class-wide `PyTypeChecker` suppression, blanket `Any`, or runtime assertions solely to satisfy inspections.

### Existing Flow, Unchanged
The cleanup describes this existing flow; it does not add a pipeline or alter module responsibilities.
```mermaid
graph LR
    Packages[CompData packages] --> Requests[BaseReq request list]
    Requests --> Dispatch[process_sync_reqs]
    Dispatch -->|PdiReq| Callback[Send callback]
    Dispatch -->|ComponentState| Refresh[Refresh manager]
```

# Deferred Runtime Risks

### Recommendations Only — Do Not Implement
The `updates_to_reqs()` and `do_update_field()` references were refreshed during this review; the separate `as_bytes` finding is retained from the earlier audit and was not reinspected here.

| Location | Risk left unchanged | Suggested follow-up fix |
| --- | --- | --- |
| `BaseReq.updates_to_reqs()`, lines 259–282 | The checks reject missing TMCC IDs and, with assertions enabled, require D4 records in `0..0xFFFE`. The upper-bound issue is resolved. Repeated nullable property reads still trigger warnings; assertions can be disabled under optimization, and valid initialized state IDs remain a caller contract. | Check and pass the same local snapshots to resolve the warnings. If validation must survive optimization, replace the assertion with an explicit check of the same range and a descriptive exception; retain mapped-record semantics. |
| `BaseReq.do_update_field()`, lines 330–335 | Truthiness does not establish initialized state; missing identity can fail before or during `state.is_legacy` and package creation. The later guard in `updates_to_reqs()` cannot protect this earlier call. | Validate state type, supported scope, and ID before reading dependent properties or generating updates. Define a consistent caller-facing failure policy rather than substituting an ID. |
| `BaseReq.as_bytes`, lines 927–930 | An absent/non-D4 lookup result omits record bytes yet still emits a framed packet; a missing record number raises during serialization. | Validate the lookup result and mapped record before assembling the packet. Prefer a descriptive failure over sending an incomplete packet; never serialize the 4D TMCC ID as a substitute for the record number. |

A future runtime-fix task should cover absent IDs, absent/non-D4 lookup results, missing/sentinel/out-of-range records, and ensure no malformed packet is sent. Do not add knowingly failing tests for those unfixed behaviors in this cleanup. Normal initialized engine/train assumptions do not establish safety for arbitrary component scopes.

# Testing

### Behavior-Preservation Checks
- Extend the existing text-encoding test for `None`, empty/whitespace text, and padded ASCII, asserting exact bytes. Remove its obsolete `PyTypeChecker` suppression once the corrected signature makes it unnecessary.
- Add compact parameterized `encode_throw_rate()` tests for `None`, mapped values, and unmapped values, preserving default `9`.
- Cover brake/momentum `None`, zero, representative values, and the existing cap; verify fuel/water omission for absent data and unchanged percentage text for zero, intermediate, and full values. Prefer independent parsed records over protected field mutation.
- Add isolated mixed-list tests proving requests reach the callback in order and component-state markers reach the refresh manager, including a route state. Cover empty input and `refresh=False`; stub refresh requests and asynchronous thread creation so no worker or hardware connection starts.
- Exercise initialized engine and train update paths for direct and 4D requests, including appended refresh markers. Retain all existing exact-wire and reverse-lookup assertions and validity-mask regressions.
- Reuse `tests/db/test_comp_data.py` tests for empty and populated package lists rather than duplicating their extensive matrices.

### Verification During Implementation
- Consult the Python environment guidance and confirm the configured PyCharm interpreter before running Python toolchain commands.
- Run every new/modified test and the relevant existing suites with `../bin/python -m pytest tests/pdi/test_base_req.py tests/pdi/test_pdi_req.py tests/db/test_comp_data.py`.
- Run `../bin/python -m ruff format --check <changed Python files>`; if needed, format those files and repeat the check. Run Ruff lint on the changed files as well.
- Inspect all changed production files and each entire modified test file with PyCharm, including warnings and weak warnings where supported. Resolve all in-scope findings and rerun inspections; report deferred runtime findings separately rather than suppressing them.
- Use only narrowly scoped, explained inspection-specific suppressions for genuinely necessary test operations. Review names, comments, docstrings, and assertions for American English.
- Run the full suite with `../bin/python -m pytest`. Report actual results, remaining warning locations, and anything not verified; do not reuse historical pass counts as current evidence.
- The completed cleanup subsequently confirmed that PyCharm could report weak warnings. Continue inspecting warnings and weak warnings and report any current tooling limitation; do not reuse past clean results as verification of later edits.

# Delivery Steps

### ✓ Step 1: Correct helper contracts and nullable numeric inference
Harmless list, text, throw-rate, and numeric-conversion warnings are resolved without changing outputs.
- Correct update-package return annotations in `comp_data.py`, text encoding in `pdi_req.py`, and throw-rate encoding in `base_req.py`.
- Explicitly type the four nullable numeric fields and consistently narrow values used by the existing conversion calculations.
- Extend `test_pdi_req.py` and `test_base_req.py` with exact-output/default/nullable-value checks; remove only obsolete suppressions.
- Run the affected tests and existing package-list tests; complete formatting, PyCharm inspections, and American English checks for this slice.

### ✓ Step 2: Accurately type the existing request and refresh flow
Request/state contracts and supported-path lookup inference are corrected while runtime-risk code remains unchanged.
- Update mixed-list return, accumulator, input, and callback annotations in `base_req.py` and the type-only refresh-state definition in `base3_db_refresh_manager.py`.
- Add narrowly documented casts for the established engine/train store contract and constructed outbound-address invariant; leave optional state IDs and mapped records unsuppressed.
- Add isolated dispatch and refresh-marker coverage for initialized engine/train updates and non-engine refresh states, preserving packet and callback behavior.
- Run all affected tests and the full suite; repeat formatting, inspections, and language checks after changes.
- Report the resolved harmless findings and the untouched runtime risks with the separate validation recommendations above, including any inspection limitations.