# Cab UI design references — November 8, 2026

Screenshots provided by Dave Swindell, preserved in the order supplied:

1. [Current Qt rearchitecture](01-qt-rearchitecture.png).
2. [Current PyCab on master](02-master-pycab.png).
3. [Previous Lionel Cab 3 app](03-lionel-cab3-previous.png).
4. [New Lionel Cab 3 keypad page](04-lionel-cab3-new-keypad.png).
5. [New Lionel Cab 3 operations page](05-lionel-cab3-new-operations.png).

The Lionel version descriptions are the user's identification of the supplied screenshots.

## Design direction

- Preserve the simple Switch and Route workflows; enlarge controls and reflow rows per the November 9 physical-display feedback.
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

## November 9 control refinements

- Direction buttons and Aux buttons share equal widths within their respective rows.
- Brake, momentum, and quilling horn start at zero at the top and increase downward.
- The throttle thumb displays target speed; the readout above it displays current speed.
- Speed +/− buttons send a direct ABSOLUTE_SPEED based on current reported speed.
  Both the buttons and the command adapter block these nudges while a local or remote
  ramp is active. Throttle dragging retains the ramp request path.
- Aux controls retain hold progress and show a brief hint after half a second:
  Repeat sequence, Lighting panel, or More controls, as applicable.
- The Qt application uses the existing bundled PyCab icon at small and large sizes.

## Five-inch Pi touch sizing — November 9

The physical display photos, including the dime for scale, showed that operating
controls and roster rows were too small. The tall Pi/PyCab operating layouts now
prioritize touch targets and readable captions over long slider tracks. The Aux
row spans the screen below the driving area, and artwork is bounded to make room.
The compact Steam Deck operating layout retains its separate sizing.

| Control | Previous size | Updated size |
| --- | --- | --- |
| Operating scope bar | 52 high, 12-pixel label | 84 high, 20-pixel label |
| Roster scope bar | 52 high | 104 high, 24-pixel label |
| Reset / ALL STOP | 46 high | 72 high, 24-pixel text |
| Drive / Effects | 34 high | 54 high, 22-pixel text |
| Direction | 38 high | 60 high, 20-pixel text |
| Speed +/− and mode selector | 36 high | 54 high, larger text |
| Aux squares | 96 × 96 | 144 × 144, 18-pixel text |
| Engine/train roster rows | 72 high | 144 high, 28-pixel names and 36-pixel IDs |
| Switch/route roster rows | 68 high | 184 high, 92-high action buttons |
| Accessory roster rows | 82 high | 208 high, 76-high quick actions |

Dimensions are logical pixels. Roster buttons and search/filter rows are enlarged;
filters can scroll horizontally, and lists show fewer entries. Switch/route names
and state occupy a line above the action buttons. Incremental roster updates still
preserve scroll position. Larger Effects tiles use two columns in tall layouts
and scroll independently of the driving controls.

Validation: all three device presets rendered, all five rosters rendered with
representative data, a scrolled switch action targeted the correct ID and retained
position, and speed-step lockout, target/current speed, Aux hints, and hold progress
were rechecked. Full suite: 8,761 passed, 35 skipped. Physical Pi touch usability
still needs the operator's review on the device.

## Five-column revision — November 9

The next physical-display review reduced the preceding oversized operating layout:

- Three fifths of the operating area contain three equal button columns; the other
  two fifths contain the variable control and throttle.
- The variable-control lane uses one quarter of the slider area, and the throttle
  uses three quarters, excluding their gutter. The mode selector spans the slider
  block so its name remains readable.
- Tall-layout operating tiles are 112 pixels high, down from 150. Aux buttons are
  108-pixel squares, down from 144, aligned with the three operating columns.
- Aux buttons remain visible on both Drive and Effects; Effects scrolls separately.
- The engine-type label above the driving block is removed.
- Scope navigation is always 84 pixels high with 76-pixel buttons, a fixed 20-pixel
  font, and the label Acc. Its size does not change between rosters, operation pages,
  or selected scopes. Long locomotive titles do not change the operating header height.

The Pi/PyCab throttle rail is 555 pixels tall in the reference rendering. All three
presets passed geometry checks for the 3:2 operating split and 3:1 slider split.
Direction feedback, current/target speed, direct speed-step lockout, and Aux hold
progress/hints were rechecked. Full suite: 8,761 passed, 35 skipped.

## Paired controls and selector alignment — November 9

Related actions now share rows in the first two of the three operating columns:
Bell/Horn, Brake/Boost, couplers, Crew/Tower, startup/shutdown, smoke, volume,
RPM, labor, and equipment-specific on/off or up/down controls. The third column
is left empty for pairs. The three momentum levels retain one three-button row.
Aux 1–3 occupy their own row and match operating tile width and height instead
of using smaller squares.

The variable-control selector now sits directly above its slider. That lane uses
one third of the driving block's slider width; the throttle uses two thirds.
The Pi selector is approximately 82 pixels wide. Momentum is displayed as Mom.
in the closed selector, with the full Momentum name retained in the menu.

All three presets passed geometry checks for paired rows, equal Aux/operation
sizes, selector/slider alignment, and the 1:2 slider-lane ratio. Current/target
speed, ramp lockout, and Aux hold behavior were rechecked. Full suite: 8,761
passed, 35 skipped.

## Drive row arrangement — November 10

Reset and ALL STOP are 25% taller, rounded to whole pixels: 54 to 68 in tall
layouts and 42 to 53 in compact layouts. Their widths and the header frame remain
unchanged.

The standard locomotive Drive page uses these one-based row/column positions:

| Row | Column 1 | Column 2 | Column 3 |
| --- | --- | --- | --- |
| 1 | Start Up | Shut Down | Volume + |
| 2 | Bell | Horn | Volume − |
| 3 | Smoke − | Smoke + | Boost |
| 4 | Rear Coupler | Front Coupler | Brake |
| 5 | Crew | Tower | |
| 6 | Aux1 | Aux2 | Aux3 |

Startup/shutdown, volume, and smoke controls move from Effects to Drive, retaining their
existing command and hold behavior. Acela startup/shutdown variants use the same
positions. Unsupported empty rows are omitted for other equipment, whose remaining
applicable controls remain available.

All three presets passed checks for the requested positions, unchanged header
widths, matching Aux dimensions, selector alignment, and current/target feedback.
Full suite: 8,761 passed, 35 skipped.


## Compact title controls and speed limit editor — November 10

Drive, the engine/train TMCC ID, and Effects share a row tucked immediately
beneath the title, between Reset and ALL STOP. The two tabs are 50 pixels tall.
Horn is the initial variable-slider mode when supported; state feedback retains
a mode the user explicitly selects, while changing locomotives resets to Horn.

The Speed Lim state tile opens Set Speed Limit, replacing the button beneath
the throttle. The editor combines numeric keyboard entry, an on-screen keypad,
and a synchronized slider. Set or the return key commits the limit; Cancel,
the close button, Escape, or changing locomotives discards the draft. No limit
is selected with Clear and requires Set. Limits use the locomotive protocol range (31 or 199), so
an existing lower limit does not prevent increasing it. Driving shortcuts are
disabled while this editor is open.

Pi, PyCab, and Steam Deck previews passed header geometry and live dialog
interaction checks with command delivery mocked. The dialog tests cover both
protocol ranges, validation, pointer-release submission, draft cancellation,
keypad/backspace, slider synchronization, and clearing the limit.

Full suite: 8,763 passed, 35 skipped. Ruff checks passed; PyCharm inspections,
including warnings and weak warnings, found no issues in the new test file.
