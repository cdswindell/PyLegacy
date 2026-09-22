# PyLegacy Tests

## PyTrain CLI coverage

Install the test dependencies from `tests/requirements.txt` into the configured environment.
From the project root, measure this module without imposing a threshold on unrelated modules:

```bash
../bin/python -m pytest tests/cli --cov=src.pytrain.cli.pytrain --cov-branch --cov-report=term-missing --cov-report=html
```

Startup tests use opt-in `bare_pytrain` and `pytrain_startup` fixtures in
`tests/cli/conftest.py`. They bypass singleton construction, retain real argument
parsing, and replace service factories and runtime handoffs with inert doubles.
Process arguments, environment, current-instance/singleton state, and logging
levels and handlers are restored, including on exceptions. No hardware or network
services are needed. Runtime loops and discovery internals are tested separately.

The eventual target is 100% line and branch coverage, not the Step 1 baseline.
Step 1 measured baseline (Python 3.13.15, pytest-cov 7.1.0, coverage 7.10.7):
241 CLI tests pass, including 40 new startup/basic API tests. Line coverage is
512/1,187 (43.14%); branch coverage is 118/500 (23.60%); combined coverage is
37.34%, with no exclusions. The full suite passes (6,562 tests).

The coverage dependency is constrained below 7.11 because 7.16.1 raised an
import-time `KeyError` for the first importing test/conftest with the dotted
module command above. The same command succeeds with the verified 7.10.7
release.

Known production blockers (no exclusions or production changes applied):
- `base3_ip_addr`, line 475: the final return is unreachable because `is_client`
  is exactly the negation of `is_server`.
- Constructor lines 199–200: the missing-connection error is unreachable with the
  real parser. `client` defaults to true with no option to disable it; without a
  Base, server, or SER2, execution always enters client discovery instead.

Step 2 tests cover command registration/routing and real parse-only commands,
PDI request bytes through inert server/client transports, and bounded state
synchronization/database queries. Command construction needs `PyTrain._current`
registered even with `do_fire=False`; the command fixture registers its isolated
instance and rejects transport construction and thread startup.

Additional production findings from Step 2 (no production changes applied):
- `_handle_command`, branch 1196 to 1324: a nonempty stripped string split with
  `split()` cannot have an empty first token. Proposed cleanup: remove the
  redundant conditional and dedent its body.
- `_handle_command`, line 1222: the command parser never sets `command="help"`;
  argparse handles `-help` itself and exits. Proposed cleanup: remove that dead
  dispatch clause.
- `_do_pdi`, branch 1636 to 1640: a missing action already raises at lines
  1584–1585. Proposed cleanup: replace the final `elif ca is not None` with `else`.
- Debug logging of `pdi engine 7` raises `AttributeError: _run_level` in
  `BaseReq` before enqueueing. A characterization test records this existing
  defect; fixing the request representation requires separate production review.
- `pdi d4_engine clear 7` currently sends nothing; the no-op is explicitly tested.

Step 2 validation (Python 3.13.15): 274 new cases; all 515 CLI tests passed in
4.08 seconds and all 6,836 unit tests passed in 9.91 seconds. The focused command
above with `--cov-report=json` additionally reports 864/1,187 covered lines
(72.79%), 331/500 covered branches (66.20%), and 70.84% combined coverage.
State/query methods, `parse_cli`, `decode_command`, and `send_command` reached
100% line/branch coverage. `_handle_command` has only the dead help line and
two unreachable branch arcs remaining; `_do_pdi` has all lines and 89/90
branches covered. Runtime/discovery/administrative gaps remain for later steps.
Ruff formatting checks pass for the three new test files. Validation used
120-second pytest command bounds with `-q --tb=short --maxfail=10` and a
60-second formatter bound; no coverage exclusions were added.

