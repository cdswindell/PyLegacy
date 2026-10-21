---
sessionId: session-261021-130700-1ie3
---

# Root Causes

### Corrected protocol diagnosis
The user confirmed that Lionel intentionally uses different transmit and receive formats for native target-speed updates. The earlier report calling the missing transmit-side `0xFF` marker a production defect is withdrawn. The receive parser does not need to accept outgoing packets as if they were Base 3 echoes.

For two-digit addresses, the unframed command bodies are:
- Controller to Base 3: `[command, tmcc_id, target_speed]` — three bytes, without `0xFF`.
- Base 3 to controllers: `[command, tmcc_id, 0xFF, target_speed]` — four bytes.
- `src/pytrain/pdi/constants.py` defines `UPDATE_ENGINE_SPEED = 0x2A` and `UPDATE_TRAIN_SPEED = 0x2B`. Framing, stuffing, and checksum bytes are additional.

### Remaining test assumptions
In `tests/pdi/test_base_req.py`:
- `SPEED_UPDATE_ADDRESSES` contains receive-side address bytes, including the short-address marker, but is reused by outbound cases.
- `assert_outbound_speed_packet()` constructs expected transmission bytes with `incoming_speed_packet()`, assumes receive-side field offsets, and feeds transmitted bytes directly to `PdiReq.from_bytes()`. This incorrectly equates the two directions.
- `test_update_speed_engine_and_train_encode_distinct()` expects marked short-address transmissions in its fixed vectors.
- Incoming and shared outbound assertions expect display text without the packet suffix. `BaseReq.payload` now includes `({self.packet})`; this is a separate stale display expectation, not a wire-format defect.

### Completed work retained
The earlier test-only implementation addressed these independent causes:
- `tests/db/test_comp_data.py`: command-derived ramp filtering differs from direct field conversion; state lookup assertions now account for read-only filter access.
- `tests/protocol/sequence/conftest.py`, `test_speed_ramp.py`, and `test_ramp_peer.py`: native broadcast and database submission are isolated and asserted separately, avoiding asynchronous call-count races and incomplete four-digit doubles.
- `tests/db/test_engine_state_core.py`: independent, marked native echoes cover target-only updates, scaling, and unchanged local ramp ownership. Synthetic-target and ordinary speed-command coverage remains distinct.

These changes remain complete and are not reopened. The historical delivery stages below are retained for continuity.

### Evidence and limits
Prior implementation results reported 7,858 passed, 35 skipped, and 137 failed, all failures in `tests/pdi/test_base_req.py`. This clarification turn uses those results and static inspection; no tests were rerun and no production or test files were changed. Do not attribute every historical failure to the marker or promise all 137 will disappear without evaluating the remaining assertions.

# Test-Only Follow-Up

### Scope
Update only `tests/pdi/test_base_req.py` in a separately approved implementation. Preserve production code, protocol behavior, ownership rules, and subsystem shutdown. This turn only corrects the diagnosis and plan; the clarification is not an instruction to implement changes now.

### Existing implementation and references
`BaseReq.as_bytes` emits unmarked short-address updates and uses a little-endian record mapping for four-digit updates. Its receive constructor recognizes marked echoes and uses `ComponentStateStore.by_record_no()` for four-digit records. `PdiReq.packet` formats constructed requests from framed bytes but parsed requests from their decoded command body.

Follow `tests/protocol/sequence/test_ramp_peer.py::test_startup_target_follows_claim_and_precedes_every_component`, which already checks outgoing bytes directly. Retain `incoming_speed_packet()` and the independently framed incoming state cases in `tests/db/test_engine_state_core.py` as receive-side references.

### Proposed changes
- Separate outgoing and incoming address expectations. Outgoing short addresses use one byte; incoming short addresses retain the marker. Keep the existing four-digit record mapping and the address-100 boundary cases.
- Rewrite `assert_outbound_speed_packet()` to check exact transmission bytes and relevant request properties without parsing them as an echo. Preserve factory/default-engine coverage and the case where current speed differs from target speed.
- Keep packet expectations independent of production serializers. If framing logic is shared, extract only a direction-neutral test helper; distinct direction-specific builders must supply the correct command bodies. Pin both builders with literal wire vectors.
- Preserve `outbound_speed_lookups` and `speed_update_lookups` boundaries: short addresses need no mapping; four-digit transmission uses forward lookup, and four-digit reception uses reverse lookup. Avoid hardware, singleton creation, and worker threads.
- Add explicit send/echo regression cases for engine and train scope. Compare transmission to its own expected frame, independently construct a marked Base 3 echo for the same address and target, and parse only that echo. Verify decoded identity, target-only validity, `speed is None`, and preservation of original received bytes through `as_bytes`.
- Update incoming display assertions to include the exact packet suffix. Derive expected packet text from independently specified bytes, not from the property being tested; do not replace equality with substring checks. Keep wire encoding and presentation failures distinguishable.

### Fixed short-address vectors
For address 7 and target 45, including framing and checksum:

| Direction | Engine | Train |
| --- | --- | --- |
| Send | `D1 2A 07 2D A2 DF` | `D1 2B 07 2D A1 DF` |
| Receive | `D1 2A 07 FF 2D A3 DF` | `D1 2B 07 FF 2D A2 DF` |

### Existing protocol flow
```mermaid
graph LR
  T[BaseReq transmission] -->|Unmarked short address| B[Base 3]
  B -->|Marked short address echo| P[PdiReq receive parser]
  P --> S[EngineState]
```
This documents the existing hardware-mediated exchange, not a new pipeline or architectural change. Local serializer-to-parser round trips do not model this exchange.

