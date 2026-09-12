#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#
#

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property
from math import ceil
from threading import RLock
from tkinter import font as tkfont
from types import MethodType, SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from pytrain.db.component_state import RouteState, SwitchState
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.components import RouteComponent
from pytrain.gui.controller import engine_gui as gui_mod
from pytrain.gui.controller import route_builder_panel as mod
from pytrain.gui.controller import steam_deck_input as deck
from pytrain.gui.controller.popup_manager import PopupManager
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum


class TkWidget(SimpleNamespace):
    # Most widgets never use these callbacks; keep call tracking without eager mock allocation.
    @cached_property
    def bind(self):
        return Mock()

    @cached_property
    def after_idle(self):
        return Mock()

    @cached_property
    def update_idletasks(self):
        return Mock()


class Widget:
    def __init__(self, *_args, **kwargs):
        self.parent = _args[0] if _args else None
        self.children = []
        if isinstance(self.parent, Widget):
            self.parent.children.append(self)
        self.options = kwargs
        self.value = self.text = kwargs.get("text", "")
        self.visible = kwargs.get("visible", True)
        self.enabled = True
        self.is_editing = self.is_changed = False
        self.command = kwargs.get("command")
        self.tk = TkWidget(
            master=self.parent.tk if isinstance(self.parent, Widget) else Mock(),
            config=lambda **kw: self.options.update(kw),
            winfo_exists=lambda: True,
            winfo_ismapped=lambda: self.visible,
            winfo_reqheight=lambda: self.options.get("height", 1),
            pack_propagate=lambda _value: None,
            grid_propagate=lambda _value: None,
            grid_columnconfigure=lambda *_args, **_kw: None,
            grid_rowconfigure=lambda *_args, **_kw: None,
            winfo_reqwidth=lambda: 100,
        )

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def begin_edit(self):
        self.is_editing = True

    def cancel_edit(self):
        self.is_editing = False

    def commit_edit(self):
        self.is_editing = False

    def update_command(self, command):
        self.command = command


