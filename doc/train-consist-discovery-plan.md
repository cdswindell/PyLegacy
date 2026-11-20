# Live train-consist discovery plan

Status: proposed, not implemented. Based on the Cab 3 capture supplied on
November 20, 2026 while adding Engines 18 and 10 to Train 501 (pseudo ID 101).
Discovery belongs in core PyTrain on the server, not in Qt or a legacy GUI.

## Packet evidence

| Observed packet | Interpretation | Proposed use |
| --- | --- | --- |
| `TRAIN 101 NC_NC` | Documented dialog/signal masking command: no change to either setting. It is not a documented consist-edit command. | Weak hint: request a throttled owner refresh; an unresolved alias can initiate bounded discovery. Do not rebuild a consist from this command. |
| `TRAIN 101 FACTORY_DEFAULT`, payload `EF BE` | Existing decoded command, appearing immediately before the custom variable command. | Structural-edit hint in this train-edit sequence; query authoritative records rather than assuming the consist was deleted. |
| `TRAIN 101 VARIABLE ID 0xD000 DATA 30 30 30 31 00` | Payload is NUL-terminated ASCII `0001`, not `0501`. Its purpose is unconfirmed. | Strong refresh hint, retaining the raw payload in debug logging. Do not treat `0001` as the real train ID, record number, or head engine without additional evidence. |
| `ENGINE 18 TRAIN_ADDRESS 101` and equivalent for Engine 10 | Assigns the engine to the seven-bit train address. The capture also shows Base memory updates at offset `0x1C`. | Refresh the engine and both its previous and new containing trains. Resolve pseudo 101 through the authoritative mapping to Train 501. |
| `ENGINE 18 TRAIN_UNIT MIDDLE_REVERSE` / `ENGINE 10 TRAIN_UNIT TAIL_REVERSE` | Updates consist position/orientation. The capture shows Base memory updates at offset `0x1D`. | Refresh affected records and extend the pending reconciliation window. |
| `TRAIN 101 VARIABLE ID 0xF012 DATA EF BE` | Unknown opcode. `EF BE` is little-endian `0xBEEF` and matches the payload of the preceding factory-default command. A guarded apply/finalize operation is a hypothesis, not an established meaning. | Strong hint for a final post-edit refresh; do not depend on it being present or write its guessed meaning into state. |

The structural packets are repeated, and the edit spans about eight seconds.
Paired real/pseudo reset echoes follow the final variable command. A query made
only at the first hint can return the old consist; a single short debounce is
insufficient for the entire transaction.

Lionel's [Legacy protocol specification, revision 1.21, page 17](https://www.ogrforum.com/fileSendAction/fcType/0/fcOid/156701992259624343/filePointer/156701992265497355/fodoid/156701992265497351/LCS-LEGACY-Protocol-Spec-v1.21.pdf)
defines the masking command. It does not establish the meanings of `0xD000`
or `0xF012`. PyTrain currently preserves these as `TMCC2RawVariableEnum`
commands marked `noop=True`; discovery must observe command traffic directly,
including commands that do not modify a state field.

## Existing implementation to reuse

- `comm/command_listener.py`: `CommandDispatcher.request_command_impact()` is
  already invoked on the server. Extend this central command-impact path to
  enqueue train-discovery hints; do not run discovery in each client. If a
  subscriber is used instead, scope subscriptions must filter the specific
  command enums immediately; arbitrary unknown addresses preclude a fixed
  address-specific subscription.
- `pdi/base3_db_refresh_manager.py`: already coalesces individual record reads,
  uses one worker, and prunes idle buckets. Keep that service for known-record
  refreshes; add transaction coordination without another worker per train.
- `pdi/base_req.py`: `resolve_query_state()` and
  `create_base_query_request()` already route a known pseudo address to its
  owning train. Audit the resolver's actual-record precedence before reuse:
  a real database record at ID 100 must not be redirected to an unrelated
  train merely because 100 also appears in a pseudo mapping. Record number
  zero is valid; use `is not None`, not truthiness.
- `db/component_state_store.py`: use `by_pseudo_train_id()` and the existing
  D4 record indexes. Pseudo IDs and four-digit database record numbers are
  different identities.