### Unrelated failures
Do not relax `test_incoming_speed_update_without_target_byte` to make malformed packets pass. Static inspection shows the current receive branch takes the last available byte as the target even for those address-only inputs; this is separate from valid send/echo asymmetry. Preserve those assertions and report any remaining failure for separate diagnosis rather than altering production code or claiming the full suite is green. The previously noted TMCC1 zero-speed ramp concern also remains outside this follow-up.

# Validation

### Coverage after approval
- Exercise engine and train commands; short addresses 1, 7, and 99; existing four-digit cases 100, 1234, and 9999; and targets 0, 45, and 199.
- Check exact framing, checksums, and direction-specific layouts. Include checksum-stuffing coverage using valid inputs; avoid fixed byte offsets that assume all frames are unstuffed.
- Retain four-digit mapping, missing mapping, malformed-packet, target-valid/current-invalid, and original receive-byte preservation assertions.
- Verify the short send/echo pair differs on the wire but identifies the same intended address and target after receiving the independently built echo.
- Keep the completed database, ramp, and state tests as regression coverage, without modifying them unnecessarily.

### Required verification
- Consult the Python environment instructions and resolve PyCharm's configured interpreter before running toolchain commands.
- Run every new or modified case and `../bin/python -m pytest tests/pdi/test_base_req.py`, followed by relevant database/sequence regressions and all unit tests with `../bin/python -m pytest`.
- Run `../bin/python -m ruff format --check tests/pdi/test_base_req.py`; if necessary, format the file and rerun the check.
- Inspect the entire modified test file with PyCharm, including warnings and weak warnings. Fix all findings and rerun inspections; use only narrowly scoped, explained suppressions for genuinely necessary operations, without weakening assertions.
- Review test names, comments, docstrings, and assertion messages for American English. Report residual failures and any verification that cannot be completed separately from successfully adapted test contracts.

No fresh execution, formatting, or inspection results are claimed for this planning-only clarification.

# Delivery Steps

### ✓ Step 1: Align database-update tests with ramp-aware filtering
Command-derived update tests distinguish active-ramp filtering from unchanged direct field conversion.
- Update `tests/db/test_comp_data.py` to separate the two API contracts and cover ramping, idle, and missing state.
- Preserve exact encoding assertions, TMCC1 zero-speed alias effects, reset behavior, and engine/train coverage.
- Replace obsolete lookup counts with correct read-only state-access assertions for speed, direction, reset, and RPM/labor cases.
- Run the affected tests, formatting checks, PyCharm inspections, and American English review after approval.

### ✓ Step 2: Separate ramp broadcast and database-write test boundaries
Ramp startup tests independently verify both side effects without accidental transport access or asynchronous call-count races.
- Adjust narrowly scoped fixtures in `tests/protocol/sequence/conftest.py` and assertions in `test_speed_ramp.py` and `test_ramp_peer.py`.
- Record and assert native broadcasts separately from `do_update_field("RAMP_TARGET_SPEED", ..., refresh=False)` calls.
- Use complete record mappings and isolated Base/D4 transport only where real database conversion is intentionally exercised.
- Preserve startup ordering, cancellation guards, failure cleanup, and ramp behavior assertions; validate these files with focused tests, formatting, inspections, and language review.

### ✓ Step 3: Cover native target broadcasts at the state boundary
State tests distinguish native target broadcasts from retired synthetic targets and ordinary speed commands.
- Extend `tests/db/test_engine_state_core.py` using independently framed, parsed native packets, referencing the patterns in `tests/pdi/test_base_req.py`.
- Verify target-only state updates, engine/train scope, speed scaling, and preservation of local ramp ownership.
- Retain existing synthetic-command and ordinary speed/target synchronization coverage.
- Complete focused tests and inspections for modified files, rerun formatting checks, and run `../bin/python -m pytest`; report unresolved failures or unavailable verification without changing production code.

### ✓ Step 4: Correct outgoing target-speed packet expectations
Outgoing tests verify Lionel's transmit format without assuming receive-side compatibility.
- Modify `tests/pdi/test_base_req.py` to separate send and receive address data and refactor `assert_outbound_speed_packet()` into a transmission-only assertion boundary.
- Correct fixed short-address engine/train vectors; retain factory, default scope, distinct-current-speed, and four-digit mapping coverage.
- Keep expected bytes independent of production code and include checksum-stuffing coverage.
- Run the affected outbound cases and formatting checks; inspect the modified file, resolve findings, and review American English.

### ✓ Step 5: Lock in marked echoes and exact display expectations
Receive tests explicitly model Base 3 echoes and preserve precise target-only and presentation contracts.
- Add send/echo regression cases in `tests/pdi/test_base_req.py`, constructing receive packets independently rather than parsing emitted short-address frames.
- Preserve marked incoming and four-digit parsing assertions; update stale `payload` expectations to include exact packet text.
- Retain malformed-packet assertions and report unrelated residual failures without production changes.
- Run all modified tests, relevant state/sequence regressions, and `../bin/python -m pytest`; rerun formatting, file-wide PyCharm inspections including weak warnings, and American English review.

### * Step 6: Update / Follow-up
Lionel will always send the target speed as the last byte of the 0x2A/0x2B commands. I have tightened the bounds checking associated with parsing the data packet for these commands. Please make sure there are tests that perform bounds checking, but do not try to test for malformed 0x2A/0x2B packets