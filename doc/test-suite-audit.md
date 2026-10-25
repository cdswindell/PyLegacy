# Test-suite audit: baseline and coverage inventory

Date: October 21, 2026. Scope: Steps 1–4: baseline, consolidation, test overhead, and smoke selection.
**No production code, cleanup behavior, pytest defaults, dependencies, or CI
configuration were changed by this audit.** Test consolidations and verification
are recorded below; baseline appendices remain historical.
The previously reported 18.2 seconds is historical, not this review's baseline.

## Results and evidence index

- **Final:** 8,037 passed / 35 skipped; 8,072 collected across 154 modules.
  Ordinary final median **14.294s** (14.283–14.303s), versus baseline 16.703s.
  Smoke selects 12 existing cases: **1.515s median**, with **1.455s** collection
  overhead. See the final Step 4 section; earlier results below remain historical.

- **8,068 collected cases, 3,792 test families, 155 collected modules.**
- Every full baseline: **8,033 passed, 35 skipped, zero failures**.
- Ordinary fresh-process baseline: **16.703 seconds median**, range
  **16.692–16.770 seconds**. Pytest's own reported median: 15.98 seconds.
- Uninstrumented collection: **1.48 seconds end to end**, 1.01 seconds reported
  by pytest. Selection with `-m smoke` will still pay collection/import costs.
- Step 2 preserves the mapped inputs and assertions while removing proven
  repetitions. Current collection is **8,072 cases**; see the reconciliation below.

The following appendices are part of this report, rather than a sample inventory:

| Evidence | Contents |
|---|---|
| [Complete inventory](test-suite-audit-data/inventory.md) | Every collected module and family, expanded count, resolved fixture dependencies |
| [Measured rankings](test-suite-audit-data/rankings.md) | Top 25 individual phases, cases, families, and each phase type; all 155 module totals; fixture setup totals and invocation counts |
| [Final measured rankings](test-suite-audit-data/final-rankings.md) | Three final profiled runs: top 25 cases/phases/families, all 154 module totals and fixture costs |
| `test-suite-audit-data/provenance.json` | Original module SHA-256 hashes and revision-time commit provenance; dirty-tree limitation explicit |
| `test-suite-audit-data/assertion-candidates.json` | All 41 assertion-equivalent candidate groups and unused fixture arguments |
| `test-suite-audit-data/*-process.json` | Exact command, interpreter/platform, selected environment, process cap, exit status, external wall time |
| `test-suite-audit-data/raw/` (ignored, local only) | Disposable per-case measurements and logs; removed during delivery cleanup, recreated by new runner executions |
| `test-suite-audit-data/summary.log` | Exact skip IDs/reasons and phase totals |

Delivery cleanup retained the report, inventory, rankings, scan results, provenance,
runner, and baseline/final process metadata. Final ordinary/profiled runs and
full collection use `step4-*-process.json`; the corrected 12-case smoke runs and
selection collection use `step4-corrected-*-process.json`, all directly under
`test-suite-audit-data/`. Raw logs, coverage databases, source snapshots, and
intermediate reports were task-generated and removed at the user's request.
Raw-path references below identify historical local artifacts, not committed
dependencies. The runner can capture new measurements; it cannot recreate the
original recordings or the original dirty working tree from hashes alone.

The inventory is collector-based, not a filename comparison. AST extraction covers
all collected modules, including assertions inside nested loops and helpers; the
local source snapshot preserved module/class parameter tables that a list of node names
alone would omit. Committed evidence uses hashes rather than duplicating sources. Nonprimitive parameter objects are intentionally not passed to
`repr`: an uninitialized EngineState raises from its repr. Their pytest IDs, types,
and complete source tables were available during review; the retained inventory
and hashes do not reproduce that removed snapshot. The fixture map covers resolved
FixtureDefs; pytest's special `request` object is not a separate FixtureDef.

Review method: reconcile collection and fixture closures across all three runs;
inspect assertion/call/loop evidence across the inventory; compare structural
duplicate candidates with their targets, inputs, fixtures, and failure assertions;
then inspect the high-risk overlapping modules and measured hotspots directly.
Identical bodies are only candidates, not proof of equivalent coverage. This is
not a claim that an automated AST comparison proves every remaining test unique.

## Measurement conditions and reproduction

PyCharm confirmed Python **3.13.16** at
`/Users/davids/Documents/dev/PyLegacyEnv/bin/python3.13` before Python commands.
`../bin/python` was verified to refer to the same executable. Platform:
`macOS-27.2-arm64-arm-64bit-Mach-O`; pytest **9.1.1**, pluggy **1.7.0**.
Automatically loaded plugins: **pytest-cov 7.1.0**, **platformdirs 4.13.5**.
Coverage was **not enabled**: no `--cov`, no coverage environment additions, and
no coverage timing is mixed into these results. Existing `coverage.json` and
`htmlcov` were not used as current coverage evidence.

