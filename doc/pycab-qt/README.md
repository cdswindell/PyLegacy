# PyCab Qt User Manual

PyCab is the touchscreen cab for operating a Lionel layout through PyTrain. This guide covers the Engine, Train, Switch, Accessory, and Route views and their shared tools. The images are simulated captures of the current Qt interface at **720 × 1280**, the layout for the 5-inch Raspberry Pi display. They use sample records and may differ from the Pi in font rendering and touch behavior.

<img src="screens/engine-controls-pi.png" width="360" alt="Diesel Engine Controls and throttle on the 5-inch Pi layout">

## Table of Contents

1. [Start PyCab](#start-pycab)
2. [Navigate the Cab](#navigate-the-cab)
3. [Engine Roster and Keypads](#engine-roster-and-keypads)
4. [Engine Controls](#engine-controls)
5. [Button Decorators](#button-decorators)
6. [Throttle and Secondary Slider](#throttle-and-secondary-slider)
7. [Speed and Volume](#speed-and-volume)
8. [State Tiles and Engine Information](#state-tiles-and-engine-information)
9. [Sound, Dialogs, and Lights](#sound-dialogs-and-lights)
10. [Train Operations](#train-operations)
11. [Accessory Operations](#accessory-operations)
12. [Switch Operations](#switch-operations)
13. [Route Operations and Route Builder](#route-operations-and-route-builder)
14. [Manage PyTrain](#manage-pytrain)
15. [LCS Device Manager](#lcs-device-manager)
16. [Steam Deck](#steam-deck)

## Start PyCab

From your PyLegacy checkout, activate your Python environment and install the Qt extra. Launch in client mode if PyTrain is already running on another machine.

```sh
python -m pip install -e '.[qt-gui]'
pycab --qt -client
```

PyCab starts fullscreen on a detected Raspberry Pi or an installation configured for Steam Deck. Use **Manage PyTrain → Quit** to exit from the touchscreen. The desktop app also supports the normal window close action.

| Startup option | What it does |
| --- | --- |
| `--qt` | Launches the Qt version of PyCab explicitly. The launcher also defaults to Qt when PySide6 is installed. |
| `--legacy` | Opens the older GuiZero cab. `PYTRAIN_LEGACY_GUI=1` also selects it when neither launcher flag is specified. |
| `-h`, `--help` | Shows the Qt command-line options and exits. |
| `tmcc_id` | Optional starting TMCC ID. The parser default is 1. PyCab can also restore the last engine or open the roster. |
| `-train` | Requests train scope at startup. Opens Train scope. |
| `-client` | Runs as a client and discovers a PyTrain server when no address is given. |
| `-server SERVER` | Specifies the PyTrain server address for client mode. |
| `-base [BASE]` | Connects to a Base 3 at the supplied IP address. Supply `-base` by itself to discover the Base 3 on the local network. |
| `-port PORT` | Sets the serial device. The default is `/dev/ttyUSB0`. |
| `-baudrate RATE` | Sets serial baud rate. Supported values are 9600, 19200, 38400, 57600, and 115200. The default is 9600. |
| `-echo` | Prints received TMCC and PDI commands in the terminal. |
| `--deck` | Opens the two-pane Qt Steam Deck host explicitly. `PYTRAIN_PLATFORM=steamdeck` also selects this host. |
| `--width`, `--height` | Set the Deck host dimensions; defaults are 1280 × 800. |
| `--controller-profile` | Loads a Steam Deck controller profile JSON file. |

```sh
pycab --qt -client -server 192.168.1.20 -echo
pycab --qt -base
pycab --qt -base 192.168.1.30
pycab --qt -h
```

If the shell reports that `pycab` was not found, activate the same environment you used to install the Qt extra.

## Navigate the Cab

State Info uses fixed, non-scrolling layouts in every scope, both in Info tabs and standalone panels. Compact screens use tighter section spacing to keep identity fields, configuration, board details, and action buttons visible together.

- Tap a scope button along the bottom to change scope. **Engine**, **Train**, and **Acc** return to the current selected cab or accessory, when available. Tapping the active scope again toggles between its controls and roster. A previously operated roster-based accessory returns to its roster entry.
- Hold or quickly double-tap a scope button to open its TMCC ID keypad. A double-tap consists of two taps within 400 ms anywhere on that same button. Dragging is not a double-tap.
- **Cab** returns from the Engine or Train roster to its current selection; it is disabled when no selection exists.
- Tap the title chevron for **Roster**, **Manage PyTrain**, **Route Builder**, and **LCS Device Manager**. Choosing a menu destination closes the current panel and its child dialogs. If a draft has unsaved changes, **Keep Editing** or Escape cancels navigation; **Discard** continues to the destination.
- **ALL STOP** sends the layout-wide halt command. The **Emergency** stop on the Speed/Volume tab targets the selected engine.
- **Reset** is the selected engine's reset control. Leave a dialog with **Close**, **Cancel**, or **Back**, as shown on that screen.
- On a Mac, the device preview controls let you inspect the layout at a target size. A displayed percentage below 100% means the preview is scaled to fit.

<img src="screens/navigation.png" width="300" alt="Title menu with Roster, Manage PyTrain, Route Builder, and LCS Device Manager">

## Engine Roster and Keypads

Search by name, road number, TMCC ID, or engine type. All rosters use equal-size sort buttons in the order **TMCC ID / Name / Road #**, with **TMCC ID** selected initially. Swipe the type-filter tabs horizontally for more choices; the selected tab stays visible when the roster opens. The horizontal scrollbar appears only when the tabs overflow. Swipe the roster vertically to see more rows. Long names scroll within their row. Address badges show **ENG** or **TRN** above the ID, and road numbers retain their leading zeros.

Tap a sort button to change order. Double-tap or hold a sort button to apply that order and return to the first row. The same behavior applies across scopes. Train and Route rosters leave the **Set** position blank so the search field, delete key, and keypad key remain aligned with the other scopes.

Tap a row to open its cab. Enter a numeric TMCC ID with the keypad or the search field and use **Set** to go directly to it. If the engine is missing, PyCab opens Engine Information for that ID. The engine keypad accepts up to four digits. **Set Address** is a programming command, separate from selecting a roster entry.

On the Pi, tap the search field to open the on-screen keyboard. Use the backspace key to delete a character and hold it to clear the field. **Close** on a keypad leaves without submitting. The touchscreen keyboard has a wide **Space** bar with **#**, **&**, **-**, and **+** on the same row. **Done** dismisses a roster or route field keyboard. **Save** confirms Road Name in Engine or Train Information.

<img src="screens/engine-roster.png" width="280" alt="Engine roster with search, sorting, and type filters"> <img src="screens/engine-keypad.png" width="280" alt="Engine TMCC ID keypad and Set Address">

<img src="screens/roster-touch-keyboard.png" width="420" alt="On-screen search keyboard">

## Engine Controls

The cab shows the selected engine's name, road number, and TMCC ID above the locomotive image. **Current Speed** shows reported speed. The throttle thumb shows the target. Drag or tap the throttle track to set a target, or use **+** and **−** for individual speed steps when ramping is idle. The second slider controls the selected function, such as horn, brake, or momentum. A single supported function appears as a label. The horn slider returns to zero on release. The throttle scale uses 20-step labels for Legacy and 5-step labels for TMCC. While ramping, the trough shows the remaining span between reported speed and target.

For absolute-speed throttles, **−** is disabled at zero and **+** at the maximum speed step. Cab-1 relative throttles keep both available because zero is the center.

The **Controls** tab changes with engine and control type. Corner marks show what happens on a hold. See [Button Decorators](#button-decorators).

Swipe the locomotive image to cycle through active engine tiles. Tap a tile to select its engine or tap its **×** to remove the tile. Double-tap the locomotive image to open **Engine Information**. On a Mac, use a double-click.

| Type | Distinctive controls |
| --- | --- |
| Diesel, Diesel Pullmor, Diesel Switcher | RPM and other sound and operating controls where supported. |
| Steam, Steam Pullmor, Steam Switcher | Whistle and steam-specific artwork and wording. Supported models offer Let Off, Water Injector, coal, and water controls. |
| Electric and Acela | Pantograph controls. The layout depends on protocol and engine type. |
| Passenger and FreightSounds | Car-specific sound and lighting controls. A standalone car has no active throttle. |
| Track Crane | Boom/Cab, Main/Roll, Aux Hook, outriggers, and work lights. Cab-1 uses a centered relative throttle and a direction toggle. The throttle returns to center on release. |
| Transformer | **Full On**, **Shut Down**, direction toggle, and track power controlled through speed steps. Its second tab is **Speed**. |
| Accessory engine type | A four-column Lionel-style numeric/function keypad and a narrow Cab-1 relative throttle. The **Speed/Volume** tab is omitted. Numeric keys and Horn repeat every 100 ms while held. Startup/shutdown are single actions; Aux 1 repeats while held. |

<img src="screens/steam.png" width="280" alt="Steam Controls tab"> <img src="screens/electric.png" width="280" alt="Electric Controls tab">

<img src="screens/acela.png" width="280" alt="Acela Controls tab"> <img src="screens/crane.png" width="280" alt="Crane Controls tab"> <img src="screens/transformer.png" width="280" alt="Transformer Controls tab">

<img src="screens/passenger.png" width="280" alt="Passenger car Controls tab"> <img src="screens/freight.png" width="280" alt="Freight car Controls tab">

<img src="screens/tmcc.png" width="225" alt="Tmcc"> <img src="screens/diesel-switcher.png" width="225" alt="Diesel Switcher"> <img src="screens/diesel-pullmor.png" width="225" alt="Diesel Pullmor">

<img src="screens/steam-switcher.png" width="225" alt="Steam Switcher"> <img src="screens/steam-pullmor.png" width="225" alt="Steam Pullmor">

<img src="screens/accessory-engine.png" width="300" alt="Accessory engine type with repeating numeric keys, couplers, Aux controls, and relative throttle">

## Button Decorators

<img src="screens/button-decorators.png" width="900" alt="Enlarged button corner markers beside the original Crew, Start Up, and Boost buttons">

| Corner Mark | What Holding Does |
| --- | --- |
| Overlapping squares | Opens a panel, such as Crew Dialogs or Lights. On Horn or Whistle, it selects that function on the secondary slider. |
| Plus sign | Runs an alternate hold action, such as extended startup/shutdown, railroad speed dialog, or resource refill, where supported. |
| Clockwise circular arrow | Marks a held/repeating action, as on Boost, Brake, repeating numeric keys, and Aux 1. Aux 1 repeats at 100 ms on Engine, Train, and TMCC Accessory panels. ASC2 **Hold** stays on while pressed and sends Off on release. |

The progress bar shows hold progress on buttons that wait for a hold threshold. A hold-only control does not automatically gain a double-tap action.

## Throttle and Secondary Slider

The throttle handle is offset toward the left, with tick marks and speed numbers on the right. Its Target readout follows the selected speed. The highlighted segment spans the gap between Current Speed and Target in either direction.

The narrower secondary trough has its scale on the left and its thumb overhangs that side. The labels change with the selector. Horn shows 0–15, Brake shows 0–7, and Momentum shows Low, steps 1–6, and High on Legacy. TMCC momentum has Low, Med, and High.

<img src="screens/sliders-ramp-up.png" width="330" alt="Throttle ramping up from 42 to 120 with the Horn scale visible"> <img src="screens/sliders-ramp-down.png" width="330" alt="Throttle ramping down from 120 to 42 with the Horn scale visible">

<img src="screens/secondary-brake.png" width="330" alt="Secondary slider showing Brake steps from 0 to 7"> <img src="screens/secondary-momentum.png" width="330" alt="Secondary slider showing Low, intermediate steps, and High">

## Speed and Volume

The railroad speed presets run from **Restricted** through **Highball**. Tap to ramp to that preset. On supported engines, holding adds the tower request and engineer acknowledgment. **Normal** ramps to zero, **Roll** ramps to roll speed, and **Emergency** commands zero immediately with emergency dialog where supported.

Hold an enabled fuel, coal, or water gauge to refill. **Set Address** programs the selected address. The lower controls adjust master volume, blend, and effort where supported. Disabled or absent controls reflect the selected equipment's capabilities.

<img src="screens/speed-volume.png" width="300" alt="Speed and Volume tab with railroad speed presets, gauges, and sound controls">

<img src="screens/tmcc-speed-volume.png" width="225" alt="Tmcc Speed Volume"> <img src="screens/crane-speed-volume.png" width="225" alt="Crane Speed Volume"> <img src="screens/transformer-speed-volume.png" width="225" alt="Transformer Speed Volume">

<img src="screens/passenger-speed-volume.png" width="225" alt="Passenger Speed Volume"> <img src="screens/freight-speed-volume.png" width="225" alt="Freight Speed Volume">

## State Tiles and Engine Information

Tap an enabled state tile below the controls to edit its value. Dimmed tiles are unavailable for the selected engine.

| Tile | How to use it |
| --- | --- |
| Momentum | Choose **Low**, **Medium**, or **High**. For Legacy, the slider selects the value for **Medium**. |
| Brake | Set the train brake level or tap **Off** to send zero. |
| Smoke | Pick a level for Legacy or **On** and **Off** for TMCC. The choice applies immediately. |
| Speed Lim | Enter a number or move the slider, then tap **Set**. The panel shows the available range. **Clear** removes a set limit. |
| Effort and RPM | Set a level with the slider or use **Default**. The defaults are 12 for effort and 0 for RPM. |

<img src="screens/momentum.png" width="225" alt="Momentum"> <img src="screens/train-brake.png" width="225" alt="Train Brake"> <img src="screens/smoke.png" width="225" alt="Smoke">

<img src="screens/speed-limit.png" width="225" alt="Speed Limit"> <img src="screens/effort.png" width="225" alt="Effort"> <img src="screens/rpm.png" width="225" alt="RPM">

**Info** is an Engine/Train cab tab and shows roster fields, live status, and consist details. The other tabs remain available; the cab image keeps the same size, shape, and position across Controls, Speed/Volume, and Info. Info opened this way has no redundant **Close** button. Double-tapping the image also opens information. Leaving a tab or choosing a title-menu destination with a pending draft prompts before discarding it.

**Engine Information** shows roster fields, live status, and consist details. Tap a field to edit it. On the Pi, **Road Name** opens a touchscreen keyboard with **Save**. **Road Number** opens a numeric editor. **Engine Type**, **Control Type**, and **Sound Type** show selectable choices. Scroll the engine type list as needed. For an existing engine, confirm the field editor to write the change. For a new engine, field edits are staged until you tap **Create**. Hold **Clear** for three seconds to clear an existing record. Leaving with pending changes can prompt you to keep editing or discard them.

<img src="screens/engine-information-pi.png" width="280" alt="Engine Information and Real Time Status"> <img src="screens/create-engine.png" width="280" alt="Create Engine for an unused address">

<img src="screens/engine-road-name-touch-keyboard.png" width="420" alt="Road Name editor with the on-screen keyboard">

<img src="screens/road-number.png" width="225" alt="Road Number keypad"> <img src="screens/engine-type.png" width="225" alt="Scrollable Engine Type choices"> <img src="screens/control-type.png" width="225" alt="Control Type choices"> <img src="screens/sound-type.png" width="225" alt="Sound Type choices">

On desktop, **Road Name** opens a text editor for the physical keyboard.

<img src="screens/road-name.png" width="225" alt="Road Name">

## Sound, Dialogs, and Lights

- Hold **Bell** where supported to open Bell/Horn or Bell/Whistle Options. The panel offers tone cycling and playback controls where the protocol and engine support them.
- Hold **Crew** or **Tower** to browse spoken commands. A category button opens its list. **Back** returns to the categories and **Close** dismisses the panel. Speed choices in these dialog panels play the announcement only.
- Hold **Aux 2** on supported Legacy engines for the Lights panel. The available groups depend on engine type. TMCC Aux 2 uses a single action and has no Lights sublabel. The bottom row includes **Aux 2**, **Close**, and **Cab** where supported.
- Passenger cars provide separate **Conductor**, **Station**, and **Steward** dialog panels. Tap for a dialog or hold to choose one. The Conductor panel groups dialogs and actions.

<img src="screens/bell-horn.png" width="225" alt="Bell and Horn Options"> <img src="screens/crew.png" width="225" alt="Engineer and Crew Dialogs"> <img src="screens/tower.png" width="225" alt="Tower Dialogs"> <img src="screens/lights.png" width="225" alt="Lights panel">

<img src="screens/conductor.png" width="225" alt="Conductor dialogs and actions"> <img src="screens/station.png" width="225" alt="Station dialogs"> <img src="screens/steward.png" width="225" alt="Steward dialogs">

<img src="screens/bell-whistle.png" width="225" alt="Bell Whistle"> <img src="screens/crew-acknowledge.png" width="225" alt="Crew Acknowledge"> <img src="screens/crew-arrive-depart.png" width="225" alt="Crew Arrive Depart">

<img src="screens/crew-status.png" width="225" alt="Crew Status"> <img src="screens/crew-conductor.png" width="225" alt="Crew Conductor"> <img src="screens/crew-station.png" width="225" alt="Crew Station">

<img src="screens/crew-steward.png" width="225" alt="Crew Steward"> <img src="screens/crew-etc.png" width="225" alt="Crew Etc"> <img src="screens/crew-general.png" width="225" alt="Crew General">

<img src="screens/tower-speed.png" width="225" alt="Tower Speed"> <img src="screens/tower-arrive-depart.png" width="225" alt="Tower Arrive Depart"> <img src="screens/lights-cab-lights.png" width="225" alt="Lights Cab Lights">

<img src="screens/lights-car-lights.png" width="225" alt="Lights Car Lights"> <img src="screens/lights-ditch-lights.png" width="225" alt="Lights Ditch Lights"> <img src="screens/lights-ground-lights.png" width="225" alt="Lights Ground Lights">

<img src="screens/lights-marker-lights.png" width="225" alt="Lights Marker Lights"> <img src="screens/lights-mars-lights.png" width="225" alt="Lights Mars Lights"> <img src="screens/lights-rule-17.png" width="225" alt="Lights Rule 17">

<img src="screens/lights-strobe-lights.png" width="225" alt="Lights Strobe Lights"> <img src="screens/lights-tender-lights.png" width="225" alt="Lights Tender Lights">

## Train Operations

Tap **Train** to browse the roster or return to the last train you operated. Select a train from the list or use its TMCC ID keypad. The cab includes **Controls**, **Speed/Volume**, and **Info**, with the fields and controls available for the selected train. Train rosters use the same searchable list, sort order, and horizontally scrollable type tabs as Engine rosters.

<img src="screens/train-roster.png" width="225" alt="Train Roster"> <img src="screens/train-keypad.png" width="225" alt="Train Keypad"> <img src="screens/train-controls.png" width="225" alt="Train Controls">

<img src="screens/train-speed-volume.png" width="225" alt="Train Speed Volume"> <img src="screens/train-information-pi.png" width="225" alt="Train Information">

<img src="screens/train-road-name-touch.png" width="420" alt="Train Road Name touchscreen keyboard">

## Accessory Operations

Tap **Acc** for **Accessories**. Search by name, road number, or TMCC ID, or use its numeric keypad. The filter tabs are **All**, **Operating**, **LCS**, **TMCC**, **Sensor**, **BPC2**, **ASC2**, and **AMC2**. Only module types reported in the layout appear; **Operating** is omitted when no configured operating accessories exist. **LCS** includes BPC2, ASC2, AMC2, and IR Sensor Track. ASC2 devices operating as switches appear in Switch scope instead.

**Show Unnamed** follows the same user-defined-record rule as Switches; an LCS association does not make an unnamed record named. Entering an exact TMCC ID can still reach a hidden device. For AMC2, Sensor Track, and TMCC/Command Control accessories, submitting an ID opens its controls directly.

Operating accessories appear first, alphabetically, under **All**. Each configured instance appears once, with its image as a badge and no road number. Other rows use a rounded address badge with an LCS type or **ACC** prefix. A long name scrolls within its row. TMCC rows omit raw AUX state dumps.

<img src="screens/accessory-roster.png" width="300" alt="Accessories roster with configured artwork badges, sort buttons, and scrollable filter tabs"> <img src="screens/accessory-keypad.png" width="300" alt="Accessory address keypad">

### ASC2 and BPC2 roster controls

<img src="screens/accessory-lcs-roster.png" width="300" alt="LCS accessory roster with power icons, ASC2 Hold, and state feedback">

Operate relay-backed accessories directly from their row. **On** and **Off** use the standard power icons, and their filled backgrounds show the reported state. ASC2 mixed-mode ports also have **Hold** with the clockwise-arrow decorator: pressing sends On, releasing sends Off. Holding the row body for the standard hold threshold performs the same momentary operation until release or cancellation; ordinary taps and scrolling do not energize it. On, Off, Hold, and Edit keep their own actions when pressed. BPC2 rows offer On/Off. Unknown state highlights neither action. Operation feedback keeps your place in the roster.

**Edit** opens State Info with direct Road Name and Road Number fields, configuration details, board information, and firmware. **Aa** title-cases the name. On a Mac, type with the system keyboard; on Pi/Deck, tap for the touch keyboard or numeric keypad. LCS-backed records show **Clear** disabled. Changes are written only with **Save**.

<img src="screens/asc2-info.png" width="280" alt="ASC2 accessory State Info with direct identity fields, mixed mode, port, and firmware"> <img src="screens/bpc2-info.png" width="280" alt="BPC2 State Info with numeric and named mode and board details">

### ASC2 Mode 1 uncoupling tracks

An ASC2 in **Mode 1 — Uncoupling (ACC)** uses one TMCC ID for eight outputs. Open its roster row, or enter its exact TMCC ID, to display **Uncouplers / Relays / ACC / Info**. **ACC** opens the standard accessory keypad with its relative throttle, addressed to the module’s base TMCC ID. Uncouplers contains keys **1–8**, each selecting the correspondingly numbered track output. Each activation sends one **CONTROL3** request to the module's base ID, with the selected sub-ID and a **one-second pulse**. Holding a key does not repeat; no separate Off command is needed. This follows [Lionel's single-address ASC2 operating guidance](https://control.lionel.com/lcs/products/asc2/).

**Relays** provides explicit On/Off control of all eight outputs using CONTROL2. Tap a relay to toggle it, or use All On/All Off. Unknown state is labeled explicitly. **Edit Group** lets you change several desired states before **Apply** sends one request; only changed outputs are included in the valid-bits mask. **Cancel** discards the draft. Leaving a draft prompts for Discard or Keep Editing. Filled green buttons reflect reported On states; group changes use amber. Device responses confirm requests, and unconfirmed outputs become unknown after a timeout. **Refresh** requests current relay states. CONTROL2 has no pulse-duration field; use Uncouplers for timed uncoupling pulses. The Relays page displays a prominent warning that latched relay operation will burn out uncoupling tracks.

A configured **Uncoupler Track** Operating accessory uses the same keypad when its `uncouple` assignment identifies a Mode 1 ASC2. Existing Mode 0 uncoupler assignments keep their press/release Hold control. No legacy GUI class is used to construct either Qt panel.

```json
{
  "gui": "uncoupler",
  "instance_id": "yard-uncouplers",
  "display_name": "Yard Uncoupling Tracks",
  "tmcc_ids": {"uncouple": 24}
}
```

The assignment above is the module's single TMCC ID, not eight consecutive accessory IDs. The actual board must report Mode 1 before the keypad is offered. **Configure**, beside the image, opens that ASC2 instance in LCS Device Manager with its current base ID and mode. Unnamed boards remain hidden unless Show Unnamed is enabled, but their exact ID can still open the controls directly.

### Configured operating accessories

Select a configured row for its larger accessory image and metadata-driven controls. **Controls** and **Info** are tabs below the image. Each operation has its own compact labeled frame. A known latching operation uses one button showing the next action: a green On graphic while off, and a red Off graphic while on. A pending indicator can appear while waiting for state feedback.

Dependent actions remain disabled until their power operation is on. The Fire Station, for example, has Power and Alarm; Alarm is unavailable while Power is off. Held, pulse, and repeating actions follow their registry definitions and decorators. Animated artwork plays according to the operation's hold, latch, or animation duration; a command pulse and visual animation duration are separate.

Stations use Power and a second latched operation. Passenger variants show **Arrive/Depart**; freight and brewery variants show **Load/Unload**. Those same operation names appear in roster status summaries.

<img src="screens/operating-fire-gated.png" width="280" alt="Fire Station with Alarm disabled while power is off"> <img src="screens/operating-fire.png" width="280" alt="Fire Station with enabled Alarm after power is on">

<img src="screens/operating-passenger.png" width="280" alt="Passenger station Power and Arrive/Depart controls"> <img src="screens/operating-brewery.png" width="280" alt="Brewery Power and Load/Unload controls">

**Info** for a configured operating accessory is read-only. It shows **Type:** from the registry and a table of **Key / Operation / Assignment**, including component TMCC IDs and LCS ports. These are configured instances from `accessory_config.json`; changing their definition is separate from editing a Base accessory record.

<img src="screens/operating-passenger-info.png" width="300" alt="Read-only Station Info with port keys, operations, and LCS assignments"> <img src="screens/accessory-operating.png" width="300" alt="Construction accessory controls from the registry">

### TMCC/Command Control accessories

Unassigned TMCC accessories open a four-column numeric/function keypad with coupler, Boost/Brake, Aux, Set, and Cab-1 relative throttle controls. Numeric keys and Aux 1 repeat at 100 ms while held, marked with clockwise arrows. These commands address **ACC**, not Engine scope. Horn, Bell, Startup, and Shutdown positions are not supplied for TMCC accessories. **Set** programs the current address. The **Info** tab displays editable State Info in the same page, with Controls still available and no redundant Close button.

<img src="screens/tmcc-accessory.png" width="280" alt="TMCC accessory Controls and Info tabs above the keypad and relative throttle"> <img src="screens/tmcc-accessory-info.png" width="280" alt="TMCC accessory State Info with direct name and road-number inputs">

A configured TMCC operating accessory has **Controls / ACC / Info** tabs. **ACC** exposes that same full accessory keypad without replacing the surrounding accessory page. **Info** shows its overall TMCC ID once, the registry type, and the panel keys that operate each function.

For the Smoke Fluid Loader, Lights use numeric 9 On and 8 Off. Because reliable light state is unavailable, separate On/Off buttons do not pretend to indicate feedback. The horizontal Fluid Boom control is spring-centered −5…+5, with its current relative command value in the throttle-style handle. Tap the trough to send the relative command at that position, or drag and hold to repeat it. Dispense sends Brake.

<img src="screens/operating-smoke-loader.png" width="280" alt="Smoke Fluid Loader Lights, Dispense, and horizontal relative boom control"> <img src="screens/operating-smoke-acc.png" width="280" alt="Smoke Fluid Loader ACC tab with full keypad and throttle"> <img src="screens/operating-smoke-info.png" width="280" alt="Smoke Fluid Loader Info with overall ID, registry type, and command-key table">

### AMC2 motors and lights

**Motors** and **Lights** are separate tabs. Each channel has a vertical 0–100% slider and On/Off buttons. Off keeps the remembered slider level; On returns to it. Double-tap On to set 100%, or Off to set 0%, regardless of the previous value. An off channel's slider is dimmed but remains movable; moving it turns the channel on at the new level. Slider commands are sent on release.

**Info** is a third tab beside Motors and Lights. Its fixed layout shows editable name/number plus read-only AMC2 configuration, board information, and firmware without a scroll panel. On compact screens, the fields are arranged more tightly to keep them visible above the footer. **Configure**, beside the image, opens the current AMC2 configuration options, including output type and restore-on-power-up settings. Double-clicking, double-tapping, or holding an accessory image opens its Info tab; this applies to AMC2, Sensor Track, and configured Operating accessories.

<img src="screens/amc2.png" width="280" alt="AMC2 Motors tab with vertical sliders and remembered On/Off levels"> <img src="screens/amc2-lights.png" width="280" alt="AMC2 Lights tab with four separate lamp controls"> <img src="screens/amc2-info.png" width="280" alt="AMC2 State Info with identity and underlying configuration">

### IR Sensor Track

The **Action** tab contains the available track actions in a scrolling list, with paired Right ➟ Left and Left ➟ Right entries aligned in columns. The selected action has a filled background. The **Info** tab sits beside Action and shows editable name/number, current configuration, board information, and firmware in the same page. Leaving an Info tab with unsaved changes prompts you to keep editing or discard the draft. There is no redundant Configure button for the action list.

<img src="screens/sensor.png" width="280" alt="IR Sensor Track Action list with aligned directional labels"> <img src="screens/sensor-info.png" width="280" alt="Sensor Track State Info including action configuration and firmware">

### Add an accessory

**Add…** opens a creation panel for TMCC ID, Road Name, and Road Number. For a TMCC/Command Control accessory, follow the PROGRAM-mode tip before **Add Accessory**. That action sends SET ADDRESS and writes the identity fields. If the road number is blank, it follows the entered TMCC ID when that ID loses focus or is accepted from its keypad. Once you supply your own road number, later ID changes preserve it.

<img src="screens/accessory-add.png" width="300" alt="Add Accessory with address, name, number, and programming instructions">

## Switch Operations

Search the switch roster by name, road number, or TMCC ID. Sort with **TMCC ID / Name / Road #**, initially TMCC ID. The **All / Thru / Out** tabs filter by reported position and update as switch feedback arrives. Enable **Show Unnamed** to include records that are not user-defined. Where known, LCS module information appears under the road name.

- Tap **Thru** for the straight path or **Out** for the diverging path. The selected action and rounded **SW** badge use green for Thru and amber for Out. Unknown state uses a neutral badge and highlights neither action. Unselected buttons retain their standard background.
- Double-tap the body of a tile to toggle the switch. An unknown switch goes to **Thru**. Swipe to scroll.
- Tap **Edit…** to change the road name or number, then **Save**. On the Pi, tap **Road Name** for the on-screen keyboard or **Road Number** for the four-digit keypad. **Add Switch** also opens a numeric keypad for its TMCC ID. Hold **Clear** for three seconds to clear the record.
- Tap **Add…** to create a record. For a Lionel Command Control switch, follow the PROGRAM-mode instruction before adding. If its address belongs to an ASC2 switch port, programming is disabled: the Command Control checkbox is unchecked/disabled and the action becomes **Save** for identity fields. **Set** is also disabled for ASC2 switch ports on the roster/keypad.

<img src="screens/switch-roster.png" width="225" alt="Switch roster"> <img src="screens/switch-keypad.png" width="225" alt="Switch keypad with Set Address"> <img src="screens/switch-edit.png" width="225" alt="Edit Switch"> <img src="screens/switch-add.png" width="225" alt="Add Switch">

<img src="screens/switch-overwrite.png" width="225" alt="Switch Overwrite"> <img src="screens/switch-road-number.png" width="225" alt="Switch Road Number"> <img src="screens/switch-address-editor.png" width="225" alt="Switch Address Editor">

<img src="screens/switch-road-name-touch.png" width="420" alt="Switch Road Name touchscreen keyboard">

## Route Operations and Route Builder

The roster shows **Aligned** or **Unset** when alignment is known. Rounded **RTE** badges use green for Aligned and amber for Unset; unknown alignment has a neutral badge and blank status. Sort with **TMCC ID / Name / Road #**, initially TMCC ID. **All / Aligned / Unset** tabs filter the roster rather than changing its sort order. Tap **Fire** or double-tap the body of a tile to fire the route. Swipe to scroll the roster. **Add…** sits to the left of the title. The unused Set-key position remains blank to align search controls across scopes.

1. Tap **Edit…** on a route, **Add…** on the roster, or **Route Builder** in the title menu.
2. Enter the route TMCC ID (1–98), name, and route number. Tap a field on the Pi for its keyboard or keypad.
3. Use **Add…** to pick elements. A route holds up to 16 elements.
4. Tap an element to select it. Set a turnout to **Thru** or **Out**. Double-tap an Out tile, or double-tap or hold **Out**, to flip the left/right diagram. This edits the route element. **Move Left** and **Move Right** change its position in the sequence.
5. **Remove** deletes the selected element from the draft. **Clear All** empties the draft's element list. **Save** writes the route. Holding the footer **Clear** clears the stored record. **Cancel** leaves the editor and prompts before discarding unsaved changes.

<img src="screens/route-roster.png" width="225" alt="Route roster"> <img src="screens/route-keypad.png" width="225" alt="Route TMCC ID keypad"> <img src="screens/route-builder.png" width="225" alt="Route Builder with three-rail element graphics"> <img src="screens/route-picker.png" width="225" alt="Add to Route element picker">

<img src="screens/discard-changes.png" width="225" alt="Keep Editing or Discard confirmation">

<img src="screens/route-address-editor.png" width="225" alt="Route Address Editor"> <img src="screens/route-name-touch-keyboard.png" width="225" alt="Route Name Editor"> <img src="screens/route-number-editor.png" width="225" alt="Route Number Editor">

## Manage PyTrain

Open **Manage PyTrain** from the title menu. The panel shows the layout name, local IP, and PyTrain version. A client also shows the server version when available.

- Hold **Reload Database** for one second to resync the Base 3 database. **Reloading…** flashes while the sync is active.
- **Reload Accessories** and **Refresh Images** update their respective data and briefly display a status message.
- **Logging** and **Debugging** show their active state with checkboxes. Choose **Local** or **All** before a maintenance action to target this node or the layout's PyTrain nodes.
- **Restart**, **Reboot**, **Update PyTrain**, **Upgrade Pi OS**, **Quit**, and **Shutdown** require a three-second hold. The progress bar turns amber during the final half-second. Stop trains before actions that interrupt control.

<img src="screens/manage.png" width="300" alt="Manage PyTrain with database, logging, and maintenance controls">

## LCS Device Manager

Open **LCS Device Manager** from the title menu or **LCS…** in Switches or Accessories. **My Modules** shows modules that have reported themselves. Sort by TMCC ID, module type, or scope.

To configure a module, select its type and tap **Next**. Choose its base TMCC ID and mode, then review the assigned addresses, any overlaps, and the options for that device. Changing the address recalculates the current assignment and overlap information. Follow the programming instructions on **Review and Configure** before tapping **Configure**. Use **Back** to revise a choice or **Cancel** to leave.

<img src="screens/lcs.png" width="280" alt="LCS module type selection"> <img src="screens/lcs-modules.png" width="280" alt="My LCS Modules inventory">

<img src="screens/lcs-device.png" width="225" alt="LCS device address and mode"> <img src="screens/lcs-options.png" width="225" alt="LCS configuration options"> <img src="screens/lcs-review.png" width="225" alt="LCS Review and Configure">

## Steam Deck

A Steam Deck installation opens a single 1280 × 800 Qt window with two independent cab panes. Each pane uses the same rosters, controls, Info pages, and tools described above. The focused pane has a cyan border, starts on the right, and changes when a pane is touched or a profile focus binding is used. Keyboard shortcuts apply to the focused pane.

The Qt adapter uses the existing Steam Deck controller profile and input provider/router. Left/right stick targets, focused controls, repeating actions, catalog navigation, and profile help are supported. Changing focus, scope, or selection, disconnecting, or exiting releases held/repeating actions. Admin chords retain the normal hold guard. Deep choosers, Route Builder, and LCS wizard navigation currently use the touchscreen; these editors block engine commands.

The primary Deck deployment is Flatpak. That external package must include the Qt extra/platform plugins, preserve controller/device access, and set `PYTRAIN_PLATFORM=steamdeck` or launch with `--deck`. This checkout does not contain its Flatpak manifest, so these captures and Python tests do not verify the installed Flatpak. Physical controller, Gamescope, font, and touch behavior still need a Deck test. The legacy frontend remains available with `--legacy` or `PYTRAIN_LEGACY_GUI=1`.
