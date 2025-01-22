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
        self.age = max_age_seconds
        self.container = dict()
        self._lock = RLock()

    def __repr__(self) -> str:
        rep = ""
        for k, v in self.container.items():
            ttl = max(self.age - time() - v, 0)
            if ttl > 0:
                rep += f"{k.hex()} TTL: {ttl}\n"
        return rep

    def __len__(self) -> int:
        return len(self.container)

    def __contains__(self, value) -> bool:
        return self.contains(value)

    def contains(self, value):
        with self._lock:
            if value not in self.container:
                return False
            if time() - self.container[value] > self.age:
                del self.container[value]
                return False
            return True

    def add(self, value):
        with self._lock:
            if self.contains(value) is False:
                self.container[value] = time()

    def clear(self):
        with self._lock:
            self.container.clear()

    def discard(self, value):
        with self._lock:
            if value in self.container:
                del self.container[value]

    def remove(self, value):
        with self._lock:
            if value not in self.container:
                raise KeyError(f"{value} not found in set")
            self.discard(value)
