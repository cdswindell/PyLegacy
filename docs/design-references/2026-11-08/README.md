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
the close button, Escape, or changing locomotives discards the draft. Clear
immediately removes the limit and closes the dialog, even with an invalid draft.
Clear is enabled only when the locomotive already has a limit. Set and the return
key are enabled only for valid numeric input, never an empty field or zero.
The dialog explicitly displays TMCC speed limit: 1–31 or Legacy speed limit: 1–199.
Limits use the locomotive protocol range (31 or 199), so
an existing lower limit does not prevent increasing it. Driving shortcuts are
disabled while this editor is open.

Pi, PyCab, and Steam Deck previews passed header geometry and live dialog
interaction checks with command delivery mocked. The dialog tests cover both
protocol ranges, validation, pointer-release submission, draft cancellation,
keypad/backspace, slider synchronization, and clearing the limit.

Full suite: 8,763 passed, 35 skipped. Ruff checks passed; PyCharm inspections,
including warnings and weak warnings, found no issues in the new test file.


## Drive and Speed page tabs — November 10

Drive and Speed now form a 40-pixel tab strip across the left three-column
control area. A muted selected background and blue underline identify the active
page. The former Effects page is labeled Speed; its available commands are
unchanged. The locomotive image stays visible on both pages, and switching tabs
changes only the action controls below it. The throttle and variable slider
remain shared and retain their positions.

The header again groups the locomotive title and TMCC ID closely between Reset
and ALL STOP. Tall-layout artwork is 108 pixels high, down from 120, to make room
for the tabs. Compact-layout artwork remains 52 pixels high. Aux controls retain
the same operation-button size and remain available on either page.

Pointer checks cover both tab directions on Pi, PyCab, and Steam Deck, including
unchanged artwork/throttle geometry. Existing Switch and Route layouts are
unchanged.

Full suite: 8,763 passed, 35 skipped.


## Raised tabs and navy background — November 10

The supplied Cab3 reference uses a predominant deep navy near #0d1f58, with
darker areas near #071438. Engine/Train operating and roster backgrounds now
use a gentle wash from #173775 through #0d1f58 to #09183f. The slider panel,
recent-engine bar, and scope-bar surround use related navy shades. Existing
button artwork and operation-button sizes remain unchanged.

Drive and Speed now have rounded upper corners, outlined raised edges, a
subtle vertical highlight, and a shared blue page surface. The active tab rises
above the inactive tab and its lower edge blends into the page. Both pages
retain their shared locomotive image and unchanged slider geometry.

Pointer switching and device previews passed for Pi, PyCab, and Steam Deck.
Switch, Route, and Accessory retain their current background styling.

Full suite: 8,763 passed, 35 skipped.


## Header clearance — November 10

Added 16 logical pixels above the driving area to separate the page tabs from
Reset and ALL STOP. Button sizes and the tab hit areas remain unchanged; the
control area and sliders give up only those 16 pixels of height.

All three device previews passed. Full suite: 8,763 passed, 35 skipped.


## Touch sizing and current-speed layout — November 10

Implemented the selected Readout above design: the full-width current-speed
readout uses the bundled Digital Dream font and always displays three digits.
Direction buttons are 64 pixels tall in tall layouts and 52 in compact layouts.
The variable-slider selector and speed +/− buttons share a height of 60 pixels
(tall) or 52 (compact), with larger step symbols. The variable range label is
restored below its slider. The throttle retains its full-length track; only the
thumb is 20% shorter (77/50 pixels), preserving its target label, value, and grip.

Reset and ALL STOP now share both width (132/106) and height (88/72). Page tabs
are 56 pixels tall. The locomotive title remains centered with two-line wrapping
for long names. Artwork extends upward into the tab-to-image gap without moving
the action buttons down. The slider panel's upper edge is raised to meet the
tabs, with its lower edge unchanged.

Recent-engine cards are wider and their bar is 90/78 pixels tall, with larger
identity/state text and 44-pixel close controls. Roster rows are 25% shorter:
Engine/Train 108, Switch/Route 138, and Accessory 156 pixels. Switch/Route row
actions remain 60 pixels tall, and row padding accommodates the existing text.

Cab and function buttons show a brief visual acknowledgement for short taps and
keyboard activation; their command timing and hold/repeat logic still use the
actual pointer state. Tabs, selector, roster rows, and keyboard keys have visible
pressed states. Popup surfaces and the native control palette are dark navy.
The ID keypad now matches the speed-limit panel's 440-pixel maximum width.

TouchSearchField opens a self-contained QWERTY search keyboard on Linux (Pi and
Steam Deck), without an optional Qt Virtual Keyboard dependency. Search changes
filter the roster live; Done, close, or Escape dismisses without selecting an
engine. It includes digits, Shift, Backspace, space, hyphen, and Clear. macOS
retains normal hardware-keyboard text entry. The keyboard interaction test covers
these edits, dismissal, one edit per key, and minimum footer touch-target sizes.

Preview and pointer checks cover Pi, PyCab, and Steam Deck; all command delivery
was mocked during UI checks.

Reset and ALL STOP text is 24 pixels in tall layouts and 20 in compact layouts,
with their matched button sizes unchanged. Full suite: 8,764 passed, 35 skipped.
Ruff and PyCharm inspections, including weak warnings, passed for the new test.
