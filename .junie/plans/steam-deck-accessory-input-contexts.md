---
sessionId: session-260828-132535-zk0m
---

# Understanding

### Confirmation of your request

Yes — understood. To restate it in my own words so we are aligned before any code moves:

1. **This is a spec pass, not an implementation pass.** We expect several rounds of revision before anything is built.
2. **Accessories are the last scope to wire up**, and they are the hardest because one ACC port (TMCC ID / address) can be any of seven different things: BPC2, ASC2, AMC2, Sensor Track, a Lionel operating accessory, an operating accessory driven through ASC2 ports, or an unassigned port awaiting configuration.
3. **The GUI compounds it**: the same scope shows three different panel shapes — an operating-accessory control panel, an ASC2/BPC2/Sensor-Track ops panel, and a generic ACC control panel.
4. **The binding depends on the cross product** of what the port *is* and what panel is *showing*.
5. **It must be configurable, not hard-coded** — and you have accepted that this may require reworking what is already built.
6. **The Controls help page is explicitly out of scope this turn.** I have recorded exactly what it will need in the "Controls Page Notes" tab, and I will not touch it.
7. **A new Controls page may be needed** just for accessories; I have costed that but not committed to it.

### Amendments received on this pass

Four, all folded in below.

**A-1 — The generic ACC bindings follow the *panel*, not the component.** The hard buttons bind **whenever the generic ACC control panel is displayed, even for an LCS device.** The earlier predicate (`is_lcs_component is False`) was wrong, and the code shows exactly why: `apply_ops_mode_ui_non_engine` (`keypad_view.py:788-830`) branches Sensor Track → AMC2 → BPC2-or-ASC2 → **else**, and that `else` is the generic panel. An **LCS STM2** is `is_lcs_component is True` and matches none of the four, so it lands on the generic panel today — as does any LCS port whose `_control_req` / `_config_req` has not identified it yet. Under the old predicate those ports showed a full set of aux keys on screen and claimed nothing on the pad.

**A-2 — Stick ↔ sends `TMCC1AuxCommandEnum.TOGGLE_DIRECTION`.** This costs nothing new: the generic panel already carries a `toggle.jpg` key wired to `host.on_acc_command(["TOGGLE_DIRECTION"])` (`keypad_view.py:239-253`), and `on_acc_command` resolves any name through `TMCC1AuxCommandEnum.by_name`. The stick simply reaches the command that button already sends.

**A-3 — On a power district, the stick pushed right turns the power on and pushed left turns it off.** This was never specified: your original BPC2 requirement named R2, L2 and the D-pad pair only, and `direction` is bound in exactly one place in the table — `_ACC_GENERIC_BINDINGS` — which `acc_bpc2` deliberately does not inherit (the structural half of A-1). So the stick resolves nothing there and is claimed by the `acc` base under FR-0, which is the "does nothing" you saw. Working as specified; the specification was short.

The part of A-3 that is a genuine gap rather than a missing row: **the table cannot express it today.** `Dispatch.axis_signed` gates only *whether* a positive deflection fires — a route uses it to mean "up and right fire, down and left are swallowed" — and there is no way to give left and right **different** dispatches. That is the one new piece of mechanism this pass adds, and it is KD-9.

**A-4 — On an ASC2, the stick works the whole panel: pushed right On, pushed left Off, pushed up *or* down the momentary output.** Confirmed, and it splits cleanly into a half that is already specced and a half that is not:

- **The left/right pair is A-3 arriving by inheritance.** `acc_asc2` inherits `acc_bpc2`, so the `direction_left` / `direction_right` rows Step 6 adds reach the ASC2 panel with no entry of their own. This also settles open question 8 — the pair reaches ASC2, which is what you have just asked for — so nothing new is needed for it beyond building Step 6.
- **The vertical stick is genuinely new mechanism.** A momentary output has to stay energised for as long as the stick is held and drop the moment it recenters, and neither existing axis mode can say that: `axis_latched` fires once on deflection and has **no release at all**, and the analog mode (`acc_throttle`) sends a value rather than a press/release pair. So `Dispatch` gains a third axis mode — a held axis — which is KD-10.

A-4 answers the vertical half of open question 7 for the ASC2 panel. It stays open for a bare BPC2, where there is no momentary output for a held stick to hold.

One consequence worth stating up front, because it is the one place this could go quietly wrong: on the ASC2 panel **two controls can now hold the same output at once** — A (or D-pad ↑) and the stick. The off must therefore be sent when the *last* holder lets go, not when either does, or letting the stick recenter would kill an output the operator is still holding A down for.

### Your requirements, as I now read them

| Context | Predicate | Bindings |
|---|---|---|
| Generic ACC panel | the generic ACC panel is the one displayed — **regardless of `is_lcs_component`** | Stick ↕ → Throttle (relative speed); **Stick ↔ → `TOGGLE_DIRECTION`**; L1 → Rear Coupler; R1 → Front Coupler; D-pad ↑/↓ → Boost / Brake |
| BPC2 panel | `is_power_district` is True | R2, D-pad → and **stick pushed right** → `send_lcs_on_command`; L2, D-pad ← and **stick pushed left** → `send_lcs_off_command` |
| ASC2 panel | `is_asc2` is True | R2, D-pad → and **stick pushed right** → On; L2, D-pad ← and **stick pushed left** → Off; A, D-pad ↑ and **stick pushed up or down** → `KeypadView.when_pressed` while held, `when_released` on release / recenter |

Every binding in that table now has an on-screen twin on the panel it belongs to, which is a useful check that the mapping is honest rather than invented.

### One structural consequence of A-1

Because the generic bindings are now keyed to *the generic panel being shown*, they must **not** be inherited by the BPC2 and ASC2 contexts — those panels do not show the aux keys, so a coupler or a Boost has nothing to act on there. The chain therefore gains a base:

- `acc` — base for **any** accessory panel: swallow engine-only controls, nothing more.
- `acc_generic` — the aux-key bindings, reached only when the generic panel is up.
- `acc_bpc2`, `acc_asc2` — as before, over the same `acc` base.

This is a rename of what the earlier draft called `acc`, not a new mechanism.

### Decisions you have already made

- **Defaults in Python, overridable from `steam_deck_default.json`.**
- **Migrate switches and routes onto the new mechanism now**, so there is one mechanism rather than two.
- **Ordered context chain** — a pane reports `("acc_asc2", "acc_bpc2", "acc")` and the most specific entry wins.
- **Full profile `dpad` section** — the D-pad stops being hard-coded and becomes as bindable as buttons and axes.
- **Verb-plus-payload entries** — each binding names a dispatch verb and its payload.
- **AMC2, Sensor Track, operating-accessory overlay and unassigned ports are deferred** to a later pass.
- **The generic bindings follow the displayed panel**, so an LCS device on the generic panel is bound like any other accessory.

### Open questions I would like settled in the next pass

These are deliberately *not* resolved in this spec — they are what the next round of back-and-forth should decide:

