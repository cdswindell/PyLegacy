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

from math import ceil
from threading import RLock
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import pytest

from pytrain.db.component_state import RouteState, SwitchState
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.components import RouteComponent
from pytrain.gui.controller import engine_gui as gui_mod
from pytrain.gui.controller import route_builder_panel as mod
from pytrain.gui.controller.popup_manager import PopupManager
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum


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
        self.tk = SimpleNamespace(
            master=self.parent.tk if isinstance(self.parent, Widget) else None,
            config=lambda **kw: self.options.update(kw),
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
        self.options = kwargs
        self.bindings = {}
        self.drawn = []
        self.x = self.y = 0
        self.dragged = []
        self.focus_set = Mock()

    def config(self, **kwargs):
        self.options.update(kwargs)

    def pack(self, **_kwargs):
        pass

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
        lines = ceil(len(options["text"]) * size / options["width"])
        return 0, 0, options["width"], lines * (size + 5)

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
        callback = self.options.get("yscrollcommand")
        if callback:
            callback(self.y / total, min(1, (self.y + self.options["height"]) / total))

    def xview_scroll(self, delta, _units):
        self.xview_moveto((self.x + delta * 20) / self.options["scrollregion"][2])

    def yview(self):
        total = self.options["scrollregion"][3]
        return self.y / total, min(1, (self.y + self.options["height"]) / total)

    def yview_scroll(self, delta, _units):
        self.yview_moveto((self.y + delta * self.options["yscrollincrement"]) / self.options["scrollregion"][3])

    def canvasx(self, x):
        return self.x + x

    def canvasy(self, y):
        return self.y + y

    def scan_mark(self, x, y):
        self.mark = (x, y)

    def scan_dragto(self, x, y, gain):
        self.dragged.append((x, y, gain))


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
    for name in ("Box", "TitleBox", "PushButton", "Text", "EditableText"):
        monkeypatch.setattr(mod, name, Widget)
    monkeypatch.setattr(mod, "RouteDiscardDialog", Mock(return_value=SimpleNamespace(result=False)))
    monkeypatch.setattr(mod, "HoldButton", HoldWidget)
    monkeypatch.setattr(mod.tk, "Canvas", Canvas)
    monkeypatch.setattr(mod.tk, "StringVar", Variable)
    monkeypatch.setattr(mod.tk, "Radiobutton", Canvas)
    monkeypatch.setattr(mod.tk, "PhotoImage", PhotoImage)
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


def known_switch(panel, tmcc_id=7, name="Main siding", *, deleted=False):
    state = SimpleNamespace(
        tmcc_id=tmcc_id,
        name=name,
        road_name=name,
        is_road_name=True,
        road_number=f"{tmcc_id:04d}",
        is_road_number=True,
        is_deleted=deleted,
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


@pytest.mark.parametrize(
    "width,height,compact,system,rows",
    [
        (639, 800, True, "linux", 3),
        (800, 1280, False, "linux", 6),
        (800, 800, False, "linux", 3),
        (600, 960, False, "darwin", 6),
        (600, 960, False, "win32", 6),
        (639, 800, True, "darwin", 3),
    ],
)
def test_picker_size_and_page_navigation_follow_available_layout(
    panel, monkeypatch, width, height, compact, system, rows
):
    monkeypatch.setattr(mod, "platform", system)
    panel.gui.width, panel.gui.height, panel.gui.compact = width, height, compact
    panel.gui.emergency_box_width = width
    panel.build(Widget())
    panel.configure(12)
    for tmcc_id in range(1, 16):
        known_switch(panel, tmcc_id)
    panel.open_picker()
    panel.set_sort("TMCC ID")

    assert panel._picker.options["height"] == rows * panel.picker_row_height
    panel.scroll_picker(1)
    assert panel._picker.y == rows * panel.picker_row_height
    event = SimpleNamespace(x=40, y=10)
    panel._scroll_start(panel._picker, event)
    panel._scroll_end(panel._picker, event, False)
    assert panel._candidate == (CommandScope.SWITCH, rows + 1)
    panel.scroll_picker(99)
    assert not panel._picker_next.enabled
    panel.scroll_picker(-99)
    assert not panel._picker_previous.enabled
    panel._search_field.value = "no match"
    panel._on_search(None, None, None)
    assert not panel._picker_next.enabled
    assert not panel._picker_previous.enabled


@pytest.fixture(params=["darwin", "win32"])
def desktop_panel(panel, monkeypatch, request):
    monkeypatch.setattr(mod, "platform", request.param)
    panel.gui.compact = False
    panel.gui.width, panel.gui.height = 600, 960
    panel.gui.emergency_box_width = 600
    panel.build(Widget())
    panel.configure(12)
    return panel


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
    assert not panel._picker_next.enabled
    for _ in range(20):
        assert up(None) == "break"
    assert panel._candidate == (CommandScope.SWITCH, 1)
    assert panel._picker.yview()[0] == 0
    assert not panel._picker_previous.enabled
    assert not panel.draft.components and not panel.draft.dirty


def test_desktop_picker_keys_use_current_filter_sort_and_scope(desktop_panel):
    panel = desktop_panel
    known_switch(panel, 7, "Alpha")
    known_switch(panel, 3, "Zulu")
    known_route(panel, 7)
    panel.open_picker()
    panel.set_filter("All")
    panel.set_sort("TMCC ID")
    panel.toggle_sort_direction()
    for scope, state in panel._candidates:
        panel._picker.bindings["<Down>"](None)
        assert panel._candidate == (scope, state.tmcc_id)
    panel._search_field.value = "Alpha"
    panel._on_search(None, None, None)
    panel._picker.bindings["<Up>"](None)
    assert panel._candidate == (CommandScope.SWITCH, 7)
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
    assert not panel._picker_next.enabled
    panel._picker.bindings["<TouchpadScroll>"](SimpleNamespace(delta=0x7FFF))
    assert panel._picker.yview()[0] == 0
    assert not panel._picker_previous.enabled


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
def test_metadata_group_and_pi_section_spacing(panel, compact, height, gap):
    panel.gui.width = panel.gui.emergency_box_width = 800
    panel.gui.height, panel.gui.compact = height, compact
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
    panel.gui.height, panel.gui.compact = height, False
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
def test_search_field_reclaims_label_space_and_uses_search_commit_label(panel, width, height, compact):
    panel.gui.width = panel.gui.emergency_box_width = width
    panel.gui.height, panel.gui.compact = height, compact
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


def test_route_builder_buttons_have_shading_relief_and_surrounding_space(panel):
    buttons = [
        panel._previous_btn,
        panel._next_btn,
        panel._earlier_btn,
        panel._later_btn,
        panel._add_btn,
        panel._remove_btn,
        panel._clear_btn,
        panel._picker_previous,
        panel._picker_next,
        panel._cancel_btn,
        panel._clear_route_btn,
        panel._save_btn,
        *panel._filter_btns,
        *panel._sort_btns,
    ]
    for field in (panel._name_field, panel._number_field, panel._search_field):
        row = field.parent.parent
        buttons.extend(child for slot in row.children for child in slot.children if child.text == "Edit")
    assert len(buttons) == 21
    for button in buttons:
        assert button.options["relief"] == "raised"
        assert button.options["bd"] >= 2
        assert button.bg == mod.BUTTON_BG
        assert button.options["activebackground"] != button.bg
        assert button.parent.options["padx"] >= 4
        assert button.parent.options["pady"] >= 3
        assert button.parent.options["height"] - 2 * button.parent.options["pady"] >= 44


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


@pytest.mark.parametrize("filter_name", ["Switches", "Routes", "All"])
@pytest.mark.parametrize("selected", [False, True])
def test_picker_backgrounds_match_catalog_state_and_preserve_selection(panel, filter_name, selected):
    switch = SwitchState()
    switch._address = 7
    switch.initialize(CommandScope.SWITCH, 7)
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
                assert row["fill"] == (
                    mod.ACTIVE_STATE_BG if active else mod.SELECTED_BG if is_selected else mod.CARD_BG
                )
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
    manager = panel.gui.popup_manager = PopupManager(panel.gui)
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


@pytest.mark.parametrize("filter_name", ["Switches", "Routes", "All"])
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


def test_picker_filter_sort_search_and_choices_are_remembered(panel):
    known_switch(panel, 7, "Alpha")
    known_switch(panel, 3, "zulu")
    known_switch(panel, 8, "Deleted", deleted=True)
    known_route(panel, 7)
    panel.open_picker()
    assert [state.tmcc_id for _, state in panel._candidates] == [7, 3]
    panel.set_filter("All")
    assert len(panel._candidates) == 3
    assert {scope for scope, _ in panel._candidates} == {CommandScope.SWITCH, CommandScope.ROUTE}
    panel.set_sort("TMCC ID")
    assert [state.tmcc_id for _, state in panel._candidates] == [3, 7, 7]
    panel.toggle_sort_direction()
    assert [state.tmcc_id for _, state in panel._candidates] == [7, 7, 3]
    panel.cancel()
    panel.open_picker()
    assert (panel._filter, panel._sort, panel._descending) == ("All", "TMCC ID", True)
    panel._search_field.value = "ALP"
    panel._on_search(None, None, None)
    assert [(scope, state.tmcc_id) for scope, state in panel._candidates] == [(CommandScope.SWITCH, 7)]
    panel.choose_candidate(0)
    panel._search_field.value = "no match"
    panel._on_search(None, None, None)
    assert not panel._candidates
    assert not panel._save_btn.enabled
    assert panel._candidate is None


@pytest.mark.parametrize("filter_name", ["Switches", "Routes", "All"])
@pytest.mark.parametrize("search", ["ALP", "no match", "   "])
def test_search_button_clears_text_and_restores_filtered_sorted_list(panel, filter_name, search):
    known_switch(panel, 7, "Alpha")
    known_switch(panel, 3, "Zulu")
    known_switch(panel, 8, "Deleted", deleted=True)
    known_route(panel, 7)._road_name = "Alpha route"
    known_route(panel, 4)._road_name = "Yard route"
    panel.open_picker()
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
    panel.set_filter("All")
    panel.choose_candidate(next(i for i, (scope, _) in enumerate(panel._candidates) if scope == CommandScope.ROUTE))
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
    assert not panel._picker_previous.enabled
    assert panel._picker_next.enabled
    panel.scroll_picker(1)
    assert panel._picker_previous.enabled
    event = SimpleNamespace(x=40, y=10)
    panel._scroll_start(panel._picker, event)
    panel._scroll_end(panel._picker, event, False)
    assert panel._candidate == (CommandScope.SWITCH, mod.PICKER_ROWS + 1)
    panel.scroll_picker(99)
    assert not panel._picker_next.enabled


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
def test_touch_cancel_uses_large_pane_centered_confirmation(panel, width, height, compact, result):
    panel.gui.width, panel.gui.height, panel.gui.compact = width, height, compact
    panel.gui.emergency_box_width = width
    panel.gui.root = SimpleNamespace(tk=object())
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
