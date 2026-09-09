---
sessionId: session-260909-100452-z6gv
---

# Log Findings

### What the `deckpress` trace proves

The log you captured accounts for the whole delay. Squeeze to first echo is **2.247 s**, and none of it is a defect in the input layer:

| Time | Event | Elapsed |
|---|---|---|
| 13.947 | `trigger rest` axis=5 raw=-0.969 → `squeeze` raw=-0.639 fraction=0.164 | — |
| 13.947 | `hold squeeze axis=5 action=startup threshold=1.000s` | 0.000 s |
| 14.960 | `hold fired axis=5 action=startup_delayed held=1.013s polls=50 gap=0.020s worst_gap=0.021s` | **1.013 s** |
| 14.961 | `Enqueue command [ENGINE 60 START_UP_DELAYED] (client)` | +0.001 s |
| 14.990 | `Enqueue command [ENGINE 60 START_UP_DELAYED] (client)` — the same command again | +0.029 s |
| 16.194 | first echo printed: `[ENGINE 60 START_UP_DELAYED]` | **+1.233 s** |
| 16.502 | second echo printed | +0.308 s |
| 17.281 | `trigger release` raw=-1.000, `hold release … emitted nothing; the hold already reported` | 3.334 s |

**1. The hold measured 1.013 s against a 1.000 s threshold.** `polls=50`, `gap=0.020s`, `worst_gap=0.021s` — the Tk loop never stalled, so the stalled-poll theory is dead. The 1.0 s threshold is real and it is the only threshold in the code.

**2. ~1.23 s of the wait is the round trip, not the Deck.** `CommBufferProxy.enqueue_command` (`comm_buffer.py:595`) sends synchronously over a fresh socket and the second send started 29 ms later, so the client→server hop is under 29 ms. `ClientStateListener.offer` (`client_state_listener.py:144`) stamps the echo on arrival with no batching, and `Base3Buffer.run` writes as soon as `select` wakes. The second-plus is the server → Base 3 → echo → relay path, outside this codebase.

**3. The command is sent twice.** `EngineGui.__init__` defaults `repeat: int = 2` (`engine_gui.py:145`), `get_repeats` only overrides it for the entries in `REPEAT_EXCEPTIONS` (`engine_gui_conf.py:431`), and `CommandReq._enqueue_command` loops the repeat with no spacing (`command_req.py:262`). Hence two enqueues and two echoes.

**4. The resting trigger has almost no margin.** The `rest` line reports raw=-0.969, which normalizes to 0.0155 against `trigger_dead_zone` 0.02 — under 0.005 of headroom. `_normalize_trigger` also computes `release = max(0.0, trigger_dead_zone - hysteresis)`, which with the bundled 0.02 / 0.05 collapses to exactly **0.000** (visible on every trigger line). A resting value that drifts to -0.95 would read as permanently squeezed and never be seen to let go.

### What this plan does about it

Per your answers: make the hold threshold a profile setting with a **0.75 s** default, and raise the resting-trigger margin. Items 2 and 3 above (the duplicate send, round-trip instrumentation, an instant on-screen cue) are recorded here but **deliberately not implemented** — you did not select them.

# Requirements

### Overview & Goals

The long-press threshold that separates `START_UP_IMMEDIATE` from `START_UP_DELAYED` is a module constant (`LONG_PRESS_SECONDS = 1.0`), so the only way to change how long R2 must be squeezed is to edit code and push a build. Make it a profile setting like every other feel-related number on the pad, shorten the shipped default to 0.75 s, and give the analog triggers enough dead zone that a trigger at rest can never read as squeezed.

### Scope

**In Scope**

- A `long_press_seconds` key in the control profile, validated alongside `dead_zone` / `repeat_interval` / `trigger_dead_zone`.
- The default long-press threshold drops from 1.0 s to **0.75 s**, applied to triggers *and* buttons carrying `startup` / `shutdown`.
- `long_press_seconds: 0.75` written into `steam_deck_default.json`, where an operator will find the other tunables.
- The `deckpress` diagnostics report the *effective* threshold rather than a constant.
- `trigger_dead_zone` in the bundled profile raised from 0.02 to **0.10**, so a resting trigger is unambiguous and the release threshold sits at 0.05 instead of 0.000.

**Out of Scope**

- The duplicate send (`EngineGui` `repeat=2`). Diagnosed above; not changed.
- Round-trip (send → echo) instrumentation.
- Any new on-screen confirmation when a hold fires.
- The Python fallback `DEFAULT_TRIGGER_DEAD_ZONE = 0.02`, which stays as-is so a hand-written profile that puts the quilling horn on a trigger keeps its responsive onset.
- Anything in the comm layer: `comm_buffer.py`, `base3_buffer.py`, `client_state_listener.py` are untouched.

### User Stories

- As an operator, I want to dial the startup/shutdown hold time in my profile so the pad feels right without waiting for a new build.
- As an operator, I want the shipped hold to be 0.75 s, so a deliberate hold is confirmed sooner while a tap is still clearly a tap.
- As an operator, I want a trigger I am not touching to never count as squeezed, so a startup can never fire from a resting trigger and a release is always recognized.
- As a maintainer, I want a profile that omits the new key to keep loading and behaving predictably.

### Functional Requirements

