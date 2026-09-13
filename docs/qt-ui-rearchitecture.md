# Qt UI rearchitecture

The new `pytrain_ui` package is the presentation boundary for PyTrain. It may depend on `pytrain`; core PyTrain code must not depend on Qt or the new presentation package.

The existing GuiZero implementation remains in `pytrain.gui` during migration. New UI work goes into `pytrain_ui`, with Qt Quick/QML under `pytrain_ui.qt`.

Migrate one vertical slice at a time: define presentation state and commands, adapt existing PyTrain state/commands, implement the Qt/QML view, route the launcher, then retire the matching GuiZero implementation after parity testing.

The first target is EngineGui/cab control because it exercises live state, throttle and direction, press/hold/repeat behavior, artwork, touch input, Steam Deck input, and gauges.

`pygame-ce` remains the controller input layer. Controller events should call the same semantic command API as touch and mouse input. Center-return throttle sticks should represent rate and direction of speed change rather than absolute speed position.