class HoldWidget(Widget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_hold = kwargs.get("on_hold")
        self.cancel_interaction = Mock()


class Canvas:
    def __init__(self, *_args, **kwargs):
        self.master = _args[0] if _args else None
        self.options: dict[str, Any] = kwargs
        self.bindings = {}
        self.drawn = []
        self.x = self.y = 0
        self.dragged = []
        self.focus_set = Mock()
        self.pack_options = {}
        self.grid_options = {}
        self.mark = None

    def config(self, **kwargs):
        self.options.update(kwargs)

    def pack(self, **kwargs):
        self.pack_options = kwargs

    def grid(self, **kwargs):
        self.grid_options = kwargs

    def bind(self, sequence, command):
        self.bindings[sequence] = command

    def delete(self, _tag):
        self.drawn.clear()

    def create_text(self, *args, **kwargs):
        self.drawn.append(("text", args, kwargs))
        return len(self.drawn) - 1

    def bbox(self, item):
        _, _, options = self.drawn[item]
        size = options["font"][1]
        width = options["width"] or max(1, len(options["text"]) * size)
        lines = ceil(len(options["text"]) * size / width)
        return 0, 0, width, lines * (size + 5)

    def itemconfigure(self, item, **kwargs):
        self.drawn[item][2].update(kwargs)

    def create_rectangle(self, *args, **kwargs):
        self.drawn.append(("rectangle", args, kwargs))

    def create_line(self, *args, **kwargs):
        self.drawn.append(("line", args, kwargs))

    def create_oval(self, *args, **kwargs):
        self.drawn.append(("oval", args, kwargs))

    def xview(self):
        total = self.options["scrollregion"][2]
        return self.x / total, min(1, (self.x + self.options["width"]) / total)

    def xview_moveto(self, fraction):
        total = self.options["scrollregion"][2]
        self.x = max(0, min(fraction * total, total - self.options["width"]))

    def yview_moveto(self, fraction):
        total = self.options["scrollregion"][3]
        self.y = max(0, min(fraction * total, total - self.options["height"]))
        callback: Callable[[float, float], None] | None = self.options.get("yscrollcommand")
        if callback is not None:
            callback(self.y / total, min(1, (self.y + self.options["height"]) / total))

    def xview_scroll(self, delta, _units):
        self.xview_moveto((self.x + delta * 20) / self.options["scrollregion"][2])

    def yview(self, *args):
        if args:
            if args[0] == "moveto":
                self.yview_moveto(float(args[1]))
            else:
                self.yview_scroll(int(args[1]), args[2])
            return None
        total = self.options["scrollregion"][3]
        return self.y / total, min(1, (self.y + self.options["height"]) / total)

    def yview_scroll(self, delta, units):
        step = self.options["height"] * 0.9 if units == "pages" else self.options["yscrollincrement"]
        self.yview_moveto((self.y + delta * step) / self.options["scrollregion"][3])

    def canvasx(self, x):
        return self.x + x

    def canvasy(self, y):
        return self.y + y

    def scan_mark(self, x, y):
        self.mark = (x, y)

    def scan_dragto(self, x, y, gain):
        self.dragged.append((x, y, gain))


class Scrollbar:
    def __init__(self, master, **kwargs):
        self.master = master
        self.options = kwargs
        self.fractions = (0.0, 1.0)
        self.place_options = {}

    def place(self, **kwargs):
        self.place_options = kwargs

    def set(self, first, last):
        self.fractions = (float(first), float(last))

    def get(self):
        return self.fractions


class Variable:
    def __init__(self, **kwargs):
        self.value = kwargs.get("value", "")

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class PhotoImage:
    def __init__(self, width, height):
        self._width, self._height = width, height
        self.pixels = []

    def width(self):
        return self._width

    def height(self):
        return self._height

    def put(self, color, to):
        self.pixels.append((color, to))


class Store:
    def __init__(self):
        self.states = {}

    def get_state(self, scope, tmcc_id, create=False):
        assert create is False
        return self.states.get((scope, tmcc_id))

    def get_all(self, scope):
        return [state for (key, _), state in self.states.items() if key == scope]


@pytest.fixture
def panel(monkeypatch):
    monkeypatch.setattr(mod, "platform", "linux")
    for name in ("Box", "TitleBox", "PushButton", "CheckBox", "Text", "EditableText"):
        monkeypatch.setattr(mod, name, Widget)
    monkeypatch.setattr(mod, "RouteDiscardDialog", Mock(return_value=SimpleNamespace(result=False)))
    monkeypatch.setattr(mod, "HoldButton", HoldWidget)
    monkeypatch.setattr(mod.tk, "Canvas", Canvas)
    monkeypatch.setattr(mod.tk, "Scrollbar", Scrollbar)
    monkeypatch.setattr(mod, "TouchScrollbar", Mock(side_effect=Scrollbar))
    monkeypatch.setattr(mod.tk, "StringVar", Variable)
    monkeypatch.setattr(mod.tk, "Radiobutton", Canvas)
    monkeypatch.setattr(mod.tk, "PhotoImage", PhotoImage)
    monkeypatch.setattr(tkfont, "Font", lambda *, root, font: SimpleNamespace(measure=lambda text: len(text) * font[1]))
    host = SimpleNamespace(
        width=639,
        height=800,
        compact=True,
        emergency_box_width=639,
        s_12=12,
        s_14=14,
        s_16=16,
        s_18=18,
        s_20=20,
        state_store=Store(),
        app=SimpleNamespace(tk=object(), yesno=lambda *_args: False),
        _scope_tmcc_ids={},
        ops_mode=lambda **_kw: None,
        _message_queue=Mock(),
        _rebuild_state_caches=Mock(),
    )
    host.clear_record = MethodType(gui_mod.EngineGui.clear_record, host)
    builder = mod.RouteBuilderPanel(host)
    builder.build(Widget())
    builder.build_footer(Widget())
    builder.configure(12)
    return builder


@pytest.mark.parametrize("callback_name", ["bind", "after_idle", "update_idletasks"])
def test_widget_callbacks_are_created_on_demand_and_isolated(callback_name):
    widget, other = Widget(), Widget()
    assert callback_name not in vars(widget.tk)
    assert callback_name not in vars(other.tk)
    callback = getattr(widget.tk, callback_name)
    assert getattr(widget.tk, callback_name) is callback
    assert callback_name not in vars(other.tk)
    callback("event")
    callback.assert_called_once_with("event")
    getattr(other.tk, callback_name).assert_not_called()


def known_switch(panel, tmcc_id=7, name="Main siding", *, deleted=False):
    state = SimpleNamespace(
        tmcc_id=tmcc_id,
        name=name,
        road_name=name,
        is_road_name=True,
        road_number=f"{tmcc_id:04d}",
        is_road_number=True,
        is_deleted=deleted,
        is_user_defined=True,
    )
    panel.gui.state_store.states[(CommandScope.SWITCH, tmcc_id)] = state
    return state


def known_route(panel, tmcc_id=4, components=()):
    state = RouteState()
    state._address = tmcc_id
    state.initialize(CommandScope.ROUTE, tmcc_id)
    state.comp_data.components = list(components)
    panel.gui.state_store.states[(CommandScope.ROUTE, tmcc_id)] = state
    return state


def add_switch(panel, tmcc_id=7):
    known_switch(panel, tmcc_id)
    panel.open_picker()
    panel.choose_candidate(next(i for i, (_, state) in enumerate(panel._candidates) if state.tmcc_id == tmcc_id))
    panel.add_selected()


def picker_space(panel, available, overhead=280):
    overlay = panel._picker_page.tk.master.master
    overlay.winfo_height.return_value = overhead + available
    overlay.winfo_reqheight.side_effect = lambda: overhead + panel._picker.master.winfo_reqheight()
    panel._resize_picker()


class DeckPickerGui(SimpleNamespace):
    @property
    def route_picker(self):
        return gui_mod.EngineGui.route_picker.fget(self)

    @property
    def list_scroll_panel(self):
        return gui_mod.EngineGui.list_scroll_panel.fget(self)


@pytest.fixture
def deck_picker(panel):
    gui = DeckPickerGui(**vars(panel.gui))
    gui._route_builder_panel = panel
    gui._catalog_panel = None
    gui.input_contexts = ()
    gui.on_engine_command = Mock()
    panel._gui = gui
    panel._overlay = Widget()
    for tmcc_id in range(1, 13):
        known_switch(panel, tmcc_id, f"Switch {tmcc_id:02d}")
    panel.open_picker()
    picker_space(panel, panel.picker_row_height * 4)
    focus = SimpleNamespace(gui=gui)
    halt = Mock()
    router = deck.DeckInputRouter(
        deck.ControlProfile.load(),
        left=lambda: gui,
        right=lambda: None,
        focused=lambda: focus.gui,
        global_actions={"halt": halt},
    )
    return panel, router, focus, halt


def pad_press(router, name, button=None):
    router.handle(deck.DeckAction(name, "focused", 1.0, "pressed", button=button))
    router.handle(deck.DeckAction(name, "focused", 0.0, "released", button=button))


@pytest.mark.parametrize("target", ["left", "focused"])
@pytest.mark.parametrize("context", [(), (deck.SWITCH_CONTEXT,), (deck.ROUTE_CONTEXT,)])
def test_deck_analog_scrolls_picker_without_selecting_or_driving(deck_picker, target, context):
    panel, router, _, _ = deck_picker
    panel.gui.input_contexts = context
    panel.choose_candidate(0)
    router.handle(deck.DeckAction("throttle", target, -0.25, "changed"))
    for now in (10.0, 10.2, 10.4, 10.6, 10.8):
        router.tick(now)
    assert panel._picker.y == panel.picker_row_height
    router.handle(deck.DeckAction("throttle", target, 0.0, "changed"))
    router.tick(11.0)
    assert panel._picker.y == panel.picker_row_height
    assert panel._candidate == panel._picker_cursor == (CommandScope.SWITCH, 1)
    assert not panel.draft.dirty
    panel.gui.on_engine_command.assert_not_called()


def test_deck_touchpad_scrolls_picker_and_cards_without_changing_route(deck_picker):
    panel, router, _, _ = deck_picker
    for value in (0.25, 0.75):
        router.handle(deck.DeckAction(deck.QUILLING_HORN, "left", value, "changed"))
    assert panel._picker.y > 0 and panel._candidate is None
    panel.cancel()
    for tmcc_id in range(1, 9):
        add_switch(panel, tmcc_id)
    panel._cards.xview_moveto(0)
    before = RouteComponent.to_bytes(panel.draft.components), panel._selected
    router.handle(deck.DeckAction(deck.QUILLING_HORN, "left", 0.4, "changed"))
    assert panel._cards.x == 0, "changing pages starts a new stroke"
    router.handle(deck.DeckAction(deck.QUILLING_HORN, "left", 0.6, "changed"))
    assert panel._cards.x == pytest.approx(0.2 * deck.CONFIG_PAD_TRAVEL_PX)
    assert (RouteComponent.to_bytes(panel.draft.components), panel._selected) == before
    panel.gui.on_engine_command.assert_not_called()


@pytest.mark.parametrize("stop", ["cancel", "hidden", "search", "disconnect"])
def test_deck_analog_scroll_stops_when_picker_is_unavailable(deck_picker, stop):
    panel, router, _, _ = deck_picker
    router.handle(deck.DeckAction("throttle", "left", -1.0, "changed"))
    router.handle(deck.DeckAction(deck.QUILLING_HORN, "left", 0.25, "changed"))
    router.tick(10.0)
    if stop == "cancel":
        panel.cancel()
    elif stop == "hidden":
        panel._overlay.hide()
    elif stop == "search":
        panel._search_field.begin_edit()
        for name in ("throttle", deck.QUILLING_HORN):
            router.handle(deck.DeckAction(name, "left", 0.75, "changed"))
    else:
        router.clear()
    router.tick(10.25)
    assert panel._picker.y == 0
    assert not router._list_scrolls and not router._list_pads
    panel.gui.on_engine_command.assert_not_called()


def test_route_controller_scroll_clamps_and_preserves_small_movements(deck_picker):
    panel, _, _, _ = deck_picker
    for _ in range(panel.picker_row_height - 1):
        panel.scroll_by_pixels(1)
    assert panel._picker.y == 0
    panel.scroll_by_pixels(1)
    assert panel._picker.y == panel.picker_row_height
    panel.scroll_by_pixels(10000)
    assert panel._picker.yview()[1] == 1
    panel.scroll_by_pixels(17)
    panel.scroll_by_pixels(-panel.picker_row_height)
    assert panel._picker.y == 7 * panel.picker_row_height
    panel.scroll_by_pixels(-10000)
    assert panel._picker.y == 0
    panel.set_filter("Routes")
    panel.scroll_by_pixels(10000)
    assert panel._picker.y == 0 and panel._candidate is None


@pytest.mark.parametrize("field_name", ["_name_field", "_number_field"])
def test_route_metadata_editing_consumes_analog_input_without_scrolling(deck_picker, field_name):
    panel, router, _, _ = deck_picker
    panel.cancel()
    for tmcc_id in range(1, 9):
        add_switch(panel, tmcc_id)
    panel._cards.xview_moveto(0)
    getattr(panel, field_name).begin_edit()
    router.handle(deck.DeckAction("throttle", "left", -1.0, "changed"))
    for value in (0.25, 0.75):
        router.handle(deck.DeckAction(deck.QUILLING_HORN, "left", value, "changed"))
    router.tick(10.0)
    router.tick(10.25)
    assert panel._cards.x == 0
    assert not router._levers and not router._quills
    panel.gui.on_engine_command.assert_not_called()


def test_deck_picker_browses_without_selecting_and_reveals_complete_rows(deck_picker):
    panel, router, _, _ = deck_picker
    sort = panel._sort, panel._descending, [button.text for button in panel._sort_btns]
    for index in range(12):
        pad_press(router, deck.DPAD_DOWN)
        assert panel._picker_cursor == (CommandScope.SWITCH, index + 1)
        assert panel._candidate is None and not panel._save_btn.enabled
        start = index * panel.picker_row_height
        assert panel._picker.y <= start
        assert start + panel.picker_row_height <= panel._picker.y + panel._picker.options["height"]
    pad_press(router, deck.DPAD_DOWN)
    assert panel._picker_cursor == (CommandScope.SWITCH, 12)
    for _ in range(15):
        pad_press(router, deck.DPAD_UP)
    assert panel._picker_cursor == (CommandScope.SWITCH, 1)
    assert panel._picker.y == 0
    assert not panel.draft.components and not panel.draft.dirty
    assert (panel._sort, panel._descending, [button.text for button in panel._sort_btns]) == sort
    panel.gui.on_engine_command.assert_not_called()


@pytest.mark.parametrize("sort", ["Name", "TMCC ID"])
@pytest.mark.parametrize("descending", [False, True])
@pytest.mark.parametrize("filter_name", ["Routes", "Switches"])
def test_deck_picker_browses_mixed_choices_without_changing_sort(deck_picker, sort, descending, filter_name):
    panel, router, _, _ = deck_picker
    for tmcc_id in range(1, 5):
        known_route(panel, tmcc_id)
    panel.set_filter(filter_name)
    panel.set_sort(sort)
    if descending:
        panel.toggle_sort_direction()
    choices = [(scope, state.tmcc_id) for scope, state in panel._candidates]
    for choice in choices:
        pad_press(router, deck.DPAD_DOWN)
        assert panel._picker_cursor == choice
    for choice in reversed(choices[:-1]):
        pad_press(router, deck.DPAD_UP)
        assert panel._picker_cursor == choice
    assert panel._sort == sort and panel._descending == descending
    assert panel._filter == filter_name and panel._candidate is None
    assert not panel.draft.components and not panel.draft.dirty
    panel.gui.on_engine_command.assert_not_called()


@pytest.mark.parametrize("context", [(), (deck.SWITCH_CONTEXT,), (deck.ROUTE_CONTEXT,)])
def test_deck_picker_selects_clears_and_adds_highlighted_not_previous_choice(deck_picker, monkeypatch, context):
    panel, router, _, _ = deck_picker
    monkeypatch.setattr(panel.gui, "input_contexts", context)
    panel.choose_candidate(0)
    assert panel._candidate == (CommandScope.SWITCH, 1) and panel._save_btn.enabled
    pad_press(router, "bell", deck.BACK_PAGE_BUTTON)
    assert panel._candidate is None and not panel._save_btn.enabled
    assert panel._picking
    panel.choose_candidate(0)
    pad_press(router, deck.DPAD_DOWN)
    assert panel._candidate == (CommandScope.SWITCH, 1)
    pad_press(router, deck.SEQUENCE_CONTROL, deck.SELECT_BUTTON)
    assert [c.tmcc_id for c in panel.draft.components] == [2]
    assert not panel._picking
    panel.gui.on_engine_command.assert_not_called()


@pytest.mark.parametrize("context", [(), (deck.SWITCH_CONTEXT,), (deck.ROUTE_CONTEXT,)])
@pytest.mark.parametrize("scope", [CommandScope.SWITCH, CommandScope.ROUTE])
def test_deck_picker_right_adds_highlighted_not_previous_choice(deck_picker, monkeypatch, context, scope):
    panel, router, _, _ = deck_picker
    monkeypatch.setattr(panel.gui, "input_contexts", context)
    if scope == CommandScope.ROUTE:
        known_route(panel, 1)
        known_route(panel, 2)
        panel.set_filter("Routes")
    panel.choose_candidate(0)
    router.handle(deck.DeckAction(deck.DPAD_DOWN, "focused", 1.0, "pressed"))
    router.tick(10.0)
    router.tick(10.1)
    assert panel._picker_cursor == (scope, 2) and panel._candidate == (scope, 1)
    pad_press(router, deck.DPAD_RIGHT)
    assert [component.tmcc_id for component in panel.draft.components] == [2]
    assert panel.draft.components[0].is_route == (scope == CommandScope.ROUTE)
    assert panel.draft.dirty and not panel._picking and panel.visible
    assert not router._picker_scrolls
    router.tick(10.8)
    assert len(panel.draft.components) == 1
    panel.gui.on_engine_command.assert_not_called()


@pytest.mark.parametrize("name,button", [("volume_down", deck.CLOSE_POPUP_BUTTON), (deck.DPAD_LEFT, None)])
def test_deck_picker_x_cancels_only_add_and_reopening_resets_cursor(deck_picker, name, button):
    panel, router, _, _ = deck_picker
    add_switch(panel, 7)
    panel.open_picker()
    components = RouteComponent.to_bytes(panel.draft.components)
    panel.draft.set_metadata("Keep this route", "12")
    panel._close = Mock()
    router.handle(deck.DeckAction(deck.DPAD_DOWN, "focused", 1.0, "pressed"))
    router.tick(10.0)
    router.tick(10.1)
    pad_press(router, name, button)
    assert not panel._picking and panel.gui.route_picker is None
    assert panel.draft.dirty and panel.draft.road_name == "Keep this route"
    assert RouteComponent.to_bytes(panel.draft.components) == components
    assert not router._picker_scrolls
    router.tick(10.8)
    panel._close.assert_not_called()
    panel.gui.on_engine_command.assert_not_called()
    panel.open_picker()
    assert panel._picker_cursor is None and panel._candidate is None


@pytest.mark.parametrize("name,button", [(deck.SEQUENCE_CONTROL, deck.SELECT_BUTTON), (deck.DPAD_RIGHT, None)])
def test_deck_picker_a_selects_and_adds_without_prior_dpad_press(deck_picker, name, button):
    panel, router, _, _ = deck_picker
    panel.scroll_picker("scroll", "4", "units")
    pad_press(router, name, button)
    assert [c.tmcc_id for c in panel.draft.components] == [5]


def test_deck_picker_cursor_tracks_touch_sort_and_filter_without_stale_selection(deck_picker):
    panel, router, _, _ = deck_picker
    panel.choose_candidate(6)
    pad_press(router, deck.DPAD_DOWN)
    assert panel._picker_cursor == (CommandScope.SWITCH, 8)
    panel.toggle_sort_direction()
    assert panel.pad_mark()
    assert panel._candidate == (CommandScope.SWITCH, 8)
    panel.set_filter("Routes")
    for name, button in [(deck.DPAD_DOWN, None), (deck.DPAD_RIGHT, None), (deck.SEQUENCE_CONTROL, deck.SELECT_BUTTON)]:
        pad_press(router, name, button)
    assert panel._picker_cursor is None and panel._candidate is None
    assert panel._picking and not panel.draft.components
    panel.gui.on_engine_command.assert_not_called()


def test_deck_picker_repeats_at_catalog_cadence_and_stops_on_release(deck_picker):
    panel, router, _, _ = deck_picker
    router.handle(deck.DeckAction(deck.DPAD_DOWN, "focused", 1.0, "pressed"))
    for now in (10.0, 10.1, 10.4):
        router.tick(now)
    assert panel._picker_cursor == (CommandScope.SWITCH, 1)
    router.tick(10.6)
    router.tick(10.8)
    assert panel._picker_cursor == (CommandScope.SWITCH, 3)
    router.handle(deck.DeckAction(deck.DPAD_DOWN, "focused", 0.0, "released"))
    router.tick(11.0)
    assert panel._picker_cursor == (CommandScope.SWITCH, 3)
    assert panel._candidate is None


@pytest.mark.parametrize("stop", ["cancel", "hidden", "focus", "search", "disconnect"])
def test_deck_picker_stops_held_navigation_when_no_longer_available(deck_picker, stop):
    panel, router, focus, _ = deck_picker
    router.handle(deck.DeckAction(deck.DPAD_DOWN, "focused", 1.0, "pressed"))
    router.tick(10.0)
    router.tick(10.1)
    if stop == "cancel":
        panel.cancel()
    elif stop == "hidden":
        panel._overlay.hide()
    elif stop == "focus":
        focus.gui = None
    elif stop == "search":
        panel._search_field.begin_edit()
    else:
        router.handle(deck.DeckAction("disconnect", "global", 0.0, "released"))
    router.tick(10.6)
    assert panel._picker_cursor == (CommandScope.SWITCH, 1)
    panel.gui.on_engine_command.assert_not_called()


@pytest.mark.parametrize(
    "cancel_name,cancel_button", [("volume_down", deck.CLOSE_POPUP_BUTTON), (deck.DPAD_LEFT, None)]
)
def test_deck_picker_search_editing_blocks_selection_but_allows_cancel_and_halt(
    deck_picker, cancel_name, cancel_button
):
    panel, router, _, halt = deck_picker
    panel._search_field.begin_edit()
    for name, button in [(deck.DPAD_DOWN, None), (deck.DPAD_RIGHT, None), (deck.SEQUENCE_CONTROL, deck.SELECT_BUTTON)]:
        pad_press(router, name, button)
    assert panel._candidate is None and not panel.draft.components
    router.handle(deck.DeckAction("halt", "global", 1.0, "pressed"))
    halt.assert_called_once_with()
    pad_press(router, cancel_name, cancel_button)
    assert not panel._picking and not panel._search_field.is_editing
    panel.gui.on_engine_command.assert_not_called()


@pytest.mark.parametrize(
    "name,button",
    [(deck.DPAD_DOWN, None), (deck.SEQUENCE_CONTROL, deck.SELECT_BUTTON), ("volume_down", deck.CLOSE_POPUP_BUTTON)],
)
def test_deck_picker_stops_commands_held_before_opening(deck_picker, name, button):
    panel, router, _, _ = deck_picker
    panel.cancel()
    router.handle(deck.DeckAction(name, "focused", 1.0, "pressed", button=button))
    panel.gui.on_engine_command.assert_called()
    panel.gui.on_engine_command.reset_mock()
    panel.open_picker()
    for now in (10.0, 10.1, 10.6, 10.8):
        router.tick(now)
    router.handle(deck.DeckAction(name, "focused", 0.0, "released", button=button))
    assert not router._boosts and not router._sequences and not router._held_commands
    assert panel._picker_cursor is None
    panel.gui.on_engine_command.assert_not_called()


def test_deck_picker_highlight_does_not_check_radio_or_replace_active_green(deck_picker):
    """Active-state shading is removed; controller focus and selection remain visible."""
    panel, router, _, _ = deck_picker
    state = SwitchState()
    state._address = 1
    state.initialize(CommandScope.SWITCH, 1)
    state.comp_data.road_name = "Main siding"
    state._state = TMCC1SwitchCommandEnum.THRU
    panel.gui.state_store.states[(CommandScope.SWITCH, 1)] = state
    panel.set_sort("TMCC ID")
    pad_press(router, deck.DPAD_DOWN)
    rectangles = [options for kind, _, options in panel._picker.drawn if kind == "rectangle"]
    assert all(options["fill"] == mod.CARD_BG for options in rectangles)
    assert rectangles[0]["outline"] == mod.SELECTED_COLOR and rectangles[0]["width"] == 3
    assert all(options["width"] == 1 for options in rectangles[1:])
    assert len([kind for kind, _, _ in panel._picker.drawn if kind == "oval"]) == len(panel._candidates)
    panel.choose_candidate(0)
    rectangles = [options for kind, _, options in panel._picker.drawn if kind == "rectangle"]
    assert rectangles[0]["fill"] == mod.SELECTED_BG
    assert len([kind for kind, _, _ in panel._picker.drawn if kind == "oval"]) == len(panel._candidates) + 1
    pad_press(router, "bell", deck.BACK_PAGE_BUTTON)
    rectangles = [options for kind, _, options in panel._picker.drawn if kind == "rectangle"]
    assert all(options["fill"] == mod.CARD_BG for options in rectangles)
    assert len([kind for kind, _, _ in panel._picker.drawn if kind == "oval"]) == len(panel._candidates)


@pytest.mark.parametrize("invalid", ["deleted", "self_route"])
@pytest.mark.parametrize("name,button", [(deck.SEQUENCE_CONTROL, deck.SELECT_BUTTON), (deck.DPAD_RIGHT, None)])
def test_deck_picker_a_keeps_existing_component_validation(deck_picker, invalid, name, button):
    panel, router, _, _ = deck_picker
    if invalid == "self_route":
        known_route(panel, 12)
        panel.set_filter("Routes")
    else:
        panel._candidates[0][1].is_deleted = True
    pad_press(router, name, button)
    assert not panel.draft.components and panel._picking
    assert (
        "no longer available" in panel._status.value
        if invalid == "deleted"
        else "cannot include itself" in panel._status.value
    )
    panel.gui.on_engine_command.assert_not_called()


@pytest.mark.parametrize(
    "width,height,compact,system,available,bar_width",
    [
        (639, 800, True, "linux", 330, 38),
        (480, 800, True, "linux", 330, 38),
        (800, 1280, False, "linux", 590, 48),
        (800, 800, False, "linux", 287, 48),
        (600, 960, False, "darwin", 431, 30),
        (600, 960, False, "win32", 431, 30),
        (639, 800, True, "darwin", 240, 38),
    ],
)
def test_picker_size_and_page_navigation_follow_available_layout(
    panel, monkeypatch, width, height, compact, system, available, bar_width
):
    monkeypatch.setattr(mod, "platform", system)
    panel.gui.width, panel.gui.height = width, height
    monkeypatch.setattr(panel.gui, "compact", compact)
    panel.gui.emergency_box_width = width
    panel.build(Widget())
    panel.configure(12)
    for tmcc_id in range(1, 16):
        known_switch(panel, tmcc_id)
    panel.open_picker()
    panel.set_sort("TMCC ID")
    picker_space(panel, available)

    rows = available // panel.picker_row_height
    assert panel.picker_rows == rows
    assert panel._picker.options["height"] == rows * panel.picker_row_height
    assert 0 <= available - panel._picker.options["height"] < panel.picker_row_height
    bar = panel._picker_scrollbar
    assert panel._picker.options["width"] + panel.picker_bar_width == panel.content_width
    assert bar.options["width"] == bar.place_options["width"] == panel.picker_bar_width == bar_width
    assert bar.place_options["x"] == -bar_width
    assert bar.place_options["relheight"] == 1.0
    assert bar.master is panel._picker.master
    assert panel._picker.pack_options["padx"] == (0, panel.picker_bar_width)
    assert bar.get() == (0, rows / 15)
    bar.options["command"]("moveto", str(rows / 15))
    first = min(rows, 15 - rows)
    assert panel._picker.y == first * panel.picker_row_height
    event = SimpleNamespace(x=40, y=10)
    panel._scroll_start(panel._picker, event)
    panel._scroll_end(panel._picker, event, False)
    assert panel._candidate == (CommandScope.SWITCH, first + 1)
    bar.options["command"]("scroll", "99", "pages")
    assert bar.get()[1] == 1
    bar.options["command"]("scroll", "-99", "pages")
    assert bar.get()[0] == 0
    panel._search_field.value = "no match"
    panel._on_search(None, None, None)
    assert bar.get() == (0, 1)
    assert not panel._save_btn.enabled


@pytest.mark.parametrize("compact", [True, False])
def test_picker_scrollbar_replaces_page_buttons_and_matches_scroll_box(panel, monkeypatch, compact):
    monkeypatch.setattr(panel.gui, "compact", compact)
    mod.TouchScrollbar.reset_mock()
    panel.build(Widget())
    bar = panel._picker_scrollbar
    if compact:
        mod.TouchScrollbar.assert_called_once_with(
            panel._picker.master, command=panel.scroll_picker, width=38, min_thumb_length=32
        )
    else:
        mod.TouchScrollbar.assert_not_called()
        assert bar.options["orient"] == "vertical"
        assert bar.options["takefocus"] == 0
        assert bar.options["bg"] == mod.BAR_COLOR
        assert bar.options["troughcolor"] == mod.BAR_TROUGH_COLOR
        assert bar.options["activebackground"] == mod.BAR_ACTIVE_COLOR
        assert bar.options["highlightbackground"] == mod.BAR_EDGE_COLOR
    assert not hasattr(panel, "_picker_previous")
    assert not hasattr(panel, "_picker_next")


@pytest.mark.parametrize("action", ["search", "filter", "sort", "direction", "reopen"])
def test_picker_refresh_resets_scrollbar_and_keeps_selection_rules(panel, action):
    for tmcc_id in range(1, 16):
        known_switch(panel, tmcc_id, f"Switch {tmcc_id:02d}")
    known_route(panel, 4)
    panel.open_picker()
    panel.choose_candidate(14)
    bar = panel._picker_scrollbar
    bar.options["command"]("moveto", "1")
    assert bar.get()[0] > 0
    if action == "search":
        panel._search_field.value = "Switch 01"
        panel._on_search(None, None, None)
    elif action == "filter":
        panel.set_filter("Routes")
    elif action == "sort":
        panel.set_sort("TMCC ID")
    elif action == "direction":
        panel.toggle_sort_direction()
    else:
        panel.cancel()
        panel.open_picker()
    assert bar.get()[0] == 0
    assert bar.get() == panel._picker.yview()
    assert panel._save_btn.enabled == (action in {"sort", "direction"})
    if action in {"search", "filter"}:
        assert bar.get() == (0, 1)
        bar.options["command"]("scroll", "1", "pages")
        assert panel._picker.y == 0
    assert not panel.draft.components and not panel.draft.dirty


@pytest.mark.parametrize("desktop", [False, True])
def test_picker_scrollbar_arrows_move_one_row_without_selecting(panel, desktop, monkeypatch):
    monkeypatch.setattr(mod, "platform", "win32" if desktop else "linux")
    monkeypatch.setattr(panel.gui, "compact", not desktop)
    panel.build(Widget())
    panel.configure(12)
    for tmcc_id in range(1, 16):
        known_switch(panel, tmcc_id)
    panel.open_picker()
    bar = panel._picker_scrollbar
    bar.options["command"]("scroll", "1", "units")
    assert panel._picker.y == panel.picker_row_height
    assert bar.get() == panel._picker.yview()
    assert panel._candidate is None and not panel._save_btn.enabled
    bar.options["command"]("scroll", "-1", "units")
    assert bar.get()[0] == 0
    assert not panel.draft.components and not panel.draft.dirty


def test_steam_deck_picker_fits_four_touch_rows_in_original_height(panel):
    panel.open_picker()
    picker_space(panel, 210)
    assert panel.picker_rows == 4
    assert panel.picker_row_height - 4 >= 44
    assert panel._picker.options["height"] <= 3 * 70
    for tmcc_id in range(1, 6):
        known_switch(panel, tmcc_id)
    panel.open_picker()
    panel.set_sort("TMCC ID")
    event = SimpleNamespace(x=panel.content_width - 20, y=3.5 * panel.picker_row_height)
    panel._scroll_start(panel._picker, event)
    panel._scroll_end(panel._picker, event, False)
    assert panel._candidate == (CommandScope.SWITCH, 4)
    assert panel._save_btn.enabled
    panel.add_selected()
    assert panel.draft.components[0].tmcc_id == 4


@pytest.mark.parametrize("rows,remainder", [(1, 0), (2, 47), (4, 0), (7, 15), (10, 47), (0, 47)])
def test_picker_resize_uses_whole_rows_without_changing_entry_height(panel, rows, remainder):
    panel.open_picker()
    row_height = panel.picker_row_height
    picker_space(panel, rows * row_height + remainder)
    assert panel.picker_rows == rows
    assert panel.picker_row_height == row_height
    assert panel._picker.options["height"] == max(1, rows * row_height)
    assert panel._picker.master.winfo_reqheight() == panel._picker.options["height"]
    assert panel._picker_scrollbar.get() == (0, 1)


def test_picker_resize_preserves_selection_and_clamps_scroll_position(panel):
    for tmcc_id in range(1, 16):
        known_switch(panel, tmcc_id)
    panel.open_picker()
    picker_space(panel, 4 * panel.picker_row_height)
    panel.choose_candidate(14)
    panel.scroll_picker("moveto", "1")
    picker_space(panel, 7 * panel.picker_row_height + 10)
    assert panel.picker_rows == 7
    assert panel._picker.y == 8 * panel.picker_row_height
    assert panel._picker_scrollbar.get() == (8 / 15, 1)
    picker_space(panel, 2 * panel.picker_row_height)
    assert panel._picker.y == 8 * panel.picker_row_height
    assert panel._candidate == (CommandScope.SWITCH, 15)
    assert panel._save_btn.enabled
    assert not panel.draft.components and not panel.draft.dirty


def test_picker_resize_accounts_for_changes_to_controls_and_is_stable(panel):
    panel.open_picker()
    picker_space(panel, 300, overhead=280)
    assert panel.picker_rows == 6
    picker_space(panel, 300 - panel.picker_row_height, overhead=280 + panel.picker_row_height)
    assert panel.picker_rows == 5
    panel._picker.config = Mock(wraps=panel._picker.config)
    panel._resize_picker()
    panel._picker.config.assert_not_called()


@pytest.mark.parametrize("unavailable", ["editor", "hidden", "destroyed", "unmeasured"])
def test_picker_resize_ignores_unavailable_geometry(panel, unavailable):
    panel.open_picker()
    picker_space(panel, 240)
    if unavailable == "editor":
        panel.cancel()
    elif unavailable == "hidden":
        panel._picker_page.hide()
    elif unavailable == "destroyed":
        panel._picker_page.tk.winfo_exists = lambda: False
    else:
        panel._picker_page.tk.master.master.winfo_height.return_value = 1
    panel._picker.config = Mock(wraps=panel._picker.config)
    panel._resize_picker()
    panel._picker.config.assert_not_called()


def test_picker_resize_is_scheduled_once_for_geometry_changes(panel):
    panel.open_picker()
    picker_space(panel, 240)
    overlay = panel._picker_page.tk.master.master
    overlay.after_idle.reset_mock()
    panel._schedule_picker_resize()
    panel._schedule_picker_resize()
    overlay.after_idle.assert_called_once_with(panel._resize_picker)
    assert any(call.args[0] == "<Configure>" for call in overlay.bind.call_args_list)
    assert any(call.args[0] == "<Map>" for call in panel._picker_page.tk.bind.call_args_list)


@pytest.mark.parametrize("filter_name", ["Routes", "Switches"])
def test_steam_deck_picker_aligns_inline_details_and_truncates_long_names(panel, filter_name):
    long_name = "W" * 31
    known_switch(panel, 7, long_name)
    known_switch(panel, 8, "Short")
    route = known_route(panel, 4)
    route._road_name = "Yard exit"
    known_route(panel, 5)._road_name = long_name
    panel.open_picker()
    panel.set_filter(filter_name)
    texts = [(coords, options) for kind, coords, options in panel._picker.drawn if kind == "text"]
    assert len(texts) == 4 * len(panel._candidates)
    columns = None
    for index, (scope, state) in enumerate(panel._candidates):
        row = texts[index * 4 : index * 4 + 4]
        positions = [coords[0] for coords, _ in row]
        assert positions == sorted(positions)
        assert columns is None or columns == positions
        columns = positions
        assert all(coords[1] == (index + 0.5) * panel.picker_row_height for coords, _ in row)
        assert all(options["anchor"] == "w" for _, options in row)
        number = state.road_number if state.is_road_number else "—"
        assert [options["text"] for _, options in row[1:]] == [
            scope.title,
            f"· Road #{number}",
            f"· ID {state.tmcc_id:02d}",
        ]
        name = row[0][1]
        assert name["font"][1] == panel.gui.s_14
        assert name["width"] == 0
        assert positions[0] + len(name["text"]) * name["font"][1] < positions[1]
        if state.road_name == long_name:
            assert name["text"].endswith("…")
            assert len(name["text"]) < len(long_name)
    assert panel.gui.state_store.get_state(CommandScope.SWITCH, 7).road_name == long_name


@pytest.fixture(params=["darwin", "win32"])
def desktop_panel(panel, monkeypatch, request):
    monkeypatch.setattr(mod, "platform", request.param)
    monkeypatch.setattr(panel.gui, "compact", False)
    panel.gui.width, panel.gui.height = 600, 960
    panel.gui.emergency_box_width = 600
    panel.build(Widget())
    panel.configure(12)
    return panel


@pytest.mark.parametrize("filter_name", ["Routes", "Switches"])
def test_desktop_picker_double_click_adds_scrolled_component_and_returns_to_main(desktop_panel, filter_name):
    panel = desktop_panel
    for tmcc_id in range(1, 10):
        known_switch(panel, tmcc_id)
        known_route(panel, tmcc_id)
    panel.open_picker()
    panel.set_filter(filter_name)
    panel.set_sort("TMCC ID")
    panel.toggle_sort_direction()
    panel.choose_candidate(0)
    canvas = panel._picker
    canvas.yview_moveto(0.5)
    event = SimpleNamespace(x=40, y=10)
    index = int(canvas.canvasy(event.y) // panel.picker_row_height)
    scope, state = panel._candidates[index]
    assert index > 0

    canvas.bindings["<ButtonPress-1>"](event)
    canvas.bindings["<ButtonRelease-1>"](event)
    assert panel._candidate == (scope, state.tmcc_id)
    assert panel._picking and not panel.draft.components

    assert canvas.bindings["<Double-Button-1>"](event) == "break"
    canvas.bindings["<ButtonRelease-1>"](event)
    assert [component.tmcc_id for component in panel.draft.components] == [state.tmcc_id]
    assert panel.draft.components[0].is_route is (scope == CommandScope.ROUTE)
    assert panel.draft.dirty
    assert panel._selected == 0 and panel._gesture is None
    assert panel._main_page.visible and not panel._picker_page.visible and not panel._picking
    assert panel._save_btn.text == "Save Route"
    assert panel._lookup_route(12) is None

    canvas.bindings["<Double-Button-1>"](event)
    assert len(panel.draft.components) == 1


@pytest.mark.parametrize("location", ["above", "below", "empty"])
def test_desktop_picker_double_click_outside_rows_does_not_add_selection(desktop_panel, location):
    panel = desktop_panel
    known_switch(panel)
    panel.open_picker()
    panel.choose_candidate(0)
    if location == "empty":
        panel._search_field.value = "no matches"
        panel._on_search(None, None, None)
    event = SimpleNamespace(x=40, y=-1 if location == "above" else panel.picker_row_height + 10)

    assert panel._picker.bindings["<Double-Button-1>"](event) == "break"

    assert not panel.draft.components and not panel.draft.dirty
    assert panel._picking and panel._picker_page.visible and not panel._main_page.visible


@pytest.mark.parametrize("unavailable", ["deleted", "missing", "recursive"])
def test_desktop_picker_double_click_keeps_validation_errors_in_picker(desktop_panel, unavailable):
    panel = desktop_panel
    state = known_switch(panel)
    panel.open_picker()
    if unavailable == "recursive":
        known_route(panel, 12)
        panel.set_filter("Routes")
    elif unavailable == "deleted":
        state.is_deleted = True
    else:
        del panel.gui.state_store.states[(CommandScope.SWITCH, state.tmcc_id)]
    event = SimpleNamespace(x=40, y=10)

    assert panel._picker.bindings["<Double-Button-1>"](event) == "break"
    panel._picker.bindings["<ButtonRelease-1>"](event)

    assert not panel.draft.components and not panel.draft.dirty
    assert panel._picking and panel._picker_page.visible and not panel._main_page.visible
    assert ("cannot include itself" if unavailable == "recursive" else "no longer available") in panel._status.value


@pytest.mark.parametrize("platform", ["darwin", "win32", "linux"])
@pytest.mark.parametrize("compact", [False, True])
def test_double_click_is_limited_to_desktop_picker(panel, monkeypatch, platform, compact):
    monkeypatch.setattr(mod, "platform", platform)
    monkeypatch.setattr(panel.gui, "compact", compact)
    panel.build(Widget())
    assert ("<Double-Button-1>" in panel._picker.bindings) is (not compact and platform in {"darwin", "win32"})
    assert "<Double-Button-1>" not in panel._cards.bindings


def test_desktop_picker_keys_select_and_reveal_without_adding(desktop_panel):
    panel = desktop_panel
    for tmcc_id in range(1, 16):
        known_switch(panel, tmcc_id)
    panel.open_picker()
    panel.set_sort("TMCC ID")
    down, up = panel._picker.bindings["<Down>"], panel._picker.bindings["<Up>"]
    assert down(None) == "break"
    assert panel._candidate == (CommandScope.SWITCH, 1)
    for _ in range(20):
        down(None)
    assert panel._candidate == (CommandScope.SWITCH, 15)
    assert panel._picker.yview()[1] == 1
    assert panel._picker_scrollbar.get()[1] == 1
    for _ in range(20):
        assert up(None) == "break"
    assert panel._candidate == (CommandScope.SWITCH, 1)
    assert panel._picker.yview()[0] == 0
    assert panel._picker_scrollbar.get()[0] == 0
    assert not panel.draft.components and not panel.draft.dirty


@pytest.mark.parametrize(
    "filter_name,expected_scope", [("Routes", CommandScope.ROUTE), ("Switches", CommandScope.SWITCH)]
)
def test_desktop_picker_keys_use_current_filter_sort_and_scope(desktop_panel, filter_name, expected_scope):
    panel = desktop_panel
    known_switch(panel, 7, "Alpha")
    known_switch(panel, 3, "Zulu")
    known_route(panel, 7)._road_name = "Alpha route"
    known_route(panel, 3)._road_name = "Zulu route"
    panel.open_picker()
    panel.set_filter(filter_name)
    panel.set_sort("TMCC ID")
    panel.toggle_sort_direction()
    for scope, state in panel._candidates:
        panel._picker.bindings["<Down>"](None)
        assert panel._candidate == (scope, state.tmcc_id)
    panel._search_field.value = "Alpha"
    panel._on_search(None, None, None)
    panel._picker.bindings["<Up>"](None)
    assert panel._candidate == (expected_scope, 7)
    panel._search_field.value = "no matches"
    panel._on_search(None, None, None)
    for key in ("<Up>", "<Down>"):
        assert panel._picker.bindings[key](None) == "break"
    assert panel._candidate is None and not panel._save_btn.enabled


def test_desktop_card_keys_browse_without_reordering_or_editing(desktop_panel):
    panel = desktop_panel
    assert panel._cards.bindings["<Right>"](None) == "break"
    assert panel._selected is None
    state = known_route(panel, 12, [RouteComponent(i, i % 3) for i in range(16, 0, -1)])
    panel.configure(12, state)
    before = RouteComponent.to_bytes(panel.draft.components)
    for _ in range(20):
        assert panel._cards.bindings["<Right>"](None) == "break"
    assert panel._selected == 15 and panel._cards.xview()[1] == 1
    for _ in range(20):
        assert panel._cards.bindings["<Left>"](None) == "break"
    assert panel._selected == 0 and panel._cards.xview()[0] == 0
    assert RouteComponent.to_bytes(panel.draft.components) == before
    assert not panel.draft.dirty


def test_desktop_lists_receive_focus_without_stealing_inline_edits(desktop_panel):
    panel = desktop_panel
    for canvas, field in ((panel._cards, panel._name_field), (panel._picker, panel._search_field)):
        assert canvas.options["takefocus"] is True
        for event in ("<Map>", "<Enter>"):
            canvas.focus_set.reset_mock()
            canvas.bindings[event](None)
            canvas.focus_set.assert_called_once_with()
            field.is_editing = True
            canvas.focus_set.reset_mock()
            canvas.bindings[event](None)
            canvas.focus_set.assert_not_called()
            field.is_editing = False
        canvas.focus_set.reset_mock()
        canvas.bindings["<ButtonPress-1>"](SimpleNamespace(x=20, y=20))
        canvas.focus_set.assert_called_once_with()


def test_touch_lists_keep_touch_bindings_without_desktop_focus(panel):
    for canvas in (panel._cards, panel._picker):
        assert not canvas.options["takefocus"]
        assert not {"<Map>", "<Enter>", "<Left>", "<Right>", "<Up>", "<Down>"}.intersection(canvas.bindings)
        assert {"<B1-Motion>", "<MouseWheel>", "<Button-4>", "<Button-5>"}.issubset(canvas.bindings)


@pytest.mark.parametrize("horizontal", [False, True])
@pytest.mark.parametrize("delta,units", [(120, -1), (-240, 2), (1, -1), (-1, 1), (0, 0)])
def test_desktop_wheel_browses_both_lists(desktop_panel, horizontal, delta, units):
    panel = desktop_panel
    canvas = panel._cards if horizontal else panel._picker
    scroll = Mock()
    if horizontal:
        canvas.xview_scroll = scroll
    else:
        canvas.yview_scroll = scroll
    assert canvas.bindings["<MouseWheel>"](SimpleNamespace(delta=delta)) == "break"
    if delta:
        if mod.platform == "darwin":
            units = -delta
        if not horizontal:
            units *= panel.picker_row_height
        scroll.assert_called_once_with(units, "units")
    else:
        scroll.assert_not_called()
    if horizontal:
        scroll.reset_mock()
        assert canvas.bindings["<Shift-MouseWheel>"](SimpleNamespace(delta=-1)) == "break"
        scroll.assert_called_once_with(1, "units")
    assert not panel.draft.dirty


@pytest.mark.parametrize("desktop_panel", ["darwin"], indirect=True)
@pytest.mark.parametrize("horizontal", [False, True])
@pytest.mark.parametrize("dx,dy", [(0, -1), (0, 1), (0, -40), (0, 40), (-25, 0), (25, 0), (2, -30), (-30, 2), (0, 0)])
@pytest.mark.parametrize("signed", [False, True])
def test_mac_touch_surface_scrolls_by_pixels_without_editing(desktop_panel, horizontal, dx, dy, signed):
    panel = desktop_panel
    state = known_route(panel, 12, [RouteComponent(i, i % 3) for i in range(8, 0, -1)])
    panel.configure(12, state)
    if horizontal:
        canvas = panel._cards
        canvas.xview_moveto(0.4)
        before = canvas.x
    else:
        for tmcc_id in range(1, 16):
            known_switch(panel, tmcc_id)
        panel.open_picker()
        panel.choose_candidate(0)
        canvas = panel._picker
        canvas.yview_moveto(0.4)
        before = canvas.y
    selection = panel._selected, panel._candidate
    components = RouteComponent.to_bytes(panel.draft.components)
    packed = ((dx & 0xFFFF) << 16) | (dy & 0xFFFF)
    if signed and packed >= 0x80000000:
        packed -= 0x100000000

    assert canvas.bindings["<TouchpadScroll>"](SimpleNamespace(delta=packed)) == "break"

    movement = dx if horizontal and abs(dx) > abs(dy) else dy
    assert (canvas.x if horizontal else canvas.y) == pytest.approx(before - movement)
    assert (panel._selected, panel._candidate) == selection
    assert RouteComponent.to_bytes(panel.draft.components) == components
    assert not panel.draft.dirty


@pytest.mark.parametrize("desktop_panel", ["darwin"], indirect=True)
def test_mac_touch_surface_scroll_handles_empty_lists_and_boundaries(desktop_panel):
    panel = desktop_panel
    for canvas in (panel._cards, panel._picker):
        for packed in (0, 0x80008000, 0x7FFF7FFF):
            assert canvas.bindings["<TouchpadScroll>"](SimpleNamespace(delta=packed)) == "break"
        assert canvas.x == canvas.y == 0
    for tmcc_id in range(1, 16):
        known_switch(panel, tmcc_id)
    panel.open_picker()
    panel._picker.bindings["<TouchpadScroll>"](SimpleNamespace(delta=0x8000))
    assert panel._picker.yview()[1] == 1
    assert panel._picker_scrollbar.get()[1] == 1
    panel._picker.bindings["<TouchpadScroll>"](SimpleNamespace(delta=0x7FFF))
    assert panel._picker.yview()[0] == 0
    assert panel._picker_scrollbar.get()[0] == 0


@pytest.mark.parametrize("desktop_panel", ["darwin"], indirect=True)
def test_mac_older_tk_keeps_wheel_and_keyboard_navigation(desktop_panel, monkeypatch):
    bind = Canvas.bind

    def old_tk_bind(canvas, sequence, command):
        if sequence == "<TouchpadScroll>":
            raise mod.tk.TclError('bad event type or keysym "TouchpadScroll"')
        bind(canvas, sequence, command)

    monkeypatch.setattr(Canvas, "bind", old_tk_bind)
    panel = desktop_panel
    panel.build(Widget())
    panel.configure(12)
    for tmcc_id in range(1, 16):
        known_switch(panel, tmcc_id)
    panel.open_picker()
    panel.set_sort("TMCC ID")
    for canvas in (panel._cards, panel._picker):
        assert "<TouchpadScroll>" not in canvas.bindings
        assert "<MouseWheel>" in canvas.bindings
    panel._picker.bindings["<MouseWheel>"](SimpleNamespace(delta=-1))
    assert panel._picker.y == panel.picker_row_height
    panel._picker.bindings["<Down>"](None)
    assert panel._candidate == (CommandScope.SWITCH, 2)


@pytest.mark.parametrize("desktop_panel", ["win32"], indirect=True)
def test_windows_retains_its_existing_scroll_bindings(desktop_panel):
    for canvas in (desktop_panel._cards, desktop_panel._picker):
        assert "<TouchpadScroll>" not in canvas.bindings
        assert "<MouseWheel>" in canvas.bindings


@pytest.mark.parametrize("width", [639, 800])
def test_component_cards_are_twenty_five_percent_shorter(panel, width):
    panel.gui.width = width
    assert panel.card_height == int(int(panel.row_height * 3.5) * 0.75)


@pytest.mark.parametrize("compact,height,gap", [(True, 800, 0), (False, 800, 0), (False, 1280, 16)])
def test_metadata_group_and_pi_section_spacing(panel, monkeypatch, compact, height, gap):
    panel.gui.width = panel.gui.emergency_box_width = 800
    panel.gui.height = height
    monkeypatch.setattr(panel.gui, "compact", compact)
    panel.build(Widget())
    group = panel._metadata_box
    assert group.options["text"] == "Info"
    assert group.options["bd"] == 1
    assert panel._name_field.parent.parent.parent is group
    assert panel._number_field.parent.parent.parent is group
    assert panel.section_gap == gap
    siblings = panel._main_page.children
    move_index = siblings.index(panel._earlier_btn.parent.parent)
    add_index = siblings.index(panel._add_btn.parent.parent)
    assert add_index == move_index + (2 if gap else 1)
    if gap:
        assert siblings[add_index - 1].options["height"] == gap
        index = siblings.index(group)
        assert siblings[index - 1].options["height"] == gap
        assert siblings[index + 1].options["height"] == gap
        assert panel.footer_pad_px == gap
    else:
        assert panel.footer_pad_px == 4


@pytest.mark.parametrize("width,height,system", [(800, 1280, "linux"), (631, 1009, "darwin"), (631, 1009, "win32")])
@pytest.mark.parametrize("existing", [False, True])
def test_info_tmcc_id_is_read_only_aligned_and_follows_edited_route(
    panel, monkeypatch, width, height, system, existing
):
    class PlainText(Widget):
        pass

    monkeypatch.setattr(mod, "Text", PlainText)
    monkeypatch.setattr(mod, "platform", system)
    panel.gui.width = panel.gui.emergency_box_width = width
    panel.gui.height = height
    monkeypatch.setattr(panel.gui, "compact", False)
    panel.build(Widget())

    for tmcc_id in (2, 42):
        state = known_route(panel, tmcc_id, [RouteComponent(7, 0), RouteComponent(4, 3)]) if existing else None
        if state:
            state._road_name = "Yard departure"
            state._road_number = "0099"
        panel.configure(tmcc_id, state)
        field = panel._tmcc_id_field
        rows = panel._metadata_box.children
        assert [row.children[0].value for row in rows] == ["Route Name", "Route #", "TMCC ID"]
        assert type(field) is PlainText
        assert field.value == f"{tmcc_id:02d}"
        assert field.parent.parent is rows[2]
        assert rows[2].children == [rows[2].children[0], field.parent]
        assert "editor" not in field.options
        assert "on_commit" not in field.options
        assert not hasattr(field, "when_clicked")
        for editable in (panel._name_field, panel._number_field):
            row = editable.parent.parent
            assert row.options == rows[2].options
            assert row.children[0].options == {**rows[2].children[0].options, "text": row.children[0].value}
            assert editable.parent.options == field.parent.options
            for option in ("align", "size", "height", "anchor", "padx", "bd"):
                assert editable.options[option] == field.options[option]
        panel._name_field.value = "Main line"
        panel._number_field.value = "1234"
        panel._on_metadata(None, None, None)
        if existing:
            panel.select_relative(1)
        assert field.value == f"{tmcc_id:02d}"
        assert panel.draft.tmcc_id == tmcc_id


def test_compact_info_keeps_two_rows(panel):
    assert panel._tmcc_id_field is None
    assert [row.children[0].value for row in panel._metadata_box.children] == ["Route Name", "Route #"]


def test_header_and_single_line_selection_follow_card_order(panel):
    assert panel._count.value == "0 of 16 cards used"
    known_switch(panel, 33, "Suspended Right")
    known_switch(panel, 34, "Suspended Left")
    panel.configure(2, known_route(panel, 2, [RouteComponent(33, 1), RouteComponent(34, 1)]))
    assert panel._route_label.value == "Route 02"
    assert panel._count.value == "2 of 16 cards used"
    assert panel._route_label.parent is panel._count.parent
    summary = panel._route_label.parent
    assert summary.options["align"] == "top"
    assert summary.options.get("width") != "fill"
    assert [child.value for child in summary.children] == ["Route 02", "   ·   ", "2 of 16 cards used"]
    assert panel._route_label.options["align"] == "left"
    assert panel._count.options["align"] == "left"
    assert panel._selection.value == "Card 1: Suspended Right"
    assert panel._selection.options["height"] == 1
    panel.select_relative(1)
    assert panel._selection.value == "Card 2: Suspended Left"
    panel.move_selected(-1)
    assert panel._selection.value == "Card 1: Suspended Left"
    panel.remove_selected()
    assert panel._selection.value == "Card 1: Suspended Right"
    assert panel._count.value == "1 of 16 cards used"


def test_touch_card_browsing_hint(panel):
    assert panel._main_page.children[1].value == "Tap a card to change it; swipe to browse."


def test_desktop_card_browsing_hint(desktop_panel):
    assert desktop_panel._main_page.children[1].value == "Select a card to modify; scroll or use ← / → to browse."


@pytest.mark.parametrize("width,height,compact", [(800, 1280, False), (631, 1009, False), (639, 800, True)])
def test_search_field_reclaims_label_space_and_uses_search_commit_label(panel, monkeypatch, width, height, compact):
    panel.gui.width = panel.gui.emergency_box_width = width
    panel.gui.height = height
    monkeypatch.setattr(panel.gui, "compact", compact)
    panel.build(Widget())
    field = panel._search_field
    row = field.parent.parent
    caption = row.children[0]
    assert caption.value == "Search"
    assert caption.options["width"] == 6
    assert row.options["width"] == panel.content_width
    assert field.parent.options["width"] == "fill"
    assert field.options["width"] == "fill"
    assert field.options["field_name"] == "Search"
    assert field.options["commit_label"] == "Search"
    assert field.options["on_commit"] == panel._on_search
    for metadata in (panel._name_field, panel._number_field):
        assert metadata.parent.parent.children[0].options["width"] == 12
        assert metadata.options["commit_label"] == "Save"


@pytest.mark.parametrize(
    "width,height,compact,system,extra,pad_x,pad_y,spare",
    [
        (639, 800, True, "linux", 0, 4, 3, 200),
        (800, 1280, False, "linux", 6, 5, 4, 0),
        (800, 1280, False, "linux", 11, 5, 4, 56),
        (800, 1280, False, "linux", 18, 5, 4, 200),
        (631, 1009, False, "darwin", 7, 4, 3, 200),
        (631, 1009, False, "win32", 7, 4, 3, 200),
    ],
)
def test_route_builder_buttons_have_shading_relief_and_surrounding_space(
    panel, monkeypatch, width, height, compact, system, extra, pad_x, pad_y, spare
):
    panel.gui.width = panel.gui.emergency_box_width = width
    panel.gui.height = height
    monkeypatch.setattr(panel.gui, "compact", compact)
    monkeypatch.setattr(mod, "platform", system)
    panel.build(Widget())
    panel.build_footer(Widget())
    overlay = panel._main_page.tk.master.master
    baseline = panel.button_height_extra
    overlay.winfo_height.return_value = 941 + spare
    overlay.winfo_reqheight.side_effect = lambda: 941 + 8 * (panel.button_height_extra - baseline)
    panel._resize_buttons()
    assert panel.row_height == max(44, int(44 * width / 639))
    assert panel.card_height == int(int(panel.row_height * 3.5) * 0.75)
    assert (panel.button_pad_x, panel.button_pad_y) == (pad_x, pad_y)
    assert panel.control_row_height == panel.row_height + extra + 2 * pad_y
    buttons = [
        panel._previous_btn,
        panel._next_btn,
        panel._earlier_btn,
        panel._later_btn,
        panel._add_btn,
        panel._remove_btn,
        panel._clear_btn,
        panel._cancel_btn,
        panel._clear_route_btn,
        panel._save_btn,
        *panel._filter_btns,
        *panel._sort_btns,
    ]
    for field in (panel._name_field, panel._number_field, panel._search_field):
        row = field.parent.parent
        buttons.extend(child for slot in row.children for child in slot.children if child.text == "Edit")
        assert row.options["height"] == panel.control_row_height
    assert len(buttons) == 18
    for button in buttons:
        assert button.options["relief"] == "raised"
        assert button.options["bd"] >= 2
        assert button.bg == mod.BUTTON_BG
        assert button.options["activebackground"] != button.bg
        assert button.parent.options["padx"] >= 4
        assert button.parent.options["pady"] >= 3
        assert button.parent.options["height"] - 2 * button.parent.options["pady"] >= 44
        original_height = (
            panel.card_height if button in (panel._previous_btn, panel._next_btn) else panel.row_height + 2 * pad_y
        )
        assert button.parent.options["height"] == original_height + extra
        assert (button.parent.options["padx"], button.parent.options["pady"]) == (pad_x, pad_y)
    assert panel._positions.options["height"] == panel.control_row_height
    assert panel._show_unlabeled.parent.options["height"] == panel.control_row_height
    assert panel._cards.options["height"] == panel.card_height
    if not compact:
        assert panel._tmcc_id_field.parent.parent.options["height"] == panel.control_row_height


@pytest.fixture
def pi_panel(panel, monkeypatch):
    panel.gui.width = panel.gui.emergency_box_width = 800
    panel.gui.height = 1280
    monkeypatch.setattr(panel.gui, "compact", False)
    panel.build(Widget())
    panel.build_footer(Widget())
    overlay = panel._main_page.tk.master.master
    overlay.winfo_height.return_value = 1060
    overlay.winfo_reqheight.side_effect = lambda: 941 + 8 * (panel.button_height_extra - 6)
    return panel


def test_pi_buttons_resize_stably_and_shrink_when_space_is_reduced(pi_panel):
    panel = pi_panel
    overlay = panel._main_page.tk.master.master
    panel._resize_buttons()
    assert panel.button_height_extra == 18
    assert panel._save_btn.parent.options["height"] == 81
    for slot, _ in panel._button_slots:
        slot.tk.config = Mock(wraps=slot.tk.config)
    panel._resize_buttons()
    assert panel.button_height_extra == 18
    for slot, _ in panel._button_slots:
        slot.tk.config.assert_not_called()
    overlay.winfo_height.return_value = 941
    panel._resize_buttons()
    assert panel.button_height_extra == 6
    assert panel._save_btn.parent.options["height"] == 69
    overlay.winfo_height.return_value = 1060
    panel._resize_buttons()
    assert panel.button_height_extra == 18


@pytest.mark.parametrize("unavailable", ["picker", "hidden", "destroyed", "unmeasured"])
def test_pi_button_resize_ignores_unavailable_editor_geometry(pi_panel, unavailable):
    panel = pi_panel
    if unavailable == "picker":
        panel.open_picker()
    elif unavailable == "hidden":
        panel._main_page.hide()
    elif unavailable == "destroyed":
        panel._main_page.tk.winfo_exists = lambda: False
    else:
        panel._main_page.tk.master.master.winfo_height.return_value = 1
    panel._resize_buttons()
    assert panel.button_height_extra == 6
    assert not panel._button_resize_pending


def test_pi_button_resize_is_scheduled_once_and_retained_in_picker(pi_panel):
    panel = pi_panel
    overlay = panel._main_page.tk.master.master
    panel._schedule_button_resize()
    panel._schedule_button_resize()
    overlay.after_idle.assert_called_once_with(panel._resize_buttons)
    assert any(call.args[0] == "<Configure>" for call in overlay.bind.call_args_list)
    assert any(call.args[0] == "<Map>" for call in panel._main_page.tk.bind.call_args_list)
    panel._resize_buttons()
    panel.open_picker()
    assert panel.button_height_extra == 18
    assert panel._search_btn.parent.options["height"] == panel.control_row_height
    panel._schedule_button_resize()
    assert [invocation.args for invocation in overlay.after_idle.call_args_list] == [
        (panel._resize_buttons,),
        (panel._resize_picker,),
    ]
    assert not panel._button_resize_pending


def test_switch_radios_use_large_indicators_and_keep_exclusive_draft_selection(panel):
    add_switch(panel)
    for radio in panel._radios:
        assert radio.options["indicatoron"] is False
        assert radio.options["compound"] == "left"
        assert radio.options["image"].width() >= 24
        assert radio.options["selectimage"].width() >= 24
        assert radio.options["image"].pixels != radio.options["selectimage"].pixels
        assert radio.grid_options["padx"] >= 4 and radio.grid_options["pady"] >= 3
    for value, flag in (("out", 1), ("thru", 0)):
        panel._position.set(value)
        next(r for r in panel._radios if r.options["value"] == value).options["command"]()
        assert panel.draft.components[0].flags == flag
        assert sum(r.options["background"] == mod.SELECTED_BG for r in panel._radios) == 1
    panel.remove_selected()
    assert all(r.options["state"] == "disabled" for r in panel._radios)


def test_picker_indicators_are_large_circles_not_font_glyphs(panel):
    known_switch(panel)
    panel.open_picker()
    rings = [coords for kind, coords, _options in panel._picker.drawn if kind == "oval"]
    assert len(rings) == 1
    assert rings[0][2] - rings[0][0] >= 24
    panel.choose_candidate(0)
    assert len([kind for kind, _, _ in panel._picker.drawn if kind == "oval"]) == 2


@pytest.mark.parametrize("filter_name", ["Routes", "Switches"])
@pytest.mark.parametrize("selected", [False, True])
def test_picker_backgrounds_match_catalog_state_and_preserve_selection(panel, filter_name, selected):
    """Catalog state colors no longer apply here; only selection changes the background."""
    switch = SwitchState()
    switch._address = 7
    switch.initialize(CommandScope.SWITCH, 7)
    switch.comp_data.road_name = "Main siding"
    panel.gui.state_store.states[(CommandScope.SWITCH, 7)] = switch
    route = known_route(panel, 7, [RouteComponent(7, 0)])
    route._signature = {"S7": True}
    panel.open_picker()
    panel.set_filter(filter_name)

    for active in (True, False, None):
        switch._state = {True: TMCC1SwitchCommandEnum.THRU, False: TMCC1SwitchCommandEnum.OUT, None: None}[active]
        route._current_state = {"S7": active}
        for index in range(len(panel._candidates)):
            if selected:
                panel.choose_candidate(index)
            else:
                panel._draw_picker()
            rows = [options for kind, _, options in panel._picker.drawn if kind == "rectangle"]
            for row_index, row in enumerate(rows):
                is_selected = selected and row_index == index
                assert row["fill"] == (mod.SELECTED_BG if is_selected else mod.CARD_BG)
                assert row["outline"] == (mod.SELECTED_COLOR if is_selected else "#c1c8d0")
            dots = [
                options for kind, _, options in panel._picker.drawn if kind == "oval" and options["fill"] != "white"
            ]
            assert len(dots) == int(selected)
            assert panel._save_btn.enabled is selected


def test_long_card_names_fit_without_changing_the_full_selection_label(panel):
    known_switch(panel, name="W" * 31)
    panel.open_picker()
    panel.choose_candidate(0)
    panel.add_selected()

    names = [
        (item, options["text"])
        for item, (kind, _, options) in enumerate(panel._cards.drawn)
        if kind == "text" and options["text"].startswith("WW")
    ]
    assert len(names) == 1
    item, name = names[0]
    assert name.endswith("…")
    bounds = panel._cards.bbox(item)
    assert bounds[3] - bounds[1] <= panel.card_height * 0.35
    assert panel._selection.value == "Card 1: " + "W" * 31


def test_add_edit_and_remove_only_change_the_draft(panel):
    add_switch(panel)
    assert panel.draft.components[0].is_thru
    assert panel._selected == 0
    panel.set_position(1)
    assert panel.draft.dirty
    assert [(c.tmcc_id, c.is_out) for c in panel.draft.components] == [(7, True)]
    assert panel._lookup_route(12) is None
    assert panel._main_page.visible
    assert not hasattr(panel, "_id_field")
    panel.remove_selected()
    assert not panel.draft.components
    assert not panel._remove_btn.enabled
    assert "Tap Add" in panel._selection.value


def test_empty_provisional_route_can_be_opened_without_display_fallback_metadata(panel):
    state = known_route(panel, 12)
    panel.configure(12, state)
    assert panel.draft.components == ()
    assert panel.draft.road_name == panel.draft.road_number == ""
    assert not panel.draft.dirty


def test_database_clear_is_a_three_second_hold_only_footer_button(panel):
    button = panel._clear_route_btn
    assert isinstance(button, HoldWidget)
    assert button.text == "Clear"
    assert button.options["hold_threshold"] == 3.0
    assert button.options["show_hold_progress"] is True
    assert button.options["cancel_on_leave"] is True
    assert button.options.get("on_press") is None
    assert button.options.get("command") is None
    assert button.options.get("on_repeat") is None
    assert button.on_hold == panel.clear_route
    assert button.parent.parent is panel._cancel_btn.parent.parent
    assert button.parent.parent is panel._save_btn.parent.parent
    assert not button.enabled
    state = known_route(panel, 12)
    panel.configure(12, state)
    assert button.enabled
    assert "Hold Clear for 3 seconds" in panel._status.value


@pytest.mark.parametrize("flags", [0, 2])
def test_clear_deletes_only_the_edited_route_from_base3_and_discards_draft(panel, monkeypatch, flags):
    state = known_route(panel, 12, [RouteComponent(7, flags)])
    other = known_route(panel, 4)
    panel.configure(12, state)
    panel.set_position(1)
    panel._name_field.value = "Unsaved name"
    panel._number_field.is_editing = panel._number_field.is_changed = True
    panel.gui.app.yesno = Mock(side_effect=AssertionError("The hold already confirms clearing"))
    monkeypatch.setattr(panel.gui, "active_state", other, raising=False)
    panel._close = Mock(side_effect=lambda: panel.confirm_close())
    clear = Mock(wraps=state.clear)
    monkeypatch.setattr(state, "clear", clear)
    clear_record = Mock()
    monkeypatch.setattr(state, "clear_record", clear_record)
    monkeypatch.setattr(
        ComponentStateStore,
        "delete_state",
        lambda target: panel.gui.state_store.states.pop((target.scope, target.tmcc_id)),
    )
    send = Mock()
    monkeypatch.setattr(mod.BaseReq, "process_sync_reqs", send)

    panel._clear_route_btn.on_hold()

    clear.assert_called_once_with(notify=False, clear_db=True)
    clear_record.assert_called_once_with(state)
    assert state.is_deleted
    assert panel._lookup_route(12) is None
    assert panel._lookup_route(4) is other
    assert not other.is_deleted
    panel.gui._message_queue.put.assert_called_once_with((panel.gui._rebuild_state_caches, [state]))
    panel._close.assert_called_once()
    panel.gui.app.yesno.assert_not_called()
    assert panel.draft is None
    assert panel._state is None
    assert not panel._number_field.is_editing
    assert not panel._save_btn.enabled
    assert not panel._clear_route_btn.enabled
    panel.save()
    panel.clear_route()
    send.assert_not_called()
    clear.assert_called_once()


def test_successful_clear_hides_panel_through_popup_manager(panel, monkeypatch):
    state = known_route(panel, 12, [RouteComponent(7, 0)])
    panel.configure(12, state)
    panel.set_position(1)
    panel._name_field.value = "Unsaved name"
    panel.gui.app.yesno = Mock(side_effect=AssertionError("Clear must not prompt to discard"))
    panel.gui.locked = RLock
    manager = PopupManager(panel.gui)
    monkeypatch.setattr(panel.gui, "popup_manager", manager, raising=False)
    panel._overlay = overlay = Widget()
    overlay.confirm_close = panel.confirm_close
    overlay.tk.place_forget = Mock()
    manager._state.current_popup = overlay
    manager._post_close_actions[id(overlay)] = panel._on_closed
    underlying = Widget(visible=False)
    manager._state.on_close_show = underlying
    monkeypatch.setattr(state, "clear_record", Mock())
    monkeypatch.setattr(
        ComponentStateStore,
        "delete_state",
        lambda target: panel.gui.state_store.states.pop((target.scope, target.tmcc_id)),
    )

    assert panel.visible
    panel._clear_route_btn.on_hold()

    assert state.is_deleted
    assert not panel.visible
    assert manager.current_popup is None
    assert underlying.visible
    overlay.tk.place_forget.assert_called_once()
    panel.gui.app.yesno.assert_not_called()


@pytest.mark.parametrize("unavailable", ["missing", "deleted", "nondeletable"])
def test_clear_rechecks_route_availability_at_hold_completion(panel, monkeypatch, unavailable):
    state = known_route(panel, 12)
    panel.configure(12, state)
    clear = Mock()
    monkeypatch.setattr(state, "clear", clear)
    if unavailable == "missing":
        panel.gui.state_store.states.pop((CommandScope.ROUTE, 12))
    elif unavailable == "deleted":
        state._deleted = True
    else:
        monkeypatch.setattr(RouteState, "is_deletable", property(lambda _self: False))
    panel.clear_route()
    clear.assert_not_called()
    assert not panel._clear_route_btn.enabled
    assert panel.draft is not None


def test_clear_is_disabled_while_choosing_a_component(panel, monkeypatch):
    state = known_route(panel, 12)
    panel.configure(12, state)
    clear = Mock()
    monkeypatch.setattr(state, "clear", clear)
    panel.open_picker()
    assert not panel._clear_route_btn.enabled
    panel.clear_route()
    clear.assert_not_called()
    panel.cancel()
    assert panel._clear_route_btn.enabled


@pytest.mark.parametrize("failure", [False, OSError("offline")])
def test_failed_clear_keeps_unsaved_route_open(panel, monkeypatch, failure):
    state = known_route(panel, 12, [RouteComponent(7, 0)])
    panel.configure(12, state)
    panel.set_position(1)
    original = panel.draft
    clear = Mock(return_value=False, side_effect=failure if isinstance(failure, Exception) else None)
    monkeypatch.setattr(state, "clear", clear)
    panel._close = Mock()
    panel.clear_route()
    clear.assert_called_once_with(notify=False, clear_db=True)
    panel._close.assert_not_called()
    assert panel.draft is original and panel.draft.dirty
    assert "not cleared" in panel._status.value
    assert not state.is_deleted


def test_closing_or_reconfiguring_cancels_a_pending_clear_hold(panel):
    panel._clear_route_btn.cancel_interaction.reset_mock()
    panel._on_closed()
    panel._clear_route_btn.cancel_interaction.assert_called_once()
    panel._clear_route_btn.cancel_interaction.reset_mock()
    panel.configure(4, known_route(panel, 4))
    panel._clear_route_btn.cancel_interaction.assert_called_once()


def test_editing_switch_position_preserves_other_flag_bits(panel):
    panel.draft = mod.RouteDraft(12, [RouteComponent(7, 0x81)])
    panel._selected = 0
    panel.set_position(0)
    assert panel.draft.components[0].flags == 0x80
    panel.set_position(1)
    assert panel.draft.components[0].flags == 0x81


def test_nested_route_add_is_draft_only_and_has_no_switch_controls(panel):
    state = known_route(panel, components=[RouteComponent(7, 0)])
    panel.open_picker()
    panel.set_filter("Routes")
    panel.choose_candidate(0)
    panel.save()
    assert panel.draft.components[0].is_route
    assert panel._selection.value == "Card 1: Route 4"
    assert panel._count.value == "1 of 16 cards used"
    card_text = [options["text"] for kind, _, options in panel._cards.drawn if kind == "text"]
    assert card_text == ["1   ROUTE", "Route 4", "ID 04"]
    assert all(radio.options["state"] == "disabled" for radio in panel._radios)
    panel.set_position(0)
    assert panel.draft.components[0].is_route
    assert state.components[0].tmcc_id == 7
    assert panel._lookup_route(12) is None


@pytest.mark.parametrize("indirect", [False, True])
def test_recursive_routes_are_blocked_with_an_explanation(panel, indirect):
    known_route(panel, 12)
    if indirect:
        known_route(panel, 4, [RouteComponent(12, 3)])
    panel.open_picker()
    panel.set_filter("Routes")
    panel.choose_candidate(
        next(i for i, (_, state) in enumerate(panel._candidates) if state.tmcc_id == (4 if indirect else 12))
    )
    panel.add_selected()
    assert not panel.draft.components
    assert panel._picking
    assert panel._status.value == "Route 12 cannot include itself, directly or through another route."


def test_unloaded_nested_route_is_not_added(panel):
    state = RouteState()
    state._address = 4
    panel.gui.state_store.states[(CommandScope.ROUTE, 4)] = state
    panel.open_picker()
    panel.set_filter("Routes")
    panel.choose_candidate(0)
    panel.add_selected()
    assert not panel.draft.components
    assert panel._picking
    assert "load" in panel._status.value.lower()


def test_navigation_reaches_all_sixteen_without_reordering(panel):
    for tmcc_id in range(16, 0, -1):
        panel.draft.set_component(None, tmcc_id, 0, panel._lookup_route)
    panel.select_row(0)
    before = RouteComponent.to_bytes(panel.draft.components)
    assert not panel._add_btn.enabled
    panel.select_relative(99)
    assert panel._selected == 15
    assert panel._cards.x > 0
    assert not panel._next_btn.enabled
    assert RouteComponent.to_bytes(panel.draft.components) == before
    panel.remove_selected()
    assert panel._selected == 14
    assert panel._add_btn.enabled
    panel.select_relative(-99)
    assert panel._selected == 0
    assert panel._cards.x == 0
    assert not panel._previous_btn.enabled


def test_move_keeps_selection_on_same_component_and_does_not_sort(panel):
    add_switch(panel, 7)
    add_switch(panel, 3)
    panel.move_selected(-1)
    assert [c.tmcc_id for c in panel.draft.components] == [3, 7]
    assert panel._selected == 0
    assert not panel._earlier_btn.enabled
    panel.move_selected(1)
    assert [c.tmcc_id for c in panel.draft.components] == [7, 3]
    assert panel._selected == 1
    assert not panel._later_btn.enabled


def test_clear_all_requires_confirmation_and_preserves_metadata(panel):
    add_switch(panel)
    panel.draft.set_metadata("Yard", "0012")
    panel.clear_components()
    assert panel.draft.components
    panel.gui.app.yesno = lambda *_args: True
    panel.clear_components()
    assert not panel.draft.components
    assert panel._selected is None
    assert panel.draft.road_name == "Yard"


@pytest.mark.parametrize("filter_name", ["Routes", "Switches"])
def test_add_to_route_requires_a_current_selection(panel, filter_name):
    known_switch(panel)
    known_route(panel)
    panel.open_picker()
    panel.set_filter(filter_name)
    assert panel._save_btn.text == "Add to Route"
    assert panel._candidate is None
    assert not panel._save_btn.enabled
    panel.save()
    assert panel.draft.components == ()
    panel.set_sort("TMCC ID")
    panel.toggle_sort_direction()
    assert not panel._save_btn.enabled

    event = SimpleNamespace(x=40, y=10)
    panel._scroll_start(panel._picker, event)
    panel._scroll_end(panel._picker, event, False)
    assert panel._candidate is not None
    assert panel._save_btn.enabled
    panel.set_sort("Name")
    assert panel._save_btn.enabled
    panel._search_field.value = "no matches"
    panel._on_search(None, None, None)
    assert panel._candidate is None
    assert not panel._save_btn.enabled
    panel._search_field.value = ""
    panel._on_search(None, None, None)
    assert not panel._save_btn.enabled
    panel._navigate_list(1, False)
    assert panel._save_btn.enabled
    panel.cancel()
    assert panel._save_btn.text == "Save Route"
    assert panel._save_btn.enabled
    panel.open_picker()
    assert panel._candidate is None
    assert not panel._save_btn.enabled


def test_picker_scope_order_and_show_unlabeled_checkbox(panel):
    panel.open_picker()
    assert [button.text.removeprefix("● ") for button in panel._filter_btns] == ["Routes", "Switches"]
    checkbox = panel._show_unlabeled
    assert checkbox.text == "Show Unlabeled"
    assert checkbox.value == 0
    assert checkbox.enabled
    assert checkbox.parent.options["grid"] == [2, 0]
    assert checkbox.parent.options["height"] == panel.control_row_height
    widths = [widget.parent.options["width"] for widget in (*panel._filter_btns, checkbox)]
    assert sum(widths) == panel.content_width
    assert widths[2] > widths[0] == widths[1]
    assert checkbox.options["indicatoron"] is False
    assert checkbox.options["image"].width() >= 24
    assert checkbox.options["selectimage"].pixels != checkbox.options["image"].pixels
    panel._filter_btns[0].command()
    assert panel._filter == "Routes"
    assert not checkbox.enabled
    assert [button.text for button in panel._filter_btns] == ["● Routes", "Switches"]
    panel._filter_btns[1].command()
    assert checkbox.enabled
    assert [button.text for button in panel._filter_btns] == ["Routes", "● Switches"]


@pytest.mark.parametrize("user_defined", [True, False, None])
@pytest.mark.parametrize("labeled", [True, False])
def test_picker_filters_switches_by_is_user_defined_not_display_labels(panel, user_defined, labeled):
    switch = known_switch(panel)
    switch.is_user_defined = user_defined
    switch.is_road_name = switch.is_road_number = labeled
    panel.open_picker()
    assert panel._candidates == ([(CommandScope.SWITCH, switch)] if user_defined else [])
    panel._show_unlabeled.value = 1
    panel._show_unlabeled.command()
    assert panel._candidates == [(CommandScope.SWITCH, switch)]
    panel.choose_candidate(0)
    panel.add_selected()
    assert [component.tmcc_id for component in panel.draft.components] == [switch.tmcc_id]


@pytest.mark.parametrize("show_unlabeled", [0, 1])
def test_show_unlabeled_never_includes_deleted_or_out_of_range_switches(panel, show_unlabeled):
    for tmcc_id in (0, 7, 100):
        known_switch(panel, tmcc_id, deleted=tmcc_id == 7).is_user_defined = False
    panel.open_picker()
    panel._show_unlabeled.value = show_unlabeled
    panel._show_unlabeled.command()
    assert panel._candidates == []
    assert not panel._save_btn.enabled


def test_show_unlabeled_clears_hidden_selection_and_cursor_and_preserves_draft(panel):
    for tmcc_id in range(1, 10):
        known_switch(panel, tmcc_id).is_user_defined = False
    panel.draft.set_metadata("Keep this route", "12")
    panel.open_picker()
    assert not panel._candidates
    panel._show_unlabeled.value = 1
    panel._show_unlabeled.command()
    panel.set_sort("TMCC ID")
    panel.choose_candidate(8)
    panel.pad_step(0)
    assert panel._picker.yview()[0] > 0
    assert panel._candidate == panel._picker_cursor == (CommandScope.SWITCH, 9)
    assert panel._save_btn.enabled
    panel._show_unlabeled.value = 0
    panel._show_unlabeled.command()
    assert panel._candidate is None and panel._picker_cursor is None
    assert not panel._candidates and not panel._save_btn.enabled
    assert panel._picker_scrollbar.get() == (0, 1)
    assert panel._picker_count.value.startswith("0 available")
    assert panel.draft.road_name == "Keep this route" and panel.draft.road_number == "12"
    assert not panel.draft.components


def test_show_unlabeled_preserves_filter_sort_search_and_is_ignored_for_routes(panel):
    known_switch(panel, 1, "Alpha")
    known_switch(panel, 2, "Alpha unlabeled").is_user_defined = False
    known_switch(panel, 3, "Zulu unlabeled").is_user_defined = False
    route = known_route(panel, 4)
    route._road_name = "Alpha route"
    panel.open_picker()
    panel.set_sort("TMCC ID")
    panel.toggle_sort_direction()
    panel._search_field.value = "ALP"
    panel._on_search(None, None, None)
    panel.choose_candidate(0)
    panel._show_unlabeled.value = 1
    panel._show_unlabeled.command()
    assert [state.tmcc_id for _, state in panel._candidates] == [2, 1]
    assert panel._candidate == (CommandScope.SWITCH, 1)
    assert panel._save_btn.enabled
    panel.set_filter("Routes")
    assert not panel._show_unlabeled.enabled
    assert panel._candidates == [(CommandScope.ROUTE, route)]
    assert panel._candidate is None and not panel._save_btn.enabled
    panel.cancel()
    panel.open_picker()
    assert panel._show_unlabeled.value == 1
    assert not panel._show_unlabeled.enabled
    assert panel._candidates == [(CommandScope.ROUTE, route)]
    panel.set_filter("Switches")
    assert panel._show_unlabeled.enabled and panel._show_unlabeled.value == 1
    assert [state.tmcc_id for _, state in panel._candidates] == [2, 1]
    assert (panel._sort, panel._descending, panel._search_field.value) == ("TMCC ID", True, "ALP")
    panel._show_unlabeled.value = 0
    panel._show_unlabeled.command()
    assert [state.tmcc_id for _, state in panel._candidates] == [1]
    panel.set_filter("Routes")
    assert panel._candidates == [(CommandScope.ROUTE, route)]
    assert not panel.draft.dirty


def test_picker_filter_sort_search_and_choices_are_remembered(panel):
    known_switch(panel, 7, "Alpha")
    known_switch(panel, 3, "zulu")
    known_switch(panel, 8, "Deleted", deleted=True)
    known_route(panel, 7)
    panel.open_picker()
    assert [state.tmcc_id for _, state in panel._candidates] == [7, 3]
    panel.set_filter("Routes")
    assert [(scope, state.tmcc_id) for scope, state in panel._candidates] == [(CommandScope.ROUTE, 7)]
    panel.set_filter("Switches")
    assert {scope for scope, _ in panel._candidates} == {CommandScope.SWITCH}
    panel.set_sort("TMCC ID")
    assert [state.tmcc_id for _, state in panel._candidates] == [3, 7]
    panel.toggle_sort_direction()
    assert [state.tmcc_id for _, state in panel._candidates] == [7, 3]
    panel.cancel()
    panel.open_picker()
    assert (panel._filter, panel._sort, panel._descending) == ("Switches", "TMCC ID", True)
    panel._search_field.value = "ALP"
    panel._on_search(None, None, None)
    assert [(scope, state.tmcc_id) for scope, state in panel._candidates] == [(CommandScope.SWITCH, 7)]
    panel.choose_candidate(0)
    panel._search_field.value = "no match"
    panel._on_search(None, None, None)
    assert not panel._candidates
    assert not panel._save_btn.enabled
    assert panel._candidate is None


@pytest.mark.parametrize("filter_name", ["Routes", "Switches"])
@pytest.mark.parametrize("show_unlabeled", [0, 1])
@pytest.mark.parametrize("search", ["ALP", "no match", "   "])
def test_search_button_clears_text_and_restores_filtered_sorted_list(panel, filter_name, show_unlabeled, search):
    known_switch(panel, 7, "Alpha")
    known_switch(panel, 3, "Zulu")
    known_switch(panel, 8, "Deleted", deleted=True)
    known_switch(panel, 9, "Alpha unlabeled").is_user_defined = False
    known_route(panel, 7)._road_name = "Alpha route"
    known_route(panel, 4)._road_name = "Yard route"
    panel.open_picker()
    panel._show_unlabeled.value = show_unlabeled
    panel.set_filter(filter_name)
    panel.set_sort("TMCC ID")
    panel.toggle_sort_direction()
    candidates = panel._candidates.copy()
    field = panel._search_field
    button = field.parent.parent.children[1].children[0]
    assert button.text == "Edit"
    button.command()
    assert field.is_editing
    field.cancel_edit()

    field.value = search
    panel._on_search(field, search, "")
    assert button.text == "Clear"
    assert panel._candidates == [
        (scope, state) for scope, state in candidates if search.strip().casefold() in state.road_name.casefold()
    ]
    panel.cancel()
    panel.open_picker()
    assert button.text == "Clear"
    button.command()

    assert field.value == ""
    assert not field.is_editing
    assert button.text == "Edit"
    assert panel._candidates == candidates
    assert panel._picker_count.value.startswith(f"{len(candidates)} available")
    assert panel._picker.yview()[0] == 0
    assert (panel._filter, panel._sort, panel._descending) == (filter_name, "TMCC ID", True)
    assert panel._candidate is None
    assert not panel._save_btn.enabled
    assert not panel.draft.dirty
    button.command()
    assert field.is_editing


def test_search_can_still_be_edited_by_selecting_text_and_cleared_during_edit(panel):
    known_switch(panel)
    panel.open_picker()
    field = panel._search_field
    button = field.parent.parent.children[1].children[0]
    field.value = "Main"
    panel._on_search(field, "Main", "")
    assert button.text == "Clear"
    field.when_clicked()
    assert field.is_editing
    button.command()
    assert field.value == ""
    assert not field.is_editing
    assert button.text == "Edit"
    assert len(panel._candidates) == 1


def test_clearing_search_in_editor_restores_edit_button_without_changing_metadata_buttons(panel):
    known_switch(panel)
    panel.open_picker()
    field = panel._search_field
    button = field.parent.parent.children[1].children[0]
    field.value = "Main"
    panel._on_search(field, "Main", "")
    assert button.text == "Clear"
    field.value = ""
    panel._on_search(field, "", "Main")
    assert button.text == "Edit"
    for metadata in (panel._name_field, panel._number_field):
        metadata.value = "12"
        edit = metadata.parent.parent.children[1].children[0]
        assert edit.text == "Edit"
        edit.command()
        assert metadata.is_editing


def test_picker_selection_distinguishes_route_and_switch_with_same_id(panel):
    known_switch(panel, 7)
    known_route(panel, 7)
    panel.open_picker()
    panel.choose_candidate(0)
    assert panel._candidate == (CommandScope.SWITCH, 7)
    panel.set_filter("Routes")
    assert panel._candidate is None and panel._picker_cursor is None
    assert not panel._save_btn.enabled
    panel.choose_candidate(0)
    assert panel._candidate == (CommandScope.ROUTE, 7)
    panel.add_selected()
    assert panel.draft.components[0].is_route


def test_picker_rechecks_deleted_components_before_adding(panel):
    state = known_switch(panel)
    panel.open_picker()
    panel.choose_candidate(0)
    state.is_deleted = True
    panel.add_selected()
    assert not panel.draft.components
    assert "no longer available" in panel._status.value


def test_picker_arrows_and_tap_use_scrolled_coordinates(panel):
    for tmcc_id in range(1, 10):
        known_switch(panel, tmcc_id)
    panel.open_picker()
    panel.set_sort("TMCC ID")
    bar = panel._picker_scrollbar
    assert bar.get()[0] == 0
    assert bar.get()[1] < 1
    bar.options["command"]("scroll", str(panel.picker_rows), "units")
    assert bar.get()[0] > 0
    event = SimpleNamespace(x=40, y=10)
    panel._scroll_start(panel._picker, event)
    panel._scroll_end(panel._picker, event, False)
    assert panel._candidate == (CommandScope.SWITCH, panel.picker_rows + 1)
    bar.options["command"]("moveto", "1")
    assert bar.get()[1] == 1


def test_swiping_cards_does_not_select_or_reorder_and_tap_does(panel):
    add_switch(panel, 7)
    add_switch(panel, 3)
    original = RouteComponent.to_bytes(panel.draft.components)
    panel.select_row(0)
    start, end = SimpleNamespace(x=300, y=50), SimpleNamespace(x=20, y=50)
    panel._scroll_start(panel._cards, start)
    panel._scroll_drag(panel._cards, end, True)
    panel._scroll_end(panel._cards, end, True)
    assert panel._cards.dragged
    assert panel._selected == 0
    assert RouteComponent.to_bytes(panel.draft.components) == original
    tap = SimpleNamespace(x=panel.card_width + 12, y=30)
    panel._scroll_start(panel._cards, tap)
    panel._scroll_end(panel._cards, tap, True)
    assert panel._selected == 1
    assert RouteComponent.to_bytes(panel.draft.components) == original


def test_cancel_protects_components_metadata_and_pending_keyboard_edits(panel):
    panel._name_field.is_editing = panel._name_field.is_changed = True
    assert panel.confirm_close() is False
    panel._end_inline_edits()
    panel._name_field.value = "Yard departure"
    panel._on_metadata(None, None, None)
    assert panel.draft.dirty
    assert panel.confirm_close() is False
    panel.gui.app.yesno = lambda *_args: True
    mod.RouteDiscardDialog.return_value.result = True
    assert panel.confirm_close() is True
    assert panel._lookup_route(12) is None


@pytest.mark.parametrize("width,height,compact", [(639, 800, True), (800, 1280, False)])
@pytest.mark.parametrize("result", [None, False, True])
def test_touch_cancel_uses_large_pane_centered_confirmation(panel, monkeypatch, width, height, compact, result):
    panel.gui.width, panel.gui.height = width, height
    monkeypatch.setattr(panel.gui, "compact", compact)
    panel.gui.emergency_box_width = width
    monkeypatch.setattr(panel.gui, "root", SimpleNamespace(tk=object()), raising=False)
    panel.gui.app.yesno = Mock(side_effect=AssertionError("touch displays must use the larger dialog"))
    panel.draft.set_metadata("Unsaved", "")
    mod.RouteDiscardDialog.return_value.result = result
    assert panel.confirm_close() is bool(result)
    args, kwargs = mod.RouteDiscardDialog.call_args
    assert args == (panel.gui.root.tk,)
    assert width * 0.8 <= kwargs["width"] < width
    assert kwargs["text_size"] >= 18
    assert kwargs["button_height"] >= 64
    assert panel.draft.dirty


def test_desktop_cancel_uses_new_wording_in_native_dialog(desktop_panel):
    desktop_panel.draft.set_metadata("Unsaved", "")
    desktop_panel.gui.app.yesno = Mock(return_value=True)
    assert desktop_panel.confirm_close()
    desktop_panel.gui.app.yesno.assert_called_once_with("Discard route changes?", "Discard unsaved route changes?")
    mod.RouteDiscardDialog.assert_not_called()


def test_discard_dialog_has_large_message_and_buttons_with_safe_default(monkeypatch):
    frame, label = Mock(), Mock()
    keep, discard = Mock(), Mock()
    button = Mock(side_effect=[keep, discard])
    monkeypatch.setattr(mod.tk, "Frame", frame)
    monkeypatch.setattr(mod.tk, "Label", label)
    monkeypatch.setattr(mod.tk, "Button", button)
    dialog = object.__new__(mod.RouteDiscardDialog)
    dialog._width, dialog._text_size, dialog._button_height = 540, 18, 64
    dialog.bind = Mock()
    dialog.body("body")
    frame.assert_called_with("body", width=540, height=128)
    assert label.call_args.kwargs["text"] == "Discard unsaved route changes?"
    assert label.call_args.kwargs["font"] == ("Helvetica", 18)
    dialog.buttonbox()
    frame.assert_called_with(dialog, width=540, height=64)
    assert button.call_args_list[0].kwargs["text"] == "Keep Editing"
    assert button.call_args_list[0].kwargs["command"] == dialog.cancel
    assert button.call_args_list[1].kwargs["text"] == "Discard"
    assert button.call_args_list[1].kwargs["command"] == dialog.ok
    assert dialog.initial_focus is keep
    dialog.bind.assert_any_call("<Escape>", dialog.cancel)
    dialog.bind.assert_any_call("<Return>", dialog._on_return)


@pytest.mark.parametrize("discard_focused", [False, True])
def test_discard_dialog_return_only_discards_when_explicitly_focused(discard_focused):
    dialog = object.__new__(mod.RouteDiscardDialog)
    dialog._discard_btn = object()
    dialog.focus_get = Mock(return_value=dialog._discard_btn if discard_focused else object())
    dialog.ok, dialog.cancel = Mock(), Mock()
    dialog._on_return()
    assert dialog.ok.call_count == int(discard_focused)
    assert dialog.cancel.call_count == int(not discard_focused)
    dialog.apply()
    assert dialog.result is True


def test_picker_cancel_does_not_discard_route_or_prompt_for_search(panel):
    add_switch(panel)
    before = RouteComponent.to_bytes(panel.draft.components)
    panel.open_picker()
    panel._search_field.value = "Main"
    panel.gui.app.yesno = lambda *_args: pytest.fail("picker cancel must not discard route")
    panel.cancel()
    assert not panel._picking
    assert RouteComponent.to_bytes(panel.draft.components) == before
    mod.RouteDiscardDialog.assert_not_called()


def test_unchanged_route_can_close_without_prompt(panel):
    panel.gui.app.yesno = lambda *_args: pytest.fail("unchanged route should not prompt")
    panel.open_picker()
    panel.cancel()
    assert panel.confirm_close()
    mod.RouteDiscardDialog.assert_not_called()


def test_invalid_metadata_is_visible_and_prevents_save(panel):
    panel._number_field.value = "abcd"
    panel._on_metadata(None, None, None)
    assert panel.draft.road_number == ""
    assert panel.confirm_close() is False
    panel._close = lambda: pytest.fail("invalid save must stay open")
    panel.save()
    assert "Route not saved" in panel._status.value
    assert panel._lookup_route(12) is None


def test_existing_metadata_edits_are_isolated_and_reopening_discards_them(panel):
    state = known_route(panel, 12, [RouteComponent(7, 0)])
    state._road_name = "Yard Departure"
    state._road_number = "0012"
    panel.configure(12, state)
    assert (panel._name_field.value, panel._number_field.value) == ("Yard Departure", "0012")
    panel._name_field.value = "Main Line"
    panel._number_field.value = "1234"
    panel._on_metadata(None, None, None)
    panel.set_position(1)
    assert panel.draft.dirty
    assert (state.road_name, state.road_number) == ("Yard Departure", "0012")
    assert state.components[0].is_thru
    panel._on_closed()
    panel.configure(12, state)
    assert (panel.draft.road_name, panel.draft.road_number) == ("Yard Departure", "0012")
    assert panel.draft.components[0].is_thru
    assert not panel.draft.dirty


def test_save_new_route_creates_provisional_target_only_on_save(panel, monkeypatch):
    calls = []

    def create(scope, tmcc_id):
        assert scope == CommandScope.ROUTE
        calls.append(tmcc_id)
        return known_route(panel, tmcc_id)

    panel.gui.create_provisional_component = create
    panel._close = lambda: None
    monkeypatch.setattr(mod.BaseReq, "process_sync_reqs", lambda reqs, **_kwargs: calls.append(reqs))
    add_switch(panel)
    assert not calls
    panel.save()
    assert calls[0] == 12
    assert calls[1][-1] is panel._lookup_route(12)
    assert len(calls[1]) == 4
    assert not panel.draft.dirty


def test_failed_save_keeps_unsaved_draft_open(panel, monkeypatch):
    add_switch(panel)
    known_route(panel, 12)

    def fail(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(mod.BaseReq, "process_sync_reqs", fail)
    panel._close = lambda: pytest.fail("failed save must stay open")
    panel.save()
    assert panel.draft.dirty
    assert "offline" in panel._status.value


def test_save_submits_metadata_and_ordered_components_without_operating_layout(panel, monkeypatch):
    add_switch(panel, 7)
    add_switch(panel, 3)
    state = known_route(panel, 12)
    panel._name_field.value = "Yard Departure"
    panel._number_field.value = "0012"
    events = []
    monkeypatch.setattr(mod.BaseReq, "process_sync_reqs", lambda reqs, **kw: events.append((reqs, kw)))
    panel._close = lambda: events.append("close")
    panel.gui.ops_mode = lambda **kw: events.append(kw)
    panel.save()

    reqs, kwargs = events[0]
    assert kwargs == {"do_async": True}
    assert reqs[-1] is state
    assert len(reqs) == 4
    assert reqs[2].start == 0x60
    assert reqs[2].data_bytes == b"\x00\x07\x00\x03" + b"\xff" * 28
    assert events[1:] == ["close", {"update_info": True, "state": state}]
    assert panel.gui._scope_tmcc_ids[CommandScope.ROUTE] == 12
    assert panel.draft.road_name == "Yard Departure"
    assert not state.components
    assert not panel.draft.dirty


class PanelRecorder:
    def __init__(self, _gui):
        self.visible = False
        self.overlay = object()
        self.configured = []

    def configure(self, *args):
        self.configured.append(args)


def _gui(tmcc_id="42"):
    gui = gui_mod.EngineGui.__new__(gui_mod.EngineGui)
    gui.scope = CommandScope.ROUTE
    gui._cv = RLock()
    gui._route_builder_panel = None
    gui._state_store = Store()
    gui.tmcc_id_text = SimpleNamespace(value=tmcc_id)
    gui._scope_tmcc_ids = {CommandScope.ROUTE: 7}
    gui.opened = []
    gui.show_popup = lambda *args, **kwargs: gui.opened.append((args, kwargs))
    gui.warnings = []
    gui._app = SimpleNamespace(warn=lambda *args: gui.warnings.append(args))
    return gui


def test_builder_uses_entered_id_not_previous_ops_selection_and_does_not_create_record(monkeypatch):
    monkeypatch.setattr(gui_mod, "RouteBuilderPanel", PanelRecorder)
    gui = _gui("42")
    gui.on_route_builder()
    assert gui._route_builder_panel.configured == [(42, None)]
    assert gui._state_store.states == {}
    assert gui.opened == [((gui._route_builder_panel.overlay,), {"hide_image_box": True})]


@pytest.mark.parametrize("flags", [0x02, 0x06, 0x82, 0xFE])
def test_builder_opens_existing_route_from_ops_and_preserves_out_variant(panel, monkeypatch, flags):
    raw = bytes([flags, 7, 0, 3]) + b"\xff" * 28
    state = known_route(panel, 12, RouteComponent.from_bytes(raw))
    gui = _gui("12")
    gui._state_store = panel.gui.state_store
    gui._route_builder_panel = panel
    panel._overlay = Widget(visible=False)
    send = Mock()
    monkeypatch.setattr(mod.BaseReq, "process_sync_reqs", send)

    gui.on_route_builder()

    assert gui.opened == [((panel.overlay,), {"hide_image_box": True})]
    assert not gui.warnings
    assert panel._main_page.visible
    assert panel._position.get() == "out"
    assert panel.draft.components[0].flags == flags
    assert not panel.draft.dirty
    send.assert_not_called()
    panel.set_position(1)
    assert panel.draft.components[0].flags == flags
    assert not panel.draft.dirty
    panel._close = Mock()
    panel.save()
    requests = send.call_args.args[0]
    assert requests[2].data_bytes == raw
    assert requests[-1] is state
    panel._close.assert_called_once()
    assert state.components[0].flags == flags


@pytest.mark.parametrize("tmcc_id", ["00", "01", "99", "bad"])
def test_builder_rejects_invalid_new_route_ids(tmcc_id):
    gui = _gui(tmcc_id)
    gui.on_route_builder()
    assert gui.warnings
    assert not gui.opened


def test_declining_discard_prevents_scope_navigation():
    gui = _gui()
    gui._route_builder_panel = SimpleNamespace(visible=True)
    gui._popup = SimpleNamespace(close_requested=lambda: False)
    gui.on_scope(CommandScope.SWITCH)
    assert gui.scope == CommandScope.ROUTE
