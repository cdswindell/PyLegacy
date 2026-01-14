#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from __future__ import annotations

from threading import Event, RLock, get_ident
from typing import Dict, Type, TypeVar

T = TypeVar("T")


# noinspection PyTypeChecker
class _SingletonMeta(type):
    _lock = RLock()
    _instances: Dict[type, object] = {}
    _init_done: Dict[type, Event] = {}
    _init_owner: Dict[type, int] = {}

    def instance(cls, *args, **kwargs):
        me = get_ident()

        with _SingletonMeta._lock:
            inst = _SingletonMeta._instances.get(cls)
            if inst is not None:
                done = _SingletonMeta._init_done[cls]
                owner = _SingletonMeta._init_owner.get(cls)
                # If we're re-entering from the initializing thread, return immediately.
                if not done.is_set() and owner == me:
                    return inst
                # Otherwise, wait (outside the lock) for init to complete.
                if not done.is_set():
                    pass
                else:
                    return inst
            else:
                # First time: allocate and PUBLISH instance BEFORE calling __init__
                inst = object.__new__(cls)
                _SingletonMeta._instances[cls] = inst

                done = Event()
                done.clear()
                _SingletonMeta._init_done[cls] = done
                _SingletonMeta._init_owner[cls] = me

                # Per your unit-test expectation
                if not hasattr(inst, "_initialized"):
                    setattr(inst, "_initialized", False)

        # If we got here and init isn't done, either we need to init or we need to wait.
        done = _SingletonMeta._init_done[cls]
        owner = _SingletonMeta._init_owner.get(cls)

        if owner != me:
            done.wait()
            return _SingletonMeta._instances[cls]

        try:
            cls.__init__(inst, *args, **kwargs)  # run exactly once
        finally:
            with _SingletonMeta._lock:
                _SingletonMeta._init_owner.pop(cls, None)
                done.set()

        return inst

    def reset(cls):
        with _SingletonMeta._lock:
            _SingletonMeta._instances.pop(cls, None)
            _SingletonMeta._init_done.pop(cls, None)
            _SingletonMeta._init_owner.pop(cls, None)

    def __call__(cls, *args, **kwargs):
        # Foo(...) behaves like Foo.instance(...)
        return cls.instance(*args, **kwargs)


def singleton(cls: Type[T]) -> Type[T]:
    namespace = dict(cls.__dict__)
    namespace.pop("__dict__", None)
    namespace.pop("__weakref__", None)
    return _SingletonMeta(cls.__name__, cls.__bases__, namespace)  # type: ignore[return-value]