Working directory was the project root. `pytest.ini` sets `pythonpath = ./src`
and registers `allow_thread` and documentary `timeout` markers; it sets no
default selection or exclusions. `PYTHONPATH=.`; `PYTEST_ADDOPTS`,
`PYTEST_PLUGINS`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD`, and `PYTRAIN_API_CHECKOUT`
were unset. Processes were sequential, not concurrent. Each run started a fresh
interpreter; OS filesystem caches were not flushed. Existing randomized test
inputs were left unchanged/unseeded, so this is not a bit-for-bit deterministic
input replay. Background machine load was not controlled. These measurements
describe the local working tree, not a pristine checkout; unrelated modifications
in `src/pytrain/db/base_state.py` and `src/pytrain/db/sync_state.py` were left alone.

Exact ordinary baseline command, repeated in three fresh subprocesses:

```sh
../bin/python -m pytest --durations=0 --durations-min=0
```

Reusable bounded runner (uses its own `sys.executable`; rejects existing labels):

```sh
../bin/python scripts/audit_test_suite.py plain-new-1 --plain --timeout 120
../bin/python scripts/audit_test_suite.py plain-new-2 --plain --timeout 120
../bin/python scripts/audit_test_suite.py plain-new-3 --plain --timeout 120
../bin/python scripts/audit_test_suite.py profile-new-1 --timeout 120
../bin/python scripts/audit_test_suite.py profile-new-2 --timeout 120
../bin/python scripts/audit_test_suite.py profile-new-3 --timeout 120
../bin/python scripts/audit_test_suite.py collection-new --collect-only --timeout 60
../bin/python scripts/audit_test_suite.py --summarize --runs profile-new --report-dir doc/test-suite-audit-data/report-new
../bin/python scripts/audit_test_suite.py --summarize --plain --runs plain-new --report-dir doc/test-suite-audit-data/report-new-plain
```

The summary commands read three named runs from the default ignored
`raw/` directory; `--output-dir` selects another input/run directory. It reads no
current test sources, so deletion of consolidated modules is safe. The report
directory must not exist: dated appendices cannot be overwritten. Raw JSON and
logs are automatically gzipped; process metadata stays readable JSON. Ordinary
wall-time comparisons use the three `plain-new-*-process.json` values, separately
from instrumented rankings. Sources are hashed at run time for new process metadata. The
runner's profiled child command adds `-p scripts.audit_test_suite`. The recorded
baseline commands used its initial filename, `-p scripts.test_suite_audit`;
it was subsequently moved outside pytest's test-file naming pattern. Profiling
records fixture setup hooks and individual test reports without changing tests.
It prints failed node IDs/messages and collection errors when results exist,
preserves complete output, and returns nonzero on failures/timeouts.

Baseline runner subprocesses had a 120-second cap; collection terminal commands
also had a 60-second cap. The final renamed-runner collection verification used
an explicit 60-second subprocess cap and passed in 1.661 seconds
(the redundant verification artifact is no longer committed).
No timeout fired. A separate enforced per-case timeout was **not installed or
enabled**: the existing `timeout` mark is documentary, not pytest-timeout.
Thus a stalled test is bounded by the process cap, not a promised 5–20-second
case deadline. Keep this limitation in mind when reusing the runner; existing
real-thread/process test timeouts and cleanup behavior were not weakened.
The subprocess timeout kills the direct pytest child only; multiprocessing
grandchildren could survive a timeout. No timeout occurred in these measurements.

| Run | Ordinary wall | Pytest elapsed | Profiled wall | Setup sum | Call sum | Teardown sum |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 16.770 | 16.00 | 16.723 | 2.867 | 10.020 | 0.715 |
| 2 | 16.692 | 15.93 | 16.780 | 2.956 | 9.966 | 0.655 |
| 3 | 16.703 | 15.98 | 16.452 | 2.937 | 9.767 | 0.646 |
| Median | **16.703** | **15.98** | **16.723** | **2.937** | **9.966** | **0.655** |

Seconds, rounded to three decimals except pytest's printed values. Phase sums
exclude collection, interpreter startup, reporting, artifact serialization, and
other pytest overhead; do not subtract their sum and call the remainder
"collection." The roughly 0.020-second difference between ordinary/profiled
medians is smaller than run-to-run noise and is not an isolated overhead estimate.

Collection was also measured with
`/usr/bin/time -p ../bin/python -m pytest --collect-only` (1.48 seconds wall).
The instrumented collection probe was 1.616 seconds. An earlier inventory probe
failed during parameter repr, before executing tests; failed and redundant probes
are excluded from statistics and removed from the deliverable.

## Whole-suite coverage disposition

All families and expanded combinations are enumerated in the inventory and raw
collection data. The following summarizes review boundaries, not replacements for
that inventory. **Retain every case unless an explicit survivor is mapped below.**

| Area | Modules | Cases | Coverage distinctions retained |
|---|---:|---:|---|
| ATC | 1 | 4 | Block initialization and changed/unchanged update state |
| CLI | 18 | 963 | Command parsers and bytes, startup suppression, service discovery, state/admin operations, update ownership, cache synchronization, GUI hosts, shell generation, real source-launcher subprocesses |
| Communication | 5 | 60 | Proxy disconnect errors, enqueue arguments, dispatcher lifecycle, listener queue/decode/cleanup contracts |
| Database | 16 | 1,115 | Component data encoding and boundaries, engine/train capabilities and state precedence, accessory/IRDA behavior, cache workers, startup/watcher notifications, serialization, ramp ownership |
| GPIO/I2C | 5 | 40 | Device/register interaction through bus doubles, status indicators, text-buffer behavior; not redundant with GUI state presentation |
| GUI | 58 | 3,445 | Headless widget and controller contracts, platform/layout matrices, input bindings and repeat/dead-zone behavior, overlays/popups, route editing, LCS panels, image presentation, checkpoints, compatibility and import isolation |
| Integration | 1 | 34 | Optional external API exit/handoff matrix; collected but skipped here |
| PDI | 13 | 665 | Request-specific encoding/decoding, payload/checksum and field boundaries, state translation, listeners and device-specific actions |
| Protocol | 16 | 1,550 | Definitions/enums, request encoding/decoding, ramp geometry and ownership/cancellation, multibyte requests, RPM/speed conversion, validation overlap |
| Root tests | 4 | 24 | Deck packaging/entry-point guarantees, self-update policy, public PyTrain/version behavior and version-tuple parsing |
| Utilities | 18 | 168 | Validation, paths and indexing, logging/process ownership, parsing, sockets/IP, timing, text, and configuration helpers |
| **Total** | **155** | **8,068** | No deletion based on names, suffixes, or common production line coverage |

`tests/test_base.py` is a support module with zero collected tests; it supplies
request generation, mock buffers, thread exception tracking, and `wait_until`.
The five conftest files, I2C bus double, integration child launcher, and package
initializers are support rather than additional test cases. Fixture evidence
includes **95 project definitions** and **450 pytest/plugin definitions**, many
of the latter being parameter pseudo-fixtures or xunit wrappers, not expensive
resource fixtures. Shared support sources were reviewed with the collected modules.

### Fixture and isolation findings

- `tests/cli/conftest.py` already isolates bare PyTrain instances and suppresses
  startup side effects; preserve fresh mutable state and monkeypatch lifetimes.
- `tests/protocol/sequence/conftest.py` supplies PDI send/ramp transport doubles.
  Repeated parameter combinations exercise different geometry, command, ownership,
  and wire-state conditions; equal call shapes do not establish redundancy.
- Engine state modules have their own `pin_process_globals` fixtures. Preserve
  singleton isolation, protocol-control-type defaults, and store patches.
- GUI widgets and parsers are mutable. Route-panel construction is measurable,
  but widening fixture scope would leak selection, history, mocks, and scheduled
  callbacks. Existing source-analysis caches in controller-view/LCS-import tests
  should not be rebuilt as a new optimization.
- Four autouse `run_before_and_after_tests` fixtures request unused `tmpdir`:
  `comm/test_command_listener.py:18` (4 setups), `comm/test_dispatch_listener.py:46`
  (28), `db/test_component_state.py:51` (64), and
  `db/test_component_state_store.py:18` (1). Step 3 should remove all four
  dependencies, preserving dispatcher/listener reset, shutdown, joins, and
  termination assertions. These induce **97 `tmp_path` directory setups**.
  Their measured dependency setup sums are 0.039322, 0.035371, and 0.036566 seconds;
  median **0.036566 seconds**, about 33% of all `tmp_path` setup time (0.111 seconds
  across 282 invocations). This is an upper bound on savings, not a promised
  wall-time reduction. The hook excludes dependency setup: directory creation
  is charged to `tmp_path`, not the roughly 0.001-second `tmpdir` wrapper total.
- The unused-argument AST scan also found 16 `monkeypatch` arguments, enumerated
  in `assertion-candidates.json`. They are low-priority cleanup candidates, not
  grounds for weakening fixtures or changing scope; check indirect fixture effects
  before removal. No unused `tmp_path` argument was found in that scan.
- No global sleep replacement, shared mutable parser, reused mock, process-start
  method exclusion, or weakened shutdown timeout is justified by these results.

## Duplicate-to-survivor mappings and nonduplicates

### Validation consolidation (implemented in Step 2)

`tests/protocol/test_validations.py::TestValidations::test_validate_int` tests
the same utility as `tests/utils/test_validations.py`, not a different protocol
validation implementation. The inherited TestBase setup/teardown are empty.

| Original assertion/input | Surviving utility home / required preservation |
|---|---|
| `validate_int(5) == 5` | Existing `TestValidateInt.test_returns_int_when_already_int` is identical |
| `5.4 -> 5`, `5.99 -> 5` | `test_truncates_float_to_int`, two parameters |
| `"5" -> 5` | `test_converts_string_digits_to_int`; existing `"42"` retained |
| `"text"` ValueError and message | `test_raises_value_error_for_non_numeric_string_default_label`; `"abc"` retained |
| default `None` TypeError and message | `test_rejects_none_by_default`; allow_none=True remains separately tested |
| `5`, minimum `10`, default-label message | `test_min_value_enforced_no_label`; existing `-1`/`0` retained |
| `15`, maximum `10`, default-label message | `test_max_value_enforced_no_label`; existing `11`/`10` retained |
| `15`, maximum `10`, label `"Value"`, suffix `(15)` | `test_max_value_enforced_with_label_and_suffix`; existing `"Speed"`/`11` retained |

The utility object's TypeError-message assertion formerly ended with
`or " is not an integer"`, making it always true. It now compares the complete
message with the same object's string representation, avoiding a hard-coded
memory address. TypeError, explicit boundaries, inside-range cases, allow_none,
custom labels, and all float-validation tests remain. The protocol module was
removed only after its unique inputs were moved into these utility cases.

### Additional candidates and structural false positives

The whole-suite exact-body scan found four groups; each was checked beyond body
text. This scan does not establish that semantically equivalent but differently
written tests are duplicates.

| Candidate | Decision and survivor |
|---|---|
| `test_engine_state.py::TestEngineStateBehavior::test_train_state_rejects_non_train_scope` and `test_engine_state_core.py::TestTrainStateCore::test_a_train_rejects_any_other_scope` | Same TrainState(ENGINE), ValueError, and `expected TRAIN` match. Both autouse fixtures pin CommBuffer.is_server and ComponentStateStore.is_state_synchronized to False. Step 2 removed the first test and retained the core survivor. Broader TrainState tests remain. |
| CLI LCS/PyCab `test_send_builds_no_requests` | Retain both: same assertions resolve through different `_command_for` helpers/classes. Adjacent send tests explicitly differ on synchronization policy. |
| Controller labels `test_engine_commands_are_named_by_their_enum` / `test_awkward_enum_names_are_overridden` | Retain both: disjoint parameter tables exercise enum-derived labels versus explicit overrides. |
| GUI checkpoint state-flag selection / overlapping-flag precedence | Retain both: distinct parameter tables test simple dispatch versus precedence when several flags are true. |

Additional input-level repetition: `TestMakeService.test_parser` loops over
`range(2, len("-version"))` but passes `["-version"][:i]`. Each of the six
iterations receives the same one-element list. A single existing `-version`
check is the survivor for five redundant invocations. If abbreviation coverage
was intended, changing to actual string prefixes is a separate coverage repair,
not removal of proven existing distinct cases. Preserve help, default parsing,
and parser-error assertions. This is a larger efficiency opportunity than
deleting a submillisecond duplicate assertion.

### Assertion-equivalent review supplement

`assertion-candidates.json` lists all 41 groups, in the order referenced below.
The scan compares sorted AST `assert` expressions (at least two), not mock calls,
`pytest.raises`, inputs, or fixture semantics; it is a candidate generator only.

| Groups | Decision and distinguishing behavior |
|---|---|
| 1 | Retain disabled cache sync versus failed startup/no retry; different build-call and exception assertions. |
| 2–5 | Retain different CLI classes and entry points (LCS, routes, PyCab), even with shared defaults/forwarding assertions. |
| 6–7 | Retain cleanup versus deferred-action failures, and non-Linux versus Steam Deck OS-update policy. |
| 8–12 | Retain accessory/switch state classes, reversed/linear serialization, single/repeated echoes/PDI limit records, unknown IRDA direction/propagation failure, and LCS/switch packet normalization. |
| 13–17 | Retain axis precedence/panel dispatch, distinct unbound controls, CAB-1/no selected engine, hidden/visible admin cancellation, and failed/no-expand overlays. |
| 18–24 | Retain release/catalog-close, remote claim/claim-and-release, button/trigger holds, panel-close/disconnect, trigger/face-button switch and route dispatch, and both ASC2 holder release orders. |
| 25–26 | Retain fitting versus already-fitting layout, and release versus leave cancellation. |
| 27 | Retain standalone component creation versus pane-hosted creation: distinct host integration. |
| 28 | Consolidation mapping: checkpoint `test_no_panel_is_reported_off_an_accessory_screen` → keypad `test_accessory_panel_kind_is_none_off_an_accessory_panel`. Same ENGINE/accessory and ACC/None inputs, same property and two None assertions; neither builds widgets. Host ID-map/callback differences are irrelevant to these early-return inputs. |
| 29 | Retain checkpoint `test_the_switch_screen_carries_its_own_set_and_info_keys` and keypad `test_the_switch_screen_carries_both_a_set_and_an_info_key`. Both use SWITCH address 7 and assert visible Set/Info cells, but checkpoint `_built` retains `DummyAccessoryState(7)` and `_ops` passes it onward; keypad `_ops` sets active state to None for SWITCH. This preserves stale accessory state versus no-state screen transitions. |
| 30–34 | Retain inside/just-outside pointer boundary, recovery timeout/disabled recovery, same-address edits/base refresh, highlighted/no-highlight paging, actual lamp change/forced-on color. |
| 35–40 | Retain invalid index/component, direct/indirect cycles, animation-capable/incapable page, width/unmapped retry, prewarmed/early-press overlay, and send/database ramp failures. |
| 41 | In `tests/utils/test_unique_deque.py::TestUniqueDequeue`, `test_create_no_args` is subsumed by `test_getters_fail_on_zero_len_unique_deque`: same class, no fixture arguments, identical local construction and three assertions, followed by pop/popleft/delete/remove error checks. Retain the latter as the survivor. |

The GUI pair is specifically `tests/gui/test_gui_checkpoint.py` versus
`tests/gui/test_keypad_view.py`, both importing `controller.keypad_view`, not
separate GUI layers. Copied host/Tk doubles are not independently valuable
coverage by themselves; the switch pair is retained for its concrete state difference.
Retain the rest of checkpoint: overlapping flags include additional
sensor/AMC combinations, non-accessory state rejection and explicit non-active
state queries. Single-assert flag cases also overlap with keypad dispatch tests,
but removing whole parameter families would lose those combinations. No whole
checkpoint module deletion is justified.

### Module distinctions (subject to the narrow mappings above)

| Pair/cluster | Distinct contracts |
|---|---|
| `utils/test_path_util.py`, `utils/test_path_utils.py` | Installation/filename lookup and exclusions versus indexing, suffix handling, cached/default roots, nondefault freshness, traversal errors and invalidation. Retain both. |
| `comm/test_command_listener.py`, `_ai.py` | Lifecycle/singleton/queue/control behavior versus actual worker decoding, malformed bytes and subscription delivery. Retain real workers and shutdown assertions. |
| `db/test_component_state_store.py`, `_ai.py` | Real listener-to-store delivery and state changes versus direct store update, lookup, reset/filter and error paths. Direct calls do not replace asynchronous integration. |
| Engine state/core/component-data modules | Similar fields are observed through different command/PDI updates, control-type precedence, record fallbacks, exports, and derived capabilities. Only the narrow wrong-scope candidate above is mapped. |
| Protocol requests, PDI requests, CLI commands | Enum values/bit layout, decoded round trips, device payloads, and parser-to-command dispatch have different assertions and malformed-input boundaries. |
| Ramp geometry, speed ramp, echoes, peer/two-controller and claim-state modules | Numeric invariants, actual step scheduling, echo ownership, concurrent cancellation and stale claims are different layers; keep parameter boundaries and interleavings. |
| GUI state/catalog/checkpoint/controller/compatibility modules | Source-level import/layout contracts do not replace runtime headless behavior; platform matrices, fallback branches, input modality and callback ownership remain distinct. |

Cancellation is not an ordinary cleanup failure. Preserve tests for continued
best-effort teardown and logging, retained failed ownership for retry, API handoff,
and propagated KeyboardInterrupt/SystemExit. No matrix may be replaced by a
single happy-path assertion merely because production line coverage overlaps.

## Measured hotspots and priorities

See the rankings appendix for all top-25 tables, ranges, and all module totals.
Here are the leading aggregate costs, **sum of setup/call/teardown**, median over
the three profiled processes:

| Module | Seconds | Action |
|---|---:|---|
| Utility multiprocessing logging | 1.472 | Keep fork/spawn/forkserver guarantees; exclude from future smoke, not full suite |
| GUI route-builder panel | 1.407 | Profile fresh panel construction/mock creation; never share mutable panels |
| CLI make-service | 1.182 | Remove repeated identical version invocation after survivor review |
| CLI make-GUI | 1.144 | Separate shell-text assertions from incidental installation/version discovery where justified |
| CLI routes | 0.626 | Keep both real source-launch directories without PYTHONPATH |
| DB cache synchronization | 0.573 | Real worker termination alone costs 0.505; preserve the regression |
| CLI PyTrain | 0.455 | Keep parser/command/startup variants; no blanket fixture-scope widening |
| GUI controller controls panel | 0.415 | Measured-font test costs 0.338; keep real font behavior where it is the assertion |
| Protocol ramp geometry | 0.392 | Numerous cheap parameter cases; do not prune mathematical boundaries |
| Protocol speed ramp | 0.380 | In-flight abort synchronization costs 0.201; keep actual concurrency |

Individual subprocess costs: logging `spawn` 0.592, `forkserver` 0.570,
`fork` 0.313 seconds; route launcher directories 0.304 and 0.298 seconds.
These are case totals, not estimates from test names.

Leading fixture setup totals: route `panel` **0.846** (317 setups), sequence
`pdi_send` **0.279** (859), `desktop_panel` **0.117** (89), `tmp_path` **0.111**
(282), CLI `runtime` **0.101** (144), and touch-list `mod` **0.097** (19).
The fixture hook measures setup exclusive of dependency setup. Teardown is
measured per case, not attributed to individual fixture finalizers; neither
fixture totals nor module medians should be summed with phase totals twice.
Some GUI setup cases fluctuate from about 0.003 to 0.10 seconds; do not infer a
stable slow parameter from one sample or promise its maximum as a saving.

Priorities identified in Step 1 (items 1–2 implemented in Step 2, item 3 in Step 3):

1. **Correctness-first consolidation:** repair the validation assertion and move
   all unique inputs. The runtime saving is negligible; stronger assertions and
   maintainable coverage are the benefit.
2. **Eliminate repeated work, not contracts:** the service parser's six identical
   version requests are inside the slowest call (median 0.773 seconds). Measure
   after retaining one. The full call cost is only an upper bound on savings.
3. **Isolate incidental filesystem discovery:** replace `Path.cwd()` in
   nondefault freshness with a controlled temporary tree; preserve changing
   roots/content and observed freshness. This case is about 0.015 seconds here;
   the entire path-utils module is only 0.068. The distinct installation lookup
   in `test_path_util.py` costs 0.166 and deserves separate review, not deletion.
4. **Investigate expensive fresh GUI setup:** panel construction dominates
   route-builder fixtures. Reuse immutable analysis only after profiling that
   component. Keep independent state and reset/cleanup behavior.
5. **Keep meaningful waits:** the cache worker and in-flight ramp abort tests
   intentionally exercise real scheduling. Use condition/event waits only for
   incidental delays. `wait_until` already exists; do not introduce another
   polling helper or replace threads with mocks to reduce time.
6. **Future smoke:** select existing inexpensive encoding/decoding, PDI, state,
   CLI, headless GUI, and cleanup-failure cases. Exclude costly subprocess
   matrices only from smoke. Collection is already approximately 1.5 seconds;
   five seconds may be feasible but is not yet a measured smoke result.

`tests/protocol/test_command_req.py` totals **0.166 seconds**, not a dominant
hotspot despite broad loops. Its loop domains and source assertions are included
in the source evidence: commands, addresses, data, scope, encoding/decoding and
invalid inputs must not be replaced by a few representative enum members. A
small number of function names can represent substantial coverage.

## Optional integration and validation status

`PYTRAIN_API_CHECKOUT` was unset. All **34** optional integration cases were
collected and skipped: 24 exit-receiver combinations (six commands, callback or
queued, server or client), two callback-cache-failure cases, and eight real
signal-handoff cases. Their prerequisite is a compatible local PyTrainApi
checkout. Their execution cost is **unknown**, not zero and not included in the
default runtime claim. The remaining skip is the client parameter of the
server-specific GUI-exit test. Exact reasons/IDs are in `summary.log`.

For Step 1 no focused coverage comparison was needed because no test behavior
was consolidated; Step 2 results are below, separate from ordinary timing.
Baseline and inventory collection were exercised successfully;
the new audit runner was formatted and inspected in PyCharm with warnings and
weak warnings enabled. No existing test file was edited in Step 1. A final ordinary full
suite run was recorded separately in ignored `raw/validation.log.gz`: **8,033 passed,
35 skipped in 16.02 seconds**, 16.75 seconds external wall time.

Revision verification: full suite **8,033 passed, 35 skipped in 15.65 seconds**;
fresh collection again found 8,068 cases. Ruff format check and PyCharm runner
inspection (including warnings) passed. A focused runner check copied the three
archived measurements under an alternate `after` prefix, prohibited `.py` source
reads, reproduced rankings byte-for-byte, verified existing-directory rejection,
and exercised plain wall-time summaries. No baseline reruns were needed. Raw
measurements/logs and the old snapshot were ignored local artifacts; the committed
family inventory, rankings, process summaries, hashes, and scan results remain
the compact deliverable (at that revision, about 0.6 MB on disk, down from 8.7 MB;
ignored local raw files were not part of that size). Original source hashes are exact, but the commit ID was
recorded during revision and cannot establish an original clean-checkout baseline.
Concurrent production edits, including `src/pytrain/protocol/sequence/speed_ramp.py`
visible at final status, were not modified by this audit.

Step 3 adds an interim after-optimization median below; smoke membership/runtime
remain for Step 4. Keep these dated baseline artifacts immutable and
reconcile any later removed case against its explicit surviving assertion/input.

## Step 3: filesystem and fixture overhead

Replaced the freshness test's repository root with a small temporary project tree
(the existing `_make_tree` helper), alongside a separate temporary cache root.
It still passes two nondefault `Path` roots, first asserts a miss, creates
`engine.json` in the second root, then finds it without resetting the index.
This removes incidental repository-size dependence without changing production
indexing or testing a mocked filesystem.

Removed unused `tmpdir` dependencies from the autouse cleanup fixtures in:

- `tests/comm/test_command_listener.py` (4 cases)
- `tests/comm/test_dispatch_listener.py` (28 cases)
- `tests/db/test_component_state.py` (64 cases)
- `tests/db/test_component_state_store.py` (1 case)

Their bodies, scopes, shutdown calls, and singleton cleanup assertions remain
unchanged. This eliminates 97 unnecessary temporary-directory fixture chains.
The baseline combined setup cost was approximately **0.0366s**, a small saving,
not seconds. No cases were removed: collection remains **8,072**.

### Measurements and verification

The SDK was reconfirmed as Python 3.13.16. All commands used its absolute path
listed above (equivalent to `../bin/python`). Plugins, coverage-disabled settings,
and environment match the baseline; runs were sequential fresh processes.
Unrelated user production edits were not touched, so this is not an isolated
benchmark of Step 3 versus a frozen production revision.

Focused command before and after the initial edits:

```sh
../bin/python -m pytest tests/utils/test_path_utils.py \
  tests/comm/test_command_listener.py tests/comm/test_dispatch_listener.py \
  tests/db/test_component_state.py tests/db/test_component_state_store.py \
  --durations=10 --durations-min=0
