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

The legacy cab should remain available until the Qt implementation has been exercised on macOS, Raspberry Pi touch hardware, and Steam Deck controller hardware. Retirement of GuiZero is a separate decision after parity testing, not a prerequisite for making Qt the preferred cab presentation.


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

- [ ] Implement the Wi-Fi signal-strength meter in the Qt GUI. Deferred; not implemented yet.
- [ ] Separate core PyTrain and the GUI into independently installable packages in the same repository. Move shared accessory metadata, registry definitions, and configuration models out of `pytrain.gui` into a GUI-independent core location, retaining compatibility imports for legacy callers. Keep Qt dependencies in the GUI package so core-only installations do not require them. Deferred; do not implement yet.