Step 3 adds 55 runtime cases in `test_pytrain_runtime.py`: finite interactive/API/
headless loops, replay errors, startup ordering, deferred actions, queue accounting,
synchronous button scripts, and individual shutdown failures. The local `runtime`
fixture reuses `bare_pytrain` and rejects process execution, signals, sleeps, and
thread startup. Script tests intercept `Thread.start` and invoke the real loader's
`run()` against temporary files; shutdown tests use a real, nonblocking `Queue`.

Step 3 validation (Python 3.13.15): the runtime file passed in 0.33 seconds;
570 CLI tests passed in 4.41 seconds; all 6,891 unit tests passed in 9.80 seconds.
`run`, `queue_command`, `shutdown`, `shutdown_service`, and both `ButtonsFileLoader`
methods have 100% line and branch coverage. Module totals are 1,000/1,187 lines
(84.25%), 381/500 branches (76.20%), and 81.86% combined, without exclusions.
Ruff formatting passes for the new file. Commands used the configured
`../bin/python3.13` interpreter:

```bash
../bin/python3.13 -m pytest tests/cli/test_pytrain_runtime.py -q --tb=short --maxfail=5
../bin/python3.13 -m ruff format --check tests/cli/test_pytrain_runtime.py
../bin/python3.13 -m pytest tests/cli -q --tb=short --maxfail=10 --cov=src.pytrain.cli.pytrain --cov-branch --cov-report=term-missing --cov-report=json --cov-report=html
../bin/python3.13 -m pytest -q --tb=short --maxfail=10
```

Runtime characterization findings requiring review before production changes:
- `shutdown_service`, lines 1146–1148: failed Zeroconf unregistration skips close;
  either unregistration or close failure leaves service references intact.
  `shutdown()` catches that error and continues all remaining cleanup operations.
  A potential improvement is a `try/finally` around unregistration/close.
- `run`, lines 408–411: unexpected state-loading, button-loader join, or command
  errors perform service cleanup but do not invoke full `shutdown()`. Tests preserve
  this behavior; moving full cleanup into `finally` would need production review.

Step 4 extends the existing discovery/cache service files with 52 cases. Discovery
uses real inert `ServiceInfo` objects, mocked network readiness/browser/Zeroconf,
and finite event results: Base-only fallback takes 32 simulated half-second polls;
timeout takes 480. Tests verify combined-server preference, delayed arrivals,
logging independence, malformed advertisements, and cleanup/error propagation.
Cache tests cover advertisement encoding, manager arguments, capability gates,
idempotence, invalid properties, and stop-failure recovery without background work.

Step 4 validation (Python 3.13.15): 59 focused tests passed in 0.30 seconds;
622 CLI tests passed in 4.15 seconds; all 6,943 unit tests passed in 9.40 seconds.
`get_service_info`, `on_service_state_change`, `register_service`, `update_service`,
`cache_sync_properties`, `_start_cache_sync`, and `shutdown_service` have 100%
line and branch coverage. Module totals are 1,084/1,187 lines (91.32%), 426/500
branches (85.20%), and 89.51% combined, without exclusions. Remaining gaps are
outside discovery/cache, including the previously documented unreachable paths.
Both changed Python files pass Ruff formatting. Commands used the configured
interpreter (shown relative to the project); focused/formatter bounds were 60
seconds and CLI/full-suite bounds were 120 seconds:

```bash
../bin/python3.13 -m pytest tests/cli/test_pytrain_service_discovery.py tests/cli/test_cache_sync_service.py -q --tb=short --maxfail=5
../bin/python3.13 -m ruff format --check tests/cli/test_pytrain_service_discovery.py tests/cli/test_cache_sync_service.py
../bin/python3.13 -m pytest tests/cli -q --tb=short --maxfail=10 --cov=src.pytrain.cli.pytrain --cov-branch --cov-report=term-missing --cov-report=json --cov-report=html
../bin/python3.13 -m pytest -q --tb=short --maxfail=10
```

