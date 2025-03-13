#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
import platform
import subprocess

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