1. `ControlProfile` exposes `long_press_seconds: float`, defaulting to 0.75 s when the profile omits it.
2. `from_dict` rejects a value outside `0.1 .. 5.0` with a `ProfileError` naming `long_press_seconds`.
3. A trigger or button bound to `startup` / `shutdown` emits its `*_DELAYED` action the moment the hold reaches the **profile's** threshold, while the control is still down — the behavior added earlier, now driven by the profile.
4. A press released before that threshold still reports its `*_IMMEDIATE` action on the release.
5. The bundled profile sets `long_press_seconds: 0.75`, so the Deck's hold is 0.75 s out of the box.
6. The `deckpress[hold]` lines print `threshold=` from the profile, so a `-debug` session reports the number actually in force.
7. The poll-stall diagnostic stays proportionate to the effective threshold (one tenth of it) rather than to a fixed constant.
8. The bundled profile's `trigger_dead_zone` is 0.10, keeping it above `hysteresis` (0.05) so the release threshold is 0.05 rather than 0.000.

### Non-Functional Requirements

- No new threads, no per-poll allocation, no change to the 20 ms poll cadence.
- Existing profiles (including `examples/steam-deck.json`, which binds no triggers) keep loading unchanged.
- `STARTUP_LONG_PRESS_SECONDS` stays importable — roughly twenty test sites and the cross-module spelling in `accessory_bindings.py` depend on the module-level names.

# Technical Design

### Current Implementation

**The threshold** — `src/pytrain/gui/controller/steam_deck_input.py`

```python
LONG_PRESS_SECONDS = 1.0                       # line 156
STARTUP_LONG_PRESS_SECONDS = LONG_PRESS_SECONDS # line 158, back-compat alias
DIAG_POLL_STALL_SECONDS = LONG_PRESS_SECONDS / 10.0  # line 183
```

It is compared in exactly three places, all on `SteamDeckInputProvider` (which already holds `self.profile`):

- `_held_long_press_actions()` — the sweep at the end of `poll()`; two `now - pressed_at < LONG_PRESS_SECONDS` tests, one for buttons and one for trigger axes, each followed by a `fired …` diagnostic.
- `_trigger_long_press_actions()` — the release fallback for a poll that saw squeeze and release together, plus the `squeeze` / `release` diagnostics.
- `_long_press_button_actions()` — the same fallback for a button, plus its `press` / `release` diagnostics.

**The profile** — `ControlProfile` (line 611) is a frozen dataclass whose optional feel settings each have a default and a range check in `from_dict` (line 638): `trigger_dead_zone`, `touch_dead_zone`, per-button `repeat_interval`. `long_press_seconds` slots straight into that pattern.

**The trigger dead zone** — `_normalize_trigger` (line 1224):

```python
fraction = max(0.0, min(1.0, (value + 1.0) / 2.0))
dead_zone = self.profile.trigger_dead_zone
release = max(0.0, dead_zone - self.profile.hysteresis)
```

With the bundled `trigger_dead_zone: 0.02` and `hysteresis: 0.05`, `release` is 0.000 — which is what every `deckpress[trigger]` line in your log printed.

### Key Decisions

1. **`LONG_PRESS_SECONDS` becomes the default, not a second source of truth.** Its value changes to `0.75` and it is used as the dataclass field default; the provider reads `self.profile.long_press_seconds` at every decision point. The name and the `STARTUP_LONG_PRESS_SECONDS` alias survive, so no test import or cross-module spelling breaks.
2. **Range `0.1 .. 5.0`.** At the 20 ms poll, 0.1 s is five polls — the shortest hold that can honestly be told from a tap. Anything past 5 s would read as broken hardware. Same shape as the `repeat_interval` check.
3. **Profile-wide, not per-binding.** One number covers both triggers and both startup/shutdown buttons, so L2 and R2 cannot disagree about what a hold is. A per-binding override (like the per-button `repeat_interval`) stays available later if you want it.
4. **The stall diagnostic follows the threshold.** `DIAG_POLL_STALL_SECONDS` is replaced by `DIAG_POLL_STALL_FRACTION = 0.1`, applied to the effective threshold, keeping the original rationale ("a tenth of the measurement, well clear of the 20 ms poll") true at any configured value.
5. **The dead zone is raised in the bundled JSON only.** In the bundled profile the triggers are *digital* (`4` → shutdown, `5` → startup); the quilling horn lives on the trackpads. So 0.10 costs nothing there and buys real margin. The Python fallback stays 0.02 for hand-written profiles that use a trigger as an *analog* horn, where a small onset is the point. From your log a normal squeeze is first seen at fraction 0.164, already past 0.10 — the hold still starts on the first axis event.
6. **The release threshold is fixed by arithmetic, not by new code.** With `trigger_dead_zone` 0.10 and `hysteresis` 0.05, `release` becomes 0.05, so a release is recognized before the trigger returns to its exact resting extreme. `_normalize_trigger` itself is not changed (you declined the separate release floor); instead `from_dict` logs a warning when `trigger_dead_zone <= hysteresis`, so a profile that can never see a release announces itself at load time.

### Proposed Changes

**`steam_deck_input.py`**