Discovery/cache characterization findings (no production changes applied):
- `update_service` mutates `ServiceInfo.properties` but does not rebuild its
  serialized `text` payload. A round-trip characterization test shows receivers
  still see the old cache capability/port. Proposed fix for approval: construct
  a replacement `ServiceInfo` with merged properties while preserving service
  metadata, and register that replacement after unregistering the old object.
- `cache_sync_properties` falls back for nonnumeric ports but accepts zero,
  negative, and out-of-range integers. Invalid UTF-8 raises `UnicodeDecodeError`.
  Port-range validation and decode-error handling would need production review.
- `_start_cache_sync` marks startup complete before building the manager, so a
  build failure is not retried. Resetting the flag on failure requires approval.
- Discovery browser-construction/poll errors are logged and close Zeroconf;
  cancellation errors still close Zeroconf but propagate. Zeroconf-construction
  and close errors also propagate. Tests preserve these current behaviors.

## Step 5 final validation

Added 134 cases across the new administrative tests and extended update/debug
tests. These cover real administrative request enums, callback deduplication,
targeted/broadcast/client routing, resync, interrupts, API statuses, service
detection, relaunch arguments/errors, update ordering, and debug/echo transitions
and no-ops. Signals, process replacement, subprocesses, threads, and delays are
intercepted. API shutdown and status recording are asserted before interruption.

Python 3.13.15 results: 160 focused tests passed in 0.33 seconds; 756 CLI tests
passed in 4.40 seconds; all 7,077 unit tests passed in 9.61 seconds. Ruff formatting
checks passed for all three changed Python files. Module coverage is **1,184/1,187
lines (99.75%), 495/500 branches (99.00%), and 99.53% combined**, with zero
exclusions. All administrative/update/debug lines and branches are covered.

Commands used the configured interpreter at
`/Users/davids/Documents/dev/PyLegacyEnv/bin/python3.13` (shown relative below).
Formatter/focused tests used 60-second bounds; CLI/full-suite tests used 120 seconds:

```bash
../bin/python3.13 -m ruff format --check tests/cli/test_pytrain_admin.py tests/cli/test_pytrain_update.py tests/cli/test_pytrain_debug_toggle.py
../bin/python3.13 -m pytest tests/cli/test_pytrain_admin.py tests/cli/test_pytrain_update.py tests/cli/test_pytrain_debug_toggle.py -q --tb=short --maxfail=5
../bin/python3.13 -m pytest tests/cli -q --tb=short --maxfail=10 --cov=src.pytrain.cli.pytrain --cov-branch --cov-report=term-missing --cov-report=json --cov-report=html
../bin/python3.13 -m pytest
```

Literal 100% remains blocked by exactly these unreachable paths in
`src/pytrain/cli/pytrain.py`. Proposed cleanup requires user approval; none was
implemented, and `--cov-fail-under=100` was not enabled. References below reflect
the compatibility follow-up's current source; earlier step references are historical:

| Missing line / branch arc | Reason and proposed cleanup |
| --- | --- |
| 200 / 199 → 200 | The real parser defaults to client discovery when no connection is supplied; SER2 is necessarily enabled in this remaining constructor arm. Remove the impossible missing-connection guard, retaining SER2 initialization. Line 199 itself is covered. |
| 475 / 473 → 475 | Client is the negation of server. Remove the final fallback return and use an `else` for the client arm. |
| 1196 → 1327 | A nonempty stripped string cannot split into an empty first token. Remove the redundant conditional and dedent its body. |
| 1225 / 1224 → 1225 | Argparse handles help by exiting; it never returns `command="help"`. Remove the dead dispatch clause. |
| 1639 → 1643 | Missing actions already raise before reaching this arm. Replace `elif ca is not None` with `else`. |

No production files were modified for this step. Earlier characterization findings
remain unchanged and require separate review. Update tests also preserve the
current behavior that API `update()` upgrades pip before raising its exit exception,
whereas API `upgrade()` exits before running subprocesses; nonzero unchecked pip
results still proceed to relaunch, while OS exceptions propagate.

