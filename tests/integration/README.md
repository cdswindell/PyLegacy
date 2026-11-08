# Local API receiver integration tests

These tests are **opt-in**. Without `PYTRAIN_API_CHECKOUT`, collection only creates
skipped cases: it does not import the API, probe its dependencies, or start children.
The variable must identify an existing checkout containing
`src/pytrain_api/pytrain_api.py`. Invalid explicit configuration fails, not skips.

```sh
PYTRAIN_API_CHECKOUT=/path/to/PyTrainApi \
PYTRAIN_API_PYTHON=/path/to/existing/api/environment/bin/python \
../bin/python -m pytest tests/integration/test_pytrain_api_exit.py -v -s
```

`PYTRAIN_API_PYTHON` is optional (default: pytest's interpreter). That interpreter
must already have both projects' runtime dependencies installed. Nothing is cloned,
downloaded, updated, or installed; neither checkout's dependency files are changed.
Use the same variables with `../bin/python -m pytest` for the complete suite.

Each of the 24 server/client × callback/queued × exit-action cases runs in a fresh
isolated (`-I -B`, no bytecode writes) child with a 30-second timeout. Timeout handling
kills and waits for the child. Only this checkout's canonical `pytrain` and the selected API source are
added to its import path. Class/enum identity and source origins are asserted;
Python/Uvicorn versions and action traces appear with `-s` and on failures.
Validated with the local API environment's Python 3.12.14 and Uvicorn 0.53.0.
Using that environment avoids adding API dependencies to the unit-test environment.

The real API and PyTrain constructors, command routing, shutdown, deferred methods,
and API post-server status dispatcher execute. Hardware, discovery, transport,
thread startup, dotenv access, and destructive commands are replaced at boundaries.
In the deterministic matrix, the queued run loop is driven synchronously inside a
controlled Uvicorn-return boundary; signals are recorded, not delivered. Real host update/reboot/relaunch
methods run with recorded shell/subprocess calls and a terminal `execv` sentinel.
Synthetic environment values replace user credentials; no `.env` is read or written.

Characterized existing behavior (not changed here): queued UPGRADE reports UPDATE,
callback UPGRADE reports UPGRADE, and queued UPDATE upgrades pip once in PyTrain
and again in the host. QUIT performs no host update or relaunch. Echoes and late
different commands cannot change the selected action or add notifications.

Two additional server/client cases inject a cache-stop error through real callback
shutdown. They verify an incomplete-cleanup warning, status publication before exactly
one notification, and normal host UPDATE/relaunch after the controlled server returns.
Other shutdown work completes, but notification does not mean cache resources were
released: the same manager remains owned until an explicit successful cleanup retry.
Late callbacks and retry add no notifications or host actions and preserve the status.
Cache stop itself is a controlled boundary; no independent API cache is simulated.

Queued cache-failure coverage belongs to fast unit tests (e.g.,
`test_failed_cache_stop_warns_and_continues_to_update`). The existing opt-in
integration failure cases remain callback-specific. Both callback and queued
shutdown now apply warning-and-continue policy: final cleanup independently logs
ordinary cache-stop failures and continues, ensuring that retained cache ownership
does not impede queued API handoff. Retained managers remain retryable, and exactly
one notification occurs.

Eight additional POSIX cases deliver **real SIGINT only to the isolated child**:
server/client system UPDATE endpoint delivery and queued UPDATE, RESTART, and QUIT.
These retain real `uvicorn.run()`, `Server.serve()`, signal capture/restoration/replay,
and wrapper return to the real API constructor. Only the server's `_serve()` service
body is replaced, so no listener or application startup runs. The endpoint function
runs directly with fake `CommandReq.send()` transport, not through HTTP/authentication.

A test-owned worker starts only after the main thread verifies Uvicorn installed
its handler. Async events bound worker completion and signal reception to five
seconds; a `finally` block joins workers with a five-second limit. The parent retains
its 30-second kill-and-wait timeout. Traces distinguish exactly one PyTrain `notify`,
one main-thread `uvicorn-receive`, and one intentional `uvicorn-replay`; replay is
not a second PyTrain send. Assertions cover cleanup/status before notification,
late echoes, wrapper return, and subsequent main-thread host dispatch. These cases
passed with Python 3.12.14 and Uvicorn 0.53.0. Run only them with
`-k real_signal` appended to the command above.

The 34 integration cases do **not** establish pre-Uvicorn startup interruption
safety, live HTTP/authentication deployment behavior, live hardware behavior, or
system-service relaunch behavior. No real Git, pip, apt, shutdown, or exec runs here.