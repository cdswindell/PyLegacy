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
from typing import Optional, Type, TypeVar

T = TypeVar("T")


def singleton(cls: Type[T]) -> Type[T]:
    _lock = RLock()
    _instance: Optional[T] = None

    class SingletonWrapper(cls):  # type: ignore[misc]
        @classmethod
        def instance(cls, *args, **kwargs) -> T:
            nonlocal _instance

            # Fast path (no lock if already initialized)
            inst = _instance
            if inst is not None and getattr(inst, "_singleton_init_done", False):
                return inst

            # Create or fetch instance under lock
            need_init = False
            with _lock:
                if _instance is None:
                    _instance = super().__new__(cls)  # type: ignore[arg-type]
                    # Per your unit test: decorator sets this and leaves it False.
                    if not hasattr(_instance, "_initialized"):
                        setattr(_instance, "_initialized", False)
                    setattr(_instance, "_singleton_init_done", False)

                inst = _instance
                if not getattr(inst, "_singleton_init_done", False):
                    # Mark that init is needed, but do not run user code under the lock
                    need_init = True

            # Run user __init__ OUTSIDE the lock (prevents deadlocks)
            if need_init:
                with _lock:
                    # Double-check in case another thread initialized in the meantime
                    if not getattr(inst, "_singleton_init_done", False):
                        super(SingletonWrapper, inst).__init__(*args, **kwargs)
                        setattr(inst, "_singleton_init_done", True)

            return inst

        @classmethod
        def reset(cls) -> None:
            nonlocal _instance
            with _lock:
                _instance = None

        def __new__(cls, *args, **kwargs):
            return cls.instance(*args, **kwargs)

        def __init__(self, *args, **kwargs):
            # Prevent Python from calling __init__ on every Foo(...)
            # Real init happens once in instance().
            return

    SingletonWrapper.__name__ = cls.__name__
    SingletonWrapper.__qualname__ = cls.__qualname__
    SingletonWrapper.__doc__ = cls.__doc__

    return SingletonWrapper
