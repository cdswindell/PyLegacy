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
from io import BytesIO
from threading import Event, get_ident
from types import SimpleNamespace
from typing import Callable

import pytest
from PIL import Image

import src.pytrain.gui.guizero_base as mod
import src.pytrain.gui.controller.popup_manager as popup_mod
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandEnum


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
    def __init__(self, button_divisor: float = 6.0) -> None:
        self.destroy_gui_calls = 0
        super().__init__(
            title="Dummy GUI",
            width=320,
            height=240,
            stand_alone=False,
            full_screen=True,
            button_divisor=button_divisor,
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
    monkeypatch.setattr(
        mod.CommandDispatcher,
        "get",
        staticmethod(lambda: SimpleNamespace(version="PyTrain Test")),
        raising=True,
    )
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


def test_scaled_image_dimensions_never_reach_zero() -> None:
    gui = DummyGui()

    assert gui._calc_scaled_image_size(432, 167) == (1, 1)
    assert gui._calc_scaled_image_size(432, 167, force_lionel=True) == (1, 1)

    gui.close()


def test_compact_prepared_image_preserves_source_aspect_ratio() -> None:
    source = BytesIO()
    Image.new("RGB", (600, 300)).save(source, format="PNG")
    gui = DummyGui()

    gui._compact = True
    compact = gui._prepare_scaled_pil_image(source, available_width=360, available_height=120)
    assert compact.size == (240, 120)

    gui._compact = False
    portrait = gui._prepare_scaled_pil_image(source, available_width=360, available_height=120)
    assert portrait.size == (360, 120)

    gui.close()


def test_button_divisor_supports_compact_landscape_controls() -> None:
    portrait = DummyGui()
    landscape = DummyGui(button_divisor=8.0)

    assert portrait.button_size == 53
    assert portrait.titled_button_size == 43
    assert landscape.button_size == 40
    assert landscape.titled_button_size == 32

    portrait.close()
    landscape.close()


def test_poll_shutdown_processes_up_to_five_messages_per_tick() -> None:
    gui = DummyGui()
    handled: list[int] = []

    for i in range(7):
        gui.queue_message(lambda value=i: handled.append(value))

    gui.run()

    app = DummyApp.last_instance
    assert app is not None
    poll_shutdown = app.repeat_callbacks[0]
    poll_shutdown()

    assert handled == [0, 1, 2, 3, 4]
    assert gui._message_queue.qsize() == 2


def test_poll_shutdown_logs_callback_exception_and_continues(caplog) -> None:
    gui = DummyGui()
    handled: list[str] = []

    def boom() -> None:
        raise RuntimeError("boom")

    gui.queue_message(boom)
    gui.queue_message(lambda: handled.append("ok"))

    gui.run()

    app = DummyApp.last_instance
    assert app is not None
    poll_shutdown = app.repeat_callbacks[0]

    with caplog.at_level("ERROR"):
        poll_shutdown()

    assert handled == ["ok"]
    assert "Error processing GUI message callback" in caplog.text


def test_submit_request_sends_on_worker_thread_with_repeat_and_delay(monkeypatch) -> None:
    gui = DummyGui()
    req = mod.CommandReq(TMCC1HaltCommandEnum.HALT)
    sent = Event()
    seen: dict[str, int | float] = {}
    caller_thread = get_ident()

    def fake_send(*, repeat: int = 1, delay: float = 0.0, **_kwargs) -> None:
        seen["repeat"] = repeat
        seen["delay"] = delay
        seen["thread_id"] = get_ident()
        sent.set()

    monkeypatch.setattr(req, "send", fake_send, raising=False)

    try:
        gui.submit_request(req, repeat=3, delay=0.25)

        assert sent.wait(1.0)
        assert seen["repeat"] == 3
        assert seen["delay"] == pytest.approx(0.25)
        assert seen["thread_id"] != caller_thread
    finally:
        gui.close()
        gui._join_request_worker(timeout=1.0)


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
    )
    manager._post_close_actions[id(overlay)] = lambda ov: seen.append(ov)
    manager._state.current_popup = overlay

    manager.close()

    assert seen == ["hide", "forget", overlay]


class _NullContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_resolve_font_family_accepts_embedded_family_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod.tkfont, "families", lambda _root: ("Helvetica", "Digital dream"))

    assert mod.resolve_font_family(object(), "DigitalDream") == "Digital dream"


def test_resolve_font_family_uses_readable_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod.tkfont, "families", lambda _root: ("Helvetica", "TkDefaultFont"))

    assert mod.resolve_font_family(object(), "DigitalDream") == "TkDefaultFont"


def _sized_png(tmp_path, name: str, size: tuple[int, int] = (200, 200)) -> str:
    path = tmp_path / name
    Image.new("RGB", size, "white").save(path, format="PNG")
    return str(path)


def test_get_image_honors_the_requested_size_on_a_cache_hit(tmp_path, monkeypatch) -> None:
    """The size used to be ignored whenever the path was already cached.

    Keyed on the path alone, the *first* caller for a file decided the size for every later one,
    silently. bell.jpg and horn.jpg are each requested twice at different sizes -- once by a keypad
    button at titled_button_size, once by the freight-sounds pair at its own smaller size -- and
    since the keypad is built first, the pair was handed images far larger than its buttons.
    """
    sizes: list[tuple[int, int]] = []
    monkeypatch.setattr(mod.ImageTk, "PhotoImage", lambda img: sizes.append(img.size) or object())
    gui = DummyGui()
    path = _sized_png(tmp_path, "bell.png")

    gui.get_image(path, size=106, inverse=False)
    gui.get_image(path, size=47, inverse=False)

    assert sizes == [(106, 106), (47, 47)], "the second request was served at its own size"

    gui.close()


def test_get_image_still_caches_a_repeated_identical_request(tmp_path, monkeypatch) -> None:
    # The point is correctness, not abandoning the cache: same path and same size is still one
    # PhotoImage, so the extra entries are one per *distinct* size, not one per call.
    built: list[tuple[int, int]] = []
    monkeypatch.setattr(mod.ImageTk, "PhotoImage", lambda img: built.append(img.size) or object())
    gui = DummyGui()
    path = _sized_png(tmp_path, "horn.png")

    first = gui.get_image(path, size=47, inverse=False)
    second = gui.get_image(path, size=47, inverse=False)

    assert first is second
    assert built == [(47, 47)]

    gui.close()


def test_get_image_treats_an_int_size_and_a_square_tuple_as_one_entry(tmp_path, monkeypatch) -> None:
    # size is normalized before the key is built, so these are the same request. Normalizing after
    # would give them separate entries and double the images for no reason.
    built: list[tuple[int, int]] = []
    monkeypatch.setattr(mod.ImageTk, "PhotoImage", lambda img: built.append(img.size) or object())
    gui = DummyGui()
    path = _sized_png(tmp_path, "cycle.png")

    gui.get_image(path, size=47, inverse=False)
    gui.get_image(path, size=(47, 47), inverse=False)

    assert built == [(47, 47)]

    gui.close()


def test_get_image_separates_entries_that_differ_only_by_flag(tmp_path, monkeypatch) -> None:
    # inverse changes what is returned (a pair rather than one image), so it belongs in the key.
    monkeypatch.setattr(mod.ImageTk, "PhotoImage", lambda img: object())
    gui = DummyGui()
    path = _sized_png(tmp_path, "load.png")

    plain = gui.get_image(path, size=47, inverse=False)
    pair = gui.get_image(path, size=47, inverse=True)

    assert not isinstance(plain, tuple)
    assert isinstance(pair, tuple) and len(pair) == 2

    gui.close()
