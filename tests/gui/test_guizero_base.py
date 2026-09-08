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
    def __init__(self, button_divisor: float = 6.0, scale_by: float = 1.5) -> None:
        self.destroy_gui_calls = 0
        super().__init__(
            title="Dummy GUI",
            width=320,
            height=240,
            stand_alone=False,
            full_screen=True,
            button_divisor=button_divisor,
            scale_by=scale_by,
        )

    # Signatures mirror the abstract GuiZeroBase hooks; the base calls both with no arguments.
    def build_gui(self) -> None:
        return

    def destroy_gui(self) -> None:
        self.destroy_gui_calls += 1

    def calc_image_box_size(self) -> tuple[int, int]:
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

    # GuiZeroBase.app is annotated App, but run() drops the reference during shutdown; the
    # widened local records that so the assertion below reads as possible, not as dead code.
    app_after_run: mod.App | None = gui.app
    assert app_after_run is None
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


class _BoxedGui(DummyGui):
    """A DummyGui with an image strip of a stated size, and a host's answer on proportions."""

    def __init__(self, height: int, width: int, preserve_aspect: bool = False) -> None:
        self._box = (height, width)
        self._preserve_aspect = preserve_aspect
        super().__init__()

    def calc_image_box_size(self) -> tuple[int, int]:
        return self._box

    @property
    def preserve_image_aspect(self) -> bool:
        return self._preserve_aspect


def test_nothing_preserves_a_pictures_proportions_unless_a_host_asks_for_it() -> None:
    # The Pi's control panel and the Steam Deck are every host that does not, and the Deck
    # keeps them anyway through its own compact branch. So the default is the arithmetic
    # everything has always been drawn with; see _fit_image_size.
    assert mod.GuiZeroBase.preserve_image_aspect.fget(object()) is False


def test_a_short_strip_stretches_the_engine_picture_unless_the_host_says_otherwise() -> None:
    # The measured defect, in its own numbers: a 3:1 locomotive (1086x362 is the cached image
    # for engine 12) in the desktop window's 631x91 strip. The width is filled and the height
    # fitted, so the picture comes out 6.9:1 -- a stripe. Asked to keep its proportions it is
    # drawn at the height instead, smaller and right.
    stretching = _BoxedGui(height=91, width=631)
    keeping = _BoxedGui(height=91, width=631, preserve_aspect=True)

    assert stretching._calc_scaled_image_size(1086, 362) == (631, 91)
    assert keeping._calc_scaled_image_size(1086, 362) == (273, 91)

    stretching.close()
    keeping.close()


def test_a_strip_tall_enough_for_the_picture_costs_the_host_nothing_to_ask() -> None:
    # The other half of the desktop fix: with the ops keypad drawn smaller the strip is 221px
    # tall, the width binds again, and both answers are the same picture -- so preserving the
    # proportions is not a smaller image, it is the same one whenever there is room for it.
    stretching = _BoxedGui(height=221, width=631)
    keeping = _BoxedGui(height=221, width=631, preserve_aspect=True)

    assert stretching._calc_scaled_image_size(1086, 362) == (631, 210)
    assert keeping._calc_scaled_image_size(1086, 362) == (631, 210)

    stretching.close()
    keeping.close()


def test_an_accessory_photo_fills_the_height_it_is_given_either_way() -> None:
    # The ACC path asks for preserve_height, so the photo is drawn as tall as the strip. Nearly
    # square art (the LCS ASC2 photo is 1552x1145) is therefore tiny in a 91px strip and no
    # arithmetic here can help -- what makes it bigger is the taller strip, and there the two
    # answers agree, since the height is what binds in both.
    stretching = _BoxedGui(height=91, width=631)
    keeping = _BoxedGui(height=221, width=631, preserve_aspect=True)

    assert stretching._calc_scaled_image_size(1552, 1145, preserve_height=True) == (123, 91)
    assert keeping._calc_scaled_image_size(1552, 1145, preserve_height=True) == (299, 221)

    stretching.close()
    keeping.close()


def test_a_host_that_asks_keeps_the_proportions_of_a_prepared_image_too() -> None:
    # The other scaling path, the one that runs off the Tk thread for a product-info image.
    # Both read the same helper, so a host cannot be answered one way in one and another in
    # the other; the portrait case above it is the arithmetic the Pi keeps.
    source = BytesIO()
    Image.new("RGB", (600, 300)).save(source, format="PNG")
    gui = _BoxedGui(height=120, width=360, preserve_aspect=True)

    assert gui._prepare_scaled_pil_image(source, available_width=360, available_height=120).size == (240, 120)

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


@pytest.mark.parametrize(
    ("scale_by", "expected"),
    [
        (1.0, 3),  # the Pi's touchscreen, and the geometry the panel is drawn for
        (1.5, 4),  # the default, 4.5 rounded to even
        (3.0, 5),  # scaled well up, and still a border rather than a frame
        (0.5, 2),  # scaled down, and still thick enough to see
    ],
)
def test_the_colored_border_scales_with_the_display_within_bounds(scale_by, expected) -> None:
    # The border is all of a button's color macOS shows, so it has to read at arm's length
    # on a touchscreen without swallowing the button it is drawn around.
    gui = DummyGui(scale_by=scale_by)

    assert gui.border_size == expected

    gui.close()


