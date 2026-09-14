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
