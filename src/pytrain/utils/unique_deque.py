#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from __future__ import annotations

from collections import deque
from threading import RLock
from typing import TypeVar, Generic, Iterable

_T = TypeVar("_T")


class UniqueDeque(deque, Generic[_T]):
    def __init__(self, iterable: Iterable[_T] = None, maxlen: int = None) -> None:
        self._lock = RLock()
        super().__init__(maxlen=maxlen)
        self._seen: set[_T] = set()
        if iterable is not None:
            self.extend(iterable)

    def clear(self):
        with self._lock:
            self._seen.clear()
            super().clear()

    def __add__(self, value: UniqueDeque[_T] | deque[_T] | list[_T] | tuple[_T], /) -> UniqueDeque[_T]:
        with self._lock:
            uq = self.copy()
            for x in value:
                uq.append(x)
            return uq

    def __iadd__(self, value: UniqueDeque[_T] | deque[_T] | list[_T] | tuple[_T], /) -> UniqueDeque[_T]:
        with self._lock:
            for x in value:
                self.append(x)
            return self

    def __delitem__(self, key, /):
        with self._lock:
            super().__delitem__(key)
            self._seen.discard(key)

    def __setitem__(self, key, value: _T, /):
        with self._lock:
            if value not in self._seen:
                self._seen.add(value)
                super().__setitem__(key, value)

    def __reduce__(self):
        raise NotImplementedError

    def __imul__(self, value, /):
        raise NotImplementedError

    def __mul__(self, value, /):
        raise NotImplementedError

    def insert(self, i, x: _T, /):
        raise NotImplementedError

    def remove(self, value: _T, /):
        with self._lock:
            super().remove(value)
            self._seen.discard(value)

    def popleft(self) -> _T:
        with self._lock:
            val = super().popleft()
            self._seen.discard(val)
            return val

    def pop(self):
        with self._lock:
            val = super().pop()
            self._seen.discard(val)
            return val

    def extendleft(self, iterable: Iterable[_T], /):
        with self._lock:
            for x in iterable:
                self.appendleft(x)

    def extend(self, iterable: Iterable[_T], /) -> None:
        with self._lock:
            for x in iterable:
                self.append(x)

    def copy(self) -> UniqueDeque[_T]:
        with self._lock:
            uq = UniqueDeque(self, self.maxlen)
            return uq

    def appendleft(self, x: _T, /) -> None:
        with self._lock:
            if x in self._seen:
                if self[0] != x:
                    super().remove(x)
                    super().appendleft(x)
            else:
                if self.maxlen is not None and len(self) == self.maxlen:
                    self.pop()
                self._seen.add(x)
                super().appendleft(x)

    def push(self, x: _T, /):
        self.appendleft(x)

    def append(self, x: _T, /) -> None:
        with self._lock:
            if x in self._seen:
                if self[-1] != x:
                    super().remove(x)
                    super().append(x)
            else:
                if self.maxlen is not None and len(self) == self.maxlen:
                    self.popleft()
                self._seen.add(x)
                super().append(x)
