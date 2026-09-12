#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""Offline Route Builder preview: ../bin/python scripts/routepreview.py [--pi] [--check].

Uses the real popup and editor widgets with sample records, without a Base 3 connection.
The Pi preview supplies target screen dimensions to the portrait keyboard positioning code.
--check exercises both pages and touch editors, checks their bounds, and exits.
"""

import argparse
import sys
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from guizero import App

from pytrain.db.component_state import RouteState, SwitchState
from pytrain.db.components import RouteComponent
from pytrain.gui.controller import route_builder_panel
from pytrain.gui.controller.popup_manager import PopupManager
from pytrain.gui.controller.route_builder_panel import RouteBuilderPanel
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum


class PreviewStore:
    def __init__(self):
        self.states = {}
        for tmcc_id, name in enumerate(
            (
                "East turnout",
                "Main siding",
                "Station approach",
                "West yard",
                "Longest switch name on the track",
                "W" * 31,
            ),
            1,
        ):
            state = self.add(SwitchState(), CommandScope.SWITCH, tmcc_id, name)
            state._state = TMCC1SwitchCommandEnum.THRU if tmcc_id % 2 else TMCC1SwitchCommandEnum.OUT
        route = self.add(RouteState(), CommandScope.ROUTE, 4, "Yard exit")
        route.comp_data.components = [RouteComponent(4, 1)]
        route = self.add(RouteState(), CommandScope.ROUTE, 12, "Yard departure")
        route.comp_data.components = [RouteComponent(5, 0), RouteComponent(2, 1), RouteComponent(4, 3)]

    def add(self, state, scope, tmcc_id, name):
        state._address = tmcc_id
        state.initialize(scope, tmcc_id)
        state._road_name = name
        state._road_number = f"{tmcc_id:04d}"
        self.states[scope, tmcc_id] = state
        return state

    def get_state(self, scope, tmcc_id, create=False):
        assert not create
        return self.states.get((scope, tmcc_id))

    def get_all(self, scope):
        return [state for (key, _), state in self.states.items() if key == scope]


def check_bounds(app, overlay, panel, width, budget, label):
    app.tk.update_idletasks()
    requested = (overlay.tk.winfo_reqwidth(), overlay.tk.winfo_reqheight())
    print(f"{label}: popup requests {requested[0]} × {requested[1]}; budget {width} × {budget}", flush=True)
    assert requested[0] <= width and requested[1] <= budget, (label, requested)
    for widget in (panel._save_btn.tk, panel._cancel_btn.tk, panel._clear_route_btn.tk):
        assert widget.winfo_ismapped()
        assert widget.winfo_height() >= 44
        assert widget.winfo_rooty() + widget.winfo_height() <= app.tk.winfo_rooty() + budget
        assert widget.winfo_x() >= panel.button_pad_x
        assert widget.winfo_y() >= panel.button_pad_y
    if not panel._picking:
        route, count = panel._route_label.tk, panel._count.tk
        summary = route.master
        separator = summary.winfo_children()[1]
        assert separator.cget("text") == "   ·   "
        assert count.winfo_rootx() - (route.winfo_rootx() + route.winfo_width()) == separator.winfo_width()
        assert abs(2 * summary.winfo_x() + summary.winfo_width() - panel._main_page.tk.winfo_width()) <= 2
        assert panel._selection.value.startswith(f"Card {panel._selected + 1}: ")
        assert "\n" not in panel._selection.value
        if not panel.gui.compact:
            field = panel._tmcc_id_field
            assert type(field) is route_builder_panel.Text
            assert field.value == f"{panel.draft.tmcc_id:02d}"
            value = field.tk
            row = value.master.master
            caption = row.winfo_children()[0]
            assert caption.cget("text") == "TMCC ID"
            assert value.winfo_ismapped()
            assert not value.bind("<Button-1>")
            for editable in (panel._name_field.tk, panel._number_field.tk):
                edit_row = editable.master.master
                edit_caption = edit_row.winfo_children()[0]
                assert caption.winfo_rootx() == edit_caption.winfo_rootx()
                assert caption.winfo_width() == edit_caption.winfo_width()
                assert value.winfo_rootx() == editable.winfo_rootx()
                assert value.winfo_height() == editable.winfo_height()
                assert row.winfo_rooty() >= edit_row.winfo_rooty() + edit_row.winfo_height()
                for option in ("anchor", "padx", "bd"):
                    assert value.cget(option) == editable.cget(option)
            assert (
                abs(caption.winfo_rooty() + caption.winfo_height() / 2 - value.winfo_rooty() - value.winfo_height() / 2)
                <= 1
            )
        else:
            assert panel._tmcc_id_field is None
        if panel.section_gap:
            metadata, status, add = panel._metadata_box.tk, panel._status.tk, panel._add_btn.tk
            move = panel._earlier_btn.tk
            assert add.winfo_rooty() - (move.winfo_rooty() + move.winfo_height()) >= panel.section_gap
            assert metadata.winfo_rooty() - (add.winfo_rooty() + add.winfo_height()) >= panel.section_gap
            assert status.winfo_rooty() - (metadata.winfo_rooty() + metadata.winfo_height()) >= panel.section_gap
            assert (
                panel._save_btn.tk.winfo_rooty() - (status.winfo_rooty() + status.winfo_height()) >= panel.section_gap
            )
        texts = [item for item in panel._cards.find_all() if panel._cards.type(item) == "text"]
        for index in range(len(panel.draft.components)):
            title, name, mode = [panel._cards.bbox(item) for item in texts[index * 3 : index * 3 + 3]]
            assert title[3] < name[1] and name[3] < mode[1], (label, title, name, mode)
            assert title[1] >= 0 and mode[3] <= panel.card_height
        for radio in panel._radios:
            assert radio.winfo_height() >= 44
            assert radio.winfo_width() >= radio.winfo_reqwidth()
    else:
        canvas, bar = panel._picker, panel._picker_scrollbar
        assert bar.winfo_ismapped()
        assert bar.winfo_width() == panel.picker_bar_width >= 30
        assert bar.winfo_height() == canvas.winfo_height()
        assert canvas.winfo_width() == panel.picker_view_width
        assert canvas.winfo_rootx() + canvas.winfo_width() == bar.winfo_rootx()
        assert bar.winfo_rootx() + bar.winfo_width() <= panel._picker_page.tk.winfo_rootx() + panel.content_width
        field = panel._search_field.tk
        caption = field.master.master.winfo_children()[0]
        assert caption.cget("text") == "Search"
        assert int(caption.cget("width")) == 6
        search_width, caption_width = field.winfo_width(), caption.winfo_width()
        caption.config(width=12)
        app.tk.update_idletasks()
        gained_width = search_width - field.winfo_width()
        assert gained_width == caption.winfo_width() - caption_width > 0
        caption.config(width=6)
        app.tk.update_idletasks()
        assert field.winfo_width() == search_width
        print(f"Search field gained {gained_width} pixels from the shorter label.", flush=True)
        texts = [item for item in panel._picker.find_all() if panel._picker.type(item) == "text"]
        columns = None
        for index in range(len(panel._candidates)):
            count = 4 if panel.picker_inline_details else 2
            items = texts[index * count : index * count + count]
            bounds = [panel._picker.bbox(item) for item in items]
            if panel.picker_inline_details:
                positions = [panel._picker.coords(item) for item in items]
                assert all(y == (index + 0.5) * panel.picker_row_height for _, y in positions)
                assert columns is None or columns == [x for x, _ in positions]
                columns = [x for x, _ in positions]
                assert all(left[2] < right[0] for left, right in zip(bounds, bounds[1:])), bounds
                assert bounds[0][0] > panel.indicator_size + 12
                assert bounds[-1][2] < panel.picker_view_width - 2
                if panel._candidates[index][1].road_name == "W" * 31:
                    assert panel._picker.itemcget(items[0], "text").endswith("…")
            else:
                assert bounds[0][3] < bounds[1][1], (label, bounds)
            assert all(box[1] >= index * panel.picker_row_height for box in bounds), bounds
            assert all(box[3] <= (index + 1) * panel.picker_row_height for box in bounds), bounds
            assert all(0 <= box[0] < box[2] < panel.picker_view_width for box in bounds), bounds
        if panel.picker_inline_details:
            rows = [item for item in panel._picker.find_all() if panel._picker.type(item) == "rectangle"]
            assert panel.picker_rows == 4
            assert panel._picker.winfo_height() <= 210
            for row in rows[:4]:
                _, top, _, bottom = panel._picker.coords(row)
                assert bottom - top >= 44
                assert 0 <= top < bottom <= panel._picker.winfo_height()
            print("Steam Deck picker: four visible touch rows with aligned, nonoverlapping columns.", flush=True)


def check_picker_scrollbar(app, panel):
    canvas, bar = panel._picker, panel._picker_scrollbar
    command = bar.cget("command")
    before = RouteComponent.to_bytes(panel.draft.components)
    dirty = panel.draft.dirty
    app.tk.call(command, "scroll", 1, "units")
    app.tk.update_idletasks()
    assert round(canvas.canvasy(0)) == panel.picker_row_height
    assert bar.get() == canvas.yview()
    app.tk.call(command, "moveto", 0)
    app.tk.call(command, "scroll", 1, "pages")
    app.tk.update_idletasks()
    assert canvas.yview()[0] > 0
    assert bar.get() == canvas.yview()
    app.tk.call(command, "moveto", 1)
    app.tk.update_idletasks()
    assert bar.get()[1] == canvas.yview()[1] == 1
    assert panel._candidate is None and not panel._save_btn.enabled
    y = round((len(panel._candidates) - 0.5) * panel.picker_row_height - canvas.canvasy(0))
    canvas.event_generate("<ButtonPress-1>", x=40, y=y)
    canvas.event_generate("<ButtonRelease-1>", x=40, y=y)
    app.tk.update_idletasks()
    scope, state = panel._candidates[-1]
    assert panel._candidate == (scope, state.tmcc_id)
    app.tk.call(command, "moveto", 0)
    app.tk.update_idletasks()
    assert bar.get()[0] == canvas.yview()[0] == 0
    assert panel._candidate == (scope, state.tmcc_id)
    assert RouteComponent.to_bytes(panel.draft.components) == before
    assert panel.draft.dirty == dirty
    panel.open_picker()
    print("Picker scrollbar: arrows, paging, thumb position, and scrolled selection passed.", flush=True)


def check_touch_scroll(app, panel, canvas, horizontal):
    if sys.platform != "darwin" or tk.TkVersion < 9:
        return
    assert canvas.bind("<TouchpadScroll>")
    selection = panel._selected, panel._candidate
    components = RouteComponent.to_bytes(panel.draft.components)
    dirty = panel.draft.dirty
    (canvas.xview_moveto if horizontal else canvas.yview_moveto)(0)
    position = canvas.canvasx if horizontal else canvas.canvasy
    gestures = [(0, -7, 7), (0, 2, 5), (0, 1, 4), (0, 0, 4)]
    if horizontal:
        gestures.extend([(-7, 0, 11), (2, 0, 9)])
    for dx, dy, expected in gestures:
        packed = (dx << 16) | (dy & 0xFFFF)
        canvas.event_generate("<TouchpadScroll>", delta=packed)
        app.tk.update()
        assert round(position(0)) == expected, (horizontal, dx, dy, position(0))
    assert (panel._selected, panel._candidate) == selection
    assert RouteComponent.to_bytes(panel.draft.components) == components
    assert panel.draft.dirty == dirty
    print(f"Mac touch-surface events passed: {'component cards' if horizontal else 'picker'}", flush=True)


def check_discard_dialog(app, panel, width, height):
    if panel.desktop_controls:
        return
    for action, expected in (("keep", False), ("close", False), ("discard", True)):
        errors = []

        def respond():
            dialog = next(
                child for child in app.tk.winfo_children() if isinstance(child, route_builder_panel.RouteDiscardDialog)
            )
            try:
                assert dialog.winfo_width() >= width * 0.8
                assert dialog.winfo_height() >= 200
                assert dialog.winfo_rootx() >= app.tk.winfo_rootx()
                assert dialog.winfo_rootx() + dialog.winfo_width() <= app.tk.winfo_rootx() + width
                assert dialog.winfo_rooty() >= app.tk.winfo_rooty()
                assert dialog.winfo_rooty() + dialog.winfo_height() <= app.tk.winfo_rooty() + height
                assert dialog.grab_current() is dialog
                for button in (dialog._keep_btn, dialog._discard_btn):
                    assert button.winfo_width() >= 150
                    assert button.winfo_height() >= 64
                assert dialog.initial_focus is dialog._keep_btn
                if action == "close":
                    dialog.tk.call(dialog.protocol("WM_DELETE_WINDOW"))
                else:
                    (dialog._discard_btn if action == "discard" else dialog._keep_btn).invoke()
            except Exception as exc:
                errors.append(exc)
            finally:
                if dialog.winfo_exists():
                    dialog.cancel()

        app.tk.after(100, respond)
        result = panel.confirm_close()
        if errors:
            raise errors[0]
        assert result is expected
        assert panel.draft.dirty
    print("Large discard dialog: bounds, touch targets, and keep/close/discard checks passed.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    device = parser.add_mutually_exclusive_group()
    device.add_argument("--pi", action="store_true")
    device.add_argument("--pycab", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    width, height, budget, scale = (800, 1280, 941, 1.5) if args.pi else (639, 800, 600, 1.0)
    if args.pycab:
        width, height, budget, scale = 631, 1009, 720, 631 * 1.5 / 800
    route_builder_panel.platform = sys.platform if args.pycab else "linux"
    app = App(title="Route Builder — offline preview", width=width, height=height, bg="white")
    if args.pi:
        app.tk.geometry(f"{width}x{height}+0+0")
        app.tk.winfo_screenwidth = lambda: width
        app.tk.winfo_screenheight = lambda: height
    host = SimpleNamespace(
        app=app,
        root=app,
        width=width,
        height=height,
        compact=not (args.pi or args.pycab),
        emergency_box_width=width - 4,
        button_size=round(width / (6 if args.pi else 8)),
        state_store=PreviewStore(),
    )
    for size in (12, 14, 16, 18, 20):
        setattr(host, f"s_{size}", round(size * scale))
    host._popup = PopupManager(host)
    panel = RouteBuilderPanel(host)

    def preview_save():
        if panel._picking:
            panel.add_selected()
        else:
            panel._status.value = "Preview only — nothing was sent to the layout."

    def preview_clear():
        panel._clear_route_btn.cancel_interaction()
        panel._status.value = "Preview only — no route was cleared."

    panel.save = preview_save
    panel.clear_route = preview_clear
    panel._close = lambda: app.destroy() if panel.confirm_close() else None
    overlay = panel.overlay
    for field in (panel._name_field, panel._number_field, panel._search_field):
        field.show_keyboard_on_edit = not args.pycab
    panel.configure(12, host.state_store.get_state(CommandScope.ROUTE, 12))
    overlay.show()
    app.tk.update_idletasks()
    if not args.check:
        app.display()
        return
    try:
        check_bounds(app, overlay, panel, width, budget, "Editor")
        panel.select_row(1)
        panel._radios[0].invoke()
        assert panel.draft.components[1].is_thru
        panel.move_selected(-1)
        assert panel.draft.components[0].tmcc_id == 2
        panel.open_picker()
        panel.set_filter("All")
        check_bounds(app, overlay, panel, width, budget, "Picker")
        check_picker_scrollbar(app, panel)
        assert panel._candidate is None
        assert not panel._save_btn.enabled
        assert str(panel._save_btn.tk.cget("state")) == "disabled"
        before = RouteComponent.to_bytes(panel.draft.components)
        panel._save_btn.tk.invoke()
        assert panel._picking and RouteComponent.to_bytes(panel.draft.components) == before
        rows = [item for item in panel._picker.find_all() if panel._picker.type(item) == "rectangle"]
        for row, (scope, state) in zip(rows, panel._candidates):
            active = state.is_thru if scope == CommandScope.SWITCH else state.is_aligned
            assert panel._picker.itemcget(row, "fill") == (
                route_builder_panel.ACTIVE_STATE_BG if active else route_builder_panel.CARD_BG
            )
        panel.choose_candidate(0)
        assert panel._save_btn.enabled
        assert str(panel._save_btn.tk.cget("state")) == "normal"
        candidates = panel._candidates.copy()
        field = panel._search_field
        assert panel._search_btn.text == "Edit"
        panel._search_btn.tk.invoke()
        app.tk.after(field.debounce_ms + 100, app.tk.quit)
        app.tk.mainloop()
        assert field.is_editing
        field._insert_text("no matches")
        if args.pycab:
            assert field._keyboard_window is None
            field.commit_edit()
        else:
            actions = field._keyboard_window.winfo_children()[0].winfo_children()
            assert [button.cget("text") for button in actions] == ["Clear", "Cancel", "Search"]
            actions[-1].invoke()
        assert not field.is_editing
        assert field.value == "no matches"
        assert panel._candidates == []
        assert panel._candidate is None
        assert str(panel._save_btn.tk.cget("state")) == "disabled"
        assert panel._search_btn.text == "Clear"
        app.tk.update_idletasks()
        assert panel._picker_scrollbar.get() == (0, 1)
        assert panel._search_btn.tk.winfo_width() >= panel._search_btn.tk.winfo_reqwidth(), (
            panel._search_btn.tk.winfo_width(),
            panel._search_btn.tk.winfo_reqwidth(),
        )
        panel._search_btn.tk.invoke()
        assert field.value == ""
        assert not field.is_editing
        assert panel._search_btn.text == "Edit"
        assert panel._candidates == candidates
        assert not panel._save_btn.enabled
        assert panel.picker_rows == (6 if args.pi or args.pycab else 4)
        assert panel._picker.winfo_height() == panel.picker_rows * panel.picker_row_height
        app.tk.call(panel._picker_scrollbar.cget("command"), "scroll", 1, "pages")
        app.tk.update_idletasks()
        assert panel._picker.yview()[0] > 0
        if args.pycab:
            panel._picker.focus_force()
            panel._picker.yview_moveto(0)
            for _ in panel._candidates:
                panel._picker.event_generate("<Down>")
                app.tk.update()
            assert panel._candidate == (panel._candidates[-1][0], panel._candidates[-1][1].tmcc_id)
            assert panel._picker.yview()[1] == 1
            panel._picker.event_generate("<Up>")
            app.tk.update()
            assert panel._candidate == (panel._candidates[-2][0], panel._candidates[-2][1].tmcc_id)
            panel._picker.yview_moveto(0)
            panel._picker.event_generate("<MouseWheel>", delta=-1)
            app.tk.update()
            assert panel._picker.yview()[0] > 0
            check_touch_scroll(app, panel, panel._picker, False)
        panel.cancel()
        for field in (panel._name_field, panel._number_field):
            field.begin_edit()
            app.tk.after(field.debounce_ms + 100, app.tk.quit)
            app.tk.mainloop()
            app.tk.update_idletasks()
            keyboard = field._keyboard_window
            assert field.is_editing
            if args.pycab:
                assert keyboard is None
                field._entry.focus_force()
                field._entry.icursor(1)
                before = panel._selected
                panel._cards.event_generate("<Enter>")
                field._entry.event_generate("<Left>")
                app.tk.update()
                assert app.tk.focus_get() is field._entry
                assert field._entry.index("insert") == 0
                assert panel._selected == before
            else:
                assert keyboard is not None
                assert keyboard.winfo_rootx() >= app.tk.winfo_rootx()
                assert keyboard.winfo_rootx() + keyboard.winfo_width() <= app.tk.winfo_rootx() + width
                actions = keyboard.winfo_children()[0].winfo_children()
                assert [button.cget("text") for button in actions] == ["Clear", "Cancel", "Save"]
            field.cancel_edit()
        for tmcc_id in range(16, 3, -1):
            panel.draft.set_component(None, tmcc_id, 0, panel._lookup_route)
        panel.select_relative(99)
        app.tk.update_idletasks()
        assert panel._cards.xview()[1] == 1.0
        check_bounds(app, overlay, panel, width, budget, "Full route")
        if args.pycab:
            before = RouteComponent.to_bytes(panel.draft.components)
            panel._cards.focus_force()
            for _ in range(20):
                panel._cards.event_generate("<Left>")
                app.tk.update()
            assert panel._selected == 0 and panel._cards.xview()[0] == 0
            panel._cards.event_generate("<Right>")
            app.tk.update()
            assert panel._selected == 1
            panel._cards.event_generate("<MouseWheel>", delta=-1)
            app.tk.update()
            assert panel._cards.xview()[0] > 0
            assert RouteComponent.to_bytes(panel.draft.components) == before
            check_touch_scroll(app, panel, panel._cards, True)
        check_discard_dialog(app, panel, width, height)
        print("Rendering and interaction checks passed; no layout commands sent.", flush=True)
    finally:
        app.destroy()


if __name__ == "__main__":
    main()
