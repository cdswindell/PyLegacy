#
#
# PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
# Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
# SPDX-License-Identifier: LPGL

import importlib.metadata
import platform
import sys
from importlib.metadata import PackageNotFoundError

from .atc.block import Block  # noqa: F401
from .cli.pytrain import (
    PyTrain,
    PyTrainExitException,  # noqa: F401
    PyTrainExitStatus,  # noqa: F401
)
from .db.accessory_state import AccessoryState  # noqa: F401
from .db.component_state import (
    ComponentState,  # noqa: F401
    RouteState,  # noqa: F401
    SwitchState,  # noqa: F401
)
from .db.component_state_store import ComponentStateStore  # noqa: F401
from .db.engine_state import EngineState, TrainState  # noqa: F401
from .db.irda_state import IrdaState  # noqa: F401
from .db.sync_state import SyncState  # noqa: F401
from .gpio.base_watcher import BaseWatcher  # noqa: F401
from .gpio.controller import Controller  # noqa: F401
from .gpio.crane_car import CraneCar  # noqa: F401
from .gpio.culvert_loader import CulvertLoader, CulvertUnloader  # noqa: F401
from .gpio.engine_controller import EngineController  # noqa: F401
from .gpio.engine_status import EngineStatus  # noqa: F401
from .gpio.gantry_crane import GantryCrane  # noqa: F401
from .gpio.gpio_handler import (
    GpioHandler,  # noqa: F401
    JoyStickHandler,  # noqa: F401
    PotHandler,  # noqa: F401
)
from .gpio.launch_pad import LaunchPad  # noqa: F401
from .gpio.launch_status import LaunchStatus  # noqa: F401
from .gpio.power_district import PowerDistrict  # noqa: F401
from .gpio.power_watcher import PowerWatcher  # noqa: F401
from .gpio.route import Route  # noqa: F401
from .gpio.smoke_fluid_loader import SmokeFluidLoader  # noqa: F401
from .gpio.switch import Switch  # noqa: F401
from .gpio.sys_admin import SystemAdmin  # noqa: F401
from .gui.component_state_guis import (
    AccessoriesGui,  # noqa: F401
    PowerDistrictsGui,  # noqa: F401
    RoutesGui,  # noqa: F401
    SwitchesGui,  # noqa: F401
)
from .gui.launch_gui import LaunchGui  # noqa: F401
from .protocol.command_def import CommandDefEnum  # noqa: F401
from .protocol.command_req import CommandReq  # noqa: F401
from .protocol.constants import (
    PROGRAM_NAME,
    CommandScope,  # noqa: F401
    CommandSyntax,  # noqa: F401
    ControlType,  # noqa: F401
)
from .protocol.multibyte.multibyte_constants import (
    TMCC2EffectsControl,  # noqa: F401
    TMCC2LightingControl,  # noqa: F401
    TMCC2MaskingControl,  # noqa: F401
    TMCC2R4LCEnum,  # noqa: F401
    TMCC2RailSoundsDialogControl,  # noqa: F401
    TMCC2RailSoundsEffectsControl,  # noqa: F401
    TMCC2VariableEnum,  # noqa: F401
    UnitAssignment,  # noqa: F401
)
from .protocol.sequence.sequence_constants import (
    SequenceCommandEnum,  # noqa: F401
)
from .protocol.sequence.sequence_req import (
    SequencedReq,  # noqa: F401
    SequenceReq,  # noqa: F401
)
from .protocol.tmcc1.tmcc1_constants import (
    TMCC1AuxCommandEnum,  # noqa: F401
    TMCC1EngineCommandEnum,  # noqa: F401
    TMCC1HaltCommandEnum,  # noqa: F401
    TMCC1RouteCommandEnum,  # noqa: F401
    TMCC1RRSpeedsEnum,  # noqa: F401
    TMCC1SwitchCommandEnum,  # noqa: F401
)
from .protocol.tmcc2.tmcc2_constants import (
    TMCC2EngineCommandEnum,  # noqa: F401
    TMCC2HaltCommandEnum,  # noqa: F401
    TMCC2RouteCommandEnum,  # noqa: F401
    TMCC2RRSpeedsEnum,  # noqa: F401
)
from .utils.path_utils import (
    find_dir,  # noqa: F401
    find_file,  # noqa: F401
)

PROGRAM_PACKAGE = "pytrain-ogr"


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    try:
        PyTrain(args)
        return 0
    except Exception as e:
        # Output anything else nicely formatted on stderr and exit code 1
        sys.exit(f"{PROGRAM_NAME}: error: {e}\n")


def is_package() -> bool:
    try:
        # production version
        importlib.metadata.version(PROGRAM_PACKAGE)
        return True
    except PackageNotFoundError:
        return False


def is_linux() -> bool:
    return platform.system().lower() == "linux"


def get_version() -> str:
    #
    # this should be easier, but it is what it is.
    # we handle the two major cases; we're running from
    # the PyTrain pypi package, or we're running from
    # source retrieved from git...
    #
    # we try the package path first...
    version = None
    try:
        # production version
        version = importlib.metadata.version(PROGRAM_PACKAGE)
    except PackageNotFoundError:
        pass

    # finally, call the method to read it from git
    if version is None:
        from setuptools_scm import get_version as get_git_version

        version = get_git_version(version_scheme="only-version")

    version = version if version.startswith("v") else f"v{version}"
    version = version.replace(".post0", "")
    return version


def get_version_tuple() -> tuple[int, int, int]:
    version = get_version()
    version = version.replace("v", "")
    if "+" in version:
        plus_pos = version.find("+")
        version = version[0:plus_pos]
    version = version.split(".")
    return int(version[0]), int(version[1]), int(version[2])


def get_version_bytes() -> bytes:
    version = get_version_tuple()
    ver_bytes = bytes()
    for v in version:
        ver_bytes += v.to_bytes(1, "big")
    return ver_bytes


SMOKE_LEVEL_MAP = {
    0: TMCC2EffectsControl.SMOKE_OFF,
    1: TMCC2EffectsControl.SMOKE_LOW,
    2: TMCC2EffectsControl.SMOKE_MEDIUM,
    3: TMCC2EffectsControl.SMOKE_HIGH,
}