class _HoverButton:
    """A HoldButton double for add_hover_action, recording what is set and in what order.

    bg is a property on the real button too, and guizero's setter writes -activebackground
    along with -background -- which is why the order the helper works in matters.
    """

    def __init__(self, border_thickness: int | None = 0) -> None:
        if border_thickness is not None:
            self.border_thickness = border_thickness
        self.config_calls: list[dict] = []
        self.order: list[str] = []
        self._bg: str | None = None
        self.tk = SimpleNamespace(config=self._config)

    def _config(self, **kwargs) -> None:
        self.config_calls.append(kwargs)
        self.order.extend(kwargs)

    @property
    def bg(self) -> str | None:
        return self._bg

    @bg.setter
    def bg(self, color: str) -> None:
        self._bg = color
        self.order.append("bg")

    @property
    def configured(self) -> dict:
        merged: dict = {}
        for call in self.config_calls:
            merged.update(call)
        return merged


def test_the_hover_background_goes_through_the_widget_so_a_border_can_follow_it() -> None:
    # The switch pair and the route key are colored by this helper, and the color is their
    # state. Written straight to tk it would leave a colored border showing the color
    # before -- and the border is all of it macOS paints (see HoldButton.border_color).
    btn = _HoverButton(border_thickness=3)

    mod.GuiZeroBase.add_hover_action(btn, hover_color="lightgreen", background="green")

    assert btn.bg == "green"
    assert "background" not in btn.configured


def test_the_hover_color_is_set_after_the_face_it_would_be_overwritten_by() -> None:
    # guizero's bg setter writes -activebackground as well as -background, so a hover color
    # applied first is silently replaced by the face color and the button stops reacting.
    btn = _HoverButton()

    mod.GuiZeroBase.add_hover_action(btn, hover_color="lightgreen", background="green")

    assert btn.order.index("bg") < btn.order.index("activebackground")
    assert btn.configured["activebackground"] == "lightgreen"


def test_a_button_carrying_a_colored_border_keeps_it() -> None:
    # The border is the state cue on these keys; the helper's own outline is drawn in the
    # same two Tk options, so overwriting them would replace the cue with a black hairline.
    btn = _HoverButton(border_thickness=3)

    mod.GuiZeroBase.add_hover_action(btn, background="green")

    assert "highlightthickness" not in btn.configured
    assert "highlightbackground" not in btn.configured
    assert btn.border_thickness == 3


@pytest.mark.parametrize("border_thickness", [0, None], ids=["no-border", "no-such-attribute"])
def test_every_other_button_keeps_the_plain_outline_it_has_always_worn(border_thickness) -> None:
    # Most callers hand this a button with no colored border -- and a plain guizero
    # PushButton, as the Deck's Close button is, has no border_thickness at all.
    btn = _HoverButton(border_thickness=border_thickness)

    mod.GuiZeroBase.add_hover_action(btn)

    assert btn.configured["highlightthickness"] == 1
    assert btn.configured["highlightbackground"] == "black"
    assert (btn.configured["borderwidth"], btn.configured["relief"]) == (3, "raised")
    assert btn.bg == "#f7f7f7"


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


def test_get_scaled_image_emits_no_stdout(capsys, monkeypatch) -> None:
    # The debug print in get_scaled_image was synchronous stdout I/O on the Tk thread, once per
    # scaled image. It has been removed; scaling must now be silent.
    monkeypatch.setattr(mod.ImageTk, "PhotoImage", lambda img: object())
    gui = DummyGui()
    source = BytesIO()
    Image.new("RGB", (20, 10), "white").save(source, format="PNG")

    gui.get_scaled_image(source)

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    gui.close()


class _FakeTk:
    """Minimal stand-in for a guizero widget's .tk handle used by _build_keypad_button."""

    def configure(self, *_args, **_kwargs) -> None:
        return

    config = configure

    def pack_propagate(self, *_args, **_kwargs) -> None:
        return

    def grid_rowconfigure(self, *_args, **_kwargs) -> None:
        return

    def grid_columnconfigure(self, *_args, **_kwargs) -> None:
        return

    def place_configure(self, *_args, **_kwargs) -> None:
        return


class _FakeCell:
    """A guizero Box double that records show()/hide() and emulates the visible setter."""

    def __init__(self, *_args, **kwargs) -> None:
        self.tk = _FakeTk()
        self._visible = bool(kwargs.get("visible", True))
        self.show_calls = 0
        self.hide_calls = 0

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool) -> None:
        # guizero routes visible = ... through show()/hide(); mirror that so the deferred
        # decode wrapper (which shadows show) fires whichever way a cell is revealed.
        if value:
            self.show()
        else:
            self.hide()

    def show(self) -> None:
        self._visible = True
        self.show_calls += 1

    def hide(self) -> None:
        self._visible = False
        self.hide_calls += 1


