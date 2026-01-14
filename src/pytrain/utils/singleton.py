#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from __future__ import annotations

from threading import Lock
from typing import Optional, Type, TypeVar

T = TypeVar("T")


def singleton(cls: Type[T]) -> Type[T]:
    _lock = Lock()
    _instance: Optional[T] = None

    class SingletonWrapper(cls):  # type: ignore[misc]
        @classmethod
        def instance(cls, *args, **kwargs) -> T:
            # Explicit accessor: just construct; __new__/__init__ enforce singleton behavior.
            return cls(*args, **kwargs)

        @classmethod
        def reset(cls) -> None:
            # Reset the singleton (useful for tests)
            nonlocal _instance
            with _lock:
                _instance = None

        def __new__(cls, *args, **kwargs):
            nonlocal _instance
            if _instance is None:
                with _lock:
                    if _instance is None:
                        _instance = super().__new__(cls)
                        if not hasattr(_instance, "_initialized"):
                            setattr(_instance, "_initialized", False)
                        # Internal init guard (private-ish; do not rely on externally)
                        setattr(_instance, "_singleton_init_done", False)
            return _instance

        def __init__(self, *args, **kwargs):
            # Guard to ensure original __init__ runs only once
            if getattr(self, "_singleton_init_done", False):
                return
            super().__init__(*args, **kwargs)
            setattr(self, "_singleton_init_done", True)

    # Preserve identity/introspection as much as possible
    SingletonWrapper.__name__ = cls.__name__
    SingletonWrapper.__qualname__ = cls.__qualname__
    SingletonWrapper.__doc__ = cls.__doc__

    return SingletonWrapper