1. **Numeric keypad on the generic ACC panel.** You listed it as a feature of that panel but gave it no binding. A gamepad has no clean way to offer 1–9; a chooser-style overlay (reusing `chooser_visible`) is the obvious candidate.
2. **What the generic ACC stick throttle sends.** `AccessoryState` carries `_relative_speed` and `KeypadView` has an `acc_throttle` slider with its own repeat loop. Should the stick drive `RELATIVE_SPEED` directly, or reuse the slider's send-and-repeat path so gamepad and touch cannot diverge? (Stick ↔ is now settled by A-2; this is only about stick ↕.)
3. **AUX1 on the ASC2 panel.** `KeypadView` shows `ac_aux1_cell` for ASC2 but your requirements do not bind it.
4. **Whether the operating-accessory overlay is a context or a page.** It is a popup with `OperationAssets`-driven buttons, so it may want a chooser rather than fixed bindings — this is most likely the "new page" you mentioned.
5. **Does an unassigned port claim controls or ignore them?** Claiming prevents a stray stick reaching a stale engine; ignoring is less surprising.
6. **Should the ACC contexts be pane-scoped or focused-only?** Switches and routes are per-pane; accessories may want the same.
7. **The vertical stick on a bare power district.** A-4 settles ↕ for the ASC2 panel (it holds the momentary output) but a BPC2 has no momentary output, so ↕ stays claimed and dropped there. The obvious symmetry would be `throttle_up` → On and `throttle_down` → Off, which KD-9's variant table would carry in two rows — but with the stick already meaning On/Off left and right, a second pair on the same stick may be more confusing than useful. Your call.
8. ~~**Should the A-3 stick pair be BPC2-only, or reach ASC2 as well?**~~ **Settled by A-4:** it reaches both, by inheritance.
9. **`SET_ADDRESS` and `AUX1_OPT_ONE` on the generic panel.** Both are aux keys on the panel that A-1 now binds, and neither has a control assigned. `SET_ADDRESS` in particular is one I would rather leave unbound than put on a button somebody can brush.
10. **Should a held stick on an ASC2 also drive `AUX1`?** A-4 gives the vertical stick the `CONTROL1` momentary. `AUX1` is the only other key on that panel and is still unbound (question 3), so if you want it on the pad it needs a control of its own.

# Requirements

### Overview & Goals

Give the Steam Deck gamepad meaningful control over the ACC scope, and do it through a **data-driven context mechanism** rather than another bespoke handler. The mechanism is the deliverable; the accessory contexts you specified are its first consumers, and switches and routes are migrated onto it to prove it can carry what already works.

A context is chosen by **the panel a pane is displaying**, not by a flag re-tested in the input layer — the correction behind amendment A-1, and the reason `KeypadView` gains a single property naming the panel it drew.

The end state: *what a control does in a given situation* is a table entry, editable from the bundled profile JSON, not a branch in `DeckInputRouter`.

### Scope

**In scope**

- A context-resolution mechanism: ordered context chains, per-context binding tables, Python defaults, profile overrides.
- A `dpad` section in the profile schema, making the D-pad bindable for the first time.
- A dispatch-verb registry so an entry can say *how* to send, not just *what*.
- Four accessory contexts: `acc` (base — claim only), `acc_generic`, `acc_bpc2`, `acc_asc2`.
- A single source of truth for *which accessory panel is displayed*, so the pad and the screen cannot disagree.
- Migration of `_handle_switch` / `_handle_route` onto the mechanism, behavior-for-behavior.
- A widget-free ASC2 momentary entry point on `EngineGui`.

**Out of scope (this turn)**

- **Any change to `ControlsPanel` or `control_labels.py`.** Recorded as notes only.
- AMC2, Sensor Track, unassigned-port and operating-accessory-overlay contexts.
- The numeric keypad on the generic ACC panel.
- Any change to on-screen accessory panels; the gamepad drives the panels that exist.

### User Stories

- As an operator with a generic accessory selected, I want the stick and shoulder buttons to work the way they do for an engine, so I do not have to relearn the pad per scope.
- As an operator with an LCS port that shows the generic panel (an STM2, or one not yet identified), I want the pad to drive the keys I can see, rather than going dead because the port happens to be an LCS device.
- As an operator with a reversible accessory selected, I want a flick of the stick to reverse it, so I do not have to find the toggle key on screen.
- As an operator with a power district selected, I want a trigger or a D-pad press to switch the block on and off without reaching for the screen.
- As an operator with an ASC2 selected, I want a button I can *hold* for a momentary output, because that is what the on-screen key does.
- As a user with an unusual layout, I want to retune any of this in my own profile without editing Python.
- As a maintainer, I want one mechanism for context remaps, so the next scope is a table entry rather than a fourth handler.

### Functional Requirements

**FR-0 — Base accessory context (`acc`)**

Active whenever a pane is showing **any** accessory panel. It binds nothing; it exists so that engine-only controls are **claimed and dropped** on every accessory panel, exactly as the switch and route contexts already do, and so a stick or trigger cannot address an engine the pane no longer holds. Each of FR-1 to FR-3 sits over it.

**FR-1 — Generic ACC context (`acc_generic`)**

Active when **the generic ACC control panel is the panel displayed** — that is, an accessory panel is up, an id is selected, and the state is neither Sensor Track, AMC2, BPC2 nor ASC2. **`is_lcs_component` is not consulted**: an LCS STM2, or an LCS port not yet identified, shows the generic panel and is bound here like any other accessory (amendment A-1).

| Control | Effect |
|---|---|
| Stick ↕ (own pane) | Accessory throttle / relative speed |
| Stick ↔ (own pane) | `TOGGLE_DIRECTION` — one toggle per deflection |
| L1 | Rear coupler |
| R1 | Front coupler |
| D-pad ↑ / ↓ | Boost / Brake, repeating while held |

Every one of these is a command the generic panel already offers on screen (`keypad_view.py:160-269`), so nothing new is invented for the pad.

Stick ↔ is **latched**: one `TOGGLE_DIRECTION` per push, re-armed only once the stick comes back near center, and the **sign is ignored** — left and right both toggle, because the command is a toggle and there is no left-hand or right-hand version of it. This is the same latch `_handle_direction` and `_throw_switch_from_axis` already use, driven by `direction_threshold` and `hysteresis`.

**FR-2 — BPC2 context (`acc_bpc2`)**

Active when the pane is showing an accessory panel, an id is selected, and `is_power_district` is True. Note this is **not** ACC-scope-only: `KeypadView.is_accessory_or_bpc2` (`keypad_view.py:99-104`) also admits a `LcsProxyState` power district under TRAIN scope, and that pane shows the BPC2 panel — so the context must follow that same predicate, not `scope == ACC`.

| Control | Effect |
|---|---|
| R2, D-pad →, **stick pushed right** | `send_lcs_on_command` |
| L2, D-pad ←, **stick pushed left** | `send_lcs_off_command` |

The stick pair (amendment A-3) is **latched and sign-specific**: one command per deflection, and the direction of the push chooses which. Push left for Off, let the stick come back through center, push right for On. A thumb resting on a deflected stick sends once, not once per poll.

The **vertical** stick on a *bare* power district stays claimed and dropped under FR-0 — there is no momentary output on that panel for it to hold. On an ASC2 it drives the momentary output, which is FR-3 below, and open question 7 is what remains: whether a BPC2 wants ↕ for On/Off as well.

**FR-3 — ASC2 context (`acc_asc2`)**

Active when the pane is showing an accessory panel, an id is selected, and `is_asc2` is True. Inherits `acc_bpc2`'s On/Off pair through the chain rather than restating it.

| Control | Effect |
|---|---|
| R2, D-pad →, stick pushed right | `send_lcs_on_command` |
| L2, D-pad ←, stick pushed left | `send_lcs_off_command` |
| A, D-pad ↑ | **Momentary**: press → `when_pressed`, release → `when_released` |
| **Stick ↕, either way** | **Momentary**: held past `direction_threshold` → `when_pressed`; recentered → `when_released` |

The momentary bindings are the only ones in this spec that need both phases, and they are why the dispatch verb carries the phase.

