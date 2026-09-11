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


class PreviewStore:
    def __init__(self):
        self.states = {}
        for tmcc_id, name in enumerate(
            ("East turnout", "Main siding", "Station approach", "West yard", "Longest switch name on the track"),
            1,
        ):
            self.add(SwitchState(), CommandScope.SWITCH, tmcc_id, name)
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
        texts = [item for item in panel._cards.find_all() if panel._cards.type(item) == "text"]
        for index in range(len(panel.draft.components)):
            title, name, mode = [panel._cards.bbox(item) for item in texts[index * 3 : index * 3 + 3]]
            assert title[3] < name[1] and name[3] < mode[1], (label, title, name, mode)
            assert title[1] >= 0 and mode[3] <= panel.card_height
        for radio in panel._radios:
            assert radio.winfo_height() >= 44
            assert radio.winfo_width() >= radio.winfo_reqwidth()
    else:
        texts = [item for item in panel._picker.find_all() if panel._picker.type(item) == "text"]
        for index in range(len(panel._candidates)):
            name, details = [panel._picker.bbox(item) for item in texts[index * 2 : index * 2 + 2]]
            assert name[3] < details[1], (label, name, details)
            assert name[1] >= index * panel.picker_row_height
            assert details[3] <= (index + 1) * panel.picker_row_height


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
        assert panel.picker_rows == (6 if args.pi or args.pycab else 3)
        assert panel._picker.winfo_height() == panel.picker_rows * panel.picker_row_height
        panel.scroll_picker(1)
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
        print("Rendering and interaction checks passed; no layout commands sent.", flush=True)
    finally:
        app.destroy()


if __name__ == "__main__":
    main()