```python

# The default hold, in seconds, that separates a tap from a hold on a control bound to

# startup/shutdown. A profile may override it with long_press_seconds; this is what one

# that says nothing gets.

LONG_PRESS_SECONDS = 0.75
STARTUP_LONG_PRESS_SECONDS = LONG_PRESS_SECONDS
LONG_PRESS_SECONDS_MIN = 0.1   # five polls at CONTROLLER_POLL_MS; less cannot be told from a tap
LONG_PRESS_SECONDS_MAX = 5.0
DIAG_POLL_STALL_FRACTION = 0.1  # replaces DIAG_POLL_STALL_SECONDS

@dataclass(frozen=True)
class ControlProfile:
    ...
    long_press_seconds: float = LONG_PRESS_SECONDS
```

`from_dict`, beside the existing optional-number reads:

```python
long_press_seconds = (
    cls._number(data, "long_press_seconds") if "long_press_seconds" in data else LONG_PRESS_SECONDS
)
if not LONG_PRESS_SECONDS_MIN <= long_press_seconds <= LONG_PRESS_SECONDS_MAX:
    raise ProfileError("long_press_seconds must be between 0.1 and 5 seconds")
if trigger_dead_zone <= hysteresis:
    log.warning(
        "trigger_dead_zone %.3f is not above hysteresis %.3f: a squeezed trigger is only "
        "seen to let go at its exact resting value", trigger_dead_zone, hysteresis,
    )
```

On the provider, one read-through property so the three decision points and the diagnostics cannot drift:

```python
@property
def _long_press_seconds(self) -> float:
    return self.profile.long_press_seconds
```

Applied at: both comparisons in `_held_long_press_actions`, the release fallback in `_trigger_long_press_actions`, the release fallback in `_long_press_button_actions`, every `threshold={…:.3f}s` diagnostic, and the stall test in `_diag_poll` (`self._long_press_seconds * DIAG_POLL_STALL_FRACTION`).

**`steam_deck_default.json`** — the tunables block at the top becomes:

```json
{
  "dead_zone": 0.15,
  "trigger_dead_zone": 0.10,
  "touch_dead_zone": 0.05,
  "hysteresis": 0.05,
  "long_press_seconds": 0.75,
  "throttle_rate": 36.0,
  "repeat_interval": 0.1,
  "direction_threshold": 0.75
}
```

### Data Models / Contracts

| Key | Type | Default | Valid range | Effect |
|---|---|---|---|---|
| `long_press_seconds` | float | 0.75 | 0.1 – 5.0 | Hold at which a `startup`/`shutdown` control emits its `*_DELAYED` action |
| `trigger_dead_zone` | float | 0.02 (bundled: 0.10) | 0 – 1 | Normalized travel at which a trigger counts as squeezed; release is `trigger_dead_zone - hysteresis` |

### File Structure

| File | Change |
|---|---|
| `src/pytrain/gui/controller/steam_deck_input.py` | Default constant → 0.75, range constants, `ControlProfile.long_press_seconds`, `from_dict` validation + release-collapse warning, three decision points and the diagnostics read the profile, stall threshold derived from it |
| `src/pytrain/gui/controller/steam_deck_default.json` | `long_press_seconds: 0.75`; `trigger_dead_zone` 0.02 → 0.10 |
| `tests/gui/controller/test_steam_deck_input.py` | New profile-parsing, honored-threshold, diagnostic and dead-zone tests; `test_bundled_profile_uses_small_trigger_dead_zone` reworked |
| `examples/steam-deck.json` | Unchanged — binds no triggers and sets no `trigger_dead_zone` |

### Architecture Diagram

```mermaid
graph TD
    J[steam_deck_default.json<br/>long_press_seconds 0.75<br/>trigger_dead_zone 0.10] --> P[ControlProfile.from_dict<br/>range checks]
    P --> PR[SteamDeckInputProvider]
    PR --> N[_normalize_trigger<br/>dead zone / release]
    N --> T[_trigger_long_press_actions<br/>records pressed_at]
    T --> H[_held_long_press_actions<br/>every 20 ms poll]
    H -->|held >= profile threshold| A[DeckAction startup_delayed]
    H --> D[deckpress hold<br/>threshold= from profile]
    A --> R[DeckInputRouter.handle]
    R --> G[EngineGui.on_engine_command]
```

### Risks

- **A tap becomes a hold more easily.** 0.75 s is a quarter-second less room; if a brisk squeeze starts reporting `startup_delayed`, the profile key now exists to raise it without a build.
- **Divergence from the on-screen buttons.** `HoldButton.hold_threshold` stays 1.0 s, so the pad and the screen no longer agree. Deliberate — you asked for 0.75 s on the pad — and worth revisiting if it grates.
- **Trigger travel to engage grows five-fold** (raw ≈ -0.96 → ≈ -0.80). Immaterial for a digital startup/shutdown, and your log shows the first observed squeeze already at 0.164. It *would* matter for a hand-written profile that puts the quilling horn on a trigger, which is why the Python fallback stays 0.02.
- **`DIAG_POLL_STALL_SECONDS` disappears.** Module-internal — no test or other module imports it.

### Alternatives Considered

- **Per-binding `long_press_seconds`** (like the per-button `repeat_interval`): more flexible, but it lets L2 and R2 disagree about what a hold is, for no benefit you asked for.
- **A separate release floor in `_normalize_trigger`**: fixes the collapsed release threshold for every profile rather than just the bundled one, but changes normalization behavior for profiles that are working today. You chose the dead-zone bump; the load-time warning covers the rest.

