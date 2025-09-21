#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

import threading
from typing import Any, List

import pytest

from src.pytrain.pdi import pdi_state_store as pdi_state_store_module
from src.pytrain.pdi.pdi_state_store import PdiStateStore


# noinspection PyTypeChecker
@pytest.fixture(autouse=True)
def reset_singleton():
    # Ensure a clean singleton between tests
    PdiStateStore._instance = None
    yield
    PdiStateStore._instance = None


def test_singleton_returns_same_instance():
    s1 = PdiStateStore()
    s2 = PdiStateStore()
    assert s1 is s2, "PdiStateStore should be a singleton"


def test_singleton_thread_safety():
    instances = []

    def build_store():
        instances.append(PdiStateStore())

    threads = [threading.Thread(target=build_store) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All instances should be identical
    assert len(set(map(id, instances))) == 1, "All threads should receive the same singleton instance"


def test_init_only_called_once(monkeypatch):
    created = {"count": 0}

    class FakeSystemDeviceDict:
        def __init__(self) -> None:
            created["count"] += 1

        # noinspection PyUnusedLocal,PyMethodMayBeStatic
        def register_pdi_device(self, cmd: Any) -> List[Any] | None:
            return None

    # Replace the SystemDeviceDict used inside the module before first instantiation
    monkeypatch.setattr(pdi_state_store_module, "SystemDeviceDict", FakeSystemDeviceDict, raising=True)

    s1 = PdiStateStore()
    s2 = PdiStateStore()
    assert s1 is s2
    assert created["count"] == 1, "SystemDeviceDict should be constructed only once"


# noinspection PyTypeChecker
def test_register_pdi_device_delegates_and_returns(monkeypatch):
    captured = {"arg": None}

    class FakePdiDevices:
        # noinspection PyUnusedLocal,PyMethodMayBeStatic
        def register_pdi_device(self, cmd):
            captured["arg"] = cmd
            return ["a", "b", "c"]

    store = PdiStateStore()
    # Inject our fake device dict into the singleton instance
    store._pdi_devices = FakePdiDevices()

    class DummyPdiReq:
        pass

    req = DummyPdiReq()
    result = store.register_pdi_device(req)

    assert captured["arg"] is req, "register_pdi_device should delegate to the underlying SystemDeviceDict"
    assert result == ["a", "b", "c"], (
        "register_pdi_device should return the value from SystemDeviceDict.register_pdi_device"
    )
