# Qt UI rearchitecture

The new `pytrain_ui` package is the presentation boundary for PyTrain. It may depend on `pytrain`; core PyTrain code must not depend on Qt or the new presentation package.

The existing GuiZero implementation remains in `pytrain.gui` during migration. New UI work goes into `pytrain_ui`, with Qt Quick/QML under `pytrain_ui.qt`.

The cab vertical slice now follows this dependency direction:

```
PyTrain state/commands
        ^
        |
pytrain_ui adapters
        ^
        |
pytrain_ui contracts, capabilities, actions, panels, input
        ^
        |
Qt QObject/QML presentation and pygame controller bridge
```

Presentation-neutral code owns semantic state, action applicability, press/hold/repeat behavior, panel contents, control profiles, status readouts, and physical-input primitives. QML owns visual layout and rendering. Product metadata may supply artwork but must not silently determine control capability.

`pygame-ce` remains the controller input layer. Controller events use the same semantic command surface as touch and mouse input. Center-return throttle sticks represent rate and direction of speed change rather than absolute speed position. Repeat timing and short/long gesture recognition live in `pytrain_ui.input` so they can be tested without Qt or SDL.

The `pycab` launcher now prefers the Qt cab when PySide6 is installed. Compatibility paths remain available throughout migration:

- `pycab --legacy` forces the GuiZero cab.
- `pycab-legacy` directly launches the GuiZero cab.
- `pycab --qt` or `pycab-qt` explicitly launches the Qt cab.
- `PYTRAIN_LEGACY_GUI=1` opts out of the Qt default without changing scripts or services.

The legacy cab should remain available until the Qt implementation has been exercised on macOS, Raspberry Pi touch hardware, and Steam Deck controller hardware. Retirement of GuiZero requires conversion and validation of the entire GUI suite, including the wide-screen GUI (`WideComponentStateGui`). It is a separate decision from making Qt the preferred cab presentation or merging this branch.


## Starting the Qt cab from buttons.py

A normal PyTrain startup script can register the Qt cab against its existing
runtime. No second PyTrain instance, process, or connection is created. The script
runs on the buttons loader thread; after the complete script finishes, PyTrain
starts the registered presentation on the Python main thread. Core PyTrain uses
presentation callbacks and does not import Qt or `pytrain_ui`.

```python
from pytrain.protocol.constants import CommandScope
from pytrain_ui.qt import QtCabGui

cab = QtCabGui(
    tmcc_id=37,
    scope=CommandScope.ENGINE,
    width=800,
    height=1280,
    full_screen=True,
)


def selection_changed(target):
    print(target.scope, target.tmcc_id)


unsubscribe = cab.subscribe(selection_changed)
```

Use `cab.selection` to read an atomic `CabSelection(scope, tmcc_id, revision)`.
`cab.scope` and `cab.tmcc_id` expose individual values. `cab.active_state` returns
an existing selected record; `cab.active_engine_state` returns it only for Engine
or Train scope, including selected cars. These lookups never create records and
return `None` for missing or deleted records. Before the window starts, selection
has no scope or ID. A scope with no selected record has a `None` ID.

Callbacks receive future changes to the selected `(scope, tmcc_id)`, not ordinary
state updates such as speed changes. They execute on the UI thread and must return
promptly. Call the returned `unsubscribe()` function to detach a callback. For a
worker-thread watcher, use `cab.wait_for_selection_change(revision, timeout)`;
it returns the latest newer snapshot or `None` on timeout or shutdown. Revisions
prevent lost wakeups, multiple waiters are supported, and rapid changes may be
coalesced without accumulating a queue. Use `StateWatcher` separately to monitor
the selected record's state changes.

Selection follows the displayed scope and target. Selecting a Train Link car
reports its Engine address while the throttle remains assigned to the train.
In the two-pane Steam Deck host, selection follows the focused pane.

An explicit `tmcc_id` takes precedence over saved session selection; omit it to
retain normal session restoration and roster startup. `deck=None` uses platform
detection; `deck=True` explicitly requests the two-pane host and supports
`controller_profile`. Width, height, and fullscreen options apply to the requested
host. `cab.close()` requests window exit from any thread, and closing the GUI
shuts down its existing PyTrain runtime through the normal lifecycle. Only one
startup GUI may be registered. API hosts must launch their presentation explicitly;
the automatic buttons-file GUI hook is for normal PyTrain startup, not API mode.
Legacy `EngineGui` styling and Tk embedding arguments are not Qt options.

## Fullscreen startup

The Qt cab opens fullscreen on Raspberry Pi hardware and Steam Deck installs.
Steam Deck launchers identify the platform with `PYTRAIN_PLATFORM=steamdeck`;
use that environment variable when launching directly from a terminal as well.
Mac and other desktop installs open in a normal window.

