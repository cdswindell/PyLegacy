#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from __future__ import annotations

from threading import RLock
from typing import Type, TypeVar

T = TypeVar("T")


class _SingletonMeta(type):
    _lock = RLock()
    _instances: dict[type, object] = {}

    def __call__(cls, *args, **kwargs):
        # Calling Foo(...) returns the singleton instance
        return cls.instance(*args, **kwargs)

    def instance(cls, *args, **kwargs):
        # Explicit accessor
        with _SingletonMeta._lock:
            inst = _SingletonMeta._instances.get(cls)
            if inst is None:
                inst = super().__call__(*args, **kwargs)  # alloc + __init__
                # Per your unit test requirement:
                if not hasattr(inst, "_initialized"):
                    setattr(inst, "_initialized", False)
                setattr(inst, "_singleton_init_done", True)
                _SingletonMeta._instances[cls] = inst
            return inst

    def reset(cls):
        with _SingletonMeta._lock:
            _SingletonMeta._instances.pop(cls, None)


def singleton(cls: Type[T]) -> Type[T]:
    """
    Decorator: returns a new class with the same body but using _SingletonMeta.
    """
    # Recreate the class with the same name/bases/namespace, but a singleton metaclass.
    namespace = dict(cls.__dict__)
    # Clean up attributes that shouldn't be carried over verbatim
    namespace.pop("__dict__", None)
    namespace.pop("__weakref__", None)

    return _SingletonMeta(cls.__name__, cls.__bases__, namespace)  # type: ignore[return-value]
