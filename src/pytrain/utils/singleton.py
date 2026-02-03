#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from __future__ import annotations

from threading import RLock
from typing import Type, TypeVar, cast

T = TypeVar("T")


class _SingletonMeta(type):
    _lock = RLock()
    _instances: dict[type, object] = {}
    _initializing: set[type] = set()

    def __call__(cls, *args, **kwargs):
        """
        Calling Foo(...) returns the singleton instance.

        This implementation is safe against re-entrant construction: it stores
        the allocated instance BEFORE calling __init__.
        """
        with _SingletonMeta._lock:
            inst = _SingletonMeta._instances.get(cls)
            if inst is not None:
                return inst

            if cls in _SingletonMeta._initializing:
                # Re-entrant access during __init__. Return the partially
                # constructed instance if it was stored; otherwise fail loudly.
                inst2 = _SingletonMeta._instances.get(cls)
                if inst2 is not None:
                    return inst2
                raise RuntimeError(f"Re-entrant singleton construction for {cls.__name__}")

            _SingletonMeta._initializing.add(cls)

            try:
                # Allocate without running __init__
                inst = cls.__new__(cls, *args, **kwargs)  # type: ignore[misc]

                # Store immediately to break recursion
                _SingletonMeta._instances[cls] = inst

                # Mark initialization flags expected by your tests (optional)
                if not hasattr(inst, "_initialized"):
                    setattr(inst, "_initialized", False)
                setattr(inst, "_singleton_init_done", True)

                # Now run __init__ exactly once
                cls.__init__(inst, *args, **kwargs)  # type: ignore[misc]

                return inst
            finally:
                _SingletonMeta._initializing.discard(cls)

    def instance(cls, *args, **kwargs):
        """
        Explicit accessor. Equivalent to calling cls(...).
        """
        return cls(*args, **kwargs)

    def reset(cls):
        with _SingletonMeta._lock:
            _SingletonMeta._instances.pop(cls, None)
            _SingletonMeta._initializing.discard(cls)


def singleton(cls: Type[T]) -> Type[T]:
    """
    Decorator: returns a new class with the same body but using _SingletonMeta.
    """
    namespace = dict(cls.__dict__)
    namespace.pop("__dict__", None)
    namespace.pop("__weakref__", None)

    new_cls = _SingletonMeta(cls.__name__, cls.__bases__, namespace)
    return cast(Type[T], new_cls)
