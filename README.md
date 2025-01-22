This project contains software to operate and control trains and other equipment that utilize
Lionel's [TMCC and Legacy serial command protocol](https://ogrforum.com/fileSendAction/fcType/0/fcOid/156701992259624343/filePointer/156701992265497355/fodoid/156701992265497351/LCS-LEGACY-Protocol-Spec-v1.21.pdf).
Most Lionel engines produced after 2000 support either TMCC or Legacy, and all engines produced after 2010 do.
Additionally, Lionel makes track switches, operating accessories, as well as LCS modules that control your
layout that respond to Legacy commands (see
[Lionel Layout Control System: LCS](https://control.lionel.com/docs/lionel-layout-control-system-lcs/)).

**PyTrain** is developed in pure Python and can be run on Windows, Macs (Intel and M-series) as well as
inexpensive Raspberry Pi systems. My goal is to convert physical button presses on a Pi
to the corresponding
Legacy commands in response. This will facilitate the construction of operating control panels I will place
on my layout to fire routes, turn on and off power districts, operate accessories, and run trains.

Initial development focuses on the development of command-line tools (CLI) to operate engines
and trains, throw switches, operate accessories, and fire custom routes. This will be followed by
developing code to translate physical button presses on a Raspberry Pi to Legacy and TMCC command
actions, allowing the development of physical control panels to operate trains.

<div style="font-size: 16px; ">

</div>

## Quick Start

If you are anxious to get going and take **Pytrain** for a spin, this section is for you.
If you want a more detailed overview of what **PyTrain** is, why it was written, and what
you can do with it, start with the [Audience](#audience) section below.

This section assumes you want to build a physical con

### Requirements

Minimum requirements to use **PyTrain** are:

* A Lionel Base 3 running the most current Lionel firmware
* One or more Raspberry Pi 4 or 5 Wi-Fi-equipped computers with at least 2 GB of RAM running
  Raspberry PI OS 64-bit Bookworm
* A Mac or Windows computer to set up the Raspberry Pi(s)
* All hardware connected to the same Wi-Fi network
* Python 3.10 - 3.12 installed (Python 3.11 is standard with the Bookworm release of Raspberry Pi OS)
* Internet access (to download software)

Notes:

* It is recommended to have a Lionel LCS Ser2 module connected to your **PyTrain** server, as
  the Lionel Base 3 **_does not_** broadcast all layout activity
* **PyTrain** is a command-line tool. It must be run from a Terminal window (macOS/Linux/Pi) or a Cmd
  shell (Windows). **PyTrain** does _not_ have a GUI nor run as a native app.
* **PyTrain** _may_ work with an LCS Wi-Fi module, but this configuration hasn't been tested
* The **PyTrain** CLI can be run on a Mac or Windows system. It allows complete control of _all_ TMCC or
  Legacy-equipped devices as well as allows you to monitor all TMCC and Legacy commands

### Installation

#### Create a Python Virtual Environment

**PyTrain** is a pure Python application designed to run under Python 3.10, 3.11, and 3.12.
To prevent conflicts between Python applications that use different versions of common support
libraries, most platforms (macOS and Raspberry) require new python packages to be installed into
[virtual environments](https://developer.vonage.com/en/blog/a-comprehensive-guide-on-working-with-python-virtual-environments#using-venv).
This step only needs to be done once, but it does need to happen on every system
where __PyTrain__ will be installed (macOS/Raspberry Pi/Linux example):

* Open a Terminal shell window and navigate to the folder/directory where you will install __PyTrain__
* Create the new virtual environment with the command:

```aiignore
python3 -m venv PyTrain
```

* In the same terminal window, `cd` into the directory you created above and activate the environment:

```aiignore
cd PyTrain
source ./bin/activate
```

Note: You will need to repeat these two commands any time you want to run **PyTrain**.

* Install **PyTrain**; this step only needs to be done once:

```aiignore
pip3 install pytrain-ogr
```

* Run **PyTrain** and connect to your Lionel Base 3:

```aiignore
(PyTrain) davids@CDS-Mac-Studio PyTrain  % pytrain -base 192.168.1.124
Listening for client requests on port 5110...
Listening for Lionel Base broadcasts on 192.168.1.124:50001...
Sending commands directly to Lionel Base at 192.168.1.124:50001...
Registering listeners...
Loading roster from Lionel Base at 192.168.1.124 ...Done
PyTrain, v0.9.40
PyTrain Service registered successfully!
>> 
```

### Raspberry Pi Configuration

Out of the box, as Raspberry Pi 4/5 supports **PyTrain** and can be installed and run as
detailed above. However, the Pi and its OS were developed to be low-cost, general purpose computers
capable of sending and receiving email, running web browsers, playing games, driving printers, etc.
Disabling and removing the unneeded software means there will be more of your Pi available for **PyTrain**.

**PiConfig** is a program that automatically disables and removes software
not needed to support **PyTrain**.It also can configure the hardware interfaces appropriately. Your
Pi will boot faster and use less memory if you remove all the suggested software. If you change
your mind, deleted packages can be reinstalled at any time.
**PiConfig** is installed alongside of **PyTrain**.

To run PiConfig:

* Open a Terminal shell window and navigate to the folder/directory where you installed **PyTrain**
* Activate the virtual environment:

```aiignore
source ./bin/activate
```

* Run **PiConfig** and display the `help` options:

```aiignore
(PyTrain) davids@PiZ2w:~/dev/PyTrain $ piconfig -h
usage: piconfig [-h] [-quiet] [-all] [-check] [-configuration] [-expand_file_system] [-packages] [-services] [-version]

options:
  -h, --help           show this help message and exit
  -quiet               Operate quietly and don't provide feedback
  -all                 Perform all optimizations
  -check               Check Raspberry Pi configuration (no changes made; default option)
  -configuration       Enable/disable Raspberry Pi configuration options
  -expand_file_system  Expand file system and reboot
  -packages            Only remove unneeded packages
  -services            Only disable unneeded services
  -version             Show version and exit
(PyTrain) davids@PiZ2w:~/dev/PyTrain $ 
```

* Use the `-check` option (or run the program with no switches) what changes should be made
  to your system:

```aiignore
piconfig -check
```

* Use the `-all` option to modify your Pi's configuration and remove unnecessary software (this may
  take some time to complete). Note that removal of the squeekboard keyboard may generate errors; these
  are of no concern:

```aiignore
piconfig -all
```

* Reboot your system to apply configuration changes:

```aiignore
sudo reboot
```

### Running **PyTrain**

**PyTrain** is the heart of the system. In addition to allowing you to control layout from
it's command-line interface, **PyTrain**:

* allows you to map physical button presses to Lionel TMCC commands, allowing you to build
  simple to sophisticated control panels to run your layout
* monitors the state of every TMCC/Legacy-equipped component, including engines, switches, and accessories
* communicates and controls your LCS components, including the ASC2, BPC2, STM2, and all Sensor Tracks
* communicates with the LCS SER2, if available, allowing complete visibility of all TMCC command traffic
* communicates with your Base 3 and downloads your entire/train roster, allowing you to see the current
  speed, labor, momentum, and train brake settings, along with road name and number
* the same for switches (turnouts) and TMCC/Legacy/LCS accessories
* operate as a server to other **PyTrain** clients running on other Raspberry Pis (or on your desktop)
  relaying real-time state and forwarding command actions from your control panels
* can echo all TMCC and PDI command traffic
* logs all activity
* and much more!

#### Command-line Options

**PyTrain** has several startup switches that control what it does:

```aiignore
usage: pytrain  [-h] [-base [BASE ...] | -client | -server SERVER] 
                [-ser2] [-baudrate {9600,19200,38400,57600,115200}] [-port PORT] 
                [-echo] [-headless] [-no_wait] [-ser2]
                [-server_port SERVER_PORT] [-startup_script STARTUP_SCRIPT] [-version]

Send TMCC and Legacy-formatted commands to a Lionel Base 3 and/or LCS Ser2

options:
  -h, --help            show this help message and exit
  -base [BASE ...]      Connect to Lionel Base 2/3 or LCS Wi-Fi at IP address (Server mode)
  -client               Connect to an available PyTrain server (Client mode)
  -server SERVER        Connect to PyTrain server at IP address (Client mode)
  -ser2                 Send or receive TMCC commands from an LCS Ser2
  -baudrate {9600,19200,38400,57600,115200}
                        Baud Rate used to communicate with LCS Ser2 (9600)
  -port PORT            Serial port for LCS Ser2 connection (/dev/ttyUSB0)
  -echo                 Echo received TMCC/PDI commands to console
  -headless             Do not prompt for user input (run in background),
  -no_wait              Do not wait for roster download
  -server_port SERVER_PORT
                        Port to use for remote connections, if client (default: 5110)
  -startup_script STARTUP_SCRIPT
                        Run the commands in the specified file at start up (default: buttons.py)
  -version              Show version and exit
```

For example, to connect to a Lionel Base 3, you specify the Base 3's IP address on your local
network:

```aiignore
pytrain -base 192.168.1.124
```

If you also have an LCS Ser2 connected to a USB port on your Pi:

```aiignore
pytrain -base 192.168.1.124 -ser2
```

In this configuration, **PyTrain** will send all commands directly to the Base 3, but will monitor
the Ser2 for all TMCC command activity. This is important because currently, with Base 3 firmware
v1.32, the Base 3 broadcasts a limited subset of the TMCC command activity, whereas all activity is
reflected out of the LCS Ser2.

#### Miscellaneous

* To see a list of all **PyTrain** commands:

```aiignore
>> ?
usage:  [h]
        accessory | db | decode | dialogs | echo | effects | engine | train | halt | lighting |
        pdi | quit | reboot | restart | route | shutdown | sounds | switch | update | upgrade | 
        uptime | version

Valid commands:

options:
  h, help    show this help message and exit
  accessory  Issue accessory commands
  db         Query engine/train/switch/accessory state
  decode     Decode TMCC command bytes
  dialogs    Trigger RailSounds dialogs
  echo       Enable/disable TMCC command echoing
  effects    Issue engine/train effects commands
  engine     Issue engine commands
  train      Issue train commands
  halt       Emergency stop
  lighting   Issue engine/train lighting effects commands
  pdi        Sent PDI commands
  quit       Quit PyTrain
  reboot     Quit PyTrain and reboot all nodes,
  restart    Quit PyTrain and restart on all nodes,
  route      Fire defined routes
  shutdown   Quit PyTrain and shutdown all nodes
  sounds     Issue engine/train RailSound effects commands
  switch     Throw switches
  update     Quit PyTrain and update all nodes to latest release,
  upgrade    Quit PyTrain, upgrade the OS on all nodes, and update to latest release,
  uptime     Elapsed time this instance of PyTrain has been active,
  version    Show current PyTrain version,

Commands can be abbreviated, so long as they are unique; e.g., 'en', or 'eng' are the same as typing 
'engine'. Help on a specific command is also available by typing the command name (or abbreviation), 
followed by '-h', e.g., 'sw -h'
```

* To echo TMCC/Lionel commands:

```aiignore
>> echo
TMCC command echoing ENABLED..
PDI command echoing ENABLED
>> en 67 -b
>> 17:16:09.202 [ENGINE 67 BLOW_HORN_ONE (0xf8871c)]
```

* To upgrade to new releases of **PyTrain**:
    * from a Terminal window:

```aiignore
pip install -U pytrain-ogr
```

* From within **PyTrain** itself:

```aiignore
>> update
```

## Audience

The PyLegacy project is intended for:

* Model railroad enthusiasts wanting to add
  physical control panels to run their layout, including:
    * operating accessories
    * switches (turnouts)
    * power districts
    * routes
    * layout segments (e.g., yards, stations)
    * engines, trains, and operating cars equipped with TMCC or Legacy technology
    * control and recieve information from Lionel LCS Sensor Tracks
    * LCS devices, including the ASC2, STM2, and BPC2
* Developers interested in:
    * automated train control
    * adding elements of randomness into their layouts (lights on & off, sounding horn or bell effects, etc.)
    * building sequence commands that start up, ramp an engine to speed, then stop and shut down an engine
    * integration with smart speakers and intelligent assistants (e.g., Alexa, Ok Google)
    * console control of a layout via [ssh](https://www.raspberrypi.com/documentation/computers/remote-access.html#ssh)
    * integrating model railroading and computer science
    * learning the Lionel TMCC/Legacy command protocol
    * continuing to develop software post retirement :smirk:

### Model Railroad Enthusiasts

For the first audience, model railroad enthusiasts, PyLegacy allows you to build
full functionality control panels that use physical switches, dials, and keypads to control
your layout and get real-time feedback on LEDs and multi-line LCD screens. The software,
called **_PyTrain_**, runs on small, low-cost [Raspberry Pis](https://www.raspberrypi.com). These are
inexpensive (< $100) single-board computers
that have connections (_pins_) to which you can attach physical controls (toggle switches, push buttons,
keypads, speed-control dials and levers, etc.), as well as LEDs, LCD screens, and other output devices.
An entire world of inexpensive hardware is available from Amazon and other online suppliers that let the
train enthusiast who is handy with a soldering iron build control interfaces limited only by their
imagination (and budget).

Rather than running wires from each control panel to the component(s) you want to control, you connect your
buttons, switches, LEDs, etc., to a Pi that you mount within your panel. The Raspberry Pi communicates with
your layout via Wi-Fi to a Lionel Base 3 or LCS Wi-Fi module. The only wire you need to connect to your panel
is power for the Pi itself!

What if you want multiple control panels situated near the layout elements you want to control? Simple!
Use multiple Raspberry Pis, mounting one in each control panel. The Pis communicate directly to a Base
3 (or LCS Wi-Fi module), or, you designate one of your Pi's as a _**server**_. This Pi will handle all
communication to and from your layout, and all the Pis that service your other panels, the _clients_,
communicate directly with the server over Wi-Fi.

PyTrain provides many tools to fire routes and operate turnouts, accessories, and even engines
right out of the box. All you need is to specify the TMCC ID of the component you want to operate and the
[pin(s)](https://gpiozero.readthedocs.io/en/latest/recipes.html#pin-numbering) on the Pi that the
physical buttons, LEDs, etc. connect to. **PyTrain** does the rest.

Let's say you want to control Lionel Turnout 12 (TMCC ID is 12).
The turnout can be a TMCC Command Controlled model or one that is wired to an LCS ASC2.
In this example, our panel would consist of a momentary (on)-off-(on) toggle switch and 2 bi-color red/green
LEDs. The LEDs show the active path a train would take when traversing the turnout from right to left. In the
panel below, the _through_ position is set, so the _through_ LED is green, and the _out_ LED is red. If we pull
down and release the toggle switch, the turnout changes to the _out_ position, and its LED lights green,
and the _through_ path turns red. The LEDs also respond to changes to the turnout caused by other controllers (Cab 2,
Cab 3), other control panels, and other software as well as to changes caused by the auto-derail feature of
FasTrack turnouts.

<div align="center">

![switch-example.png](https://github.com/cdswindell/PyLegacy/raw/master/doc/images/switch-example.png)

#### Simple Panel

</div>

To construct this panel, we connect the toggle switch and LEDs to pins on the Raspberry Pi. Below is a
schematic of a Pi pinout, taken from the [GPIO Zero](https://gpiozero.readthedocs.io/en/latest/index.html)
project, which is used by **PyTrain**:

<div align="center">

![pin_layout.png](https://gpiozero.readthedocs.io/en/latest/_images/pin_layout.svg)

#### Raspberry Pi GPIO Pins

</div>

To control and show the state of our turnout, we connect the center terminal of the toggle switch and
the common cathode lead of our Bi-Color LEDs to a GND pin on the Pi (any will do). We next pick
the pins we will connect the other two terminals of the toggle (up for _through_ and down for _out_), and
the 4 leads of the 2 LEDs. We can use any of the pins colored green above, as well as GPIO pins 7, 8, 9, 10, 11,
14, and 15. Pins GPIO 2 and GPIO 3 are reserved to communicate with expander boards that provide
additional GPIO pins, as are pins ID SD and ID SC.

Let's say we make the following connections:

| Pin | Component     | Function   |
|:---:|---------------|------------|
|  7  | Toggle  (Up)  | Through    |
|  8  | Toggle (Down) | Out        |
|  9  | Thru LED      | Green Lead |
| 10  | Thru LED      | Red Lead   |
| 10  | Out LED       | Green Lead |
|  9  | Out LED       | Red Lead   |

Here's the Python code to control the turnout:

```
from pytrain import GpioHandler

GpioHandler.switch(
    address = 12,     # TMCC ID of the turnout to control
    thru_pin = 7,      
    out_pin = 8,       
    thru_led_pin = 9,
    out_led_pin = 10
)
```

Note that the pins driving the 2 LEDs, 9 & 10 are connected to _both_ LEDs.
Because the LEDs in our example are bi-color, when power is applied to pin 9,
it simultaneously lights the green element in the _through_ LED and the red
element in the _out_ LED.

When we pull _down_ on the toggle switch, pin 8 is connected to GND. The **PyTrain**
sends the TMCC command to your Base 3 or LCS Wi-Fi to set the turnout to the _out_ position. It
also turns off the power to pin 9 and turns on the power to pin 10, causing the red element in
the "through" led to illuminate, and the green element in the _out_ led to illuminate. The **PyTrain**
software supports _**all**_ TMCC and Legacy commands, including almost all the
functionality available on the Cab 2 and Cab 3 controllers, including control of engine smoke, lights,
engine sounds, speed, momentum, volume, dialog, whistle and bell sounds, and much more.
It can also fire routes, control momentary and on/off accessories, rotate gantry cranes, etc.

Below is another control panel designed to operate a Lionel Command Control Gantry and the track and turnout
leading to it. This panel uses a 2-axis joystick
to move the gantry back and forth on the special GarGraves 5-rail track, as well as to lift the magnet
up and down. A Rotary Encoder is used to rotate the crane cab. The encoder I use has a push button
built in that turns the magnet on and off. A yellow LED is lit and blinks when the magnet is energized.
The panel also allows control of the two track power blocks in this part of my layout, as well
as the turnout to the two track segments.

<div align="center">

![gantry.jpg](https://github.com/cdswindell/PyLegacy/raw/master/doc/images/gantry.jpg)

#### Lionel Legacy Gantry Crane and Yard

</div>

Here's the corresponding Python code:

```
from pytrain import GpioHandler

GpioHandler.gantry_crane(
    address=96,   # TMCC ID of Gantry Crane
    cab_pin_1=20, # Cab rotation controlled by a 
    cab_pin_2=21, # Rotary Encoder connected to pins 20 & 21
    lift_chn=0,   # Boom controlled by 1 axis of Joystick
    roll_chn=1,   # Lateral motion controlled by the other
    mag_pin=16,   # Turns magnet on when pressed
    led_pin=24,   # Blinks when magnet is energized
) 

GpioHandler.switch(
    address=1,  # TMCC ID of the yard turnout
    thru_pin=7,      
    out_pin=8,       
    thru_led_pin=9,
    out_led_pin=10
)

GpioHandler.power_district(
    address=5,  # TMCC ID of North Yard Power District
    on_pin=11,  # Track Power On
    off_pin=12, # Track Power Off
    on_led=26,  # Track power on when lit
)

GpioHandler.power_district(
    address=6,  # TMCC ID of South Yard Power District
    on_pin=13,  # Track Power On
    off_pin=14, # Track Power Off
    on_led=27,  # Track power on when lit
)
```

### Developers

For developers...

## Command-line Tools

PyLegacy includes several command-line tools you
The `cli` directory contains a number of Python command line scripts allowing
you to operate engines, control switches and accessories, and fire custom routes.

### PyTrain

### PiConfig

## Contributing

## Development

### Requirements

#### Macintosh:

- Brew:

`/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`

- Python 3.12.6 (your version may be newer; Note: Python 3.13 is _**not**_ supported:

`brew install python@3.12`

- gh:

`brew install gh`

- git (if you plan to modify the code and issue pull requests):

`brew install git`

#### Raspberry Pi and Pi Zero W 2

- Python 3.11, gh, and git:

```
sudo apt update
sudo apt upgrade

sudo apt install python3
sudo apt install gh
sudo apt install git
```

For the Raspberry Pi Zero W (**NOT** the 2 W):

```
sudo apt-get install swig
```

**Note**: some or all of this software may already be installed on your pi

### Installation and one time setup

```
cd /where/you/like/your/source

# Make sure this says 3.11. or greater; don't keep going in these directions until it does
python3 --version

# authenticate gh/git:
gh auth login

# establish a virtual Python environment
# see: https://docs.python.org/3/library/venv.html
python3 -m venv PyLegacyEnv
cd PyLegacyEnv
gh repo clone cdswindell/PyLegacy
cd PyLegacy

# Activate virtual environment
source ../bin/activate; export PYTHONPATH=.

# Install 3rd-party dependencies
pip3 install -r requirements.txt

```

You will need to activate this local python environment every time you open a
new shell, after changing your working directory to the `PyLegacy` local directory by typing:

```
source ../bin/activate
export PYTHONPATH=.
```

You may wish to create a macro or alias to issue these commands for you.

## Future Enhancements

## License

This software and its use are governed by the GNU Lesser General Public License (LPGL).