## Python 3.11–3.14 compatibility follow-up

The Step 5 results above are historical, single-interpreter results. A subsequent
user matrix reported two Python 3.11 failures (7,075 passing): unknown and
ambiguous command selection raised `SystemExit(2)` despite `exit_on_error=False`.
The custom `PyTrainArgumentParser` independently initializes `_exit_on_error=True`,
which its `error()` and `exit()` overrides consult. Those errors occur before the
command-specific parser's existing flag handling.

The local production fix retains the initial parser in `_handle_command()` and
calls its existing `clear_exit_on_error()` only in parse-only mode, allowing the
existing `ArgumentError` handler to return diagnostics. The checked-in guard also
checks `isinstance(command_parser, PyTrainArgumentParser)`. Each invocation creates
a fresh parser; interactive handling and command-specific restoration remain
unchanged. This follow-up adds no further production changes and does not modify
the shared parser, transport implementation, dependencies, or coverage exclusions.

All seven invalid-input cases remain. Unknown/ambiguous cases assert meaningful
diagnostics, empty stderr, and no enqueued commands. Six additional cases exercise
each selection failure followed by a valid engine parse and normal help (`?`,
`help`, or `engine -h`) on the same instance. Spies wrap real parsers to verify
fresh default flags, clearing only for parse-only calls, and untouched interactive
flags. Help still prints usage and raises `SystemExit(0)`; neither parsing nor help
sends commands. Existing train parsing, command-specific restoration on success
and failure, and normal-send tests remain intact.

Validation on September 22, 2026 used the configured SDK executable
`/Users/davids/Documents/dev/PyLegacyEnv/bin/python3.13`, shown relative below
instead of the generic `../bin/python` spelling. Commands ran in this order:

```bash
../bin/python3.13 -m pytest tests/cli/test_pytrain_commands.py::test_parse_failure_mode_isolation
../bin/python3.13 -m ruff format --check src/pytrain/cli/pytrain.py tests/cli/test_pytrain_commands.py
../bin/python3.13 -m tox -e py311 -- tests/cli/test_pytrain_commands.py tests/utils/test_argument_parser.py
../bin/python3.13 -m pytest tests/cli --cov=src.pytrain.cli.pytrain --cov-branch --cov-report=term-missing
../bin/python3.13 -m pytest
../bin/python3.13 -m tox -e py311,py312,py313,py314,lint
```

The first two commands used 60-second bounds; remaining commands used 120 seconds.
The new regressions passed (6 tests, 0.28 seconds); both Python files passed
formatting without reformatting. Focused Python 3.11.16 command/parser tests passed
(104 tests, 0.40 seconds; tox 0.83 seconds). Python 3.13.15 CLI coverage passed
(762 tests, 4.92 seconds); the full SDK suite passed (7,083 tests, 10.43 seconds).

The unchanged tox matrix actually ran every requested environment; none was
missing or skipped:

| Environment | Interpreter | Result | Pytest duration |
| --- | --- | --- | --- |
| py311 | Python 3.11.16 | 7,083 passed | 12.52 seconds |
| py312 | Python 3.12.14 | 7,083 passed | 11.73 seconds |
| py313 | Python 3.13.15 | 7,083 passed | 11.38 seconds |
| py314 | Python 3.14.7 | 7,083 passed | 11.86 seconds |
| lint | Ruff 0.16.8 | Check and format check passed; 444 files already formatted | — |

Remeasured coverage (pytest-cov 7.1.0, coverage 7.10.7) is **1,187/1,190 lines
(99.75%), 497/502 branches (99.00%), and 99.53% combined**. Both outcomes of the
new guard are covered. The only missing lines are 200, 475, and 1225; the five
unreachable branch arcs are listed in the updated blocker table above. No gaps
were excluded, no cleanup was implemented, and no 100% gate was added. Existing
JSON/HTML reports were not regenerated as part of this follow-up.