The stick ↕ row (amendment A-4) is **sign-blind and held, not latched**: up and down both energise the output, and it stays energised for as long as the stick is away from center. This is a third axis mode — see KD-10 — because the latched mode has no release and the analog mode sends a value rather than a phase.

The left/right pair arrives here **by inheritance from `acc_bpc2`**, with no entry of its own, which is what the chain is for.

**FR-3a — Last holder wins**

A (or D-pad ↑) and the stick ↕ drive the *same* `CONTROL1` output. While more than one of them is held the output stays on, and `when_released` is sent when the **last** one lets go. Releasing one control must never turn off an output another is still holding, and no control may be left holding an output that has already been switched off.

**FR-4 — Configurability**

- Every entry above is a **default**, defined in Python.
- A `contexts` section in the profile JSON overrides, adds or removes any entry.
- Removal is explicit (`null`), so "unbind this" is expressible and not merely an omission.
- An unknown context name, action or verb is **logged and skipped**, never raised — matching `ControlProfile.load`'s existing fallback discipline.

**FR-5 — No regression**

Switch and route behavior after migration is **identical**, verified by the existing suites in `tests/gui/controller/test_steam_deck_input.py` passing unmodified except where they reference internals that move.

### Non-Functional Requirements

- **No new per-event allocation.** Context resolution runs on every action inside the Tk-driven poll that also services the touch screen; resolution is a dict lookup over a short tuple.
- **Contexts are resolved fresh per action, never cached across actions** — a pane's scope can change between two presses of the same button, which is exactly the `_handle_switch` clean-up case.
- **The pad and the screen agree by construction.** The context reported must be derived from the *same* branch that chose the panel, so no accessory can show one set of keys and answer to another.
- **Tk-free tables.** `accessory_bindings.py` imports no `tkinter` and no `guizero`, so the whole map is testable headless, as `control_labels.py` already is.

# Technical Design

### Current Implementation

The input layer is three files plus a profile:

- **`steam_deck_input.py`** — `ControlProfile` (JSON schema + validation), `SteamDeckInputProvider` (SDL/hidraw → `DeckAction`), `DeckInputRouter` (`DeckAction` → GUI calls).
- **`control_labels.py`** — pure, Tk-free rendering of a profile into help-screen sections.
- **`steam_deck_default.json`** — the bundled profile: `axes`, `buttons`, `touchpads`, `chords`. **No `dpad` section.**

Context remaps today are **module constants plus a handler per panel type**:

- `SWITCH_THRU_ACTIONS` / `SWITCH_OUT_ACTIONS` / `SWITCH_AXIS_ACTIONS` / `SWITCH_BUTTON_ACTIONS` → `_handle_switch`, gated on `gui.switch_active`.
- `ROUTE_FIRE_ACTIONS` / `ROUTE_CLAIMED_ACTIONS` / `ROUTE_AXIS_ACTIONS` → `_handle_route`, gated on `gui.route_active`.
- `_controls_only` and `_chooser_only` are the same shape one level up: claim-everything gates that run before the layout sees an action.

`handle()` is an ordered chain of early-return gates:

```
disconnect → _controls_only → _chooser_only → _handle_switch → _handle_route → throttle → direction → quilling_horn → dpad ↕ → admin → dpad ↔ → repeat buttons → (pressed-only) → global → panel commands
```

The D-pad never reaches the profile at all: `_hat_actions` emits fixed `dpad_*` names and `_handle_scroll_boost` / `_handle_select_smoke` hard-code boost/brake and smoke.

GUI-side entry points that already exist and that the verbs will call:

| Target | Location |
|---|---|
| `on_acc_command(target, data)` → `TMCC1AuxCommandEnum` for `active_state` | `engine_gui.py:2549` |
| `send_lcs_on_command(state)` / `send_lcs_off_command(state)` → BPC2 vs ASC2 branch | `engine_gui_conf.py:503-508` |
| `KeypadView.when_pressed` / `when_released` → `Asc2Req(... CONTROL1, values=1/0)` | `keypad_view.py:882-903` |
| `switch_active` / `route_active`, `on_switch_command` / `on_route_command` | `engine_gui.py:1996-2042` |

Two details shape the design:

- `when_pressed` / `when_released` take a guizero `EventData` **only** to read `event.widget.enabled`. Extracting a widget-free `on_asc2_momentary(pressed: bool)` is therefore a genuine refactor, not a reimplementation.
- `KeypadView.apply_ops_mode_ui_non_engine` (`keypad_view.py:788-830`) already branches Sensor Track / AMC2 / BPC2-or-ASC2 / **else = generic** — **the same four-way split the contexts need**. Amendment A-1 is precisely a statement about that `else`: an LCS STM2 (`is_stm2`, and `is_lcs_component is True`) matches none of the first three and lands on the generic panel, as does any LCS port not yet identified by its `_control_req` / `_config_req`. So the context must be chosen by *the branch taken*, not by a flag re-tested elsewhere.
- The generic panel's aux keys are all `on_acc_command` calls, already wired: `FRONT_COUPLER` / `REAR_COUPLER` (`keypad_view.py:173, 189`), `BOOST` / `BRAKE` (205, 221), `SET_ADDRESS` (237), `TOGGLE_DIRECTION` (253) and `AUX1_OPT_ONE` (269). Amendment A-2 therefore needs no new verb or GUI method — `on_acc_command("TOGGLE_DIRECTION")` is the same call the on-screen key makes.
- `_handle_direction` (`steam_deck_input.py:1773-1795`) already gives a horizontal stick one fire per deflection via `direction_threshold` minus `hysteresis` and a per-target latch set. Stick ↔ → `TOGGLE_DIRECTION` reuses that shape rather than adding a second notion of "the stick was pushed".

### Key Decisions

**KD-1 — Ordered context chain, reported by the pane.** `EngineGui.input_contexts` returns a tuple, most specific first, e.g. `("acc_asc2", "acc_bpc2", "acc")`. The router walks it and takes the first context defining the action. Chosen over one flat name per context because `acc_asc2` then states only its *differences* from `acc_bpc2`, which is exactly how your ASC2 requirement reads.

After amendment A-1 the chains are:

| Panel displayed | Chain |
|---|---|
| Generic ACC | `("acc_generic", "acc")` |
| BPC2 | `("acc_bpc2", "acc")` |
| ASC2 | `("acc_asc2", "acc_bpc2", "acc")` |
| Sensor Track / AMC2 | deferred — no context reported this pass |

The aux-key bindings live in `acc_generic`, **not** in the shared `acc` base. That is the structural half of A-1: because they are keyed to the generic panel, they cannot leak onto a BPC2 or ASC2 panel, where there is no coupler or Boost key to correspond to them. `acc` carries only the claim.

**KD-2 — Defaults in Python, overrides in JSON.** `accessory_bindings.py` holds `DEFAULT_CONTEXTS`; `ControlProfile.from_dict` merges a `contexts` section over it. Code-reviewed defaults, user-retunable behavior.

**KD-3 — The D-pad becomes a first-class profile section.** A `dpad` section binds `up`/`down`/`left`/`right` to actions the same way `buttons` does. `_hat_actions` keeps emitting `dpad_*` so the provider is unchanged; the *router* resolves those through the profile instead of hard-coding. Today's boost/brake/smoke behavior moves into the bundled JSON, so it is visibly a default rather than a law.

**KD-4 — Verb-plus-payload entries.** Each entry names a dispatch verb from a small registry. Verbs, and the GUI method each calls:

