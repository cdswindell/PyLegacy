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
    PyTrainExitStatus,  # noqa: F401
    PyTrainExitException,  # noqa: F401
)
from .db.component_state import (
    AccessoryState,  # noqa: F401
    ComponentState,  # noqa: F401
    EngineState,  # noqa: F401
    IrdaState,  # noqa: F401
    RouteState,  # noqa: F401
    SwitchState,  # noqa: F401
    SyncState,  # noqa: F401
    TrainState,  # noqa: F401
)
from .db.component_state_store import ComponentStateStore  # noqa: F401
from .gpio.gpio_handler import (
    GpioHandler,  # noqa: F401
    PotHandler,  # noqa: F401
    JoyStickHandler,  # noqa: F401
)
from .protocol.command_def import CommandDefEnum  # noqa: F401
from .protocol.command_req import CommandReq  # noqa: F401
from .protocol.constants import (
    PROGRAM_NAME,
    CommandSyntax,  # noqa: F401
    CommandScope,  # noqa: F401
    ControlType,  # noqa: F401
)
from .protocol.multibyte.multibyte_constants import (
    TMCC2RailSoundsDialogControl,  # noqa: F401
    TMCC2RailSoundsEffectsControl,  # noqa: F401
    TMCC2MaskingControl,  # noqa: F401
    TMCC2EffectsControl,  # noqa: F401
    TMCC2LightingControl,  # noqa: F401
    UnitAssignment,  # noqa: F401
    TMCC2R4LCEnum,  # noqa: F401
    TMCC2VariableEnum,  # noqa: F401
)
from .protocol.sequence.sequence_constants import (
    SequenceCommandEnum,  # noqa: F401
)
from .protocol.sequence.sequence_req import (
    SequenceReq,  # noqa: F401
    SequencedReq,  # noqa: F401
)
from .protocol.tmcc1.tmcc1_constants import (
    TMCC1RRSpeedsEnum,  # noqa: F401
    TMCC1HaltCommandEnum,  # noqa: F401
    TMCC1RouteCommandEnum,  # noqa: F401
    TMCC1SwitchCommandEnum,  # noqa: F401
    TMCC1AuxCommandEnum,  # noqa: F401
    TMCC1EngineCommandEnum,  # noqa: F401
)
from .protocol.tmcc2.tmcc2_constants import (
    TMCC2RRSpeedsEnum,  # noqa: F401
    TMCC2HaltCommandEnum,  # noqa: F401
    TMCC2RouteCommandEnum,  # noqa: F401
    TMCC2EngineCommandEnum,  # noqa: F401
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
    # this should be easier, but, it is what it is.
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


SMOKE_LEVEL_MAP = {
    0: TMCC2EffectsControl.SMOKE_OFF,
    1: TMCC2EffectsControl.SMOKE_LOW,
    2: TMCC2EffectsControl.SMOKE_MEDIUM,
    3: TMCC2EffectsControl.SMOKE_HIGH,
}
