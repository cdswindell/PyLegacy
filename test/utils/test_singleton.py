#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

from __future__ import annotations

import threading

from src.pytrain.utils.singleton import singleton


@singleton
class Foo:
    _init_count: int = 0

    def __init__(self, value: int = 0) -> None:
        self.__class__._init_count += 1
        self.value = value


@singleton
class Bar:
    _init_count = 0

    def __init__(self, name: str = "") -> None:
        self.__class__._init_count += 1
        if hasattr(self, "_initialized") and getattr(self, "_initialized"):
            return
        self.name = name
        self._initialized = True


def test_returns_same_instance_and_init_called_once():
    # First construction sets value
    a = Foo(123)
    # Subsequent constructions return the same instance and do not re-run __init__
    b = Foo(456)

    assert a is b
    assert a._init_count == 1
    # Value should remain from the first initialization
    assert a.value == 123
    assert b.value == 123

    # _initialized should be set to False by the decorator
    assert hasattr(a, "_initialized")
    assert a._initialized is False


def test_thread_safety_singleton_single_instance():
    instances = []
    lock = threading.Lock()

    def build_instance(i: int):
        inst = Foo(i)
        with lock:
            instances.append(inst)

    threads = [threading.Thread(target=build_instance, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All threads should have received the exact same instance
    assert len(instances) == 50
    assert len({id(x) for x in instances}) == 1

    # __init__ must have been called only once in total
    assert instances[0]._init_count == 1
    # Value remains as set during the very first construction
    assert instances[0].value == 123


def test_different_singleton_classes_are_independent():
    f = Foo(1)
    b1 = Bar("first")
    b2 = Bar("second")

    # Bar should also be singleton
    assert b1 is b2
    assert b1._init_count == 1
    assert b1.name == "first"
    assert b2.name == "first"

    # Foo and Bar are different singletons
    assert f is not b1


def test_repeated_calls_do_not_change_state():
    f2 = Foo(42)
    f1 = Foo(999)
    # State stays as initially set
    assert f1 is f2
    assert f1.value == 123  # from the very first initialization in earlier test
    assert f1._init_count == 1


def test_initialized_flag_present_and_true_on_bar():
    a = Foo(123)
    assert hasattr(a, "_initialized")
    assert getattr(a, "_initialized") is False

    b = Bar("alpha")
    assert hasattr(b, "_initialized")
    assert getattr(b, "_initialized") is True