```

Both passed 106 cases. The freshness call changed from **0.28s** to **0.00s**
(rounded, below 0.005s), versus the historical baseline's approximately 0.015s.
The initial focused run took 3.96s and the first after run 0.64s in pytest;
startup/filesystem cache effects clearly affect other cases too. Do not attribute
that whole difference to these edits or claim a stable 0.28s saving.

After inspection fixes, each of the five modules in the focused command ran independently with
`--durations=3 --durations-min=0`: external wall times in that order were
**0.550, 0.442, 0.558, 0.557, 0.449s** (9, 4, 28, 64, 1 passing cases).
The combined command with the same duration flags then ran three times:
**106 passed each**, external wall **0.617, 0.657, 0.605s**; pytest time
**0.42, 0.42, 0.38s**. This repeats the affected real-thread tests without
sharing singleton state across fresh processes. Each subprocess had a 60s cap.

Three full uninstrumented timing commands:

```sh
../bin/python scripts/audit_test_suite.py step3-plain-1 --plain --timeout 120
../bin/python scripts/audit_test_suite.py step3-plain-2 --plain --timeout 120
../bin/python scripts/audit_test_suite.py step3-plain-3 --plain --timeout 120
```

| Run | External wall seconds | Pytest seconds | Result |
|---|---:|---:|---|
| 1 | 16.287 | 15.55 | 8,037 passed, 35 skipped |
| 2 | 16.254 | 15.49 | 8,037 passed, 35 skipped |
| 3 | 17.473 | 16.40 | 8,037 passed, 35 skipped |

Median **16.287s**, range **16.254–17.473s**, versus baseline median **16.703s**,
range **16.692–16.770s**: about **0.416s (2.5%)** lower median across Steps 2–3,
but overlapping ranges and concurrent production changes preclude a causal
whole-suite speedup claim. Exact commands, environment, test hashes, and full
phase-duration logs were captured in ignored `raw/step3-plain-*` artifacts.
An additional ordinary `../bin/python -m pytest` passed **8,037**, skipped **35**.
Full runs used 120s caps; no enforced per-test timeout plugin is installed.

Ruff format check passed on all five modified Python files. PyCharm inspections
with `errorsOnly=false` included warnings and weak warnings; every file finished
with no findings after fixes. Existing typing findings were resolved by stronger
SwitchState/timestamp assertions, a constant mock `return_value=2` instead of an
unused-argument callback, and explained, localized inspection suppressions for
runtime parameter pairing, optional-property narrowing, the TMCC discriminator,
and protected queue synchronization. The accessory initial-state test retains
its None assertions despite overly narrow production enum annotations; its
unreachable-code suppression is confined to that test. American English was
reviewed, including correcting the four cleanup-fixture docstrings.

### Step 3 review follow-up: CLI lookup and parser overhead

The initial conclusion that no further measured hotspot warranted changes was
incorrect. Nondefault template lookup indexed the repository and parent virtual
environment on every render, even when the packaged template was already present.
The service rendering test now copies the real packaged template into a temporary
`working/src` tree and changes cwd to `working`; both `.` and `..` are bounded by
that test's temporary directory. The function-scoped GUI launcher fixture likewise
uses a temporary child cwd, retaining the real absolute packaged-template root.
No lookup function is mocked: real discovery, template substitution, cache flags,
platform exports, and the separate alternate-working-directory assertion remain.

`_MakeBase._command_line_parser` eagerly calls `get_version()` even for help and
invalid arguments. The service parser test retains its first real `-version`
construction (including subprocess discovery), then patches only the imported
version lookup for its ten non-version constructions. Parser instances remain
fresh; all success/error exit-code assertions remain unchanged.

Focused before/after command: `../bin/python -m pytest
tests/cli/test_make_service.py tests/cli/test_make_gui.py --durations=10
--durations-min=0` (36 passing cases both times; pytest 2.24s before, 0.70s after).
Call durations below are rounded pytest output, not wall-time assertions:

| Case | Before seconds | After seconds |
|---|---:|---:|
| `TestMakeService.test_parser` | 0.53 | 0.09 |
| Service cache-sync shell rendering | 0.41 | <0.005 |
| GUI cache-sync shell rendering | 0.38 | <0.005 |
| GUI platform rendering, SteamDeckGui | 0.20 | <0.005 |
| GUI platform rendering, EngineGui | 0.19 | <0.005 |

The two CLI modules passed independently (4 cases/0.35s and 32 cases/0.62s).
Adding both to the five-module command above passed **142 cases three times**,
each in 0.74s, including real-thread cleanup and state-store integration. Focused
processes used 60s caps. Ruff format checks and PyCharm inspections including weak
warnings passed for both modified files. Optional module paths now have explicit
non-None assertions; two narrowly explained unresolved-reference suppressions
cover the imported patch target and an optional-path false positive, and one
protected-member suppression covers fixture directory preparation. American
English was reviewed. No production files were edited in this follow-up.

Three sequential fresh-process runs used the same interpreter, plugins,
coverage-disabled settings, and environment as the plain baseline:

```sh
../bin/python scripts/audit_test_suite.py step3b-plain-1 --plain --timeout 120
../bin/python scripts/audit_test_suite.py step3b-plain-2 --plain --timeout 120
../bin/python scripts/audit_test_suite.py step3b-plain-3 --plain --timeout 120
```

| Run | External wall seconds | Pytest seconds | Result |
|---|---:|---:|---|
| 1 | 14.074 | 13.38 | 8,037 passed, 35 skipped |
| 2 | 14.355 | 13.60 | 8,037 passed, 35 skipped |
| 3 | 14.257 | 13.55 | 8,037 passed, 35 skipped |

Median **14.257s**, range **14.074–14.355s**: 2.030s below the initial Step 3
median and 2.446s (14.6%) below the plain baseline median of 16.703s.
These are observed end-to-end differences, not savings attributable solely to
this patch: concurrent production edits and system/cache variability remain
confounders. Full logs, source hashes, and process metadata were captured
in ignored `raw/step3b-plain-*`. All four targeted rendering calls round to 0.00s
in these full runs. An additional ordinary `../bin/python -m pytest` passed
**8,037**, skipped **35**, in **13.35s**; collection remains 8,072 cases.

### Retained costs and limitations

The real service `-version` path remains intentionally covered. Individual GUI
parser scenarios still cost about 0.05s each and retain real construction/version
discovery; they are smaller follow-up candidates, not reasons to share mutable
parsers or mocks. Route-builder panels remain isolated, and existing GUI
source-analysis caches already avoid repeated immutable work. The component-state
GUI unknown-key no-action wait (0.1s) and image-presenter stale-callback wait
(0.2s) remain: deterministic replacements need separate concurrency review,
not a blanket sleep reduction. Unused `monkeypatch` arguments are not demonstrated
dominant costs and were left alone rather than broadening this patch. Keep the
real multiprocessing start-method matrix, both launcher working directories,
cache-worker termination, and in-flight ramp cancellation intact. Shutdown failure,
retry ownership, logging/continuation, and KeyboardInterrupt/SystemExit matrices
remain in the full suite, not replaced with fake workers or shorter timeouts.
The 34 optional API integration cases still require `PYTRAIN_API_CHECKOUT` and
were skipped; their execution remains unverified. Smoke selection and final
selection-overhead measurements belong to Step 4.

## Step 2: completed consolidation and verification

The mappings above were rechecked against the current source and fixture bodies.
Implemented removals:

| Removed work | Surviving coverage |
|---|---|
| `protocol/test_validations.py`, one collected case with bundled inputs | Utility validation mapping above; eight additional collected cases, with every old input preserved |
| `test_engine_state.py::TestEngineStateBehavior::test_train_state_rejects_non_train_scope` | `test_engine_state_core.py::TestTrainStateCore::test_a_train_rejects_any_other_scope`; identical fixture values, input, exception type, and message match |
| Checkpoint `test_no_panel_is_reported_off_an_accessory_screen` | Keypad `test_accessory_panel_kind_is_none_off_an_accessory_panel`; both ENGINE/accessory and ACC/None inputs retained |
| Deque `TestUniqueDequeue.test_create_no_args` | `test_getters_fail_on_zero_len_unique_deque`; identical construction/three assertions plus failure checks |
| Five repeated `MakeService(["-version"])` invocations inside `test_parser` | One invocation with the same SystemExit/code assertion; all help/default/error checks retained |

All other candidate decisions remain **retain**, including the switch-screen pair
with stale accessory state versus None, all parameter precedence combinations,
the listener/state-store pairs, and shutdown/cancellation matrices. No fixture
dependency cleanup or smoke marks were included in Step 2.

Count reconciliation: **8,068 + 8 utility cases - 1 protocol case - 3 duplicate
cases = 8,072**, across 154 modules. The loop reduction changes no collected count.
The utility module grows from 24 to 32 cases. More independently collected inputs
are intentional, not additional duplicated behavior.

### Focused line/branch comparison

PyCharm reconfirmed Python 3.13.16 at the SDK path above; commands used that
absolute executable (equivalent to `../bin/python`). Before editing, the focused
selection passed **563 cases**; after consolidation, **567 in 3.06s**.
This is a coverage-instrumented pytest time, not full-suite performance evidence.
Both runs selected the following modules, with the protocol validation module
included only before deletion:

```sh
COVERAGE_FILE=doc/test-suite-audit-data/raw/step2-after.coverage ../bin/python -m pytest \
  tests/utils/test_validations.py tests/utils/test_unique_deque.py \
  tests/db/test_engine_state.py tests/db/test_engine_state_core.py \
  tests/gui/test_gui_checkpoint.py tests/gui/test_keypad_view.py tests/cli/test_make_service.py \
  --cov=src.pytrain.utils.validations --cov=src.pytrain.utils.unique_deque \
  --cov=src.pytrain.db.engine_state --cov=src.pytrain.gui.controller.keypad_view \
  --cov=src.pytrain.cli.make_service --cov-branch \
  --cov-report=json:doc/test-suite-audit-data/raw/step2-after-coverage.json --cov-report=term
