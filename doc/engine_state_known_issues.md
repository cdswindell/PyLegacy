# EngineState / CompData — open findings

Review of `src/pytrain/db/engine_state.py` and `src/pytrain/db/comp_data.py`, plus the two
call sites in `src/pytrain/db/component_state.py` and `src/pytrain/pdi/base_req.py` that the
review reached through them.

- **Baseline:** `c07c46b4`, a clean working tree. Line numbers are against that commit and were
  re-measured for this revision.
- **Method:** every finding below was measured by driving the real classes — a `BASE_MEMORY`
  response built by `BaseReq`, serialized, and parsed back by `PdiReq.from_bytes` — not by
  reading alone.
- **Characterization tests:** `tests/db/test_engine_state.py`,
  `tests/db/test_engine_state_core.py`, `tests/db/test_comp_data.py`,
  `tests/db/test_component_state.py`, `tests/pdi/test_base_req.py`,
  `tests/protocol/test_constants.py`. Where a finding is pinned, fixing it is a deliberate,
  visible change to the named test.

| severity | meaning |
|---|---|
| high | wrong state a user sees, or an exception on a reachable path |
| medium | wrong state on a narrower path, or a shape that breaks a consumer |
| low | cosmetic, or unreachable on today's call graph |

## Closed since the previous revision of this document

| # | finding | fix as landed |
|---|---|---|
| 19 | on a TMCC engine, Base smoke levels 2 and 3 rendered as *off* | `engine_state.py:1252` — any non-zero level is now `SMOKE_ON` |
| 24 | the record's own `smoke_tmcc` getter rendered those levels as *off* too | `comp_data.py:37-42` — `BASE_TO_TMCC1_SMOKE_MAP` now sends 1, 2 **and** 3 to `SMOKE_ON`, and the write direction at `:44-47` is declared outright rather than inverted from it |
| 12 | `195` versus `199` for an unset Legacy limit | `engine_state.py:513` — `decode_speed_info` now answers `199`, agreeing with `speed_max` and `speeds` |
| 17 | the missing-record guards returned `None` against a `-> bool` annotation | `engine_state.py:1011-1073` and `is_cab1` at `:1396-1400` — each rewritten as an explicit `if self.comp_data: … return False` |
| 20 | a first record could overrule a direction the operator had already set | `engine_state.py:549` — the block now also requires `self._direction is None` |
| 22 | `comp_data.is_active` passed as a bound method, so `_empty` was never `True` | `component_state.py:464` — `comp_data.is_active()` |
| 23 | `BaseReq._empty` inverted relative to its own comment | `base_req.py:460-465` — the `True`/`False` arms swapped |
| B | the stop-target rewrite | `engine_state.py:544` — declared intentional and restated: `if not self.is_ramping and self.speed is not None and not self.target_speed` |

Eight items, seven of them defects. Details of what each now does, and the tests that state it,
are in *Fixed* at the foot of this document.

## Working tree, not findings

Nothing outstanding, and nothing uncommitted: every fix listed above is in `c07c46b4`. Both
items this section carried are resolved — the two debug `print` calls, one inside `__repr__`
and one in the smoke branch of `_update_state`, both writing to the stdout the curses display
and the GUI share, are gone, as is the `BASE_TO_TMCC1_SMOKE_MAP` import the 19 fix left unused
(`ruff check` reported `F401`). The map itself is still live in `comp_data.py:973`, and now
answers for every level the record can hold.

---

## Open

### 16. The one-shot direction flag is spent even when there was nothing to initialize — high

`src/pytrain/db/engine_state.py:546-553`

```python
            if not self._initialized:
                self._initialized = True
                # initialize direction from soft status
                if self._direction is None and self.comp_data and isinstance(self.comp_data.soft_status, int):
                    if self.comp_data.is_forward:
                        self._direction = TMCC2.FORWARD_DIRECTION if self._speed_is_legacy else TMCC1.FORWARD_DIRECTION
                    elif self.comp_data.is_reverse:
                        self._direction = TMCC2.REVERSE_DIRECTION if self._speed_is_legacy else TMCC1.REVERSE_DIRECTION
```

