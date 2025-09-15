#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from threading import RLock
from time import time


class ExpiringSet:
    def __init__(self, max_age_seconds=1.0):
        assert max_age_seconds > 0
        self._age = max_age_seconds
        self._container = dict()
        self._lock = RLock()

    def __repr__(self) -> str:
        rep = ""
        for k, v in self._container.items():
            ttl = max(self._age - time() - v, 0)
            if ttl > 0:
                rep += f"{k.hex()} TTL: {ttl}\n"
        return rep

    def __len__(self) -> int:
        with self._lock:
            t = time()
            self._container = {key: value for key, value in self._container.items() if (t - value) <= self._age}
            return len(self._container)

    def __contains__(self, value) -> bool:
        return self.contains(value)

    def contains(self, value):
        with self._lock:
            if value not in self._container:
                return False
            if time() - self._container[value] > self._age:
                del self._container[value]
                return False
            return True

    def add(self, value):
        with self._lock:
            if not self.contains(value):
                self._container[value] = time()

    def clear(self):
        with self._lock:
            self._container.clear()

    def discard(self, value):
        with self._lock:
            if value in self._container:
                del self._container[value]

    def remove(self, value):
        with self._lock:
            if value not in self._container:
                raise KeyError(f"{value} not found in set")
            self.discard(value)
