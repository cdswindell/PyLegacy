#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from threading import Thread
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pytrain.db.component_state import RouteState
from pytrain.db.components import RouteComponent
from pytrain.gui import guizero_base as base_mod
from pytrain.gui.controller import routes_gui as mod
from tests.gui.test_route_builder_panel import Widget, panel as panel


class ListWidget(Widget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.items = []
        self.selection = ()
        self.bindings = {}
        self.top = 0.0
        self.inner = Mock()
        self.inner.bind.side_effect = lambda event, callback, **_: self.bindings.update({event: callback})
        self.inner.curselection.side_effect = lambda: self.selection
        self.inner.yview.side_effect = lambda: (self.top, min(1.0, self.top + 0.5))
        self.inner.yview_moveto.side_effect = lambda top: setattr(self, "top", top)
        self.inner.delete.side_effect = self.delete
        self.inner.insert.side_effect = lambda _, label: self.items.append(label)
        self.inner.get.side_effect = lambda *_: tuple(self.items)
        self.inner.selection_set.side_effect = lambda index: setattr(self, "selection", (index,))
        self.inner.selection_clear.side_effect = lambda *_: setattr(self, "selection", ())
        self.inner.nearest.side_effect = lambda y: min(
            len(self.items) - 1, max(0, int(self.top * len(self.items)) + y // 20)
        )
        self.inner.bbox.side_effect = lambda index: (0, (index - int(self.top * len(self.items))) * 20, 200, 20)
        self.children = [SimpleNamespace(tk=self.inner)]

    def delete(self, *_):
        self.items.clear()
        self.selection = ()


class RouteStore:
    def __init__(self):
        self.states = {}
        self.created = []

    def get_state(self, scope, tmcc_id, create=False):
        if create and tmcc_id not in self.states:
            self.states[tmcc_id] = state = RouteState()
            state._address = tmcc_id
            self.created.append(tmcc_id)
        return self.states.get(tmcc_id)

    def get_all(self, _scope):
        return list(self.states.values())


@pytest.fixture
def host(monkeypatch, panel):
    store = RouteStore()
    monkeypatch.setattr(base_mod.CommandDispatcher, "get", lambda: SimpleNamespace(version="Test"))
    monkeypatch.setattr(base_mod.ComponentStateStore, "get", lambda: store)
    for name in ("Box", "Text", "PushButton", "EditableText"):
        monkeypatch.setattr(mod, name, Widget)
    monkeypatch.setattr(mod, "ListBox", ListWidget)
    monkeypatch.setattr(mod, "TouchListBox", ListWidget)
    gui = mod.RoutesGui(stand_alone=False)
    gui._synchronized = True
    gui._app = SimpleNamespace(tk=Mock(), repeat=Mock(), yesno=Mock(return_value=False))
    gui.build_gui()

    def create_popup(_title, builder, *, post_close_action):
        overlay = Widget(visible=False)
        builder.build(Widget())
        builder.build_footer(Widget())
        overlay.confirm_close = builder.confirm_close
        overlay.post_close_action = post_close_action
        return overlay

    def show(overlay, **_):
        gui.controller_box.hide()
        overlay.show()

    def close_requested(overlay=None):
        overlay = overlay or gui.panel.overlay
        if not overlay.confirm_close():
            return False
        overlay.hide()
        overlay.post_close_action(overlay)
        gui.controller_box.show()
        return True

    gui._popup = SimpleNamespace(create_popup=create_popup, show=show, close_requested=close_requested)
    yield gui
    gui.close()
    gui.destroy_gui()
    gui._finalize_gui_resources()


def route(host, tmcc_id=12, *, name="Main line", deleted=False, empty=False):
    state = host.state_store.get_state(mod.CommandScope.ROUTE, tmcc_id, True)
    state.initialize(mod.CommandScope.ROUTE, tmcc_id)
    state._deleted = deleted
    if not empty:
        state._road_name = name
        state.comp_data._road_name = name
        state.comp_data.components = [RouteComponent(7, 0)]
        state._empty = False
    host.state_store.created.clear()
    return state


def test_front_page_lists_routes_by_id_and_excludes_deleted_and_empty_records(host):
    route(host, 20, name="Yard")
    route(host, 2, name="Main")
    route(host, 10, deleted=True)
    route(host, 11, empty=True)
    host.refresh_routes()
    assert host._route_rows == [(2, "02   Main"), (20, "20   Yard")]
    assert host.controller_box.visible and not host.panel.visible
    assert host._new_btn.enabled and not host._edit_btn.enabled


def test_refresh_preserves_selection_and_scroll_after_routes_are_added_or_renamed(host):
    state = route(host, 20)
    host.refresh_routes()
    host._listbox.selection_set(0)
    host._route_list.top = 0.5
    route(host, 2)
    state._road_name = "Renamed"
    state.comp_data._road_name = "Renamed"
    host.refresh_routes()
    assert host._selected_id() == 20
    assert host._route_list.top == 0.5
    assert host._edit_btn.enabled
    state._deleted = True
    host.refresh_routes()
    assert host._selected_id() is None
    assert not host._edit_btn.enabled


def test_sync_gates_both_creation_and_editing_until_queued_notification(host):
    route(host)
    host._synchronized = False
    host.refresh_routes()
    host.new_route()
    host.create_route()
    host.edit_selected()
    assert not host._new_btn.enabled and not host._create_btn.enabled
    assert not host._route_rows and not host.panel.visible
    assert "synchronization" in host._status.value
    host.start()
    callback, args = host._message_queue.get_nowait()
    assert callback == host._on_synchronized
    host._synchronized = True
    callback(*args)
    assert host._new_btn.enabled and host._route_rows


@pytest.mark.parametrize("value", ["", "0", "100", "-1", "1.2", "abc", "١", "+2"])
def test_create_rejects_invalid_ids_without_mutating_store(host, value):
    host.new_route()
    host._id_field.value = value
    host.create_route()
    assert "integer from 1 to 99" in host._status.value
    assert host._new_box.visible and not host.panel.visible
    assert not host.state_store.created


@pytest.mark.parametrize("tmcc_id", [1, 99])
def test_create_opens_draft_and_cancel_returns_to_front_without_creating_record(host, tmcc_id):
    host.new_route()
    host._id_field.value = str(tmcc_id)
    host.create_route()
    assert host.panel.visible and not host.controller_box.visible
    assert host.panel.draft.tmcc_id == tmcc_id and not host.panel.draft.components
    assert not host.state_store.created
    host.panel.cancel()
    assert not host.panel.visible and host.controller_box.visible
    assert not host.state_store.created


def test_new_route_rejects_an_existing_id_even_if_it_arrived_after_opening_form(host):
    host.new_route()
    route(host)
    host._id_field.value = "12"
    host.create_route()
    assert "already exists" in host._status.value
    assert not host.panel.visible and not host.state_store.created


def test_edit_loads_existing_metadata_and_components_without_mutating_live_route(host):
    state = route(host)
    host.refresh_routes()
    host._listbox.selection_set(0)
    host.edit_selected()
    assert host.panel.draft.tmcc_id == 12
    assert host.panel.draft.road_name == "Main line"
    assert host.panel.draft.components[0].tmcc_id == 7
    host.panel.draft.clear()
    assert state.components[0].tmcc_id == 7
    host.refresh_routes()
    assert host.panel.visible and host.panel.draft.dirty


def test_edit_revalidates_selection_after_route_is_deleted(host):
    state = route(host)
    host.refresh_routes()
    host._listbox.selection_set(0)
    state._deleted = True
    host.edit_selected()
    assert not host.panel.visible
    assert "available route" in host._status.value


@pytest.mark.parametrize("allow", [False, True])
def test_window_close_respects_dirty_draft_confirmation(host, monkeypatch, allow):
    from pytrain.gui.controller import route_builder_panel

    monkeypatch.setattr(route_builder_panel, "platform", "darwin")
    host.new_route()
    host._id_field.value = "12"
    host.create_route()
    host.panel.draft.set_metadata("Changed", "")
    host.app.yesno.return_value = allow
    host.request_close()
    host.app.yesno.assert_called_once()
    assert host.is_shutting_down is allow
    assert host.panel.visible is not allow


def test_save_new_route_uses_existing_write_path_and_returns_to_list(host, monkeypatch):
    from pytrain.gui.controller import route_builder_panel

    send = Mock()
    monkeypatch.setattr(route_builder_panel.BaseReq, "process_sync_reqs", send)
    host.new_route()
    host._id_field.value = "12"
    host.create_route()
    host.panel._name_field.value = "New route"
    host.panel.save()
    assert host.state_store.created == [12]
    send.assert_called_once()
    requests = send.call_args.args[0]
    assert len(requests) == 4 and requests[-1].tmcc_id == 12
    assert send.call_args.kwargs == {"do_async": True}
    assert host.controller_box.visible and not host.panel.visible
    assert not host.panel.draft.dirty


def test_clear_uses_database_clear_and_returns_to_list(host, monkeypatch):
    state = route(host)
    host.refresh_routes()
    host._listbox.selection_set(0)
    host.edit_selected()
    clear = Mock(side_effect=lambda **_: setattr(state, "_deleted", True))
    monkeypatch.setattr(state, "clear", clear)
    host.panel.clear_route()
    clear.assert_called_once_with(notify=False, clear_db=True)
    assert host.controller_box.visible and not host.panel.visible
    assert not host._route_rows


@pytest.mark.parametrize("system", ["darwin", "win32", "linux"])
def test_front_page_desktop_bindings_and_real_editor_gestures(host, monkeypatch, system):
    from pytrain.gui.controller import route_builder_panel

    monkeypatch.setattr(mod, "platform", system)
    monkeypatch.setattr(route_builder_panel, "platform", system)
    host.build_gui()
    desktop = system in {"darwin", "win32"}
    assert host.compact is False
    assert ("<Double-Button-1>" in host._route_list.bindings) is desktop
    assert ("<Return>" in host._route_list.bindings) is desktop
    assert ("<TouchpadScroll>" in host._route_list.bindings) is (system == "darwin")
    route(host)
    host.refresh_routes()
    host._listbox.selection_set(0)
    host.edit_selected()
    assert host.panel.desktop_controls is desktop
    assert ("<Double-Button-1>" in host.panel._picker.bindings) is desktop


@pytest.mark.parametrize("y, expected", [(5, 6), (-5, None), (250, None)])
def test_double_click_opens_clicked_scrolled_row_but_not_blank_space(host, y, expected):
    for tmcc_id in range(1, 11):
        route(host, tmcc_id)
    host.refresh_routes()
    host._route_list.top = 0.5
    assert host._double_click(SimpleNamespace(y=y)) == "break"
    assert (host.panel.draft.tmcc_id if host.panel.draft else None) == expected


def test_scroll_does_not_select_or_open_a_route(host):
    route(host)
    host.refresh_routes()
    host._scroll(48)
    host._listbox.yview_scroll.assert_called_once_with(2, "units")
    assert not host.panel.visible and host._selected_id() is None


def test_run_window_owns_main_thread_and_sync_start_never_starts_thread(host, monkeypatch):
    run = Mock()
    monkeypatch.setattr(host, "run", run)
    errors = []

    def worker():
        try:
            host.run_window()
        except RuntimeError as exc:
            errors.append(exc)

    thread = Thread(target=worker)
    thread.start()
    thread.join(timeout=5)
    assert len(errors) == 1
    run.assert_not_called()
    host.start()
    assert host.ident is None
    host.run_window()
    run.assert_called_once()
    assert host.is_shutting_down


def test_shutdown_before_sync_stops_watcher(host):
    watcher = host._sync_watcher = Mock()
    host.close()
    watcher.shutdown.assert_called_once()
    assert host._sync_watcher is None