The 20 half of this block is fixed — a direction command is now the authority. What remains is
that `_initialized` is still set **before** the guard is evaluated. A first record that never
reached offset `0x0B` leaves `soft_status is None`, so no direction is set — and no later
record can set one, because the flag is already spent.

**Measured:** an 8-byte record followed by a complete record carrying `soft_status = 1` leaves
`direction` at `None`.

**Symptom:** one runt packet at startup and the engine shows `--` for direction for the rest of
the session, until an operator sends a direction command.

**Fix** — spend the flag only when the byte was usable:

```python
            if not self._initialized and self._direction is None and self.comp_data:
                soft_status = self.comp_data.soft_status
                if isinstance(soft_status, int):  # a short record has no byte at all
                    self._initialized = True
                    if self.comp_data.is_forward:
                        ...
```

**Pinned** by `test_a_runt_first_record_spends_the_one_chance_to_read_the_direction`
(`tests/db/test_engine_state_core.py`, in `TestEngineStateKnownDefects`).

Housekeeping while in there: `_initialized` lives on `ComponentState`
(`component_state.py:115`) and this block is its **only** use anywhere in the codebase.
`_direction_initialized`, declared on `EngineState`, would say what it is for.

> **`0xFF` is not treated as a defect.** An earlier revision proposed skipping
> `soft_status == 0xFF` on the grounds that it is the never-written marker elsewhere in the
> record. Per the owner: `0x00` is what both PyTrain and Lionel write for a new record, and
> `0xFF` may well be a legal value the Base 3 sends — so **no `0xFF` guard**. Documented
> behavior, therefore: bit 0 of `0xFF` is 1, so a record carrying `0xFF` initializes the
> engine to **reverse**. Stated by
> `test_engine_data_reads_bit_zero_of_a_soft_status_with_every_bit_set` in
> `tests/db/test_comp_data.py`. Revisit only if hardware evidence says `0xFF` means "not set"
> for this byte.

### 13. `is_legacy` reads `self.address > 99` before checking the address exists — medium

`src/pytrain/db/engine_state.py:1407-1409`

```python
    def is_legacy(self) -> bool:
        # Determines legacy status based on scope and type
        if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN} and self.address > 99:
```

**Measured** on an addressless `EngineState` (and `TrainState`): `is_legacy`, `is_tmcc`,
`syntax`, `rr_speed`, `speed_max`, `speeds` and `smoke_level` all raise
`TypeError: '>' not supported between instances of 'NoneType' and 'int'`. It is the last
property family that does not survive an empty state after the 6 and 17 passes.

**Symptom:** not reachable in production — the address is set at construction on every real
path — but `repr` and the property family are exactly what you reach for while debugging that
case.

**Fix:** `and self.address is not None and self.address > 99:`.

**Pinned** by `test_a_state_with_no_address_cannot_report_its_protocol_flavor`
(`tests/db/test_engine_state_core.py`), parametrized over all six properties.

Worth noting separately: this property **mutates** `self._is_legacy` as a side effect of being
read.

### 14. A 4-digit engine cannot be serialized before its D4 mapping arrives — medium

`src/pytrain/db/engine_state.py:966-969`

```python
        else:
            pdi_cmd = PdiCommand.D4_ENGINE if self.scope == CommandScope.ENGINE else PdiCommand.D4_TRAIN
            pdi = D4Req(self.record_no, pdi_cmd, state=self)
        packets.append(pdi.as_bytes)
```

`record_no` is `self._d4_rec_no`, `None` until a `D4Action.MAP` arrives.

**Measured** on engine 1234 with a full record: `as_bytes()` →
`TypeError: int() argument must be … not 'NoneType'`; with `_d4_rec_no = 17` it returns its
packet.

