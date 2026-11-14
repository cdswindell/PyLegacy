# PyTrain GPIO wiring and configuration

## MCP23017 I²C buttons

PyTrain uses MCP23017 GPIO expanders for I²C pushbuttons. Each chip
provides 16 inputs. Connect the board's SDA and SCL to the Raspberry
Pi's I²C interface and use a common ground. For the default pull-up
configuration, wire each normally open button between an expander
input and ground. Connect one of the expander's interrupt outputs
(INTA or INTB) to an available Raspberry Pi GPIO input. PyTrain
mirrors the expander's interrupts so a single line can report presses
from both banks. Use bank A (GPA0–GPA7) for buttons on this
version of PyTrain. The interrupt capture code masks out bank B when
processing button events.

### Find the Linux bus and chip address

On Raspberry Pi OS, run `sudo raspi-config` and enable I²C under
**Interface Options** if it is disabled. Follow any reboot prompt.
[Raspberry Pi configuration documentation](https://www.raspberrypi.com/documentation/computers/configuration.html#enable-or-disable-i2c)

On Raspberry Pi OS, Debian, or Ubuntu, install the `i2c-tools` package
to get `i2cdetect`:

```sh
sudo apt update
sudo apt install i2c-tools
i2cdetect -l
ls -l /dev/i2c-*
```

The number in `i2c-1` or `/dev/i2c-1` is the Linux bus number. Select
the adapter connected to the board. If Linux lists the adapter but its
device node is missing, try `sudo modprobe i2c-dev` and list the device
nodes again.

With PyTrain stopped, probe the MCP23017 address range on the candidate
bus. The following command checks bus `1`. Substitute the number shown
by `i2cdetect -l` for the adapter you want to check.

```sh
sudo i2cdetect 1 0x20 0x27
```

A cell containing `23` means a device responded at hexadecimal address
`0x23`. Match the result to your board's address jumpers or switches.
`--` means no device responded. `UU` means a kernel driver already owns
the address and the probe was skipped.
[Debian i2cdetect manual](https://manpages.debian.org/bookworm/i2c-tools/i2cdetect.8.en.html)

PyTrain's MCP23017 button driver opens `/dev/i2c-1` through the
`smbus2` Python dependency. The account running PyTrain needs read and
write access to that device. If you find the board on another bus, connect
it to the interface exposed as `/dev/i2c-1` to use the standard button
configuration. The button tuple has no bus-number field.

### Write `buttons.py`

For a PyTrain button argument such as `thru_pin`, use a tuple in this
order:

```python
(expander_pin, interrupt_gpio, i2c_address)
```

- `expander_pin` is an MCP23017 input numbered `0`–`15`. GPA0–GPA7
  are `0`–`7`, and GPB0–GPB7 are `8`–`15`.
- `interrupt_gpio` is the Pi's BCM GPIO number for the interrupt wire.
  Use the same number in each button tuple on that expander. Use a
  separate interrupt GPIO for each expander.
- `i2c_address` is the chip's 7-bit address, such as `0x23`. You can
  omit it if the board uses PyTrain's default address of `0x23`.

A bare integer selects a Pi GPIO button. Supply the interrupt GPIO in
the tuple to receive button press and release events.

This complete `buttons.py` controls TMCC turnout 12. Wire the through
button to GPA0, the out button to GPA1, and INTA to BCM GPIO 17
(physical pin 11). The example uses an expander at `0x23` on Linux bus 1.

```python
from pytrain import Switch, TMCC1SwitchCommandEnum

Switch(
    address=12,
    thru_pin=(0, 17, 0x23),
    out_pin=(1, 17, 0x23),
    initial_state=TMCC1SwitchCommandEnum.THRU,
)
```

Save the file and add `-buttons_file` to your usual PyTrain startup
command. With no filename argument, PyTrain reads `buttons.py` in the
current directory. You can also specify a path:

```sh
pytrain -buttons_file /path/to/buttons.py
```

## Choose a controller or status display

| Class | Physical devices | When to use it |
| --- | --- | --- |
| `EngineStatus` | Supported I²C or SPI OLED | Give an existing cab or layout panel a read-only display for one engine or train. |
| `EngineController` | Momentary buttons, optional quadrature encoder, optional ADS1115 analog controls and base-status LEDs | Build a dedicated cab for an engine or train, or let your own software select which target the controls operate. |
| `Controller` | Matrix keypad, optional I²C character LCD or OLED, and optional `EngineController` hardware | Build a cab where the operator selects an engine or train on a keypad and uses the same physical controls for different targets. |

The examples below are separate `buttons.py` configurations. Load one
using the startup option above and substitute your own pins and addresses.
The examples use Broadcom (BCM) GPIO numbers. Share ground among the Pi
and its peripherals, keep the Pi's GPIO signals at 3.3 V, and choose
unused GPIOs when combining hardware. On the Pi's 40-pin header, I²C uses
SDA on BCM 2 (physical pin 3) and SCL on BCM 3 (physical pin 5). Use
bidirectional level shifting for SDA and SCL if a 5 V LCD backpack pulls
them up to 5 V. The I²C keypad and displays use Linux bus 1. Set their
addresses so each device on the bus has a distinct address. The earlier
scan checks only `0x20`–`0x27`. To probe an OLED at `0x3C` on bus 1,
run `sudo i2cdetect 1 0x3c 0x3c` with PyTrain stopped.
[Raspberry Pi GPIO and peripheral pinout](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#gpio)

## Connect a matrix keypad

A passive 4×4 keypad has four row and four column leads. Use the keypad's
pinout or a continuity meter to identify the leads. Wire rows in order
from top to bottom and columns from left to right. The default map is:

```text
1  2  3  A
4  5  6  B
7  8  9  C
*  0  #  D
```

| Matrix lead | Direct Pi wiring in the example | PCF8574 wiring |
| --- | --- | --- |
| R1, R2, R3, R4 | BCM 5, 6, 12, 13 | P0, P1, P2, P3 |
| C1, C2, C3, C4 | BCM 16, 19, 20, 21 | P4, P5, P6, P7 |

- **Direct Pi GPIO.** Pass both `row_pins` and `column_pins` to
  `Controller.build()`. The `Keypad` class drives the rows and reads the
  columns using internal pull-downs. The passive keypad connects through
  its eight matrix leads.
- **PCF8574 I²C.** Connect the keypad to the expander as shown above and
  the expander to the Pi's SDA, SCL, and ground. Use a 3.3 V-compatible
  PCF8574 board. Leave out both pin lists and pass
  `keypad_address=0x20` (the default) or the address you found. PyTrain
  polls the keypad by default. To use interrupt-driven scanning, connect
  the PCF8574's active-low `INT` output to an unused Pi GPIO and pass
  its BCM number as `interrupt_pin`.
- **Custom key layouts.** For a custom application, import `Keypad` or
  `KeyPadI2C` from `pytrain.gpio.keypad` and pass a matching `keys` map.
  For example, a direct-wired 4×3 phone keypad uses four rows, three
  columns, and `keys=TELEPHONE_4X3_KEYS` from the same module. The cab
  examples use a 4×4 keypad for the A–D functions.

## EngineStatus

`EngineStatus` follows PyTrain's synchronized state for an engine or
train. Its four-line OLED display shows identity, speed, direction, and
other available details such as brake, momentum, and smoke. Use it for
a status-only readout. It requires an OLED and PyTrain's state store.

For an I²C OLED, connect SDA, SCL, power, and ground according to the
module's pinout. Set `address` to the OLED's I²C address and `device` to its
controller chip. This example uses a 128×64 SSD1306 at `0x3C` and watches
engine 12. Use `scope=CommandScope.TRAIN` for a train ID.

```python
from pytrain import CommandScope, EngineStatus

status = EngineStatus(
    tmcc_id=12,
    scope=CommandScope.ENGINE,
    address=0x3C,
    device="ssd1306",
)
```

For an SPI SSD1322, enable SPI in `raspi-config` and use
`address=0, device="ssd1322"`. PyTrain uses SPI0 CE0. Connect the OLED's
clock to BCM 11, data input (MOSI) to BCM 10, chip select to BCM 8,
data/command to BCM 24, and reset to BCM 25. Connect power and ground
per the display module's pinout. The SSD1322 is the default OLED
driver. A character LCD is available through `Controller`.

## EngineController

`EngineController` binds buttons and an optional rotary throttle to a
target that your script selects with `update()`. Pass the engine or
train state from PyTrain's store so it can choose TMCC or Legacy
commands. If the state has no control type, it defaults to Legacy.
Use this class when your cab has a fixed target or your application
already supplies target selection. It requires no keypad or display.

Wire normally open buttons between their assigned GPIO and ground, or
use the MCP23017 button tuples above. For a basic mechanical quadrature
encoder, wire A and B to the two Pi GPIO speed inputs and common to
ground. Optional Legacy quilling horn and train brake controls use
analog inputs on a 3.3 V ADS1115 on I²C (default `0x48`). Connect the
potentiometer wipers to the channels selected by `quilling_horn_chn`
and `train_brake_chn`, with the outer terminals at 3.3 V and ground.
Optional LEDs on `base_online_pin` and `base_offline_pin` indicate base
connectivity. Use a series resistor with each LED.

This example uses an encoder on BCM 17 and 27 and buttons on BCM 22
and 23. It selects engine 12 from the state store.

```python
from pytrain import CommandScope, EngineController
from pytrain.db.component_state_store import ComponentStateStore

cab = EngineController(
    speed_pin_1=17,
    speed_pin_2=27,
    bell_pin=22,
    horn_pin=23,
)
scope = CommandScope.ENGINE
state = ComponentStateStore.get_state(scope, 12, create=False)
cab.update(12, scope, state)
```

## Controller

`Controller.build()` combines keypad selection with an optional display
and optionally creates an `EngineController` for the physical controls.
It looks up the engine or train in PyTrain's state store and retargets
the cab controls and display after a valid selection. Use `A` for engine
scope and `B` for train scope, then enter the ID and press `#`. Use `C`
to clear entry and `*` to recall recent selections. With cab controls
configured, press `D` followed by a digit to send a numeric command to
the selected target.

Choose one display mode:

- **Character LCD.** Use an HD44780-compatible LCD with a PCF8574 I²C
  backpack. Connect SDA, SCL, power, and ground as described above.
  Set `is_lcd=True, is_oled=False`, and match `lcd_address`, `lcd_rows`,
  and `lcd_cols` to the hardware. The defaults for a character LCD
  are `0x27`, four rows, and 20 columns. It shows the selected ID and,
  when space allows, state such as speed, direction, and brake.
- **OLED.** Use `is_oled=True, is_lcd=False` and set `oled_address` and
  `oled_device` using the OLED wiring above. The default is an SPI
  SSD1322 (`oled_address=0`). In this mode `Controller` creates its own
  `EngineStatus` for the selected target.
- **No display.** Set `is_lcd=False, is_oled=False`.

This example combines the directly wired keypad above, a 20×4 LCD
backpack at `0x27`, and the same throttle encoder and buttons as the
standalone cab example.

```python
from pytrain import Controller

cab = Controller.build(
    row_pins=[5, 6, 12, 13],
    column_pins=[16, 19, 20, 21],
    is_lcd=True,
    is_oled=False,
    lcd_address=0x27,
    lcd_rows=4,
    lcd_cols=20,
    speed_pins=[17, 27],
    bell_pin=22,
    horn_pin=23,
)
```

For a PCF8574 keypad, replace the two pin lists with
`keypad_address=0x20`. The LCD keeps its own address. When configuring
cab buttons through `Controller.build()`, include `speed_pins` with
both encoder GPIOs, or configure at least one of `fwd_pin`, `rev_pin`,
or `reset_pin`. These options trigger creation of the internal
`EngineController`. Include one of them when adding a bell or horn button.
