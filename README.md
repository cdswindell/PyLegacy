# PyLegacy

[![Python package](https://github.com/cdswindell/PyLegacy/actions/workflows/python-package.yml/badge.svg)]
(https://github.com/cdswindell/PyLegacy/actions/workflows/python-package.yml)

This project contains software to operate and control trains and other equipment that utilize 
Lionel's [TMCC and Legacy serial command protocol](https://ogrforum.com/fileSendAction/fcType/0/fcOid/156701992259624343/filePointer/156701992265497355/fodoid/156701992265497351/LCS-LEGACY-Protocol-Spec-v1.21.pdf).
Most Lionel engines produced after 2000 support either TMCC or Legacy, and all engines produced after 2010 do.
Additionally, Lionel produces track switches, operating accessories, as well as electronic modules to control your
layout that support Legacy commands (see [Lionel Layout Control System: LCS](https://control.lionel.com/docs/lionel-layout-control-system-lcs/)).

PyLegacy is developed in pure Python and can be run on Windows, Macintosh (Intel and M-series) as well as 
inexpensive Raspberry Pi systems. My goal is to capture physical button presses on a Pi and trigger specific
Legacy commands in response. This will facilitate the construction of operating control panels I will place
on my layout to fire routes, turn on and off power districts, operate accessories, and run trains.

Initial development focuses on the development of command-line tools (CLI) to operate engines
and trains, throw switches, operate accessories, and fire custom routes. This will be followed by 
developing code to translate physical button presses on a Raspberry Pi to Legacy and TMCC command 
actions, allowing the development of physical control panels to operate trains.


## Contents
- [PyLegacy]()
  - [Requirements](#requirements)
    - [Macintosh](#macintosh)
    - [Raspberry Pi/Linux](#raspberry-pi)
  - [Installation and one-time setup](#installation-and-one-time-setup)
  - [Licensing](#licensing)
  - [CLI Scripts](#cli-scripts)
  - [Future Development](#future-development)

## Requirements

### Macintosh:

- Brew:

`/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`

- Python 3.11 (your version may be newer):

`brew install python@3.11`

- gh:

`brew install gh`

- git (if you plan to modify the code and issue pull requests):

`brew install git`

### Raspberry Pi

- Python 3.11, gh, and git:

```
sudo apt update
sudo apt upgrade

sudo apt install python3
sudo apt install gh
sudo apt install git
```

For the Raspberry Pi Zero W:

```
sudo apt-get install swig
```

Note that some or all of this software may already be installed on your pi

## Installation and one time setup

```zsh
cd /where/you/like/your/source

#Make sure this says 3.11.x or greater; don't keep going in these directions until it does
python3 --version

# authenticate gh/git:
gh auth login

# establish a virtual Python environment
#see: https://docs.python.org/3/library/venv.html
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

## Licensing

This software and its use are governed by the GNU Lesser General Public License.

## CLI Scripts

The `src/cli` directory contains a number of Python command line scripts allowing 
you to operate engines, control switches and accessories, and fire custom routes.

## Future Development