| Verb | Calls | Phases |
|---|---|---|
| `acc_command` | `gui.on_acc_command(command, data)` | pressed |
| `engine_command` | `gui.on_engine_command(command, data)` | pressed |
| `lcs_on` / `lcs_off` | `gui.on_lcs_command(on=True/False)` | pressed |
| `asc2_momentary` | `gui.on_asc2_momentary(pressed)` | **both** |
| `switch_thru` / `switch_out` | `gui.on_switch_command(thru)` | pressed |
| `route_fire` | `gui.on_route_command()` | pressed |
| `acc_throttle` | `gui.on_acc_speed_command(value)` | analog |
| `claim` | nothing — swallow | both |

`claim` is the verb that makes the migration honest: the switch and route handlers' "swallow so it cannot reach an engine that is not there" becomes a table entry rather than a comment.

**KD-5 — Migrate switches and routes now, as a pure refactor.** `_handle_switch` / `_handle_route` are replaced by `switch` / `route` contexts in the same table. The distinctive parts — axis latching, the catalog's claw-back of the face buttons, the `_held_commands` / `_sequences` clean-up — become **per-context flags**, not lost behavior. Any behavior change here is a bug.

**KD-6 — `_controls_only` and `_chooser_only` stay as they are.** They are modal gates over *every* action, not per-action remaps, and folding them in would make the table describe two different things.

**KD-7 — One source of truth for the displayed panel: `KeypadView.accessory_panel_kind`.** Rather than have `EngineGui.input_contexts` re-derive "is this the generic panel?" as a four-way negation, extract the branch in `apply_ops_mode_ui_non_engine` into a property returning `"sensor_track" | "amc2" | "bpc2" | "asc2" | "generic" | None`, and have the UI code *and* `input_contexts` both read it. This is what makes A-1 stay true: the pad follows the panel because there is only one place that decides which panel it is. A duplicated negation is the exact drift the risk list already worried about, and re-testing `is_lcs_component` separately is how the first draft got A-1 wrong.

**KD-8 — Stick ↔ is a latched, sign-blind axis binding.** The `direction` action is bound in `acc_generic` to `acc_command TOGGLE_DIRECTION` and marked `axis_latched`, reusing the `direction_threshold` / `hysteresis` latch that `_handle_direction` and `_throw_switch_from_axis` share. Sign is ignored, as `_throw_switch_from_axis` already ignores it: the command is a toggle, so there is nothing for left and right to mean differently. A held stick toggles once, not repeatedly — the alternative would flip a crane or a gantry back and forth for as long as a thumb rested on it.

**KD-9 — A left/right split is expressed as directional pseudo-actions, not as a nested negative branch.** An axis action resolves `direction_left` / `direction_right` (and, by symmetry, `throttle_down` / `throttle_up`) **before** the plain action name, falling back to it when no variant is bound. Chosen over adding a `negative: Dispatch` field to `Dispatch` for three reasons:

1. **It already exists in the table, one row up.** `acc_bpc2` binds `dpad_right` → `lcs_on` and `dpad_left` → `lcs_off`. A-3 is that same pair on the stick, so it should read the same way — and the D-pad and the stick then become visibly two ways to reach one thing, which is what `startup` / `startup_immediate` / `startup_delayed` already do for the triggers.
2. **It survives the JSON round trip.** A profile override names `direction_left` as a flat key under `bindings`, needing no schema change; a nested negative branch would need both new schema and a second merge rule.
3. **The generic panel is untouched.** `acc_generic` binds plain `direction`, the fallback finds it, and `TOGGLE_DIRECTION` stays sign-blind per KD-8.

The sign-to-name mapping is a table in `accessory_bindings.py` rather than arithmetic in the router: `direction` → (`direction_left`, `direction_right`) and `throttle` → (`throttle_down`, `throttle_up`), positive taking the second. The bundled profile inverts axes 1 and 4, so positive already means up.

**The latch stays keyed on the physical action** (`direction`), not on the resolved variant name. Two independent latch sets would let a sweep straight across the stick fire both Off and On; one set means crossing center passes through `direction_threshold - hysteresis`, drops the latch and re-arms exactly once. That is also what makes "left for Off, back through center, right for On" behave the way an operator expects.

**KD-10 — A held axis is a third axis mode, beside latched and analog.** `Dispatch` gains `axis_held`. Where `axis_latched` fires once per deflection and never releases, and `is_analog` sends a value every time the stick moves, `axis_held` delivers a **press/release pair driven by position**: the press when `abs(value)` first crosses `profile.direction_threshold`, the release when it falls back inside `direction_threshold - hysteresis`. The thresholds are the ones the latched mode already uses, so a stick too light to throw a switch is too light to energise an output.

Four points make this the right shape rather than a variant of what already exists:

1. **It reuses the release path already built for the button.** `_handle_contexts` records a momentary press in `_momentary_holds`, keyed `(target, action)`, and delivers the release from that record rather than by re-resolving the chain — precisely so a pane re-scoped under the thumb cannot leave an output energised. A held axis records itself the same way; the only difference is what counts as a release. **A stick needs this more than a button does**, because a button's release event always arrives, while a stick's "release" is a value that may simply stop being reported.
2. **Sign-blindness is free.** `acc_asc2` binds plain `throttle`, so KD-9's variant resolution finds no `throttle_up` / `throttle_down` and falls back to it — up and down both energise, which is what A-4 asks for. A profile that wants them to differ binds the variants, and the mechanism carries it with no new code.
3. **Last-holder-wins is a predicate, not a new structure.** `_momentary_holds` is already a set of `(target, action)`; the release becomes "discard mine, and send the off only when no hold remains for this target". With a single holder that is identical to today's behavior, so FR-3a costs a condition rather than a reference count.
4. **`clear()` must release, not merely forget.** It currently empties `_momentary_holds` without sending anything. Harmless while only a button can hold — the release always arrives — but a pad that disconnects with the stick pushed would leave an accessory output energised with nothing left to turn it off. `clear()` therefore sends the off for any hold it drops.

### Proposed Changes

**1. `accessory_bindings.py` (new)** — Tk-free, `control_labels.py`-style.

```python
@dataclass(frozen=True)
class Dispatch:
    verb: str
    command: str | None = None
    axis_latched: bool = False                # one fire per deflection, sign ignored
    axis_held: bool = False                   # press on deflection, release on recenter
    data: int | None = None
    repeat: bool = False
    both_phases: bool = False

@dataclass(frozen=True)
class ContextSpec:
    name: str
    inherits: str | None = None               # next link in the chain
    bindings: Mapping[str, Dispatch | None]   # action -> dispatch; None = unbind
    claims_unbound: bool = False              # swallow anything not bound here
    yields_to_catalog: frozenset[str] = frozenset()

# acc, acc_generic, acc_bpc2, acc_asc2, switch, route

DEFAULT_CONTEXTS: Mapping[str, ContextSpec] = {...}
```

**2. `steam_deck_input.py`**

- `ControlProfile`: parse `dpad`; parse and merge `contexts`; validate verbs; keep `load`'s log-and-fall-back behavior.
- `DeckInputRouter`: add `_handle_contexts(action)` in place of `_handle_switch` / `_handle_route`, positioned identically in `handle()`'s chain. It resolves `gui.input_contexts`, walks the chain, dispatches or claims.
- Retain `SWITCH_*` / `ROUTE_*` names as thin aliases over the table so `control_labels.py` and its tests keep importing what they import — the Controls page stays untouched this turn.

**3. `engine_gui.py`**