# Testing

### Validation Approach

Everything here is exercised by the existing provider harness in `tests/gui/controller/test_steam_deck_input.py`: `SteamDeckInputProvider` takes an injected `pygame` stub and an injected `clock`, so a hold of any length is driven deterministically. The bundled profile is asserted directly through `ControlProfile.load(DEFAULT_PROFILE, fallback=False)`, as the existing bundled-profile tests already do.

After the changes, per the project guidelines: `../bin/python -m ruff format --check` on both changed Python files, then the full `../bin/python -m pytest` (currently 4022 passing).

### Key Scenarios

1. **The profile's value is honored.** A profile with `long_press_seconds: 0.25` fires `startup_delayed` on the poll that crosses 0.25 s — for a button *and* for a trigger axis — and a release at 0.20 s reports `startup_immediate` instead.
2. **The default applies when the key is absent.** `_profile()` (which omits it) yields `long_press_seconds == 0.75`.
3. **The bundled profile ships 0.75.** `ControlProfile.load()` reports `long_press_seconds == 0.75`.
4. **The diagnostics report the effective threshold.** With a 0.25 s profile and DEBUG enabled, the `deckpress[hold] squeeze …` and `… fired …` lines carry `threshold=0.250s`.
5. **The existing timing tests stay green unchanged.** The roughly twenty sites keyed on `STARTUP_LONG_PRESS_SECONDS` are all relative to the constant, so they follow it from 1.0 to 0.75 without edits — which is itself the check that nothing hard-codes the old number.
6. **The bundled trigger dead zone.** `trigger_dead_zone == 0.10`, still below `dead_zone`, and strictly above `hysteresis` so the release threshold is 0.05 rather than 0.000.

### Edge Cases

- **Out-of-range rejected:** `long_press_seconds` of 0.05 and of 6.0 each raise `ProfileError` matching `long_press_seconds`.
- **A resting trigger that drifts:** with the bundled dead zone, a raw value of -0.95 (fraction 0.025) normalizes to 0.0 — under the old 0.02 it read as *engaged*, which is the stuck-trigger hazard the log exposed at raw -0.969.
- **A real squeeze still engages immediately:** the raw -0.639 / fraction 0.164 first event from your log is past 0.10, so the hold timer still starts on the first axis event of a squeeze.
- **Collapsed release warns:** a profile with `trigger_dead_zone` 0.02 and `hysteresis` 0.05 still loads, and logs the warning naming both numbers.
- **A stalled poll still reports:** the existing stalled-poll test drives a 1.0 s gap, which stays far above the derived threshold (0.075 s at the default).
- **A hold that joins a chord** (e.g. the halt chord) and **a trigger whose panel takes a switch or route mid-squeeze** still emit nothing — the existing suppression tests must keep passing against the new threshold.

### Test Changes

- **Add:** profile parsing (honored value, default when omitted, both out-of-range rejections), threshold honored for a button and for a trigger, the diagnostic `threshold=` line, and the resting-drift normalization case.
- **Update:** `test_bundled_profile_uses_small_trigger_dead_zone` (lines 2105-2111) becomes a test of the *digital*-trigger dead zone — 0.10, below `dead_zone`, above `hysteresis` — with the reasoning that the bundled triggers carry startup/shutdown rather than the horn.
- **Unchanged:** `test_trigger_dead_zone_defaults_when_omitted` (the Python fallback stays 0.02) and all `_horn_profile()` tests, which rely on that fallback.

# Diagnostics Cost

### The question

Does the `deckpress` tracing added in `ca802b1d` cost anything, and should it be removed? Measured rather than estimated, driving the real `SteamDeckInputProvider` with the bundled profile under PyTrain's logging shape (root logger at DEBUG, handlers at INFO).

### Measurements

| Measurement | Diagnostics live | Short-circuited | Cost |
|---|---|---|---|
| idle `poll()` | 0.373 µs | 0.283 µs | **+0.09 µs** |
| `poll()` while a trigger is held | 0.586 µs | 0.430 µs | **+0.156 µs** |
| `_diag_trigger` per axis event (throttled, no line) | 0.170 µs | — | 0.170 µs |
| eager f-string at a `_diag` call site | 0.583 µs | — | 0.583 µs |
| `log.debug()` that both handlers reject | 1.98 µs | — | 1.98 µs |

The poll budget is `CONTROLLER_POLL_MS = 20`, i.e. 20,000 µs, so the diagnostics take about **0.003%** of it — roughly 5 µs per second idle, 8 µs during a hold. Even allowing 4× for the Deck's Zen 2 against the machine measured on, that stays under 0.02% of one core. No allocation on an idle poll, and `_diag_trigger_at` is keyed by axis so nothing grows without bound.

### The real finding: the guards never turn off

