#
#
# PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
# Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
# SPDX-License-Identifier: LPGL

import importlib.metadata
import sys
from importlib.metadata import PackageNotFoundError

from .gpio.gpio_handler import (
    GpioHandler,  # noqa: F401
    PotHandler,  # noqa: F401
    JoyStickHandler,  # noqa: F401
)
from .protocol.constants import PROGRAM_NAME


def main(args: list[str] | None = None) -> int:
    if args is None:
        args = sys.argv[1:]
    try:
        from .cli.pytrain import PyTrain

        PyTrain(args)
        return 0
    except Exception as e:
        # Output anything else nicely formatted on stderr and exit code 1
        sys.exit(f"{PROGRAM_NAME}: error: {e}\n")


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
        try:
            # noinspection PyUnresolvedReferences
            from ._version import __version__

            version = __version__
        except ModuleNotFoundError:
            pass

    # finally, call the method to read it from git
    if version is None:
        from setuptools_scm import get_version as get_git_version

        version = get_git_version(version_scheme="post-release", local_scheme="no-local-version")

    version = version if version.startswith("v") else f"v{version}"
    return version
