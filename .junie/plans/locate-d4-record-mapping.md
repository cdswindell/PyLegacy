---
sessionId: session-261020-161525-1wq6
---

# Findings

### Found it in `db`
The explicit conversion is in [`src/pytrain/db/components.py:54–57`](src/pytrain/db/components.py#L54), inside `ConsistComponent.from_d4_bytes()`:

```python
rec_no = int.from_bytes(data[i + 2 : i + 4], byteorder="little")
state = ComponentStateStore.by_record_no(rec_no)
if state:
    consist_components.append(ConsistComponent(state.tmcc_id, flags, rec_no, data[0]))
```

The lookup itself is [`ComponentStateStore.by_record_no()` at `src/pytrain/db/component_state_store.py:132–137`](src/pytrain/db/component_state_store.py#L132). It searches stored engines for a matching `record_no` and returns the state, whose `tmcc_id` is the ID you want. It returns `None` when no match exists.

### Related `pdi` handling
- [`src/pytrain/pdi/d4_req.py:81–87`](src/pytrain/pdi/d4_req.py#L81): `D4Req` parses a `D4Action.MAP` response’s four ASCII address digits into `_tmcc_id`; the record number is parsed at line 56.
- [`src/pytrain/db/engine_state.py:848–854`](src/pytrain/db/engine_state.py#L848): stores the mapping’s record number in `_d4_rec_no`, exposed through `record_no`.

Read-only investigation; no code changes or test runs needed.

# Delivery Steps

###   Step 1: Locate the database conversion
Identify the existing record-number-to-TMCC-ID lookup (completed).
- Locate `ComponentStateStore.by_record_no()` in `db/component_state_store.py`.
- Confirm its use with `state.tmcc_id` in `ConsistComponent.from_d4_bytes()` in `db/components.py`.

###   Step 2: Trace the protocol association
Identify where the mapping response is parsed and its record number retained (completed).
- Locate `D4Action.MAP` parsing in `pdi/d4_req.py`.
- Confirm record-number storage in `db/engine_state.py`.
- Report the source locations without modifying files.