**Symptom:** a client that syncs in that window gets an exception instead of the state the
Base has already reported.

**Fix:** do not build the record packet until it can be addressed, and let the command packets
below still go out —

```python
        if self.tmcc_id is not None and self.tmcc_id <= 99:
            packets.append(BaseReq(...).as_bytes)
        elif self.record_no is not None:
            packets.append(D4Req(self.record_no, pdi_cmd, state=self).as_bytes)
```

**Pinned** by `test_a_four_digit_engine_cannot_be_serialized_before_its_record_number_arrives`
(`tests/db/test_engine_state_core.py`).

### 21. A train record with no usable id cannot be re-serialized — medium

`src/pytrain/db/comp_data.py:1072-1078`

```python
    def as_bytes(self) -> bytes:
        if self.scope == CommandScope.TRAIN and self.tmcc_id > 99:
            comp_map = BASE_MEMORY_D4_TRAIN_READ_MAP
        else:
            comp_map = SCOPE_TO_COMP_MAP.get(self.scope)
        schema = {key: comp_map[key] for key in sorted(comp_map.keys())}
        if self.tmcc_id <= 99:
```

This is **not** the withdrawn bug 9. The parse/serialize asymmetry is correct by design (see
*Withdrawn* below); what is left is the invariant's precondition — that every record arriving
on the D4 channel carries an id greater than 99. When it does not, parse takes the D4 map and
`as_bytes` takes the standard one, and the failure is an exception rather than a wrong byte,
because the D4 map never set `_lighting` and the standard map insists on writing it.

**Measured:**

```
D4 train record, 0xB8 = "0021"      -> tmcc_id 21,  flags read from 0x6D,  as_bytes() AttributeError
D4 train record, 0xB8 = 0xFF filler -> tmcc_id 0,   as_bytes() AttributeError
        AttributeError: 'NoneType' object has no attribute 'to_bytes'
```

The plausible way in is the second: an **empty or never-written D4 slot** decodes
`0xFFFFFFFF` at `0xB8` to `0`. Whether such a record can reach `as_bytes()` at all depends on
whether the D4 scan keeps inactive records around — see *Owner decisions*. Both lines also
raise `TypeError` when `tmcc_id` is `None`.

**Fix** — extend the existing discriminator to the "no usable id" case the parse side already
treats as D4, rather than introducing a second predicate:

```python
        if self.scope == CommandScope.TRAIN and (self.tmcc_id is None or self.tmcc_id > 99):
```

**Pinned** by `test_a_record_from_the_d4_channel_needs_a_four_digit_id_to_be_written_back`
(`tests/db/test_comp_data.py`), which sits directly under the two round-trip tests that state
the invariant, so the precondition and the invariant are read together.

A one-line comment at `comp_data.py:906` would also help: the `tmcc_id is None` test there
means "only the base memory channel supplies an id; a D4 record carries its own at `0xB8`".
It reads as a bug to anyone who has not traced both callers.

### 18. The `__repr__` early return formats a `None` address — low

`src/pytrain/db/engine_state.py:249-252`, and the identical fallback at `:320-321`

```python
        if self.comp_data is None:
            return f"{self.scope.title} {self._address:04}: no information provided from Base 2/3"
```

`{None:04}` raises `TypeError`, so `repr()` on a state built but not yet addressed throws
instead of saying it knows nothing. **Measured** on `EngineState(CommandScope.ENGINE)`.

**Fix:** `addr = f"{self._address:04}" if self._address is not None else "????"`, interpolated
in both places.

**Pinned** by `test_a_state_with_no_address_cannot_say_that_it_knows_nothing`
(`tests/db/test_engine_state_core.py`).

---

## Owner decisions pending

