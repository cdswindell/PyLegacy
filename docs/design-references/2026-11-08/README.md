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
- Icon redesign and styled slider thumbs are possible future work; do not apply them yet.

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
