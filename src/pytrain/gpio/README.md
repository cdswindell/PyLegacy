# MCP23017 I²C buttons in PyTrain

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

## Find the Linux bus and chip address

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

## Write `buttons.py`

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