**Does the Base 3 fill byte `0x44` (control type) for a *train* record?** Since the bug-4 fix,
a 1-99 train with no control type answers TMCC — a 31-step ceiling and TMCC1 syntax.
`BASE_MEMORY_TRAIN_READ_MAP` is `BASE_MEMORY_ENGINE_READ_MAP.copy()` (`comp_data.py:373`), so
the field's presence is not evidence that the Base populates it. If trains come back `0xFF`
there, the head engine is the fallback to add (`self.head.is_legacy`, with a guard —
`ComponentStateStore.get_state` raises when the store has not been built).

**The commented-out map entries** — `comp_data.py:500-501`

```python
    # "FORWARD_DIRECTION": [("soft_status", )],
    # "REVERSE_DIRECTION": [("soft_status",)],
```

As it stands a direction command never writes the byte back, so `comp_data.soft_status` goes
stale against `_direction`, and `as_bytes()` ships the stale byte at `0x0B` to clients and the
cache — where a rebuilt state initializes its direction from it. `RESET` does zero it
(`comp_data.py:513`), so the intent reads as "the byte is the Base's, `_direction` is ours".
Deliberate, or should the entries come back? This is 16's blast radius.

**Do inactive D4 records reach `as_bytes()`?** Decides whether 21 is reachable in practice.

**Is bit 0 of `soft_status` really the direction bit?** Nothing in the repo documents byte
`0x0B`; `payload()` does not render it, and `__repr__` only shows the derived `FWD`/`REV`. Only
bit 0 is read — measured, values 2 and 3 behave exactly like 0 and 1 — so anything structured
above bit 0 is currently invisible. The CLI can settle it without new code
(`src/pytrain/cli/pytrain.py:1534-1540`):

```
pdi m 7 eng 0x0B 1      # read one byte at 0x0B for engine 7
<reverse engine 7 from a Cab remote>
pdi m 7 eng 0x0B 1      # did bit 0 flip?
```

A one-byte read comes back with `data_length == 1`, which `base_req.py:445` will not turn into
a `comp_data` record, so the probe cannot disturb the state being watched.

---

## Fixed

| # | finding | where |
|---|---|---|
| — | `is_aux1` read `_aux2` | `engine_state.py:1381` |
| — | `TMCC1.REVERSED_DIRECTION` (nonexistent enum) on the direction-init path | `engine_state.py:553` |
| 1 | `is_forward` / `is_reverse` raised on a short record | `comp_data.py:1173-1179`, tri-state now |
| 2 | speed written on one scale, read back on another | `_speed_is_legacy`, `engine_state.py:887-890` |
| 3 | `is_tmcc` and `is_legacy` could both be `True` | `engine_state.py:1402-1404` |
| 4 | `TrainState` hard-coded Legacy | `engine_state.py:1464-1467`, `:1656-1660` |
| 5 | TMCC1 numeric 9 recorded smoke *off*; bare `SMOKE_ON` recorded nothing | `TMCC1_SMOKE_MAP`, `TMCC_TO_BASE_SMOKE_MAP` |
| 5 | and the Base 3 write the keypress should produce never went out | the ten `AUX_NUMBER_*` members removed from `TMCC1EngineCommandEnum` |
| 6 | properties that assumed a record existed | the `if self.comp_data:` family, `engine_state.py:1075-1238` |
| 7 | `TrainState.as_dict` crashed without a consist | `engine_state.py:1678` (`else {}`) |
| 8 | off-by-one in `CompData._parse_bytes` | `comp_data.py:1111` |
| 10 | `rr_speed` resolved only the eight band starts | `to_rr_speed(exact=False)` default, `protocol/constants.py:165` |
| 11 | the production year overwrote the road number in `__repr__` | `engine_state.py:295` |
| 12 | `195` for an unset Legacy limit against `199` elsewhere | `engine_state.py:513` |
| 17 | the missing-record guards answered `None`, not `False` | `engine_state.py:1011-1073`, `:1396-1400` |
| 19 | Base smoke 2/3 rendered as *off* on a TMCC engine | `engine_state.py:1252` |
| 24 | and the record's own getter did the same | `comp_data.py:37-47`, the read map extended and the write direction declared outright |
| 20 | a first record overruled the operator's direction | `engine_state.py:549` |
| 22 | `comp_data.is_active` tested as a bound method | `component_state.py:464` |
| 23 | `BaseReq._empty` inverted against its comment | `base_req.py:460-465` |