- `input_contexts` property — built from `KeypadView.accessory_panel_kind` (KD-7) plus `switch_active` / `route_active`, so it names a panel rather than re-deriving one.
- `on_lcs_command(on)` — resolves state, calls `send_lcs_on_command` / `send_lcs_off_command`, matching `do_command`'s existing branch at lines 1985-1992.
- `on_asc2_momentary(pressed)` — delegates to `KeypadView`.
- `on_acc_speed_command(value)` — relative-speed entry point (**pending open question 2**).

**4. `keypad_view.py`**

- Add `accessory_panel_kind` (KD-7), lifting the branch out of `apply_ops_mode_ui_non_engine` so that method reads the property instead of re-testing the flags inline. Pure refactor; the branch order and its outcomes are unchanged.
- Extract the bodies of `when_pressed` / `when_released` into `asc2_control(pressed: bool)`; the existing event handlers become one-line wrappers that keep the `event.widget.enabled` check. No behavior change for touch.

**5. `steam_deck_default.json`** — add `dpad` (carrying today's boost/brake/smoke as defaults) and `contexts` (carrying the four accessory contexts: `acc`, `acc_generic`, `acc_bpc2`, `acc_asc2`).

### Data Models / Contracts

```python

# KeypadView

@property
def accessory_panel_kind(self) -> str | None:
    """Which accessory panel is displayed: sensor_track | amc2 | bpc2 | asc2 | generic.

    None when this pane is not showing an accessory panel at all. The single
    decision point: apply_ops_mode_ui_non_engine reads this too, so the panel on
    screen and the context claiming the pad cannot disagree.
    """

# EngineGui

@property
def input_contexts(self) -> tuple[str, ...]:
    """Most specific first, e.g. ("acc_asc2", "acc_bpc2", "acc"). Empty = an engine panel."""

def on_lcs_command(self, on: bool) -> None: ...
def on_asc2_momentary(self, pressed: bool) -> None: ...
def on_acc_speed_command(self, value: int) -> None: ...
```

```json
"dpad": {
  "up":    {"action": "boost",     "target": "focused", "repeat": true},
  "down":  {"action": "brake",     "target": "focused", "repeat": true},
  "left":  {"action": "smoke_down", "target": "focused"},
  "right": {"action": "smoke_up",   "target": "focused"}
},
"contexts": {
  "acc": {
    "claims_unbound": true,
    "bindings": {}
  },
  "acc_generic": {
    "inherits": "acc",
    "bindings": {
      "throttle":  {"verb": "acc_throttle"},
      "direction": {"verb": "acc_command", "command": "TOGGLE_DIRECTION", "axis_latched": true},
      "rear_coupler":  {"verb": "acc_command", "command": "REAR_COUPLER"},
      "front_coupler": {"verb": "acc_command", "command": "FRONT_COUPLER"},
      "dpad_up":   {"verb": "acc_command", "command": "BOOST", "repeat": true},
      "dpad_down": {"verb": "acc_command", "command": "BRAKE", "repeat": true}
    }
  },
  "acc_bpc2": {
    "inherits": "acc",
    "bindings": {
      "startup":  {"verb": "lcs_on"},
      "shutdown": {"verb": "lcs_off"},
      "dpad_right": {"verb": "lcs_on"},
      "dpad_left":  {"verb": "lcs_off"}
    }
  },
  "acc_asc2": {
    "inherits": "acc_bpc2",
    "bindings": {
      "sequence_control": {"verb": "asc2_momentary", "both_phases": true},
      "dpad_up":          {"verb": "asc2_momentary", "both_phases": true}
    }
  }
}
```

Note that R2/L2 are reached as `startup` / `shutdown`, and L1/R1 as `rear_coupler` / `front_coupler` — the actions the bundled profile puts on those controls — not as axis or button indices, so a user who moves them keeps the accessory behavior. This is the same action-keyed indirection the existing `SWITCH_*` constants and `CATALOG_JUMP_MODIFIER` use. It also means amendment A-2 is expressed as a remap of the `direction` action, which is what the profile calls the horizontal stick axes (`steam_deck_default.json` axes 0 and 3), rather than as a new action name.

### Architecture Diagram

```mermaid
graph TD
  SDL[SDL / hidraw] --> P[SteamDeckInputProvider]
  P -->|DeckAction| R[DeckInputRouter.handle]

  R --> CO[_controls_only]
  CO --> CH[_chooser_only]
  CH --> HC[_handle_contexts]

  K[KeypadView.accessory_panel_kind] --> G[EngineGui.input_contexts]
  G -->|acc_asc2, acc_bpc2, acc| HC
  D[DEFAULT_CONTEXTS<br/>accessory_bindings.py] --> M[Merged context map]
  J[profile contexts + dpad<br/>steam_deck_default.json] --> M
  M --> HC

  HC -->|acc_command| A1[on_acc_command]
  HC -->|lcs_on / lcs_off| A2[on_lcs_command]
  HC -->|asc2_momentary| A3[on_asc2_momentary]
  HC -->|switch / route| A4[on_switch_command<br/>on_route_command]
  HC -->|claim| X[swallowed]
  HC -->|unclaimed| EN[existing engine handling]
```

### Risks

- **The switch/route migration is the real risk.** Those handlers carry hard-won detail: axis latching with hysteresis, the catalog reclaiming A/Y, dropping pending `_throttles` / `_commanded_speeds` / `_held_commands` / `_sequences` when a pane changes scope. Mitigation: migrate with the existing tests unmodified, and treat any diff as a defect. If a behavior genuinely cannot be expressed as a flag, that is a signal to add a flag — not to accept the change.
- **`_handle_contexts` runs on every action** in the thread that also services the touch screen. Mitigation: resolution is a dict lookup over a tuple of ≤2 names; no allocation on the miss path.
- **`is_asc2` and `is_power_district` are not mutually exclusive in principle** (`is_power_district` is `is_bpc2`, and both read `_control_req` / `_config_req`). Mitigation: `accessory_panel_kind` resolves them in one ordered branch, and the chain follows it, so the most specific wins deterministically and identically for the screen and the pad.
- **A-1 widens what the generic context claims.** Ports that were previously left alone — an STM2, an LCS port not yet identified — now claim the engine-driving controls. That is the intent, but it means a control that did nothing on such a pane now sends an aux command. Mitigation: the bindings are exactly the keys that pane already shows, so anything the pad can now send was already reachable by touch.
- **Profile override surface is wide** — a user can unbind HALT. Mitigation: refuse overrides for `global`-target safety actions, as `_validate_action_target` already refuses a non-global HALT.
- **The context name and the panel on screen can drift.** This is not hypothetical: the first draft of this spec keyed the generic context off `is_lcs_component`, which is *not* what the panel branch tests, and it would have left an STM2 showing aux keys that answered to nothing. Mitigation: KD-7 — one property decides, both readers use it, and a test asserts each panel kind maps to the chain that binds the keys that panel shows.
- **`TOGGLE_DIRECTION` on an axis is easy to fire by accident.** A thumb resting on a stick would flip a gantry or a crane repeatedly. Mitigation: `axis_latched` plus `direction_threshold` — one toggle per full deflection, re-armed only near center.
- **A held axis can leave an accessory output energised.** The most consequential failure in the whole spec, because a real relay stays closed. Three ways it could happen, each with its own mitigation: the pane is re-scoped under the thumb (release delivered from `_momentary_holds` rather than by re-resolving the chain), the pad disconnects while deflected (`clear()` sends the off for every hold it drops), and a second control releases first (FR-3a's last-holder-wins). Each gets its own test.
- **Three axis modes over one field set.** `axis_latched`, `axis_held` and `is_analog` are mutually exclusive in practice and nothing in the dataclass says so. Mitigation: validate the combination where the verbs are validated, log and drop a binding claiming two, and keep the router's branch ordered so the outcome is defined even if one slips through.
- **`axis_actions()` filters on `axis_latched` alone.** It derives the legacy `*_AXIS_ACTIONS` name sets `control_labels.py` still imports, so a held-axis binding would be invisible to it. Mitigation: widen it to any axis mode as part of adding the field, rather than leaving a second definition of "is this an axis" behind.

# Controls Page Notes

### Not changing this turn — recorded per your instruction

No edit will be made to `controls_panel.py` or `control_labels.py` in this work. This is the change list for when we do.

### Why it slots in cleanly

`control_labels.py:169` already anticipates this. The comment introducing the panel-section headings reads:

> "…so the panel types still to come — **Aux** — need no new phrasing invented for them, as Routes did not."

The heading vocabulary was designed with an accessory section in mind.

### Changes needed

**1. New section titles**, beside `SWITCH_PANEL_TITLE` / `ROUTE_PANEL_TITLE` (lines 175-179), in the established `"<type> (w focus)"` form:

- `ACC_PANEL_TITLE = "Accessories (w focus)"`
- `BPC2_PANEL_TITLE = "Power Districts (w focus)"`
- `ASC2_PANEL_TITLE = "ASC2 (w focus)"`

**2. Entries stop being `FIXED_*` constants.** `FIXED_SWITCH_ENTRIES` and `FIXED_ROUTE_ENTRIES` are literals because the remaps were module constants. Once contexts come from the merged table, these sections must be **generated from it**, or the help screen will confidently describe bindings a custom profile has overridden. This is the largest change and the reason it deserves its own turn.

**3. `ControlSection.fixed` needs rethinking.** Its docstring says fixed means "a custom profile cannot change" — and it is currently True for the D-pad, switch, route, catalog and popup sections. After KD-3 and KD-5, **the D-pad, switch and route sections are no longer fixed.** Rendering them as fixed would tell the user the D-pad is not remappable at the exact moment it becomes remappable.

**4. `ACTION_LABELS` additions** (lines 109-146) for the new verbs and any new action names: LCS on/off, ASC2 momentary, accessory throttle, boost/brake and smoke as *bound* actions rather than fixed D-pad text. `DPAD_UP`'s label is currently the literal `"Boost speed"`; once bindable it must resolve through the profile.

**5. The momentary hold needs a note.** `ACTION_NOTES` (line 151) has `"hold: w dialog"` for startup/shutdown. ASC2 momentary needs something like `"hold: output on"` — it is the only binding in the set whose *release* does something. It now applies to the **stick** as well as to A, so whatever phrasing is chosen has to read sensibly against an axis row, where "hold" means "held away from center".

**6. Column budget is the hard constraint.** The comments at lines 520-536 record that the last column already fills "to within a row of the budget `ROWS_PER_COLUMN` falls back to", and that adding one row "put the catalog behind a page turn nobody would think to take." **Three new panel sections cannot fit.** Options, for you to choose from next pass:

- **A second Controls page** — the "new page just to handle accessories" you floated. `ControlsPanel` already pages (`page_controls(forward=...)` is bound to D-pad ↕ in `_controls_only`), so the machinery exists.
- **Context-sensitive Controls** — show the accessory sections only when the focused pane holds an accessory. Cheapest on layout, but the page stops being a stable reference.
- **One merged "Accessories" section** with a row per accessory type. Fits, but compresses three distinct binding sets into three rows.

My recommendation is the second page, because it is what the paging support was built for and it keeps every section legible.

**7. `tests/gui/controller/test_control_labels.py` and `test_controls_panel.py`** will both need updating — they assert section titles, ordering and column packing.

**8. Two consequences of this pass's amendments.** The accessory section must show **stick ↔ as Toggle Direction**, which means `ACTION_LABELS` cannot keep resolving `direction` to one fixed label — it means Forward/Reverse on an engine panel and Toggle Direction on the generic accessory panel, so labels become context-aware, not merely profile-aware. And the generic section's heading must not imply "non-LCS": it applies to any port showing the generic panel, an STM2 included.

# Testing

### Validation Approach

Three layers, following the split the codebase already uses:

1. **Pure table tests** — `accessory_bindings.py` and the merge logic are Tk-free, so context resolution, chain walking, override merging and validation are tested as data, the way `test_control_labels.py` tests label resolution.
2. **Router tests with stub GUIs** — `tests/gui/controller/test_steam_deck_input.py` already has `_switch_gui()` (line 3016) and `_route_gui()` (line 3240) building stubs that record calls. An `_acc_gui(kind=...)` in the same shape covers the accessory contexts.
3. **Regression by non-modification** — the existing switch and route tests are the migration's acceptance criteria. They should pass **unmodified** except where they touch internals that move.

Per the project guidelines: `../bin/python -m ruff format --check` on every changed file, then the full `../bin/python -m pytest`.

### Key Scenarios

- Generic ACC: stick ↕ drives accessory throttle; L1/R1 send rear/front coupler; D-pad ↑/↓ send Boost/Brake and repeat while held.
- Generic ACC on an **LCS** component: a state that is `is_lcs_component is True` but is none of Sensor Track / AMC2 / BPC2 / ASC2 — an STM2 — reports `("acc_generic", "acc")` and takes every binding above. This is amendment A-1's regression test, and it fails against the first draft.
- Stick ↔ sends `TOGGLE_DIRECTION` once per deflection, for a push either way, and does not send again until the stick returns inside `direction_threshold - hysteresis`.
- A BPC2 or ASC2 panel does **not** take the aux bindings: a coupler or Boost action there resolves no entry in `acc_bpc2` / `acc_asc2` and is claimed by `acc`, not sent.
- A BPC2 reached as a `LcsProxyState` power district under **TRAIN** scope reports the BPC2 chain, matching `is_accessory_or_bpc2`.
- BPC2: R2 and D-pad → each reach `on_lcs_command(on=True)`; L2 and D-pad ← each reach `on_lcs_command(on=False)`.
- BPC2 stick: pushed right reaches `on_lcs_command(on=True)` and pushed left `on_lcs_command(on=False)`, once per deflection, re-armed only inside `direction_threshold - hysteresis` — and the same pair arrives on the ASC2 panel by inheritance rather than restatement.
- The generic panel still resolves plain `direction` to `TOGGLE_DIRECTION` for a push either way, exercising KD-9's fallback: no directional variant is bound there.
- ASC2: the On/Off pair is inherited from `acc_bpc2` through the chain, not restated; A and D-pad ↑ call `on_asc2_momentary(True)` on press and `(False)` on release.
- ASC2 stick ↕: a push past `direction_threshold` calls `on_asc2_momentary(True)` once — not once per poll while it is held — and the value falling back inside `direction_threshold - hysteresis` calls `(False)` once. A push the other way does exactly the same, the binding being sign-blind.
- ASC2 stick ↕ held while the pane is re-scoped: the recenter still delivers `on_asc2_momentary(False)`, from the hold record rather than from the chain.
- A held and the stick pushed at once: releasing either leaves the output on, and only the second release sends `on_asc2_momentary(False)` — FR-3a.
- A BPC2 panel: stick ↕ resolves nothing in `acc_bpc2`, is claimed by `acc`, and never reaches `on_asc2_momentary`, which does not apply to a power district.
- Chain precedence: a pane reporting `("acc_asc2", "acc_bpc2", "acc")` takes the ASC2 entry where both it and `acc_bpc2` define an action, and falls through where only the outer link does.
- Profile override: a `contexts` entry replaces a default; `null` unbinds; the default survives untouched where the override is silent.
- An engine panel (empty `input_contexts`) reaches the existing engine handling completely unchanged.

### Edge Cases

- **Scope changes mid-press** — press on an engine panel, release after the pane becomes an accessory. This is the exact case `_handle_switch`'s `_held_commands` / `_sequences` clean-up exists for (tests at lines 3148-3156 and 3369-3377); it must hold for accessories too.
- **Catalog open over an accessory panel** — A must still confirm the highlighted entry, matching `yields_to_catalog` and the existing switch/route carve-out.
- **Controls or chooser open** — `_controls_only` / `_chooser_only` still gate everything ahead of context resolution.
- **`is_asc2` and `is_bpc2` both true** — chain order decides, deterministically, and identically for `accessory_panel_kind` and `input_contexts`.
- **Stick ↔ held over while the pane changes scope** — the latch must not survive into the next panel and toggle something the operator never pushed the stick for.
- **Stick swept straight across center on a power district** — Off then On, once each, not twice and not four times. This is what KD-9's single physical-action latch exists for.
- **A directional variant bound with no plain fallback** — a power district binds `direction_left` and `direction_right` but no `direction`, so a value at rest must still drop the latch rather than leave it held because neither variant resolved.
- **A profile that overrides only one side** — binding `direction_right` and leaving `direction_left` alone must not disturb the other, and `null` on one side must unbind only it.
- **Stick pushed diagonally** — ↕ throttle and ↔ toggle arrive as two independent axis actions; both must resolve, and the toggle latch must not be re-armed by throttle movement.
- **Malformed profile** — an unknown context, action or verb logs and is skipped; the bundled default still loads. Mirrors `ControlProfile.load`'s existing fallback, which is already tested.
- **ACC scope with id 0** (entry mode, nothing selected) — no accessory context is reported, so nothing is claimed.
- **HALT** — resolves no gui, is never gated, and no override may unbind it.
- **Momentary release lost** — if a pane changes scope between press and release, the ASC2 output must not be left latched on. The same must hold for a held stick, whose release is a *value* rather than an event.
- **Pad disconnects with the stick deflected** — `clear()` must switch a held output off rather than merely forgetting it held one. This is the one case where no further input arrives to correct the state.
- **Stick jitter around the threshold** — a value oscillating either side of `direction_threshold` must not chatter the output; the press/release pair uses the hysteresis band, exactly as the latch does.
- **Stick sitting at rest under the threshold** — a small resting offset must not energise anything, and must not accumulate a hold that a later recenter releases.
- **Stick pushed diagonally on an ASC2** — ↕ holds the momentary output and ↔ switches the district on or off, from the same physical stick; both must work and neither may consume the other's latch or hold.
- **A binding claiming two axis modes** — `axis_held` together with `axis_latched` is invalid; it is logged and dropped rather than resolved arbitrarily.

### Test Changes

- **New** `tests/gui/controller/test_accessory_bindings.py` — tables, chain resolution, merge and validation, all Tk-free.
- **Extend** `tests/gui/controller/test_steam_deck_input.py` — `_acc_gui(kind=...)` stub plus per-context cases, written in the shape of the existing switch/route blocks.
- **Extend** `tests/gui/controller/test_steam_deck_packaging.py` — the profile now has `dpad` and `contexts` sections to validate.
- **Extend** `tests/gui/test_keypad_view.py` — `asc2_control(pressed)` sends the same `Asc2Req` the event handlers did.
- **Extend** `tests/gui/test_keypad_view.py` — `accessory_panel_kind` returns each of the five kinds for the matching state, including `"generic"` for an STM2, and `None` off an accessory panel.
- **Extend** `tests/gui/test_engine_gui_accessories.py` — `input_contexts` for each accessory kind, and that it follows `accessory_panel_kind` rather than any flag of its own.
- **Extend** `tests/gui/controller/test_accessory_bindings.py` — the directional-variant resolution order, the fallback to the plain action name, and the sign-to-name table.
- **Extend** `tests/gui/controller/test_accessory_bindings.py` — `axis_held` on the `acc_asc2` `throttle` entry, the mode-exclusivity validation, and `axis_actions()` seeing a held binding.
- **Extend** `tests/gui/controller/test_steam_deck_input.py` — the held-axis press/release pair, the hysteresis band, last-holder-wins across A and the stick, the re-scope case, and `clear()` releasing a held output.
- **Unmodified** — the existing switch and route suites, which are the migration's proof.

# Delivery Steps

### ✓ Step 1: Build the context mechanism with switches and routes migrated onto it
One data-driven context mechanism carries the existing switch and route remaps, with their test suites passing unmodified.

- Add `src/pytrain/gui/controller/accessory_bindings.py` with `Dispatch`, `ContextSpec` and `DEFAULT_CONTEXTS`; Tk-free and guizero-free, in the style of `control_labels.py`.
- Express the `switch` and `route` contexts in that table, including the per-context flags their handlers need: `axis_latched` for one-throw-per-deflection, `yields_to_catalog` for the catalog reclaiming A/Y, and `claims_unbound` for the swallow.
- Add `DeckInputRouter._handle_contexts(action)` and place it in `handle()`'s chain exactly where `_handle_switch` / `_handle_route` sat, preserving gate order after `_controls_only` and `_chooser_only`.
- Carry over the pending-state clean-up on a claim: `_throttles`, `_commanded_speeds`, `_held_commands`, `_sequences`.
- Add `EngineGui.input_contexts`, returning `("switch",)` / `("route",)` from the existing `switch_active` / `route_active` predicates.
- Retain `SWITCH_*` and `ROUTE_*` module names as thin aliases over the table so `control_labels.py` keeps importing what it imports and the Controls page stays untouched.
- Add `tests/gui/controller/test_accessory_bindings.py` for chain resolution and table shape; run the existing switch and route suites unmodified as the acceptance criterion.

### ✓ Step 2: Make the D-pad and the context tables profile-configurable
The profile JSON can bind the D-pad and override any context entry, with Python defaults behind it.

- Extend `ControlProfile.from_dict` to parse a `dpad` section binding `up`/`down`/`left`/`right` like `buttons`, with `repeat` support.
- Extend it to parse a `contexts` section, merged over `DEFAULT_CONTEXTS`: override, add, `null` to unbind, and `inherits` for chaining.
- Validate dispatch verbs and context names; log-and-skip anything unknown, matching `ControlProfile.load`'s existing fallback rather than raising.
- Refuse overrides that would unbind `global`-target safety actions, alongside the existing `_validate_action_target` rules for HALT and focus.
- Move today's hard-coded D-pad behavior out of `_handle_scroll_boost` / `_handle_select_smoke` and into the bundled `steam_deck_default.json` `dpad` section, so boost/brake and smoke become visible defaults with unchanged behavior.
- Extend `tests/gui/controller/test_steam_deck_packaging.py` for the new sections, and cover merge, unbind, inherit and malformed-input paths.

### ✓ Step 3: Report which accessory panel is displayed
One property names the accessory panel on screen, and the input layer reads it instead of re-deriving it.

- Add `KeypadView.accessory_panel_kind`, returning `"sensor_track" | "amc2" | "bpc2" | "asc2" | "generic" | None`, by lifting the existing branch out of `apply_ops_mode_ui_non_engine` (`keypad_view.py:788-830`) without changing its order or its outcomes.
- Have `apply_ops_mode_ui_non_engine` read the property, so there is one decision point rather than two — the point of amendment A-1.
- Base it on `is_accessory_or_bpc2`, not `scope == ACC`, so a `LcsProxyState` power district under TRAIN scope is reported like the BPC2 panel it shows.
- Extend `EngineGui.input_contexts` to build the accessory chains from it: `("acc_generic", "acc")`, `("acc_bpc2", "acc")`, `("acc_asc2", "acc_bpc2", "acc")`, and nothing for Sensor Track or AMC2 this pass.
- Define the `acc` base context with `claims_unbound` and no bindings, so every accessory panel swallows engine-only controls.
- Cover each kind in `tests/gui/test_keypad_view.py` — notably `"generic"` for an STM2, which is `is_lcs_component is True` — and the chains in `tests/gui/test_engine_gui_accessories.py`.

### ✓ Step 4: Add the generic ACC panel bindings
Whenever the generic ACC panel is displayed — LCS device or not — the stick, shoulders and D-pad drive the keys that panel shows.

- Define the `acc_generic` context over the `acc` base: stick ↕ to accessory throttle, L1 to `REAR_COUPLER`, R1 to `FRONT_COUPLER`, D-pad ↑/↓ to `BOOST`/`BRAKE` with repeat, keyed on the `throttle`, `rear_coupler`, `front_coupler` and `dpad_*` action names so a remapped control keeps its accessory meaning.
- Bind the `direction` action to `acc_command TOGGLE_DIRECTION` with `axis_latched` (amendment A-2), reusing the `direction_threshold` / `hysteresis` latch from `_handle_direction` so a push either way toggles exactly once and a held stick does not flip the accessory repeatedly.
- Ignore the sign of the `direction` value, as `_throw_switch_from_axis` already does: the command is a toggle with no left-hand or right-hand form.
- Add `EngineGui.on_acc_speed_command(value)` for the relative-speed path; every other binding reaches the existing `on_acc_command`, which resolves names through `TMCC1AuxCommandEnum.by_name`.
- Leave `SET_ADDRESS` and `AUX1_OPT_ONE` unbound pending your decision, so nothing re-addresses an accessory by accident.
- Add an `_acc_gui(kind="generic")` stub to `tests/gui/controller/test_steam_deck_input.py` in the shape of `_switch_gui` / `_route_gui`, and cover each binding, the latch on stick ↔, the claim of engine-only controls, and an STM2 taking the full set.

### ✓ Step 5: Add the BPC2 and ASC2 contexts with the momentary output
Power districts switch on and off from the pad, and ASC2 outputs respond to a held button.

- Extract the bodies of `KeypadView.when_pressed` / `when_released` into `asc2_control(pressed: bool)`, leaving the event handlers as wrappers that keep the `event.widget.enabled` check so touch behavior is unchanged.
- Add `EngineGui.on_lcs_command(on)`, resolving state and calling `send_lcs_on_command` / `send_lcs_off_command`, mirroring the branch already in `do_command`.
- Add `EngineGui.on_asc2_momentary(pressed)`, delegating to `KeypadView.asc2_control`.
- Define the `acc_bpc2` context: R2 and D-pad → to `lcs_on`, L2 and D-pad ← to `lcs_off`, keyed on the `startup` / `shutdown` actions so a remapped trigger keeps working.
- Define the `acc_asc2` context inheriting `acc_bpc2`, adding A and D-pad ↑ on the `asc2_momentary` verb with `both_phases` so press and release are both delivered.
- Confirm neither context inherits `acc_generic`, so a coupler or Boost action on a BPC2 or ASC2 panel is claimed by `acc` and sent nowhere — there is no such key on those panels.
- Cover both contexts in the router tests, including inheritance from `acc_bpc2`, the release path, a scope change between press and release leaving no output latched on, and the aux bindings being absent.
- Cover `asc2_control` in `tests/gui/test_keypad_view.py`, asserting the same `Asc2Req` the event handlers sent.

### ✓ Step 6: Bind the stick left/right on a power district to Off/On
On a BPC2 or ASC2 panel, pushing the stick right switches the block on and pushing it left switches it off.

- Add the directional-variant resolution of KD-9 to `accessory_bindings.py`: an `AXIS_DIRECTION_NAMES` table mapping `direction` → (`direction_left`, `direction_right`) and `throttle` → (`throttle_down`, `throttle_up`), with positive taking the second, and a resolver that tries the variant for the value's sign before the plain action name.
- Have `DeckInputRouter._handle_contexts` / `_dispatch_axis` use it, keeping the latch keyed on the **physical** action name so a sweep across center fires Off then On once each, and so a stick at rest drops the latch even when no directional variant resolves.
- Add `"direction_right": Dispatch(VERB_LCS_ON, axis_latched=True)` and `"direction_left": Dispatch(VERB_LCS_OFF, axis_latched=True)` to `_ACC_BPC2_BINDINGS`, beside the `dpad_right` / `dpad_left` pair they mirror; `acc_asc2` picks them up by inheritance with no entry of its own.
- Leave `acc_generic` as it is: it binds plain `direction`, so the fallback keeps `TOGGLE_DIRECTION` sign-blind, and the vertical stick on a power district stays claimed and dropped pending open question 7.
- Allow a profile to override either side independently, including `null` to unbind one, and validate the variant names the same way plain action names are validated — log and skip an unknown one.
- Extend `tests/gui/controller/test_accessory_bindings.py` for the resolution order, the fallback, and the one-sided override; extend the `_acc_gui(kind="bpc2")` and `kind="asc2"` router tests for each direction, the latch, the sweep across center, and the generic panel still toggling for either sign.

### ✓ Step 7: Hold the ASC2 momentary output from the vertical stick
On an ASC2 panel, pushing the stick up or down energises the momentary output for as long as it is held, and letting it recenter switches it off.

- Add `Dispatch.axis_held` to `accessory_bindings.py` as the third axis mode (KD-10), with an `is_axis` property covering latched and held alike, and widen `axis_actions()` to use it so the derived `*_AXIS_ACTIONS` name sets do not miss a held binding.
- Reject a binding that claims two axis modes where the verbs are already validated: log and drop it, matching `ControlProfile.load`'s fallback discipline rather than resolving it arbitrarily.
- Add `"throttle": Dispatch(VERB_ASC2_MOMENTARY, axis_held=True, both_phases=True)` to `_ACC_ASC2_BINDINGS` — plain `throttle`, not the `throttle_up` / `throttle_down` variants, so KD-9's fallback makes it sign-blind and a push either way energises the output.
- Add the held branch to `DeckInputRouter._handle_contexts` / `_dispatch_axis`: press when `abs(value)` first crosses `profile.direction_threshold`, release when it falls back inside `direction_threshold - hysteresis`, recording the hold in the existing `_momentary_holds` set so the release survives a pane re-scoped under the thumb.
- Send the off only when the **last** holder for that target lets go (FR-3a), so releasing the stick cannot kill an output A is still holding, and releasing A cannot kill one the stick is still holding.
- Have `clear()` release every hold it drops instead of merely emptying the set, so a pad that disconnects with the stick deflected cannot leave a relay closed.
- Leave `acc_bpc2` alone: a power district has no momentary output, so ↕ stays claimed and dropped there pending open question 7.
- Cover the pair, the hysteresis band, jitter at the threshold, a resting offset, last-holder-wins, the re-scope case and `clear()` in `tests/gui/controller/test_steam_deck_input.py`; cover the table entry, the mode validation and `axis_actions()` in `tests/gui/controller/test_accessory_bindings.py`.