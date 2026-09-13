#
# PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
# Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
# SPDX-License-Identifier: LPGL

import importlib
import importlib.metadata
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
from .protocol.command_def import CommandDefEnum  # noqa: F401
from .protocol.command_req import CommandReq  # noqa: F401
from .protocol.constants import (
    CommandScope,  # noqa: F401
    CommandSyntax,  # noqa: F401
    ControlType,  # noqa: F401
    PROGRAM_BASE,  # noqa: F401
    PROGRAM_NAME,
)
from .protocol.multibyte.multibyte_constants import (
    TMCC2EffectsControl,  # noqa: F401
    TMCC2LightingControl,  # noqa: F401
    TMCC2MaskingControl,  # noqa: F401
    TMCC2R4LCEnum,  # noqa: F401
    TMCC2RailSoundsDialogControl,  # noqa: F401
    TMCC2RailSoundsEffectsControl,  # noqa: F401
    TMCC2EngineCommandEnumEx,  # noqa: F401
    TMCC2VariableEnum,  # noqa: F401
    UnitAssignment,  # noqa: F401
)
from .protocol.sequence.cycle_tone_req import (
    CycleBellToneReq,  # noqa: F401
    CycleHornToneReq,  # noqa: F401
)
from .protocol.sequence.grade_crossing_req import GradeCrossingReq  # noqa: F401
from .protocol.sequence.labor_effect import (
    LaborEffectDownReq,  # noqa: F401
    LaborEffectUpReq,  # noqa: F401
)
from .protocol.sequence.ramp_speed_req import (
    RampSpeedDialogReq,  # noqa: F401
    RampSpeedReq,  # noqa: F401
)
from .protocol.sequence.ramped_speed_req import (
    RampedSpeedDialogReq,  # noqa: F401
    RampedSpeedReq,  # noqa: F401
)
from .protocol.sequence.sequence_constants import SequenceCommandEnum  # noqa: F401
from .protocol.sequence.sequence_req import SequenceReq, SequencedReq  # noqa: F401
from .protocol.sequence.set_speed_req import SetSpeedReq  # noqa: F401
from .protocol.sequence.steward_chatter_req import StewardChatterReq  # noqa: F401
from .protocol.tmcc1.tmcc1_constants import (
    TMCC1AuxCommandEnum,  # noqa: F401
    TMCC1EngineCommandEnum,  # noqa: F401
    TMCC1HaltCommandEnum,  # noqa: F401
    TMCC1RRSpeedsEnum,  # noqa: F401
    TMCC1RouteCommandEnum,  # noqa: F401
    TMCC1SwitchCommandEnum,  # noqa: F401
)
from .protocol.tmcc2.tmcc2_constants import (
    TMCC2EngineCommandEnum,  # noqa: F401
    TMCC2EngineOpsEnum,  # noqa: F401
    TMCC2HaltCommandEnum,  # noqa: F401
    TMCC2RRSpeedsEnum,  # noqa: F401
    TMCC2RouteCommandEnum,  # noqa: F401
)
from .utils.host_info import is_linux  # noqa: F401
from .utils.path_utils import find_dir, find_file  # noqa: F401

PROGRAM_PACKAGE = "pytrain-ogr"
PROGRAM_PACKAGE_DECK = "pytrain-ogr-deck"
PROGRAM_PACKAGES = (PROGRAM_PACKAGE, PROGRAM_PACKAGE_DECK)

_LEGACY_GUI_EXPORTS = {
    "AccessoryGui": ("pytrain.gui.accessories.accessory_gui", "AccessoryGui"),
    "ConstructionGui": ("pytrain.gui.accessories.construction_gui", "ConstructionGui"),
    "ControlTowerGui": ("pytrain.gui.accessories.control_tower_gui", "ControlTowerGui"),
    "CulvertGui": ("pytrain.gui.accessories.culvert_gui", "CulvertGui"),
    "FireStationGui": ("pytrain.gui.accessories.fire_station_gui", "FireStationGui"),
    "GasStationGui": ("pytrain.gui.accessories.gas_station_gui", "GasStationGui"),
    "HobbyShopGui": ("pytrain.gui.accessories.hobby_shop_gui", "HobbyShopGui"),
    "MilkLoaderGui": ("pytrain.gui.accessories.milk_loader_gui", "MilkLoaderGui"),
    "PlaygroundGui": ("pytrain.gui.accessories.playground_gui", "PlaygroundGui"),
    "SmokeFluidLoaderGui": ("pytrain.gui.accessories.smoke_fluid_loader_gui", "SmokeFluidLoaderGui"),
    "StationGui": ("pytrain.gui.accessories.station_gui", "StationGui"),
    "AccessoriesGui": ("pytrain.gui.accessories_gui", "AccessoriesGui"),
    "ComponentStateGui": ("pytrain.gui.component_state_gui", "ComponentStateGui"),
    "EngineGui": ("pytrain.gui.controller.engine_gui", "EngineGui"),
    "SteamDeckGui": ("pytrain.gui.controller.steam_deck_gui", "SteamDeckGui"),
    "LaunchGui": ("pytrain.gui.launch_gui", "LaunchGui"),
    "MotorsGui": ("pytrain.gui.motors_gui", "MotorsGui"),
    "PowerDistrictsGui": ("pytrain.gui.power_district_gui", "PowerDistrictsGui"),
    "RoutesGui": ("pytrain.gui.routes_gui", "RoutesGui"),
    "SwitchesGui": ("pytrain.gui.switches_gui", "SwitchesGui"),
    "SystemsGui": ("pytrain.gui.systems_gui", "SystemsGui"),
    "WideComponentStateGui": ("pytrain.gui.wide_component_state_gui", "WideComponentStateGui"),
}


def __getattr__(name: str):
    legacy_gui = _LEGACY_GUI_EXPORTS.get(name)
    if legacy_gui is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = legacy_gui
    value = getattr(importlib.import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    try:
        PyTrain(args)
        return 0
    except Exception as e:
        sys.exit(f"{PROGRAM_NAME}: error: {e}\n")


def installed_package() -> str | None:
    for package in PROGRAM_PACKAGES:
        try:
            importlib.metadata.version(package)
            return package
        except PackageNotFoundError:
            continue
    return None


def is_package() -> bool:
    return installed_package() is not None


def get_version() -> str:
    version = None
    package = installed_package()
    if package is not None:
        version = importlib.metadata.version(package)

    if version is None:
        from setuptools_scm import get_version as get_git_version

        version = get_git_version(root="../..", relative_to=__file__, version_scheme="only-version")

    v_parts = version.split("+", 1)
    version = v_parts[0] + ("" if len(v_parts) == 1 else "+")
    version = version if version.startswith("v") else f"v{version}"
    version = version.replace(".post0", "")
    return version


def get_version_tuple() -> tuple[int, int, int]:
    version = get_version().replace("v", "")
    if "+" in version:
        version = version[: version.find("+")]
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