### What the tests now say

- **5** — the write half, found after this document was first written. A TMCC1 numeric also
  asks the server for a full record refresh (`command_listener.py:62-75`), so the level only
  lasts if `0x69` was written; `REQUEST_TO_UPDATES_MAP` is keyed by command name, the alias map
  is many to one and last wins, and it answered `AUX_NUMBER_9` — so nothing was written and the
  refresh restored *off* within the debounce window of the keypress. Removing those members put
  one meaning back on one key. Both halves are now pinned:
  `test_the_tmcc1_smoke_commands_own_the_numeric_keys_they_alias`
  (`tests/protocol/test_constants.py`) holds the declaration order the fix rests on, and
  `test_a_tmcc1_smoke_keypress_writes_the_base_smoke_byte` (`tests/db/test_comp_data.py`) holds
  the write — one byte at `0x69`, `01` for on and `00` for off — for all four keypress forms.
  Proven to catch the regression it names: declaring a rival `(NUMERIC, 9)` member below
  `SMOKE_ON` fails both tests and the write disappears entirely, while the state-side test stays
  green, because `TMCC1_SMOKE_MAP` insulates state but nothing insulated the write path.
  `CompData.request_to_updates` had no coverage anywhere in the suite before this.
- **12** — `test_decode_speed_info_expands_the_never_set_sentinel`
  (`tests/db/test_engine_state_core.py`) and `test_decode_speed_info_255_conversion`
  (`tests/db/test_engine_state.py`) assert `199`, and the first also asserts that
  `decode_speed_info(255)` and `speed_max` agree — the property the split violated, rather
  than just the new number.
- **17** — `test_a_capability_flag_with_nothing_to_report_is_not_claimed` asserts
  `is False`, not merely falsy, across all twelve flags including `has_lights` and `is_cab1`.
- **19** — the pin `test_a_tmcc_engine_renders_the_upper_smoke_levels_as_off` is gone;
  `test_a_tmcc_engine_reports_any_smoke_level_as_on` walks levels 1, 2 and 3 and
  `test_a_tmcc_engine_reports_the_base_level_of_zero_as_off` holds the other end. Proven to
  catch a return to the map form: reverting `engine_state.py:1252` fails both of the upper
  levels.
- **24** — the pin `test_engine_data_reads_the_upper_smoke_levels_as_off_without_a_legacy_record`
  is gone; `test_engine_data_reads_any_smoke_level_as_on_without_a_legacy_record` walks 0, 1, 2
  and 3. Extending the read map made it many to one, so the write direction could no longer be
  the inversion of it — that took `SMOKE_ON` to whichever level was declared last. Measured
  while the fix was landing: a TMCC1 keypress recorded 3 while the Base 3 was written `0x01`,
  so a Legacy engine driven from a CAB-1 read back **high** and then snapped to **low** as soon
  as the Base answered. `TMCC1_TO_BASE_SMOKE_MAP` is now declared outright
  (`comp_data.py:44-47`) rather than derived, which states the two entries the write direction
  has instead of leaving them to fall out of the other map, and
  `test_a_tmcc1_smoke_level_is_stored_as_the_value_the_base_3_is_written`
  (`tests/db/test_comp_data.py`) states the invariant it rests on rather than the value: the
  level the record stores must equal the byte `request_to_updates` sends. Proven to catch the
  regression — putting the inverted comprehension back fails it with `assert 3 == 1`, along
  with seven other smoke tests.
- One residual, not a finding: a TMCC-flavored state can only replay `SMOKE_ON`, which resolves
  to 1, so a client syncing a record that holds 2 or 3 stores 1 (measured). The record packet in
  `as_bytes` carries the true byte and the smoke command that follows it overwrites it. Harmless
  today — the state renders any non-zero level as *on* either way — and strictly better than
  before 19, when that client stored 0.
