# Cab UI design references — November 8, 2026

Screenshots provided by Dave Swindell, preserved in the order supplied:

1. [Current Qt rearchitecture](01-qt-rearchitecture.png).
2. [Current PyCab on master](02-master-pycab.png).
3. [Previous Lionel Cab 3 app](03-lionel-cab3-previous.png).
4. [New Lionel Cab 3 keypad page](04-lionel-cab3-new-keypad.png).
5. [New Lionel Cab 3 operations page](05-lionel-cab3-new-operations.png).

The Lionel version descriptions are the user's identification of the supplied screenshots.

## Design direction

- Leave the current Switch and Route screens as they are for now.
- Preserve the Reset / engine-or-train title / ALL STOP header.
- Preserve the recent/selected engine and train state strip above the scope buttons.
- Prefer roster selection over requiring numeric ID entry.
- Retain PyCab functionality and equipment-specific operating controls.
- Explore a throttle that looks like a physical throttle, inspired by Cab 3.
- Prefer larger button graphics and less unused space within and around controls.
- Compare the three device previews before changing the engine/train design.
- First design pass authorized: retain existing icon artwork, enlarge operating graphics, and try a grip-style throttle handle. Full 3D button artwork and labels embedded in graphics remain future work.

## Confirmed device preview dimensions

| Device | Layout width × height |
| --- | --- |
| Raspberry Pi | 720 × 1280 |
| PyCab | 800 × 1280 |
| One Steam Deck pane | 639 × 800 |

Dimensions describe the app content, including its state strip and scope buttons.
The preview selector appears on macOS, outside this area; it does not take space
on the actual devices. Large previews may be scaled to fit on the Mac while retaining their target layout dimensions. This previews layout,
not the physical screen size or pixel density of a device.

## First engine/train design pass

The first pass keeps the Reset / title / ALL STOP header and the existing
recent-engine strip. Drive groups the existing primary and quick actions into
large icon tiles with captions; Effects contains the remaining operation and
tuning actions. Auxiliary panels stay accessible on both pages, along with the
throttle, direction, variable control, and speed-limit setting.

A shorter layout uses smaller artwork and icons at the Steam Deck pane size.
Effects hides the artwork in that layout so the standard Legacy diesel actions
fit without scrolling. Longer equipment action lists can scroll independently
of the driving controls. The Pi layout uses larger graphics and a taller throttle.
The throttle handle has a shaded grip; original function icon artwork is retained.

Validation used synthetic Legacy engine state with outgoing command sends
blocked, rendered Drive and Effects at all three preset sizes, and verified that
Switch and Route restore their original window dimensions. Full suite: 8,750
passed, 35 skipped. Physical touch and controller evaluation remains to be done.
