#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from concurrent.futures import Future
from types import SimpleNamespace
from typing import Callable

import pytest

import src.pytrain.gui.guizero_base as mod
import src.pytrain.gui.controller.popup_manager as popup_mod


class _DummyTk:
    @staticmethod
    def geometry(_geometry: str) -> None:
        return

    @staticmethod
    def update_idletasks() -> None:
        return

    @staticmethod
    def after(_delay_ms: int, _func: Callable[[], None]) -> None:
        return


class DummyApp:
    last_instance: DummyApp | None = None

    def __init__(self, title: str, width: int, height: int) -> None:
        self.title = title
        self.width = width
        self.height = height
        self.full_screen = False
        self.bg = "white"
        self.when_closed = None
        self.tk = _DummyTk()
        self.repeat_callbacks: list[Callable[[], None]] = []
        self.destroy_calls = 0
        DummyApp.last_instance = self

    def repeat(self, _delay_ms: int, func: Callable[[], None]) -> None:
        self.repeat_callbacks.append(func)

    @staticmethod
    def display() -> None:
        return

    def destroy(self) -> None:
        self.destroy_calls += 1


class DummyGui(mod.GuiZeroBase):
    def __init__(self) -> None:
        self.destroy_gui_calls = 0
        super().__init__(
            title="Dummy GUI",
            width=320,
            height=240,
            stand_alone=False,
            full_screen=True,
        )

    @staticmethod
    def build_gui(**kwargs) -> None:
        return

    def destroy_gui(self) -> None:
        self.destroy_gui_calls += 1

    @staticmethod
    def calc_image_box_size(**kwargs) -> tuple[int, int]:
        return 0, 0


@pytest.fixture(autouse=True)
def _patch_runtime(monkeypatch):
    DummyApp.last_instance = None
    monkeypatch.setattr(mod, "App", DummyApp, raising=True)
    monkeypatch.setattr(mod.CommandDispatcher, "get", staticmethod(lambda: object()), raising=True)
    monkeypatch.setattr(mod.ComponentStateStore, "get", staticmethod(lambda: object()), raising=True)
    monkeypatch.setattr(mod.GpioHandler, "cache_handler", staticmethod(lambda *_: None), raising=True)
    yield
    DummyApp.last_instance = None


# noinspection PyUnresolvedReferences
def test_run_clears_local_app_reference_from_shutdown_closure() -> None:
    gui = DummyGui()

    gui.run()

    assert gui.app is None
    assert gui.destroy_gui_calls == 1
    assert gui.destroy_complete.is_set()

    app = DummyApp.last_instance
    assert app is not None
    assert app.repeat_callbacks

    poll_shutdown = app.repeat_callbacks[0]
    freevars = poll_shutdown.__code__.co_freevars
    assert "app" in freevars
    closure = poll_shutdown.__closure__
    assert closure is not None
    app_cell = closure[freevars.index("app")]
    assert app_cell.cell_contents is None


def test_get_prod_info_does_not_requeue_callback_while_future_pending() -> None:
    gui = DummyGui()
    future = Future()
    queued: list[tuple[Callable, tuple]] = []

    gui._prod_info_cache[44] = future
    gui.queue_message = lambda callback, *args: queued.append((callback, args))

    result = gui.get_prod_info("BEEF", lambda *_args: None, 44, available_width=100, available_height=50)

    assert result is future
    assert queued == []


def test_request_prod_info_returns_na_when_lookup_unavailable(monkeypatch) -> None:
    gui = DummyGui()

    monkeypatch.setattr(mod.ProdInfo, "by_btid", classmethod(lambda cls, _bt_id: None), raising=True)

    result = gui._request_prod_info("BEEF")

    assert result == "N/A"


def test_popup_manager_close_invokes_overlay_close_hook() -> None:
    host = SimpleNamespace(
        locked=lambda: _NullContext(),
        image_box=None,
        acc_overlay=None,
    )
    manager = popup_mod.PopupManager(host)
    seen: list[object] = []
    overlay = SimpleNamespace(
        hide=lambda: seen.append("hide"),
        tk=SimpleNamespace(place_forget=lambda: seen.append("forget")),
        on_popup_closed=lambda ov: seen.append(ov),
    )
    manager._state.current_popup = overlay

    manager.close()

    assert seen == ["hide", "forget", overlay]


class _NullContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