- **20** — `test_a_direction_command_is_not_overruled_by_a_later_first_record`, beside the
  three tests that state what a first record *is* allowed to do.
- **B** — three tests in `TestEngineStateCommandHandling`: a record supplies a target for an
  engine already moving, leaves a standing engine at zero, and leaves the target alone while a
  ramp owns it. The consequence the owner accepted is in the first of those: an engine coasting
  down under momentum toward a stop has its target pushed back up to its current speed.
- **22** and **23** — `tests/db/test_component_state.py` and `tests/pdi/test_base_req.py`,
  which had no coverage of the empty-record path at all before this round.

The 22 fix re-opens a path that had been dead: a state holding an empty roster slot now
answers `is_comp_data_empty is True`, so `_prepare_update` (`component_state.py:315-320`)
enters its "ask the Base for a configuration record" branch again. `request_config` is guarded
by `self._config_requested` (`:361`, `:374`), so it sends at most one request per state, and
`initialize` is skipped because `is_comp_data_record` is already `True` — but it is the one
behavior change of that one-liner worth watching on live hardware.

## Withdrawn / downgraded

**9 — the D4 train map asymmetry is correct by design.** The parse side
(`comp_data.py:906`) is not asking "is this id 4-digit?" but **"was an id supplied at all?"**,
and only one of the two channels supplies one:

| channel | construction site | id | map |
|---|---|---|---|
| D4 | `d4_req.py:68` — `CompData.from_bytes(data_bytes, self.scope)` | not passed | `BASE_MEMORY_D4_TRAIN_READ_MAP` |
| base memory | `base_req.py:453` — `…, tmcc_id=self.tmcc_id)` | the record-number byte | standard |

A D4 record then supplies its own id at `0xB8` (`comp_data.py:355-361`), and `_parse_bytes`
only decodes a field that is still `None` — so `0xB8` is read precisely when no id was passed
in. The two predicates are two views of one fact. Round-trip verified in both directions by
`test_a_four_digit_train_record_is_read_and_written_with_the_d4_layout` and
`test_a_two_digit_train_record_is_read_and_written_with_the_standard_layout`
(`tests/db/test_comp_data.py`), which exist so that a future "cleanup" of the asymmetry has to
break a test to land. What remains is item **21** above, the precondition.

**A — `SHUTDOWN_SET` / `RESET_SET` tuple members.** Direct match is indeed impossible
(`command.command` is a bare enum, the member is a tuple), but the effects route covers them:

```
TMCC2 RESET       direct reset False/True   effects {…, (NUMERIC,0), …}  -> reset fires
TMCC2 NUMERIC 5   direct shutdown False     effects {(NUMERIC,5), NUMERIC} -> is_started True->False
TMCC1 NUMERIC 5   no shutdown  (correct: TMCC1 shutdown is AUX1 + 5, see TMCC1_AUX_ONE_PREFIX_MAP)
```

Dead weight in the sets, not a defect. `SPEED_SET` carries its `(ABSOLUTE_SPEED, 0)` tuples for
the same reason.

**15 — `0xFF` soft status reading as reverse.** Withdrawn at the owner's direction: `0xFF` may
be a legal value from the Base 3, so no guard. See the note under 16.

**B — the stop-target rewrite.** Declared intentional by the owner and restated in the code
(`engine_state.py:544`): a record carries no target of its own, so `target == 0` is read as
"never set" and filled in from the current speed. The rewrite also narrowed the guard from
`if self.speed` to `if self.speed is not None`, which only adds the standing-engine case, where
the write is a no-op. Not a defect; the accepted consequence is documented by the tests listed
above.

---

## Suggested order

**16** (startup-visible, and the only high left) → **13 + 14 + 21** (the "guard your inputs"
family) → **18**.
