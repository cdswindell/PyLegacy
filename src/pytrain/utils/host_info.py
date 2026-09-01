#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

import os
import platform
import subprocess

from .singleton import singleton

# Environment variable the generated launcher exports to say which platform PyTrain was
# installed for (see installation/launch_pytrain.bash.template). It records an install
# *decision* rather than a hardware probe: the Steam Deck runs ordinary Linux and its
# hardware is not reliably distinguishable, and the same machine can host a plain
# install. Read it through ``HostInfo.platform`` / ``HostInfo.is_steam_deck``.
PLATFORM_ENV_VAR = "PYTRAIN_PLATFORM"
STEAM_DECK_PLATFORM = "steamdeck"


def installed_platform() -> str:
    """Platform PyTrain was installed for, lower-cased, or "" if unspecified.

    A plain function rather than a ``HostInfo`` member so a caller does not have to
    build that singleton -- which probes the hardware with ``cat`` and ``free`` -- just
    to read an environment variable. Read live, so it stays correct however early
    anything is constructed. Tolerates case and stray whitespace, the value having come
    from a shell variable.
    """
    return os.getenv(PLATFORM_ENV_VAR, "").strip().lower()


def is_steam_deck() -> bool:
    """True when this install was configured for the Steam Deck."""
    return installed_platform() == STEAM_DECK_PLATFORM


def is_linux() -> bool:
    """True on a Linux host: the Raspberry Pi and the Steam Deck, not a Mac or a PC.

    Lives here, in a leaf module, rather than only in ``pytrain/__init__``: that package
    imports every GUI before it defines anything of its own, so a module the package
    imports cannot import the package back without a circular import. A plain function
    rather than a ``HostInfo`` member for the same reason :func:`installed_platform` is --
    a caller should not have to build that singleton, which probes the hardware with
    ``cat`` and ``free``, to answer one question. ``pytrain/__init__`` re-exports it, so
    ``from pytrain import is_linux`` still works for anything outside the package.
    """
    return platform.system().lower() == "linux"


@singleton
class HostInfo:
    def __init__(self) -> None:
        if hasattr(self, "_initialized") and self._initialized:
            return
        else:
            self._initialized = True

        self._system = platform.system()
        self._release = platform.release()
        self._version = platform.version()
        self._machine = platform.machine()
        self._node = platform.node()
        self._pi_model = None
        self._total_memory = None
        self._used_memory = None
        self._free_memory = None

        # do pi-specific stuff
        result = subprocess.run("cat /proc/device-tree/model".split(), capture_output=True, text=True)
        if result.returncode == 0:
            self._pi_model = result.stdout.strip().rstrip("\x00")

        result = subprocess.run("free -m".split(), capture_output=True, text=True)
        if result.returncode == 0:
            values = result.stdout.strip().rstrip("\x00").split()
            self._total_memory = int(values[7])
            self._used_memory = int(values[8])
            self._free_memory = int(values[9])

    def __repr__(self) -> str:
        pm = f"{self.pi_model} " if self.pi_model else ""
        return f"{pm}{self._system} {self._release} {self._machine} {self._node}"

    @property
    def is_linux(self) -> bool:
        return self._system == "Linux"

    @property
    def is_windows(self) -> bool:
        return self._system == "Windows"

    @property
    def is_macosx(self) -> bool:
        return self._system == "Darwin"

    @property
    def is_pi(self) -> bool:
        return self.pi_model is not None and self.pi_model.lower().startswith("raspberry pi")

    @property
    def platform(self) -> str:
        """Platform PyTrain was installed for; see :func:`installed_platform`."""
        return installed_platform()

    @property
    def is_steam_deck(self) -> bool:
        return installed_platform() == STEAM_DECK_PLATFORM

    @property
    def pi_model(self) -> str:
        return self._pi_model

    @property
    def total_memory(self) -> int:
        return self._total_memory

    @property
    def free_memory(self) -> int:
        results = self._memory_usage()
        return results[2] if results else None

    @property
    def used_memory(self) -> int:
        results = self._memory_usage()
        return results[1] if results else None

    def _memory_usage(self) -> tuple | None:
        if self.is_pi:
            result = subprocess.run("free -m".split(), capture_output=True, text=True)
            if result.returncode == 0:
                v = result.stdout.strip().rstrip("\x00").split()
                return int(v[7]), int(v[8]), int(v[9]), int(v[10]), int(v[11]), int(v[12])
        return None
