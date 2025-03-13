#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
import platform

from .singleton import singleton


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

    def __repr__(self) -> str:
        return f"{self._system} {self._release} {self._machine} {self._node}"

    @property
    def is_linux(self) -> bool:
        return self._system == "Linux"

    @property
    def is_windows(self) -> bool:
        return self._system == "Windows"

    def is_macosx(self) -> bool:
        return self._system == "Darwin"

    def is_pi(self) -> bool:
        return False
