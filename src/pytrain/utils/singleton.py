#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from __future__ import annotations

from threading import Event, RLock
from typing import Type, TypeVar, cast

T = TypeVar("T")


class _SingletonMeta(type):
    _lock = RLock()
    _instances: dict[type, object] = {}
    _init_done: dict[type, Event] = {}

    def __call__(cls, *args, **kwargs):
        """
        Calling Foo(...) returns the singleton instance.

        Thread-safe and deadlock-resistant:
          - Only holds the global lock for instance bookkeeping.
          - Runs __init__ outside the lock.
          - Other threads wait until initialization completes.
        """
        need_init = False

        with _SingletonMeta._lock:
            inst = _SingletonMeta._instances.get(cls)
            if inst is None:
                # Allocate without calling __init__
                inst = cls.__new__(cls, *args, **kwargs)  # type: ignore[misc]
                _SingletonMeta._instances[cls] = inst

                ev = Event()
                _SingletonMeta._init_done[cls] = ev
                need_init = True
            else:
                ev = _SingletonMeta._init_done.get(cls)

        # Initialize outside the lock
        if need_init:
            try:
                if not hasattr(inst, "_initialized"):
                    setattr(inst, "_initialized", False)
                setattr(inst, "_singleton_init_done", True)
                cls.__init__(inst, *args, **kwargs)  # type: ignore[misc]
            finally:
                # Always release waiters, even if __init__ throws
                _SingletonMeta._init_done[cls].set()
            return inst

        # If instance exists but __init__ is still running in another thread, wait.
        if ev is not None and not ev.is_set():
            ev.wait()

        return inst

    def instance(cls, *args, **kwargs):
        """Explicit accessor. Equivalent to calling cls(...)."""
        return cls(*args, **kwargs)

    def reset(cls):
        with _SingletonMeta._lock:
            _SingletonMeta._instances.pop(cls, None)
            _SingletonMeta._init_done.pop(cls, None)


def singleton(cls: Type[T]) -> Type[T]:
    """
    Decorator: returns a new class with the same body but using _SingletonMeta.
    """
    namespace = dict(cls.__dict__)
    namespace.pop("__dict__", None)
    namespace.pop("__weakref__", None)
    new_cls = _SingletonMeta(cls.__name__, cls.__bases__, namespace)
    return cast(Type[T], new_cls)