class _FakeButton:
    """A HoldButton double exposing the image / images attributes the build path sets."""

    def __init__(self, *_args, **kwargs) -> None:
        self.tk = _FakeTk()
        self.image = None
        self.images = None
        self.on_press = kwargs.get("on_press")
        self.on_repeat = None


def _spy_titled_image(gui, monkeypatch) -> list[str]:
    decoded: list[str] = []

    def fake_titled(path):
        decoded.append(path)
        return f"normal::{path}", f"inverted::{path}"

    monkeypatch.setattr(gui, "get_titled_image", fake_titled)
    return decoded


def test_hidden_keypad_image_cell_defers_decode_until_first_shown(monkeypatch) -> None:
    gui = DummyGui()
    monkeypatch.setattr(mod, "Box", _FakeCell)
    monkeypatch.setattr(mod, "HoldButton", _FakeButton)
    decoded = _spy_titled_image(gui, monkeypatch)

    keypad_box = _FakeCell()
    cell, nb = gui._build_keypad_button(
        keypad_box=keypad_box,
        label=None,
        row=0,
        col=0,
        size=0,
        image="boost.jpg",
        visible=False,
        command=None,
    )

    # Building a hidden image cell must not decode anything; the button carries the image name
    # but no rendered image yet.
    assert decoded == []
    assert nb.image == "boost.jpg"
    assert nb.images is None
    assert cell.visible is False

    # The first show decodes exactly once and installs the correct image.
    cell.show()
    assert decoded == ["boost.jpg"]
    assert nb.images == ("normal::boost.jpg", "inverted::boost.jpg")
    assert cell.visible is True

    # Later shows never decode again.
    cell.show()
    assert decoded == ["boost.jpg"]

    gui.close()


def test_hidden_keypad_image_cell_decodes_when_revealed_via_visible_setter(monkeypatch) -> None:
    gui = DummyGui()
    monkeypatch.setattr(mod, "Box", _FakeCell)
    monkeypatch.setattr(mod, "HoldButton", _FakeButton)
    decoded = _spy_titled_image(gui, monkeypatch)

    cell, nb = gui._build_keypad_button(
        keypad_box=_FakeCell(),
        label=None,
        row=0,
        col=0,
        size=0,
        image="brake.jpg",
        visible=False,
        command=None,
    )
    assert decoded == []
    assert nb.images is None

    # Revealing through cell.visible = True (guizero calls show()) also triggers the decode.
    cell.visible = True
    assert decoded == ["brake.jpg"]
    assert nb.images == ("normal::brake.jpg", "inverted::brake.jpg")

    gui.close()


def test_hidden_keypad_image_cell_decodes_from_original_path_after_image_reassigned(monkeypatch) -> None:
    # Regression: a live button's image can be swapped to a rendered ImageTk.PhotoImage before
    # the cell is first shown (e.g. update_ac_status repaints the BPC2 status bulb). The
    # deferred decode must use the original build-time path, not button.image -- feeding a
    # PhotoImage back through get_titled_image/Image.open raised and aborted the panel's show
    # cascade, dropping the BPC2 buttons and device image on first display.
    gui = DummyGui()
    monkeypatch.setattr(mod, "Box", _FakeCell)
    monkeypatch.setattr(mod, "HoldButton", _FakeButton)
    decoded = _spy_titled_image(gui, monkeypatch)

    cell, nb = gui._build_keypad_button(
        keypad_box=_FakeCell(),
        label=None,
        row=0,
        col=0,
        size=0,
        image="bulb-power-off.png",
        visible=False,
        command=None,
    )
    assert decoded == []

    # Simulate update_ac_status swapping in a rendered image object before the first show.
    rendered_image = object()
    nb.image = rendered_image

    # The first show must not blow up and must decode from the original path, not the object.
    cell.show()
    assert decoded == ["bulb-power-off.png"]
    assert nb.images == ("normal::bulb-power-off.png", "inverted::bulb-power-off.png")
    assert cell.visible is True

    gui.close()


def test_visible_keypad_image_cell_decodes_during_build(monkeypatch) -> None:
    gui = DummyGui()
    monkeypatch.setattr(mod, "Box", _FakeCell)
    monkeypatch.setattr(mod, "HoldButton", _FakeButton)
    decoded = _spy_titled_image(gui, monkeypatch)

    _cell, nb = gui._build_keypad_button(
        keypad_box=_FakeCell(),
        label=None,
        row=0,
        col=0,
        size=0,
        image="front-coupler.jpg",
        visible=True,
        command=None,
    )

    # A visible-at-build image cell keeps decoding eagerly so its first render is unchanged.
    assert decoded == ["front-coupler.jpg"]
    assert nb.image == "front-coupler.jpg"
    assert nb.images == ("normal::front-coupler.jpg", "inverted::front-coupler.jpg")

    gui.close()
