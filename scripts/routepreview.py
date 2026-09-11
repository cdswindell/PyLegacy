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
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from guizero import App

from pytrain.db.component_state import RouteState, SwitchState
from pytrain.db.components import RouteComponent
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
        assert widget.winfo_height() >= 40
        assert widget.winfo_rooty() + widget.winfo_height() <= app.tk.winfo_rooty() + budget


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pi", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    width, height, budget, scale = (800, 1280, 941, 1.5) if args.pi else (639, 800, 600, 1.0)
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
        compact=not args.pi,
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
        panel.scroll_picker(1)
        app.tk.update_idletasks()
        assert panel._picker.yview()[0] > 0
        panel.cancel()
        for field in (panel._name_field, panel._number_field):
            field.begin_edit()
            app.tk.after(field.debounce_ms + 100, app.tk.quit)
            app.tk.mainloop()
            app.tk.update_idletasks()
            keyboard = field._keyboard_window
            assert field.is_editing and keyboard is not None
            assert keyboard.winfo_rootx() >= app.tk.winfo_rootx()
            assert keyboard.winfo_rootx() + keyboard.winfo_width() <= app.tk.winfo_rootx() + width
            field.cancel_edit()
        for tmcc_id in range(16, 3, -1):
            panel.draft.set_component(None, tmcc_id, 0, panel._lookup_route)
        panel.select_relative(99)
        app.tk.update_idletasks()
        assert panel._cards.xview()[1] == 1.0
        check_bounds(app, overlay, panel, width, budget, "Full route")
        print("Rendering and interaction checks passed; no layout commands sent.", flush=True)
    finally:
        app.destroy()


if __name__ == "__main__":
    main()
