#
#
# PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
# Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
# SPDX-License-Identifier: LPGL
import importlib.metadata
from importlib.metadata import PackageNotFoundError

from .gpio.gpio_handler import (
    GpioHandler,  # noqa: F401
    PotHandler,  # noqa: F401
    JoyStickHandler,  # noqa: F401
)


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
        version = importlib.metadata.version("my-package")
    except PackageNotFoundError:
        pass

    # now try the other way
    if version is None:
        from ._version import __version__

        version = __version__

    version = version if version.startswith("v") else f"v{version}"
    return version
