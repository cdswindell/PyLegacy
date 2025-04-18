#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from abc import ABC, ABCMeta, abstractmethod
from threading import Condition, Lock, RLock

from ..protocol.constants import CommandScope


class Watchable(ABC):
    __metaclass__ = ABCMeta

    _lock: Lock = RLock()
    _cv: Condition = Condition(_lock)

    @property
    def synchronizer(self) -> Condition:
        return self._cv

    @property
    def lock(self) -> Lock:
        return self._lock

    @property
    @abstractmethod
    def address(self) -> int: ...

    @property
    @abstractmethod
    def scope(self) -> CommandScope: ...
