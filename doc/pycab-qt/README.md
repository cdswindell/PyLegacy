# PyCab Qt User Manual

PyCab is the touchscreen cab for operating a Lionel layout through PyTrain. This guide covers the Engine, Train, Switch, Accessory, and Route views and their shared tools. The images are simulated captures of the current Qt interface at **720 × 1280**, the layout for the 5-inch Raspberry Pi display. They use sample records and may differ from the Pi in font rendering and touch behavior.

<img src="screens/engine-controls.png" width="360" alt="Diesel Engine Controls and throttle on the 5-inch Pi layout">

## Table of Contents

1. [Start PyCab](#start-pycab)
2. [Navigate the Cab](#navigate-the-cab)
3. [Engine Roster and Keypads](#engine-roster-and-keypads)
4. [Engine Controls](#engine-controls)
5. [Button Decorators](#button-decorators)
6. [Speed and Volume](#speed-and-volume)
7. [State Tiles and Engine Information](#state-tiles-and-engine-information)
8. [Sound, Dialogs, and Lights](#sound-dialogs-and-lights)
9. [Train Operations](#train-operations)
10. [Accessory Operations](#accessory-operations)
11. [Switch Operations](#switch-operations)
12. [Route Operations and Route Builder](#route-operations-and-route-builder)
13. [Manage PyTrain](#manage-pytrain)
14. [LCS Device Manager](#lcs-device-manager)

## Start PyCab

From your PyLegacy checkout, activate your Python environment and install the Qt extra. Launch in client mode if PyTrain is already running on another machine.

```sh
python -m pip install -e '.[qt-gui]'
pycab --qt -client
```

PyCab starts fullscreen on a detected Raspberry Pi or Steam Deck. Use **Manage PyTrain → Quit** to exit from the touchscreen. The desktop app also supports the normal window close action.

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

```sh
pycab --qt -client -server 192.168.1.20 -echo
pycab --qt -base
pycab --qt -base 192.168.1.30
pycab --qt -h
```

If the shell reports that `pycab` was not found, activate the same environment you used to install the Qt extra.

## Navigate the Cab

- Tap a scope button along the bottom to switch rosters or return to the last selected engine. Tap **Engine** again while operating an engine to return to its roster.
- Hold a scope button to open its roster with the TMCC ID keypad ready.
- Tap the title chevron for **Roster**, **Manage PyTrain**, **Route Builder**, and **LCS Device Manager**.
- **ALL STOP** sends the layout-wide halt command. The **Emergency** stop on the Speed/Volume tab targets the selected engine.
- **Reset** is the selected engine's reset control. Leave a dialog with **Close**, **Cancel**, or **Back**, as shown on that screen.
- On a Mac, the device preview controls let you inspect the layout at a target size. A displayed percentage below 100% means the preview is scaled to fit.

<img src="screens/navigation.png" width="300" alt="Title menu with Roster, Manage PyTrain, Route Builder, and LCS Device Manager">

## Engine Roster and Keypads

Search by name, road number, TMCC ID, or engine type. Use **Name**, **Road #**, or **TMCC ID** to sort, and swipe the type filters horizontally for more choices. Swipe the roster vertically to see more rows. Each row shows the address, name, road number, engine type, and control type where available.

Tap a row to open its cab. Enter a numeric TMCC ID with the keypad or the search field and use **Set** to go directly to it. If the engine is missing, PyCab opens Engine Information for that ID. The engine keypad accepts up to four digits. **Set Address** is a programming command, separate from selecting a roster entry.

On the Pi, tap the search field to open the on-screen keyboard. Use the backspace key to delete a character and hold it to clear the field. **Close** on a keypad leaves without submitting.

<img src="screens/engine-roster.png" width="280" alt="Engine roster with search, sorting, and type filters"> <img src="screens/engine-keypad.png" width="280" alt="Engine TMCC ID keypad and Set Address"> <img src="screens/search-keyboard.png" width="280" alt="On-screen search keyboard">

## Engine Controls

The cab shows the selected engine's name, road number, and TMCC ID above the locomotive image. **Current Speed** shows reported speed. The throttle thumb shows the target. Drag or tap the throttle track to set a target, or use **+** and **−** for individual speed steps when ramping is idle. The second slider controls the selected function, such as horn, brake, or momentum. A single supported function appears as a label. The horn slider returns to zero on release. The throttle scale uses 20-step labels for Legacy and 5-step labels for TMCC. While ramping, the trough shows the remaining span between reported speed and target.

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

<img src="screens/steam.png" width="280" alt="Steam Controls tab"> <img src="screens/electric.png" width="280" alt="Electric Controls tab">

<img src="screens/acela.png" width="280" alt="Acela Controls tab"> <img src="screens/crane.png" width="280" alt="Crane Controls tab"> <img src="screens/transformer.png" width="280" alt="Transformer Controls tab">

<img src="screens/passenger.png" width="280" alt="Passenger car Controls tab"> <img src="screens/freight.png" width="280" alt="Freight car Controls tab">

<img src="screens/tmcc.png" width="225" alt="Tmcc"> <img src="screens/diesel-switcher.png" width="225" alt="Diesel Switcher"> <img src="screens/diesel-pullmor.png" width="225" alt="Diesel Pullmor">

<img src="screens/steam-switcher.png" width="225" alt="Steam Switcher"> <img src="screens/steam-pullmor.png" width="225" alt="Steam Pullmor">

## Button Decorators

<img src="screens/button-decorators.png" width="900" alt="Enlarged button corner markers beside the original Crew, Aux 1, and Boost buttons">

| Corner Mark | What Holding Does |
| --- | --- |
| Overlapping squares | Opens a panel, such as Crew Dialogs or Lights. On Horn or Whistle, it selects that function on the secondary slider. |
| Plus sign | Runs an alternate action. Aux 1 runs a Lionel sequence, a railroad speed preset adds spoken dialog to the speed change, and an enabled gauge refills its resource. |
| Circular arrow | Repeats the command while held, as on Boost and Brake. |

The progress bar shows hold progress on buttons that wait for a hold threshold.

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

**Engine Information** shows roster fields, live status, and consist details. Tap a field to edit it. On the Pi, **Road Name** opens a touchscreen keyboard with **Save**. **Road Number** opens a numeric editor. **Engine Type**, **Control Type**, and **Sound Type** show selectable choices. Scroll the engine type list as needed. For an existing engine, confirm the field editor to write the change. For a new engine, field edits are staged until you tap **Create**. Hold **Clear** for three seconds to clear an existing record. Leaving with pending changes can prompt you to keep editing or discard them.

<img src="screens/engine-information.png" width="280" alt="Engine Information and Real Time Status"> <img src="screens/create-engine.png" width="280" alt="Create Engine for an unused address"> <img src="screens/road-name-touch.png" width="280" alt="Road Name editor with the on-screen keyboard">

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

Tap **Train** to browse the roster or return to the last train you operated. Select a train from the list or use its TMCC ID keypad. The cab includes **Controls**, **Speed/Volume**, and **Train Information**, with the fields and controls available for the selected train.

<img src="screens/train-roster.png" width="225" alt="Train Roster"> <img src="screens/train-keypad.png" width="225" alt="Train Keypad"> <img src="screens/train-controls.png" width="225" alt="Train Controls">

<img src="screens/train-speed-volume.png" width="225" alt="Train Speed Volume"> <img src="screens/train-information.png" width="225" alt="Train Information">

## Accessory Operations

Tap **Acc** for the accessory roster. Search by name, road number, or TMCC ID. Use the keypad to enter an address. Select a configured accessory to open its operating view and use the controls assigned to that accessory.

<img src="screens/accessory-roster.png" width="225" alt="Accessory Roster"> <img src="screens/accessory-keypad.png" width="225" alt="Accessory Keypad"> <img src="screens/accessory-operating.png" width="225" alt="Accessory Operating">

## Switch Operations

Search or sort the switch roster by **Name**, **Road #**, or **TMCC ID**. Enable **Show Unnamed** to include unnamed switches. Where known, LCS module information appears under the road name.

- Tap **Thru** for the straight path or **Out** for the diverging path. The highlighted button shows the reported position. Neither is highlighted when the position is unknown.
- Double-tap the body of a tile to toggle the switch. An unknown switch goes to **Thru**. Swipe to scroll.
- Tap **Edit…** to change the road name or number, then **Save**. On the Pi, tap **Road Name** for the on-screen keyboard or **Road Number** for the four-digit keypad. **Add Switch** also opens a numeric keypad for its TMCC ID. Hold **Clear** for three seconds to clear the record.
- Tap **Add…** to create a record. For a Lionel Command Control switch, follow the panel's instruction to put the device in PROGRAM mode before adding. **Set Address** also appears on the switch keypad.

<img src="screens/switch-roster.png" width="225" alt="Switch roster"> <img src="screens/switch-keypad.png" width="225" alt="Switch keypad with Set Address"> <img src="screens/switch-edit.png" width="225" alt="Edit Switch"> <img src="screens/switch-add.png" width="225" alt="Add Switch">

<img src="screens/switch-overwrite.png" width="225" alt="Switch Overwrite"> <img src="screens/switch-road-number.png" width="225" alt="Switch Road Number"> <img src="screens/switch-address-editor.png" width="225" alt="Switch Address Editor">

## Route Operations and Route Builder

The roster shows **Aligned** or **Unset** when alignment is known. A blank status means alignment is unknown. Sort by name, road number, TMCC ID, or alignment. Tap **Fire** or double-tap the body of a tile to fire the route. Swipe to scroll the roster.

1. Tap **Edit…** on a route, **Add…** on the roster, or **Route Builder** in the title menu.
2. Enter the route TMCC ID (1–98), name, and route number. Tap a field on the Pi for its keyboard or keypad.
3. Use **Add…** to pick elements. A route holds up to 16 elements.
4. Tap an element to select it. Set a turnout to **Thru** or **Out**. Double-tap an Out tile, or double-tap or hold **Out**, to flip the left/right diagram. This edits the route element. **Move Left** and **Move Right** change its position in the sequence.
5. **Remove** deletes the selected element from the draft. **Clear All** empties the draft's element list. **Save** writes the route. Holding the footer **Clear** clears the stored record. **Cancel** leaves the editor and prompts before discarding unsaved changes.

<img src="screens/route-roster.png" width="225" alt="Route roster"> <img src="screens/route-keypad.png" width="225" alt="Route TMCC ID keypad"> <img src="screens/route-builder.png" width="225" alt="Route Builder with three-rail element graphics"> <img src="screens/route-picker.png" width="225" alt="Add to Route element picker">

<img src="screens/discard-changes.png" width="225" alt="Keep Editing or Discard confirmation">

<img src="screens/route-address-editor.png" width="225" alt="Route Address Editor"> <img src="screens/route-name-editor.png" width="225" alt="Route Name Editor"> <img src="screens/route-number-editor.png" width="225" alt="Route Number Editor">

## Manage PyTrain

Open **Manage PyTrain** from the title menu. The panel shows the layout name, local IP, and PyTrain version. A client also shows the server version when available.

- Hold **Reload Database** for one second to resync the Base 3 database. **Reloading…** flashes while the sync is active.
- **Reload Accessories** and **Refresh Images** update their respective data and briefly display a status message.
- **Logging** and **Debugging** show their active state with checkboxes. Choose **Local** or **All** before a maintenance action to target this node or the layout's PyTrain nodes.
- **Restart**, **Reboot**, **Update PyTrain**, **Upgrade Pi OS**, **Quit**, and **Shutdown** require a three-second hold. The progress bar turns amber during the final half-second. Stop trains before actions that interrupt control.

<img src="screens/manage.png" width="300" alt="Manage PyTrain with database, logging, and maintenance controls">

## LCS Device Manager

Open **LCS Device Manager** from the title menu or **LCS…** in Switch Operations. **My Modules** shows modules that have reported themselves. Sort by TMCC ID, module type, or scope.

To configure a module, select its type and tap **Next**. Choose its base TMCC ID and mode, then review the assigned addresses, any overlaps, and the options for that device. Follow the programming instructions on **Review and Configure** before tapping **Configure**. Use **Back** to revise a choice or **Cancel** to leave.

<img src="screens/lcs.png" width="280" alt="LCS module type selection"> <img src="screens/lcs-modules.png" width="280" alt="My LCS Modules inventory">

<img src="screens/lcs-device.png" width="225" alt="LCS device address and mode"> <img src="screens/lcs-options.png" width="225" alt="LCS configuration options"> <img src="screens/lcs-review.png" width="225" alt="LCS Review and Configure">
