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
            """
            Explicit accessor. Returns the same singleton instance.
            Creates it lazily if needed (thread-safe).
            """
            nonlocal _instance
            if _instance is None:
                with _lock:
                    if _instance is None:
                        obj = super().__new__(cls)  # type: ignore[arg-type]
                        # Per your unit test: decorator sets this and leaves it False.
                        if not hasattr(obj, "_initialized"):
                            setattr(obj, "_initialized", False)
                        setattr(obj, "_singleton_init_done", False)
                        _instance = obj

            # Ensure __init__ runs once (first call wins for args)
            if not getattr(_instance, "_singleton_init_done", False):
                with _lock:
                    if not getattr(_instance, "_singleton_init_done", False):
                        super(SingletonWrapper, _instance).__init__(*args, **kwargs)
                        setattr(_instance, "_singleton_init_done", True)

            return _instance

        @classmethod
        def reset(cls) -> None:
            """
            Reset the singleton instance (useful for unit tests).
            """
            nonlocal _instance
            with _lock:
                _instance = None

        def __new__(cls, *args, **kwargs):
            # Normal construction returns the singleton too.
            return cls.instance(*args, **kwargs)

        def __init__(self, *args, **kwargs):
            # Block Python from re-running __init__ on subsequent Foo(...)
            # (Real init is performed inside instance() exactly once.)
            return

    # Preserve identity/introspection
    SingletonWrapper.__name__ = cls.__name__
    SingletonWrapper.__qualname__ = cls.__qualname__
    SingletonWrapper.__doc__ = cls.__doc__

    return SingletonWrapper