## Steam Deck host

On Steam Deck, Qt opens a single 1280 × 800 window containing two independent
cab workspaces. Each pane uses the same Engine, Train, Switch, Route, Accessory,
Info, and Manage components as the normal Qt cab. The focused pane has a cyan
border; focus starts on the right and changes when either pane is touched or a
profile focus binding is pressed. Only the focused pane handles keyboard shortcuts.
The panes share one scope-state notification bridge and the synchronized PyTrain
runtime, while keeping selections, filters, editors, and controller state separate.

Use `pycab-qt --deck --width 1280 --height 800` to request the two-pane host
explicitly, and `--controller-profile /path/to/profile.json` for a custom profile.
Platform-aware `pycab` launches select it automatically when
`PYTRAIN_PLATFORM=steamdeck` is set.

The Deck input adapter reuses `ControlProfile`, `SteamDeckInputProvider`, and
`DeckInputRouter`. The bundled profile retains left/right stick targets, focused
face buttons and triggers, trackpad input, controller repeats, and catalog navigation.
Changing focus, changing the active scope or selection, disconnecting, or exiting
cancels controller repeats and releases momentary accessory outputs. Admin chords
press the existing Qt admin button, including its three-second hold guard, rather
than bypassing it. The profile help chord opens Qt help across both panes.

Deep chooser, Route Builder, and LCS wizard navigation currently uses the touchscreen;
those editors block engine commands. The existing legacy Deck frontend remains
available through `--legacy` or `PYTRAIN_LEGACY_GUI=1`. Real Deck validation is still
required for Gamescope sizing, SDL/hidraw access, touchpad behavior, and every
physical binding. Qt code and profile JSON are included by the existing package-data
globs. This checkout contains no Flatpak manifest: the external Flatpak must install
the `qt-gui` extra and its Qt platform plugins, preserve the `pycab` entrypoint and
`PYTRAIN_PLATFORM=steamdeck`, and retain its existing device permissions and update
integration. A successful Python wheel test does not verify that external bundle.

## Device previews on macOS

The engine/train pages include Raspberry Pi (720 × 1280), PyCab (800 × 1280), and
single Steam Deck pane (639 × 800) preview buttons below the scope bar. These
resize the Mac window and keep the device layout at its target dimensions. When
needed, the entire preview scales down to fit the Mac screen; the selector shows
the scale. The selector sits outside the preview and is hidden on actual devices.
Switch and Route retain their original window size and unscaled layout.

## Visual design references

The five screenshots supplied on November 8, 2026, their identities, and the
user's design preferences are preserved in the
[design reference index](design-references/2026-11-08/README.md).

## Admin network status

Manage PyTrain displays a Network card with the local IP address and available
Wi-Fi SSID, signal bars, percentage, and quality description. It measures the
local PyCab device, not the PyTrain server or Base 3. Missing measurements display
“Signal unavailable”; a missing reading is never presented as zero strength.
Ethernet is labeled only when a physical wired Linux interface can be confirmed.

The card uses the existing `WiFiInfo` helper. Queries run on a background worker
when Admin opens and every five seconds while visible. Steam Deck panes share
one monitor. Hidden panels stop polling; overlapping queries are prevented, stale
results are ignored, and shutdown does not wait for an external network command.
Available readings depend on the helper's platform backend and host permissions,
including those of an external Steam Deck Flatpak.

## Test groups

The default `pytest` run includes core and Qt controller/unit tests. Native Qt
integration scenarios are marked `qt_gui` and run separately because they start
real applications and exercise timed gestures, rendering, and process shutdown.

- `../bin/python -m pytest` runs the fast unit suite.
- `tox -p` runs unit tests across Python 3.11–3.14 and Ruff in parallel. It excludes native GUI integration scenarios while retaining Qt controller/unit tests.
- `tox -e qt-gui` explicitly runs the native GUI scenarios using the host Python.
- Run both commands before checking in GUI changes. CI also runs the native GUI scenarios once on Python 3.13; they remain outside the default tox environment list.
- `../bin/python -m pytest -o addopts=` runs both groups in one interpreter when needed.

The GUI environment inherits `PYTHONPATH` so its child processes can import the
checkout even without an editable installation. Adding a real-window scenario
requires the `qt_gui` marker; tests of controllers and commands stay in the unit
suite. The groups preserve all existing assertions and scenarios.

## Remaining tasks

The checklist below separates work to complete before merging this branch into
`master` from follow-up work deferred from that merge. Hardware validation is
still required even where implementation and automated coverage are present.

### Pre-merge checklist

- [ ] Validate Steam Deck through the actual external Flatpak. Exercise the
  two-pane layout, every controller binding, focus changes, touch gestures,
  held-output release, Gamescope sizing, Qt platform plugins, device permissions,
  and update/restart behavior. The Qt Deck implementation exists; the external
  bundle has not been validated by the Python wheel tests.