`dual_logging.set_up_logging` pins the **root** logger at DEBUG (`dual_logging.py:90`, "required for handler levels to work") and filters on the handlers; `-debug` only moves handler levels (`pytrain.py._enable_debug` / `_disable_debug` walk `log.root.handlers`, plus that one module's own logger). So `log.isEnabledFor(logging.DEBUG)` inside `steam_deck_input` is **permanently True**:

- `_diag_poll` takes its `time.monotonic()` and does its bookkeeping on every 20 ms poll, always.
- Every edge builds its f-string eagerly — the guard inside `_diag` cannot decline work the caller already did — then calls `log.debug()`, building a `LogRecord` both handlers discard (~2.0 µs).

Two comments therefore state something false, which matters more than the microseconds:

- `poll()`: "Inert unless -debug is on."
- `__init__`: "Long-press diagnostics, gathered only under -debug (see DIAG)".

### Decision: keep, and correct

- **It is the house pattern.** `ClientStateListener.offer` and `CommandListener.offer` run the identical `isEnabledFor(logging.DEBUG)` guard on every packet — far more traffic than 50 Hz — as do `comm_buffer.py`, `component_state.py` and `pdi_listener.py`. `hold_button.py` ships a permanent `DIAG = "holdbtn"` lifecycle trace for the same reason.
- **It paid for itself.** The captured log killed the stalled-poll theory (`polls=50 gap=0.020s worst_gap=0.021s`), proved the hold measured 1.013 s, and exposed the resting trigger at raw −0.969 with the release threshold collapsed to 0.000 — the evidence behind Step 3.
- **Maintenance cost is 231 lines** (`ca802b1d`: 150 in `steam_deck_input.py`, 81 in the tests) in a 2,830-line module, with three tests pinning the log format so it cannot rot silently.
- **Log volume is bounded**: `DIAG_TRIGGER_INTERVAL_SECONDS` throttles the trigger trace to 4 lines/s per squeezed axis, and only L2/R2 reach `_diag_trigger`.

### Alternatives Considered

- **Remove it** — a clean revert of `ca802b1d` and its three tests. Rejected: the next "the pad feels slow" report would start from nothing again, and the measured cost does not justify it.
- **A truthful runtime gate** (inspect `logging.getLogger().handlers` levels, which is what `-debug` actually toggles) — costs about as much per call as the guard it replaces. Superseded: the **Root Log Level** tab fixes the gate itself, so `log.isEnabledFor(logging.DEBUG)` becomes genuinely false and the two comments become true as written.
- **Lazy `detail` and a `DIAG_VERBOSE` flag** (mirroring `HoldButton._vdiag`) — this was the original Step 4. **Withdrawn**: it optimizes the eager f-strings at the `_diag` call sites, which fire only on edges (a handful per hold, 0.583 µs each). Once the root level closes the gate, `_diag_poll` and `_diag_trigger` short-circuit at 0.041 µs and the remaining eager cost is not worth the indirection.

# Root Log Level

### The question

> Can `dual_logging` use a different root log level so there is no cost?

**Yes — and the comment justifying the current pin is wrong.** This tab covers Steps 4-6.

### Why the pin is unnecessary

`dual_logging.set_up_logging`, line 90:

```python

# Set global log level to 'debug' (required for handler levels to work)

logger.setLevel(logging.DEBUG)
```

It is not required. Python filters twice, in order:

1. `Logger.debug()` calls `isEnabledFor(DEBUG)`, which resolves the *effective* level by walking up to the first ancestor with a level set — the root, since every PyTrain module logger is `NOTSET`. Below that level nothing is built at all.
2. `Logger.callHandlers` then tests `record.levelno >= handler.level` for each handler in the chain.

A handler never sees a record its logger already rejected, so the root only has to admit what the **most permissive handler will write**: `min(console_handler.level, logfile_handler.level)`. Pinning the root at DEBUG does not make handler levels work — it makes stage 1 a no-op and defers all filtering to stage 2, *after* the `LogRecord` and its `findCaller` stack walk have been paid for.

```mermaid
graph LR
    C["log.debug(...)"] --> L{"root level admits DEBUG?"}
    L -->|"no — proposed: INFO"| X["0.062 us, nothing built"]
    L -->|"yes — today: pinned DEBUG"| R["LogRecord + findCaller: 2.139 us"]
    R --> H{"handler level admits DEBUG?"}
    H -->|"no — INFO"| D["discarded, unread"]
    H -->|yes| W["console / pytrain.log"]
```

### Measured

Real `SteamDeckInputProvider` with the bundled profile, under PyTrain's handler shape (both handlers at INFO), 200,000 iterations each:

| Call | root=DEBUG (today) | root=INFO (proposed) | Saved |
|---|---|---|---|
| `log.debug("m")`, both handlers reject | **2.139 µs** | **0.062 µs** | **34×** |
| `log.isEnabledFor(DEBUG)` | 0.041 µs | 0.041 µs | — |
| idle `provider.poll()` | 0.413 µs | 0.324 µs | 0.089 µs |
| `provider.poll()` with a trigger held | 0.638 µs | 0.494 µs | 0.144 µs |

The guard itself is free either way — `isEnabledFor` is memoized in `Logger._cache`. The win is everything it currently fails to stop: **74 of the 111 `log.debug(` call sites in `src` are unguarded**, as are **21 of zeroconf 0.151.3's 24**, and a client runs a `ServiceBrowser` for its whole life.

The codebase already pays for the pin by hand. `swipe_detector._on_move`, line 161:

> *"Deliberately does no logging: this fires continuously during a drag, on the same thread that services the touch screen, so even a debug call here is a real cost."*

At root=INFO that call would cost 0.062 µs and the workaround would be unnecessary.

### The blocker: one guard is load-bearing

`pytrain.py:1126`, in `on_service_state_change`:

```python
info = zeroconf.get_service_info(service_type, name)
if info and log.isEnabledFor(logging.DEBUG):     # <-- gates real work
    if log.isEnabledFor(logging.DEBUG):          # <-- the tell: guarded twice
        log.debug(f"Discovered {PROGRAM_NAME} Server {name} ...")
    self._pytrain_servers.append(info)
    self._server_discovered.set()
```

The `and log.isEnabledFor(logging.DEBUG)` was hoisted out of the inner guard by mistake and now gates **server discovery itself**. It works only because the root is pinned. Lower the root without fixing it and a client's `_find_server` never populates `_pytrain_servers` nor sets `_server_discovered`, so the `while waiting > 0` loop (`waiting = 480`, `self._server_discovered.wait(0.5)`, lines 1056-1063) spins the full **240 seconds** and reports *"No PyTrain Server found on local network."*

An AST sweep of all 42 `isEnabledFor` guards in `src` found this is the **only** one that gates behavior. Every other is an early `return` inside a diagnostic helper (`hold_button._diag`/`_vdiag`, `steam_deck_input._diag`/`_diag_poll`/`_diag_trigger`) or a local built solely to be logged (`image_presenter.py:259`, `bt_id`).

### The other half: `-debug` must move the root too

`_enable_debug` / `_disable_debug` (`pytrain.py:1436` / `1429`) move the handler levels and **this one module's** logger:

```python
log.setLevel(logging.DEBUG)
for handler in log.root.handlers:
    handler.setLevel(logging.DEBUG)
```

That is why `-debug` appears to work today: `pytrain.cli.pytrain`'s own logger is explicitly DEBUG (and a child logger's records reach root handlers regardless of the root's *level*), while every other module rides the pinned root. Lower the root and `-debug` would silence every module but `pytrain.py`. Both must move together.

### Scope

**In Scope**

- `set_up_logging` derives the root level from the handler levels instead of pinning DEBUG.
- A shared `set_log_level(level)` helper in `dual_logging`, used by both `-debug` toggles, that moves the root and every root handler together.
- The `on_service_state_change` discovery guard, fixed first as a prerequisite.
- Reconciling the `deckpress` comments with a gate that now really closes.

**Out of Scope**

- Adding `isEnabledFor` guards to the 74 unguarded call sites — unnecessary once the root level does the filtering, which is the point.
- Changing any handler level, log format, rotation, or what `-debug` writes.
- The `DIAG_VERBOSE` / lazy-`detail` rework from the original Step 4 (withdrawn — see the Diagnostics Cost tab).
- `set_up_logging`'s ignored return value at `pytrain.py:1832` and the half-configured state a failed setup leaves behind. Pre-existing; noted under Risks.

### Data Models / Contracts

```python

# dual_logging.py -- new, beside set_up_logging

def set_log_level(level: int) -> None:
    """Move the root logger and every root handler to `level` together.

    The root level decides whether a record is built at all; a handler level only
    decides whether an already-built record is written. Setting the two apart -- a
    DEBUG root with INFO handlers -- means every log.debug() in the program builds a
    LogRecord that is then thrown away (2.139 us measured, against 0.062 us when the
    root declines it) and every `if log.isEnabledFor(DEBUG)` guard is permanently true.
    """
    root = logging.getLogger()
    root.setLevel(level)
    for handler in root.handlers:
        handler.setLevel(level)
```

In `set_up_logging`, the pin is replaced by two statements placed where the levels become known, so the early-return failure paths still leave a sane root:

```python
logger.addHandler(console_handler)
logger.setLevel(console_handler.level)     # after the console handler is validated
...
logger.addHandler(logfile_handler)
logger.setLevel(min(console_handler.level, logfile_handler.level))
```

| Configuration | Root level today | Root level proposed |
|---|---|---|
| Default (`set_up_logging()`, both handlers INFO) | DEBUG | INFO |
| `-debug` on, or `debug on` at the prompt | DEBUG | DEBUG |
| Console WARNING, file INFO (a test case) | DEBUG | INFO |
| Setup failed before the file handler | DEBUG | console handler's level |

### File Structure

| File | Change |
|---|---|
| `src/pytrain/utils/dual_logging.py` | Root level derived from the handler levels; new `set_log_level` helper; the false "required for handler levels to work" comment replaced with the two-stage filter explanation |
| `src/pytrain/cli/pytrain.py` | `on_service_state_change` discovery guard fixed; `_enable_debug` / `_disable_debug` delegate to `set_log_level` |
| `src/pytrain/gui/controller/steam_deck_input.py` | `DIAG` block records the new cost model; the two comments that were false become accurate; a note that the poll cadence starts cold when `-debug` is toggled on mid-session |
| `tests/utils/test_dual_logging.py` | Root-level assertions, `set_log_level` coverage, and `_reset_root_logger` restoring the level |
| `tests/cli/test_pytrain_service_discovery.py` | New — discovery works with the root at INFO |

### Risks

- **A debug line someone relied on goes missing.** Only if a module logger was explicitly raised outside `_enable_debug` — an AST sweep found no such site. Nothing that is *written* today changes: both handlers are at INFO, so every DEBUG record is already discarded.
- **A future load-bearing guard.** The `pytrain.py:1126` pattern could recur, and after this change it would fail silently instead of always passing. Mitigation: the discovery regression test asserts the append with the root at INFO, which is the shape of the failure.
- **Test-order coupling.** Importing `src.pytrain.cli.pytrain` runs `set_up_logging()` as a side effect, so the root level leaks across the session — as DEBUG today, as INFO after. Verified harmless: the full suite passes with the root forced to INFO before every test (4033 passed). `_reset_root_logger` restoring `logging.WARNING` removes the coupling for good.
- **Failed setup leaves a partial configuration.** Pre-existing (`set_up_logging()`'s return value is ignored at `pytrain.py:1832`); the two-stage `setLevel` keeps that path no worse than today.

# Delivery Steps

### ✓ Step 1: Make the long-press threshold a profile setting at a 0.75 s default
`ControlProfile` carries a validated `long_press_seconds`, the shipped default becomes 0.75 s, and the bundled profile states it.

- In `src/pytrain/gui/controller/steam_deck_input.py`, change `LONG_PRESS_SECONDS` from `1.0` to `0.75` and reword its comment to say it is the default a profile that says nothing gets; keep the `STARTUP_LONG_PRESS_SECONDS` alias so the ~20 test sites and the cross-module spelling keep importing.
- Add `LONG_PRESS_SECONDS_MIN = 0.1` and `LONG_PRESS_SECONDS_MAX = 5.0`, with the rationale that 0.1 s is five polls at `CONTROLLER_POLL_MS` and anything past 5 s reads as broken hardware.
- Add `long_press_seconds: float = LONG_PRESS_SECONDS` to the `ControlProfile` dataclass, beside the other optional feel settings (`trigger_dead_zone`, `touch_dead_zone`).
- In `ControlProfile.from_dict`, read the key when present via `cls._number` and raise `ProfileError("long_press_seconds must be between 0.1 and 5 seconds")` outside the range, in the same style as the `repeat_interval` check.
- Add `"long_press_seconds": 0.75` to the tunables block at the top of `steam_deck_default.json`, where an operator will find `dead_zone` and `repeat_interval`.
- Tests in `tests/gui/controller/test_steam_deck_input.py`: the key is parsed and exposed, it defaults to 0.75 when omitted, the bundled profile reports 0.75, and 0.05 / 6.0 each raise `ProfileError`.

### ✓ Step 2: Have the provider and its diagnostics honor the configured threshold
The hold fires at the profile's threshold rather than a module constant, and the `deckpress` trace reports the number in force.

- Add a `_long_press_seconds` property on `SteamDeckInputProvider` returning `self.profile.long_press_seconds`, so the decision points and the diagnostics cannot drift apart.
- Replace `LONG_PRESS_SECONDS` with it at all three decision points: both comparisons in `_held_long_press_actions` (the button sweep and the trigger sweep), the release fallback in `_trigger_long_press_actions`, and the release fallback in `_long_press_button_actions`.
- Update every `threshold={…:.3f}s` diagnostic — the `press`, `squeeze`, `fired` and `release` lines — to print the effective value.
- Replace `DIAG_POLL_STALL_SECONDS` with `DIAG_POLL_STALL_FRACTION = 0.1` and compute the stall threshold in `_diag_poll` from the effective threshold, keeping the original rationale (a tenth of the measurement, well clear of the 20 ms poll) true at any configured value.
- Refresh the module-header commentary and the docstrings that name `LONG_PRESS_SECONDS` as *the* threshold so they describe a profile setting with a default.
- Tests: a 0.25 s profile fires `startup_delayed` on the poll crossing 0.25 s for a button and for a trigger axis, a 0.20 s release still reports `startup_immediate`, and the `deckpress[hold]` lines carry `threshold=0.250s`. The existing chord-suppression and switch/route-mid-squeeze tests must keep passing, as must the ~20 tests keyed on `STARTUP_LONG_PRESS_SECONDS` without edits.

### ✓ Step 3: Give the resting trigger real margin in the bundled profile
A trigger at rest can no longer read as squeezed, and a release is recognized before the trigger reaches its exact resting extreme.

- Raise `trigger_dead_zone` in `steam_deck_default.json` from `0.02` to `0.10`, so the log's resting raw of -0.969 (fraction 0.0155) sits well clear of the engage point, and `release = trigger_dead_zone - hysteresis` becomes 0.05 instead of the 0.000 every trigger line reported.
- Leave the Python fallback `DEFAULT_TRIGGER_DEAD_ZONE = 0.02` and `_normalize_trigger` untouched, so a hand-written profile using a trigger as an analog quilling horn keeps its responsive onset and no existing `_horn_profile()` test changes.
- Add a `log.warning` in `from_dict` when `trigger_dead_zone <= hysteresis`, naming both numbers, so a profile whose release threshold collapses to zero announces itself at load rather than presenting as a stuck trigger.
- Rework `test_bundled_profile_uses_small_trigger_dead_zone` into a test of the digital-trigger dead zone: 0.10, still below `dead_zone`, strictly above `hysteresis`, with the reasoning that the bundled triggers carry startup/shutdown rather than the horn.
- Add a normalization regression: raw -0.95 reads as rest under the bundled profile (it read as *engaged* at 0.02), while the log's raw -0.639 / fraction 0.164 still engages, so a real squeeze starts the hold on its first axis event.
- Run `../bin/python -m ruff format --check` on both changed Python files and the full `../bin/python -m pytest`.

### ✓ Step 4: Stop the debug guard from gating zeroconf server discovery
A client records a discovered PyTrain server whatever the log level, so lowering the root level later cannot break discovery.

- In `src/pytrain/cli/pytrain.py`, rewrite `on_service_state_change` (lines 1122-1130) so the compound test `if info and log.isEnabledFor(logging.DEBUG):` becomes `if info:`, with the debug line kept inside its own guard — the inner `if log.isEnabledFor(logging.DEBUG):` on line 1127 already there is the evidence that the outer one was hoisted by accident.
- `self._pytrain_servers.append(info)` and `self._server_discovered.set()` then run for every added service, which is what `_find_server`'s `while waiting > 0` loop (lines 1060-1084) waits on; today they run only because the root logger is pinned at DEBUG.
- Leave the first guard (line 1122, the state-change trace) exactly as it is — that one really is logging-only.
- Add a comment recording why the shape matters: a guard that gates behavior costs a client the full `480 × wait(0.5)` = 240 s search and a "No PyTrain Server found on local network" before anyone suspects logging.
- New `tests/cli/test_pytrain_service_discovery.py`: drive `PyTrain.on_service_state_change` against a stub `self` (it touches only `_pytrain_servers` and `_server_discovered`) and a stub Zeroconf returning a `ServiceInfo`, asserting the append and the `Event` set **with the root logger at INFO** — the case that fails today. Cover `ServiceStateChange.Added` with `get_service_info` returning `None` as the no-op.

### ✓ Step 5: Derive the root log level from the handler levels and move it with `-debug`
A `log.debug()` nobody will read costs 0.062 µs instead of 2.139 µs, and `-debug` still turns on debug logging for every module.

- In `src/pytrain/utils/dual_logging.py`, delete the `logger.setLevel(logging.DEBUG)` pin (line 90) and its false comment ("required for handler levels to work"). Replace the comment with the two-stage filter: the logger level decides whether a `LogRecord` is built, the handler level only whether it is written, so the root must admit exactly what the most permissive handler will write.
- Set `logger.setLevel(console_handler.level)` after the console handler is validated and added, then `logger.setLevel(min(console_handler.level, logfile_handler.level))` after the file handler — two statements so the early-return failure paths still leave the root at a sane level.
- Add `set_log_level(level: int)` to `dual_logging`, moving the root logger and every root handler together, with a docstring carrying the measured reason the two must not be set apart.
- In `src/pytrain/cli/pytrain.py`, have `_enable_debug` and `_disable_debug` (lines 1429-1441) call `set_log_level(logging.DEBUG)` / `set_log_level(logging.INFO)` instead of walking `log.root.handlers`, and drop the now-redundant `log.setLevel(...)` on this module's own logger so `pytrain.cli.pytrain` inherits from the root like every other module.
- Tests in `tests/utils/test_dual_logging.py`: the root level equals the minimum of the two handler levels for INFO/INFO and for WARNING/INFO; `logging.getLogger().isEnabledFor(logging.DEBUG)` is false after a default setup, which is the assertion that pins the whole point; `set_log_level(logging.DEBUG)` raises the root and both handlers and a DEBUG record then reaches the file; `set_log_level(logging.INFO)` puts it back. Extend `_reset_root_logger` to restore `logging.WARNING` so the level no longer leaks between tests.
- Add a `-debug`-toggle test driving `PyTrain._enable_debug` / `_disable_debug` against a stub `self`, asserting a non-`pytrain` module logger (e.g. `logging.getLogger("src.pytrain.comm.comm_buffer")`) gains and loses `isEnabledFor(DEBUG)` — the regression that a handler-only toggle would not catch.

### ✓ Step 6: Reconcile the deckpress diagnostics with a gate that now really closes
The `deckpress` comments describe what the code actually does, and the cost model in the module header is the measured one.

- In `src/pytrain/gui/controller/steam_deck_input.py`, the `poll()` comment "Inert unless -debug is on" and the `__init__` comment "gathered only under -debug (see DIAG)" become **true** with Step 5 in place — keep them, and drop the correction planned when they were false.
- Extend the `DIAG` block comment with the measured cost so the next reader has numbers rather than a claim: 0.041 µs for the guard, 0.089 µs of a 20,000 µs poll when debug is on, 0.062 µs versus 2.139 µs for a `log.debug` nobody reads.
- Note in `_diag_poll`'s docstring that the poll cadence starts cold when `-debug` is toggled on mid-session: with the root at INFO the counters are not gathered, so the first `deckpress` line after enabling debug reports `polls=1 gap=0.000s`. The existing `previous is None` branch already handles it; the comment stops it being read as a stall.
- Do **not** add `DIAG_VERBOSE` or the lazy `detail` callable planned earlier: `_diag_poll` and `_diag_trigger` now short-circuit at 0.041 µs, and the eager f-strings that remain are edge-only — a handful per hold at 0.583 µs.
- Tests in `tests/gui/controller/test_steam_deck_input.py`: the three existing diagnostic tests keep passing unchanged (they set DEBUG explicitly via `caplog.at_level`); add one that a full press-and-hold emits **no** `deckpress` line and takes no `time.monotonic()` reading with the provider's logger at INFO, which is the behavior the comments now promise.
- Run `../bin/python -m ruff format --check` on every changed Python file and the full `../bin/python -m pytest` (baseline 4033).