#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

import types
from typing import Any, Optional

import pytest

from src.pytrain.protocol.constants import CommandScope


# noinspection PyUnusedLocal
class DummyOled:
    def __init__(self, address: Optional[int], device: Any, auto_update: bool = False, scroll_rate: float = 0.03):
        self._rows = ["", "", "", ""]
        self._cols = 21  # pick width > 20 to exercise a wider formatting branch
        self._updates = 0
        self._clears = 0
        self._writes = []  # records (text, row, kwargs)
        self._cursor_pos = None

    def __setitem__(self, index: int, value: str) -> None:
        self._rows[index] = value

    def __getitem__(self, index: int) -> str:
        return self._rows[index]

    @property
    def rows(self) -> int:
        return len(self._rows)

    @property
    def cols(self) -> int:
        return self._cols

    @cols.setter
    def cols(self, v: int) -> None:
        self._cols = v

    def write(self, text: str, row: int, **kwargs):
        # record writes and place centered text in buffer if requested
        self._writes.append((text, row, kwargs))
        center = kwargs.get("center", False)
        blink = kwargs.get("blink", False)
        if center:
            padding = max(0, (self._cols - len(text)) // 2)
            s = " " * padding + text
        else:
            s = text
        if blink:
            # just annotate blink in buffer minimally for assertion
            s = s  # keep same; we rely on _writes to assert blinking prompt
        self._rows[row] = s[: self._cols]

    def clear(self):
        self._clears += 1
        self._rows = ["", "", "", ""]

    def update_display(self):
        self._updates += 1

    def reset(self):
        # emulate turning off/cleanup
        pass

    def show(self):
        pass

    def hide(self):
        pass

    @property
    def cursor_pos(self):
        return self._cursor_pos

    @cursor_pos.setter
    def cursor_pos(self, value):
        self._cursor_pos = value


class DummyWatcher:
    def __init__(self, state, action):
        self.state = state
        self.action = action
        self._shutdown = False

    def shutdown(self):
        self._shutdown = True


class DummyState:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __repr__(self):
        return f"DummyState({self.__dict__})"


# noinspection PyUnusedLocal
class DummyStateStore:
    def __init__(self):
        self.states = {}

    def set_state(self, scope: CommandScope, address: int, state: Any):
        self.states[(scope, address)] = state

    def get_state(self, scope: CommandScope, address: int, create: bool = True):
        return self.states.get((scope, address))


@pytest.fixture()
def patched_engine_status(monkeypatch):
    # Import target after patching module-level dependencies
    import src.pytrain.gpio.engine_status as es_mod

    # Patch atexit to avoid global registrations
    monkeypatch.setattr(es_mod.atexit, "register", lambda *_args, **_kw: None, raising=True)

    # Patch Oled and StateWatcher in the module under test
    monkeypatch.setattr(es_mod, "Oled", DummyOled, raising=True)
    monkeypatch.setattr(es_mod, "StateWatcher", DummyWatcher, raising=True)

    # Prepare and patch a stub state store
    store = DummyStateStore()
    # SYNC state: address 99
    sync_state = DummyState(is_synchronized=False)
    store.set_state(CommandScope.SYNC, 99, sync_state)
    # BASE state: used for railroad name
    base_state = DummyState(base_name="my railroad")
    store.set_state(CommandScope.BASE, 0, base_state)

    # Patch ComponentStateStore.get() to return our dummy store
    class CSStoreProxy:
        @staticmethod
        def get():
            return store

    monkeypatch.setattr(es_mod, "ComponentStateStore", CSStoreProxy, raising=True)

    # Provide convenience access in the fixture
    return types.SimpleNamespace(module=es_mod, store=store, sync_state=sync_state)


def make_engine_state(
    address: int = 1234,
    scope: CommandScope = CommandScope.ENGINE,
    overrides: Optional[dict] = None,
):
    defaults = dict(
        address=address,
        scope=scope,
        is_started=True,
        is_shutdown=False,
        road_name="My Engine",
        road_number=str(address),
        control_type_label="Legacy",
        engine_type_label="Steam",
        speed=12,
        speed_max=200,
        direction_label="FW",
        rpm=1,
        labor=7,
        train_brake=0,
        momentum=3,
        smoke_label="Med",
    )
    if overrides:
        defaults.update(overrides)
    return DummyState(**defaults)


def test_initial_sync_incomplete_shows_synchronizing_and_sets_watcher(patched_engine_status):
    es_mod = patched_engine_status.module
    # Initial sync state is false per fixture
    eng_status = es_mod.EngineStatus(tmcc_id=1234, scope=CommandScope.ENGINE)

    # Should have written "Synchronizing..." with blink=True on row 0 via DummyOled.write
    writes = eng_status.display._writes
    assert any(w[0] == "Synchronizing..." and w[1] == 0 and w[2].get("blink") is True for w in writes), (
        "Expected synchronizing prompt with blink"
    )

    # A sync watcher should have been created
    assert isinstance(eng_status._sync_watcher, DummyWatcher)
    # No monitored engine state yet since store has none
    assert eng_status.state is None

    # cleanup
    eng_status.reset()


def test_on_sync_sets_synchronized_and_updates_display_not_found(patched_engine_status):
    es_mod = patched_engine_status.module
    eng_status = es_mod.EngineStatus(tmcc_id=2222, scope=CommandScope.ENGINE)

    # Flip sync state to True and trigger on_sync
    patched_engine_status.sync_state.is_synchronized = True
    eng_status.on_sync()

    # Sync watcher is shut down and cleared
    assert eng_status._sync_watcher is None
    assert eng_status.is_synchronized is True

    # No engine state present in store for tmcc_id=2222 => should show Not Found
    writes = eng_status.display._writes
    assert any("Not Found" in w[0] and w[1] == 2 for w in writes), "Expected 'Not Found' on row 2"

    # Should have cleared display once during update_display(clear=True)
    assert eng_status.display._clears >= 1

    eng_status.reset()


def test_update_engine_sets_state_and_clears_display_and_starts_watcher(patched_engine_status):
    es_mod = patched_engine_status.module
    # Start synchronized so EngineStatus won't create sync watcher that interferes
    patched_engine_status.sync_state.is_synchronized = True

    # Preload an engine state in store
    state = make_engine_state(address=3333)
    patched_engine_status.store.set_state(CommandScope.ENGINE, 3333, state)

    eng_status = es_mod.EngineStatus(tmcc_id=3333, scope=CommandScope.ENGINE)

    # Engine state watcher created
    assert isinstance(eng_status._state_watcher, DummyWatcher)
    assert eng_status.state is state

    # Trigger update_engine to another ID with no state to ensure clear is called
    eng_status.update_engine(4444, CommandScope.ENGINE)
    assert eng_status.tmcc_id == 4444
    assert eng_status.scope == CommandScope.ENGINE
    assert eng_status.display._clears >= 1
    # Since 4444 not in store, monitored state should be None
    assert eng_status.state is None

    eng_status.reset()


def test_update_display_with_state_populates_rows_and_cursor(patched_engine_status):
    es_mod = patched_engine_status.module
    patched_engine_status.sync_state.is_synchronized = True

    # Provide monitored state directly via constructor by passing state object
    eng_state = make_engine_state(address=5555)
    patched_engine_status.store.set_state(CommandScope.ENGINE, 5555, eng_state)
    eng_status = es_mod.EngineStatus(tmcc_id=getattr(eng_state, "address"), scope=CommandScope.ENGINE)

    # After init, update_display is invoked via on_sync path or direct; ensure rows are set
    # Row 0 contains road info and labels
    assert "My Engine" in eng_status.display[0]
    assert "Legacy" in eng_status.display[0] or "Steam" in eng_status.display[0]

    # Row 1 contains scope label and tmcc id
    assert f"{eng_status.scope.label}:" in eng_status.display[1]
    assert f"{eng_status.tmcc_id:04}" in eng_status.display[1]

    # Row 2 contains Speed and direction text adapted for cols > 20
    assert "Speed:" in eng_status.display[2]
    assert "Fwd" in eng_status.display[2] or "Rev" in eng_status.display[2] or "---" in eng_status.display[2]

    # Row 3 contains TB, Mo, Sm, and RPM when cols > 20
    assert "TB:" in eng_status.display[3]
    assert "Mo:" in eng_status.display[3]
    assert "Sm:" in eng_status.display[3]
    assert "RPM:" in eng_status.display[3]

    # Cursor expected at (1, 8) when a monitored state is present
    assert eng_status.display.cursor_pos == (1, 8)

    eng_status.reset()