- `db/startup_state.py`: reuse its `D4_TRAIN` `COUNT` / `FIRST_REC` /
  `NEXT_REC` protocol pattern for unresolved mappings, without restarting
  startup synchronization or emitting another Sync Complete.
- Existing PDI/state update processing must consume replies and publish shared
  state-change notifications. Qt's Train Link model then updates naturally.

## Proposed discovery flow

1. Receive a relevant command and enqueue a hint without blocking dispatch.
   Keep a bounded transaction keyed by real train identity when known, or by
   unresolved pseudo ID otherwise. Deduplicate repeated packets and real/pseudo
   companion traffic without discarding later structural changes.
2. Resolve the owner from known mapping/record information. With a known owner,
   refresh that train's full record. Query two-digit engine records through
   Base memory; query four-digit engine/train records by their known D4 record
   numbers. Never use pseudo 101 as a D4 database record number.
3. If the mapping is unknown or possibly stale, run one rate-limited D4 train
   enumeration shared by all unresolved hints. Coalesce concurrent requests.
   Rebuild mappings only from returned records; an unchanged record count does
   not prove the mapping or consist is unchanged. If no owner is found, retain
   an expiring unresolved hint and log the outcome rather than inventing one.
4. For `TRAIN_ADDRESS`, refresh the old parent as well as the new parent. Take
   old membership from a cached authoritative consist snapshot, since the live
   engine state may already contain the new assignment by the time the command
   impact handler runs. Handle address zero as removal from a train.
5. Reconcile the union of old/new consist members and explicitly changed engines.
   Refresh affected position, orientation, and Train Link fields. Do not assume
   command order describes the complete consist or copy pseudo IDs into real
   train identity fields.
6. Use an early refresh for responsiveness, then require a refresh after the
   latest structural hint. Start with a 500 ms quiet window and a one-second
   follow-up read. Compare authoritative consist/mapping fingerprints; allow
   bounded additional reads if replies are stale or inconsistent. Tune timings
   against captured hardware runs, not a guessed meaning of `0xF012`.
7. Complete after stable authoritative responses. Enforce maximum pending hints,
   a finite retry count, deadlines, and idle cleanup. Log incomplete convergence
   and permit a later hint/manual resync to retry. No unbounded polling or
   queue growth when no GUI is connected.

Ordinary `NC_NC`, numeric reset, and momentum traffic must not continuously
trigger whole-layout scans. Weak hints receive a cooldown; stronger structural
hints can schedule a final refresh even during that cooldown. A pending query
must not consume a newer hint: retain a generation counter and schedule another
read when newer edits arrive before the old response.

This mechanism sends read requests only. Existing command/state handling remains
responsible for its existing writes; discovery must not replay factory-default,
train-address, or variable commands to the layout.

## Logging and regression coverage for implementation

Log transaction start/reason, pseudo-to-real resolution, requested record numbers,
changed membership, bounded retries, and completion at DEBUG. Log unresolved
mappings or exhausted reconciliation at WARNING with addresses and retry counts.
Shutdown must be best effort and must not delay exit or API handoff.

Add deterministic tests with a fake clock and captured packet bytes for:

- The complete supplied sequence, including repeated assignments and paired RX
  echoes; one transaction may have multiple necessary reads, not one per packet.
- Initial reads returning the old consist and a later response adding Engines
  18 and 10 with the captured middle/tail reverse assignments.
- Known and unknown owner mappings, reassignment, removal, stale mapping repair,
  and a valid record number of zero.
- Real Train 100 versus pseudo 100; no address-range-only classification.
- No-op/raw variable packets reaching discovery even when state does not change.
- A newer hint arriving while a previous query is in flight.
- Server-only work, no duplicate work from clients, no discovery-response loop,
  bounded retries, no-subscriber cleanup, and best-effort shutdown.
- Train Link additions/removals and roster/Info updates through existing shared
  state notifications, with no Qt-specific packet parser.

Further captures should vary the head engine, real train ID, record number,
pseudo ID, add/remove action, and save/cancel choice. Compare `0xD000` payloads
and whether `0xF012` appears only when applying changes before assigning either
opcode a confirmed semantic name.