- [ ] Validate the cab on Raspberry Pi touch hardware. Check layout fit, fixed
  StateInfo panels with all fields and footers visible, scrolling indicators,
  tap/double-tap/hold gestures, responsiveness, and network status. Include
  macOS regression checks for desktop and device-preview layouts.
- [ ] Exercise hybrid 2D/4D trains and Train Link on hardware. Automated coverage
  exists, but verify train/car command targeting and formats, selection and
  return-to-train behavior, train-controlled throttle and secondary sliders,
  train-controlled state tiles, car-controlled volume keys, consist changes,
  and removal of linked cars. Verify real versus pseudo train visibility and
  active engine/train tile membership.
- [ ] Complete and validate BPC2 Train-mode support. BPC2 devices programmed as
  Train addresses must be discoverable and operable with the correct addressing,
  controls, and state feedback; existing ACC-mode support does not close this task.
- [ ] Implement server-side live consist rediscovery after Cab 3 edits using the
  [discovery plan](train-consist-discovery-plan.md). First revise that plan to
  reflect the documented lashup commands now decoded as `ASSIGN_TRAIN` (`0xD000`)
  and `ROAD_SPEED` (`0xF012`), replacing its earlier unknown-command hypotheses.
  Cover known, unknown, and stale pseudo mappings; old/new parent and component
  refreshes; additions/removals; bounded retries and queue cleanup; and regression
  tests. Keep discovery in core PyTrain and reuse shared state notifications.
- [ ] Refresh documentation and screenshots for Train Link controls, active
  engines/trains, Info tabs, accessory controls, switch/route coloring, wired
  network status, ASC2 uncoupler/relay controls, and the actual Steam Deck Flatpak
  launch procedure. Reconcile this checklist with validated behavior.
- [ ] Validate the implemented Wi-Fi meter on Raspberry Pi, macOS, and the external
  Steam Deck Flatpak. Confirm available signal readings, unavailable readings,
  wired connection labeling and interface names where available, and polling
  lifecycle behavior on the target devices.
- [ ] Run final merge validation against the integrated code: Ruff and the full
  Python unit-test matrix with `tox -p`, native Qt integration tests with
  `tox -e qt-gui`, and installation/launcher smoke tests. Verify both Qt launch
  paths and the retained legacy fallback, and resolve failures before merging.

### Deferred follow-up tasks

These tasks remain in the broader UI architecture project but are outside the
pre-merge checklist. Deferral does not mean they have been implemented.

- [ ] Convert the other GUIs in `pytrain.gui`, prioritizing the wide-screen host
  (`WideComponentStateGui`, also referred to as the WideScreenGui). Preserve its
  configurable independent panes and panel selection. Include the Launch Pad,
  systems, motors, power districts, component hosts, and remaining standalone
  accessory views. Inventory each entry point and preserve its supported operations
  during migration. Review current/proposed layouts side by side before conversion.
- [ ] Build the Operating Accessory Configurator: a graphical tool, comparable to
  the LCS Device Manager and Route Builder, for maintaining and extending
  `accessory_config.json`. Use the prepared handoff and established GUI styles.
- [ ] Separate core PyTrain and the GUI into independently installable packages
  in the same repository. Move shared accessory metadata, registry definitions,
  and configuration models out of `pytrain.gui` into a GUI-independent core
  location, retaining compatibility imports for legacy callers. Keep Qt
  dependencies in the GUI package so core-only installations do not require them.
  Explicitly deferred; do not implement as part of this checklist update.
- [ ] Retire GuiZero only after the entire GUI suite has been converted and
  validated, including the wide-screen host and every standalone entry point.
  Retain the legacy launch paths until then; retirement is a separate decision
  from merging the Qt architecture or making Qt the preferred presentation.

### Implemented features awaiting final validation

- [x] ASC2 Mode 1 uncouplers, relay controls and Edit Group, and the standard ACC tab.
- [x] Train Link controls and active engine/train tiles.
- [x] Switch state filters and switch/route state coloring.
- [x] Embedded Info tabs and fixed, non-scrolling StateInfo layouts.
- [x] Admin Wi-Fi signal-strength meter using the shared `WiFiInfo` helper, with
  wired connection reporting where available.

## Live train edits from Cab 3

A proposed server-side discovery and reconciliation mechanism for train edits
is documented in [Live train-consist discovery](train-consist-discovery-plan.md).
It is not implemented yet. The plan covers unknown pseudo mappings, affected
engine/train refreshes, and bounded retries. Its packet interpretation predates
the documented `ASSIGN_TRAIN` and `ROAD_SPEED` decoding and must be updated before
implementation, as recorded in the pre-merge checklist above.