```

For the before command, add `tests/protocol/test_validations.py` and substitute
`step2-before` for both artifact prefixes. Local ignored JSON reports were compared
by **exact executed_lines, missing_lines, executed_branches, and missing_branches
sets**, not just rounded percentages: all five modules were identical.

| Production module | Executed / missing lines | Executed / missing branches |
|---|---:|---:|
| utils.validations | 39 / 2 | 16 / 0 |
| utils.unique_deque | 97 / 14 | 26 / 0 |
| db.engine_state | 914 / 152 | 378 / 134 |
| gui.controller.keypad_view | 659 / 75 | 215 / 65 |
| cli.make_service | 56 / 74 | 7 / 31 |

Assertion review supplements coverage: a temporary in-memory mutation using
`patch.object(Validations, "validate_int", side_effect=TypeError("wrong message"))`
caused `test_raises_type_error_for_non_castable_type` to raise AssertionError.
The old `False or " is not an integer"` expression was verified truthy. Production
code was not mutated on disk.

### Isolation, formatting, and inspections

- Full default command `../bin/python -m pytest`: **8,037 passed, 35 skipped in
  16.57s**, after the final Python edits, with a 120-second process cap. This is
  one validation run, not an after median or a demonstrated timing improvement.
- Each changed module ran separately via `../bin/python -m pytest -q <module>`:
  validations 32/0.23s, deque 19/0.21s, engine state 95/0.27s, checkpoint 64/0.26s,
  make-service 4/1.18s (passed cases / pytest time). Fresh-process wall times were
  0.394, 0.377, 0.445, 0.430, and 1.383 seconds respectively.
- `../bin/python -m pytest -q tests/db/test_engine_state.py::TestEngineStateRampArbitration::test_a_settling_ramp_and_an_abort_do_not_deadlock`
  passed three fresh-process repetitions (0.402–0.417s wall, 0.23s pytest each).
  Individual subprocess caps were 60s; no timeout fired. No per-test timeout
  plugin is installed, so no enforced 5–20s case deadline is claimed.
- `../bin/python -m ruff format --check tests/utils/test_validations.py tests/utils/test_unique_deque.py tests/db/test_engine_state.py tests/gui/test_gui_checkpoint.py tests/cli/test_make_service.py`
  passed for all five files after formatting the extra blank line in engine state.
- PyCharm `get_file_problems --errorsOnly false` inspected all five modified
  test files. Final inspections have no errors, warnings, or weak warnings.
  Existing findings in the two large modules were resolved with accurate optional
  annotations, explicit type assertions, and local explained suppressions for
  deliberate headless/PDI doubles, imported runtime patch targets, and callback
  parameter shadowing. Assertions and `raising=True` guards were not weakened.
- American English review: the checkpoint test name is now
  `test_an_unrecognized_lcs_port_falls_through_to_the_generic_panel`; both engine
  state test names use `canceling`, and the ramp comment uses `canceled`. The
  baseline `doc/test-suite-audit-data/inventory.md` retains its original node IDs
  as historical evidence. No test-name spelling limitation remains.
- `PYTRAIN_API_CHECKOUT` remains unavailable; the same 34 integration cases and
  one server-specific parameter are skipped. Concurrent production edits were
  left untouched. Baseline inventories/hashes/rankings were not overwritten.

## Step 4: smoke selection and final verification

The `smoke` marker is registered without default filtering. Inline decorators
and `pytest.param` marks select existing tests and individual parameter
combinations in their own modules. The former node-ID manifest and root
collection hook were removed after review: inline marks cannot become stale
through node-ID changes and do not depend on rootdir or hook order. No duplicate tests were added,
no cases were removed in this step, and the Step 2 removed-to-survivor mapping
and count reconciliation remain unchanged. Full collection remains 8,072 cases.

### Verified selection

All paths below are relative to `tests/`; together these are the 12 exact IDs
reported by `--collect-only -q -m smoke` (8,060 deselected):

| Existing case | Behavioral reason |
|---|---|
| `cli/test_pytrain.py::test_startup_options_and_api_handoff` | Real startup parsing and API queue/thread handoff through inert service doubles |
| `cli/test_pytrain_commands.py::test_decode_and_send[False]` | Protocol request encoding/decoding round trip and send dispatch |
| `cli/test_pytrain_commands.py::test_decode_and_send[True]` | PDI request encoding/decoding and send dispatch |
| `cli/test_pytrain_commands.py::test_subparser_mode_inference[engine]` | Engine command parser, address, data, scope, and protocol |
| `cli/test_pytrain_runtime.py::test_shutdown_real_helpers_isolate_failures_and_retry[True-unregister]` | Simultaneous cleanup failures, continued teardown, retained ownership and retry |
| `cli/test_pytrain_runtime.py::test_failed_cache_stop_warns_and_continues_to_update` | Logged ordinary failure does not prevent deferred update; explicit retry |
| `cli/test_pytrain_runtime.py::test_interrupted_full_shutdown_retries_cache_but_never_updates[False]` | Genuine KeyboardInterrupt propagates; update suppressed and retry succeeds |
| `db/test_ramp_claim_state.py::test_first_claim_wins_until_matching_release` | State updates preserve ownership until matching release |
| `db/test_engine_state_core.py::TestEngineStateCommandHandling::test_a_base_memory_field_update_is_applied_to_the_record` | Real PDI BASE_MEMORY update through state.update changes the engine record's max_speed |
| `gui/test_scroll_input.py::test_sub_row_motion_accumulates_and_resets_on_reversal_or_idle` | Headless GUI input accumulation, direction reversal, and idle reset |
| `pdi/test_d4_req.py::test_build_count_request_roundtrip_engine` | D4 request construction and wire round trip |
| `protocol/test_command_req.py::TestCommandReq::test_variable_target_speed_data[7-1-CommandScope.ENGINE]` | Direct TMCC2 build/bytes/from_bytes round trip, including payload, address, scope, type, and wire-length assertions |

Other parameters, SystemExit cancellation, real worker/process isolation, and
optional integration remain in the full suite. Smoke is intentionally a small
cross-section, not comprehensive regression coverage. README commands explain
affected-module runs, full pre-check-in validation, profiling, and inline-mark
maintenance: preserve marks when moving tests and review area coverage when changing membership.

### Final performance evidence

Same Python 3.13.16 SDK, platform, plugin versions, auto-loading, coverage-disabled
settings, and sequential fresh-process approach as the baseline. No production
changes were made by this step. `PYTEST_ADDOPTS` was unset for full runs and set
to `-m smoke` only in the smoke measurement subprocess environment; no persistent
environment change was made. All runs exited zero; no process timeout fired.

| Measurement | External wall seconds | Median / range |
|---|---|---|
| Original ordinary baseline | 16.692 / 16.703 / 16.770 | 16.703 / 16.692–16.770 |
| Step 3b ordinary | 14.074 / 14.355 / 14.257 | 14.257 / 14.074–14.355 |
| Final ordinary | 14.283 / 14.303 / 14.294 | 14.294 / 14.283–14.303 |
| Final profiled (separate) | 14.538 / 14.676 / 14.692 | 14.676 / 14.538–14.692 |
| Smoke (12 cases), ordinary with duration reporting | 1.515 / 1.516 / 1.508 | 1.515 / 1.508–1.516 |
| Full collection only | 1.446 | One fresh process |
| Smoke collection only (12 cases) | 1.455 | One fresh process |

The full-suite medians/rankings above were measured before the final selection
corrections; they remain comparable historical full-suite evidence, not new runs.
The corrected unfiltered verification passed in **14.223s external wall**
(13.55s pytest time). The current smoke measurements use runner labels
`step4-corrected-smoke-1`, `-2`, `-3`, and `step4-corrected-collection`;
their process JSON is retained directly in `test-suite-audit-data/`.
Each local smoke log recorded **12 passed, 8,060 deselected** (1.01–1.02s pytest time).
The earlier unsupported 1.21s wall-time claim is withdrawn.

The observed ordinary median difference is **2.409s (14.4%)** below baseline,
not a causal claim: concurrent production edits, machine load, and caches remain
confounders. The final median is only 0.037s above Step 3b. Smoke meets the local
five-second goal without any timing assertion; collection dominates its wall
time and can vary as modules/dependencies grow. Coverage-instrumented Step 2
results are not included in any performance median.

Profiled aggregate setup/call/teardown seconds respectively were
**2.688/8.114/0.639**, **2.653/8.283/0.649**, **2.642/8.231/0.648**.
Their medians are **2.653/8.231/0.648s**; these do not include all collection,
reporting, and process overhead. The final rankings appendix gives the top 25
individual cases, phases, parameter families, setup/call/teardown rankings,
all module totals, and 544 fixture definitions with setup invocation costs.
The largest fixture setup totals are route-builder `panel` **0.661s / 317
invocations**, sequence `pdi_send` **0.284s / 859**, route-builder `desktop_panel`
**0.114s / 89**, and CLI `runtime` **0.100s / 144**. These exclude dependency
setup; finalizers are attributed to case teardown, not individual fixtures.

Reproduction uses existing `scripts/audit_test_suite.py` (choose unused labels):

```sh
# Repeat each numbered command for 1, 2, and 3, sequentially.
../bin/python scripts/audit_test_suite.py step4-plain-1 --plain --timeout 120
../bin/python scripts/audit_test_suite.py step4-profile-1 --timeout 120
PYTEST_ADDOPTS='-m smoke' ../bin/python scripts/audit_test_suite.py step4-corrected-smoke-1 --plain --timeout 60
../bin/python scripts/audit_test_suite.py step4-collection --plain --collect-only --timeout 60
PYTEST_ADDOPTS='-m smoke' ../bin/python scripts/audit_test_suite.py step4-corrected-collection --plain --collect-only --timeout 60
../bin/python scripts/audit_test_suite.py --summarize --runs step4-profile --report-dir doc/test-suite-audit-data/raw/step4-report
```

Local ignored `raw/step4-*` held complete logs, source hashes, process
metadata, failures/collection diagnostics, and profile measurements. Final
process metadata and rankings were retained outside `raw/` before cleanup;
the final rankings remain separate from the baseline. These runs used process
caps of 60s for smoke/collection and 120s for full validation; no per-case timeout
plugin is installed, no enforced per-case cap is claimed, and no parallelism
was introduced. Existing worker deadlines and cleanup assertions remain intact.

### Prioritized remaining efficiency work

1. Use smoke plus affected modules during development; this provides much larger
   feedback savings than removing tiny assertions while preserving full CI.
2. Investigate route-builder fixture construction before broader sharing:
   its module totals **1.410s** and its popup-clear case **0.324s**. Only reuse
   proven immutable analysis; retain fresh GUI state, mocks, and parsers.
3. Consider narrowly stubbing incidental version lookup in non-version GUI
   parser tests (make-GUI module **0.340s**), retaining real version integration.
   Existing source-analysis caches must not be duplicated.
4. Review the previously identified 0.1s/0.2s GUI waits only with deterministic
   signaling and equivalent negative assertions; do not simply shorten sleeps.
5. Retain deliberate integration costs: multiprocessing **1.514s** total
   (spawn **0.611s**, forkserver **0.586s**, fork **0.317s** per case), launcher
   working-directory cases **0.300/0.296s**, real cache-worker termination
   **0.503s**, and in-flight ramp abort **0.202s**. None belongs in smoke.
   The broad command-request loops total **0.169s**, not a leading bottleneck.

### Validation and limitations

All 12 smoke cases passed in three fresh processes, including the real-helper
shutdown regressions, and all six measured full runs passed **8,037 cases with
35 skips**. Full collection and smoke collection were verified separately.
Final uninstrumented commands `../bin/python -m pytest -m smoke` and
`../bin/python -m pytest` also passed (12 and 8,037 cases respectively; 35 skips
only in the full run), using the confirmed equivalent absolute SDK executable.
After review, all eight inline-marked modules passed Ruff formatting and PyCharm
inspections with `--errorsOnly false`, including warnings and weak warnings.
Existing inspection findings were resolved with explicit non-None assertions,
an assertion on the queue callback's command, dynamic reads of the queue cleared
by shutdown, and local explained suppressions for mock APIs, imported patch
targets, intentional invalid sentinels, and private fixture state. No assertions
or patch-target existence guards were weakened. Names, comments, docstrings,
and documentation were reviewed for American English. No new behavior coverage
comparison is claimed beyond Step 2's focused line/branch comparison.

#### Inline-mark review verification

- Normal `--collect-only -q -m smoke` and the same command with `--rootdir=tests`
  both select the 12 cases above (8,060 deselected). Only the displayed `tests/`
  prefix changes. There is no selection hook or stale-ID registry.
- The shutdown matrix still has all six combinations in its original order;
  combining its two decorators lets only `[True-unregister]` carry the smoke mark.
- The original six inline-marked modules passed **390 tests in 1.47s** in the
  earlier review. The two added modules now pass **333 tests in 0.60s**.
- All 30 target-speed parameter IDs and their collection order exactly match
  `raw/baseline-1.json.gz`: data/address/scope, iterating data then address then
  scope. Only `(7, 1, CommandScope.ENGINE)` receives an inline smoke mark.
- Direct protocol and conventional engine-record updates are now included,
  rather than relying solely on CLI decoding and ramp ownership. Their small
  cost preserves the local five-second goal without weakening any assertions.
- Current membership, baseline-ID comparison, and full-suite verification were
  recorded in local `test-suite-audit-data/raw/step4-corrected-verification.log`
  before cleanup; the results are summarized above. Runner smoke and
  collection caps were 60s; full-suite verification used a 120s cap.
- Both newly touched modules have zero PyCharm findings, including warnings
  and weak warnings. Optional annotations and asserted local property values
  resolve type findings; three explained line-scoped PyTypeChecker suppressions
  cover deliberate ramp byte payloads forwarded through integer-annotated APIs.

The 34 optional API cases still lack `PYTRAIN_API_CHECKOUT` and were not executed;
the remaining skip is the server-specific GUI-exit parameter. Their skipped
bodies contribute no execution cost to this report. No production files,
dependencies, `tox.ini`, or CI settings were modified.