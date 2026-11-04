"""Engine SET creates an isolated draft and persists only on explicit creation."""

from contextlib import nullcontext
from queue import Queue
from threading import Condition, Event
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest

from src.pytrain.db.comp_data import EngineData
from src.pytrain.db.component_state import ComponentStateDict
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.engine_discovery_service import EngineDiscoveryService
from src.pytrain.db.engine_state import EngineState
from src.pytrain.gui.controller.catalog_panel import CatalogPanel
from src.pytrain.gui.controller.engine_add_session import EngineAddSession
from src.pytrain.gui.controller.engine_gui import EngineGui
from src.pytrain.gui.controller.engine_gui_conf import SET_KEY
from src.pytrain.gui.controller.keypad_view import KeypadView
from src.pytrain.gui.controller.popup_manager import PopupManager
from src.pytrain.gui.controller.state_info_overlay import StateInfoOverlay
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import D4Action, PdiCommand
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.pdi.pdi_listener import PdiDispatcher
from src.pytrain.pdi.pdi_req import PdiReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


@pytest.fixture
def states():
    return ComponentStateDict(CommandScope.ENGINE)


def populate(state, name="Pennsylvania", number="0088"):
    state.initialize(CommandScope.ENGINE, state.tmcc_id)
    state.comp_data.road_name = name
    state.comp_data.road_number = number
    state.comp_data.control_type = 2
    state.comp_data.engine_type = 1
    state.comp_data.sound_type = 3


@pytest.mark.parametrize("tmcc_id", [1, 8, 100, 113, 9999])
def test_missing_record_displays_defaults_without_initializing_state(states, tmcc_id):
    state = states[tmcc_id]
    draft = EngineAddSession(state)

    assert draft.values == {"name": f"Engine {tmcc_id}", "number": str(tmcc_id), "control": 1, "type": 0, "sound": 0}
    assert state.comp_data is None
    assert not state.is_comp_data_record


def test_empty_record_uses_existing_comp_data_predicate(states):
    state = states[8]
    state.initialize(CommandScope.ENGINE, 8)
    assert not state.comp_data.is_user_defined()
    draft = EngineAddSession(state)
    assert draft.values["name"] == "Engine 8"
    assert draft.values["control"] == 1
    state.comp_data.prev_link = 7
    assert state.comp_data.is_user_defined()
    draft.refresh(state)
    assert draft.values["name"] == state.comp_data.road_name


def test_existing_record_uses_database_values_and_unchanged_create_sends_nothing(states, monkeypatch):
    state = states[8]
    populate(state)
    original = state.comp_data.as_bytes()
    draft = EngineAddSession(state)
    dispatch = Mock()
    monkeypatch.setattr(BaseReq, "process_sync_reqs", dispatch)

    assert draft.values == {"name": "Pennsylvania", "number": "0088", "control": 2, "type": 1, "sound": 3}
    draft.create()
    dispatch.assert_not_called()
    assert state.comp_data.as_bytes() == original


def test_late_ir_metadata_replaces_defaults_and_preserves_deliberate_edits(states):
    state = states[8]
    draft = EngineAddSession(state)
    draft.edit("name", "My Engine")
    populate(state)
    assert draft.refresh(state)
    assert draft.values == {"name": "My Engine", "number": "0088", "control": 2, "type": 1, "sound": 3}
    assert draft.baseline["name"] == "Pennsylvania"
    assert state.comp_data.road_name == "Pennsylvania"


def test_unrelated_engine_response_cannot_change_the_draft(states):
    draft = EngineAddSession(states[8])
    populate(states[9], name="Other Engine")
    assert not draft.refresh(states[9])
    assert draft.values["name"] == "Engine 8"
    assert draft.state is states[8]


def test_manual_creation_without_ble_writes_five_fields_and_refreshes_once(states, monkeypatch):
    draft = EngineAddSession(states[8])
    dispatch = Mock()
    monkeypatch.setattr(BaseReq, "process_sync_reqs", dispatch)
    draft.create()

    requests = dispatch.call_args.args[0]
    writes = requests[:-1]
    assert len(writes) == 5
    assert all(isinstance(req, BaseReq) and req.pdi_command == PdiCommand.BASE_MEMORY for req in writes)
    assert [req.start for req in writes] == [0x1E, 0x3E, 0x44, 0x43, 0x45]
    assert writes[0].data_bytes.startswith(bytes([8]) + b"Engine 8")
    assert writes[1].data_bytes == bytes([4]) + b"0008"
    assert [req.data_bytes for req in writes[2:]] == [b"\x01", b"\x00", b"\x00"]
    assert requests[-1] is states[8]
    assert states[8].comp_data is None


def test_existing_record_writes_only_deliberate_changes_without_mutating_live_data(states):
    state = states[8]
    populate(state)
    original = state.comp_data.as_bytes()
    draft = EngineAddSession(state)
    draft.edit("name", "New Name")
    draft.edit("number", "88")
    requests = draft.requests()
    assert len(requests) == 1
    assert requests[0].data_bytes.startswith(bytes([8]) + b"New Name")
    assert state.comp_data.as_bytes() == original


@pytest.mark.parametrize("tmcc_id", [100, 113])
def test_four_digit_creation_waits_for_record_number_then_uses_it(states, monkeypatch, tmcc_id):
    state = states[tmcc_id]
    assert isinstance(state, EngineState)
    draft = EngineAddSession(state)
    assert not draft.can_create
    with pytest.raises(ValueError, match="Waiting for the Base 3"):
        draft.requests()
    # A discovered record number belongs to server state; mock its read-only property.
    monkeypatch.setattr(type(state), "record_no", property(lambda _state: 7))
    monkeypatch.setattr(ComponentStateStore, "get_state", lambda *_args, **_kwargs: state)
    requests = draft.requests()
    assert len(requests) == 5
    assert all(isinstance(req, D4Req) and req.action == D4Action.UPDATE and req.record_no == 7 for req in requests)
    assert state.comp_data is None


@pytest.mark.parametrize("key,value", [("name", ""), ("name", "x" * 32), ("number", "bad"), ("control", 255)])
def test_invalid_metadata_builds_no_writes(states, key, value):
    draft = EngineAddSession(states[8])
    draft.edit(key, value)
    with pytest.raises(ValueError):
        draft.requests()


def host_for(states, tmcc_id):
    """Supply the GUI services used by the shared handler, without constructing Tk."""
    host = SimpleNamespace(
        scope=CommandScope.ENGINE,
        state_store=SimpleNamespace(
            get_state=lambda _scope, address, create=False: states[address] if create else states.get(address)
        ),
        _state_info=None,
        _provisional=set(),
        _scope_tmcc_ids={},
        repeat=1,
        clear_throttle=Mock(),
        ops_mode=Mock(),
        on_info=Mock(),
        submit_request=Mock(),
        tmcc_id_text=SimpleNamespace(value=str(tmcc_id)),
    )
    # The headless host implements the same services used by the production bound method.
    # noinspection PyTypeChecker
    host.on_set_key = lambda scope, address: EngineGui.on_set_key(host, scope, address)
    # noinspection PyTypeChecker
    host.on_add_engine = lambda address: EngineGui.on_add_engine(host, address)
    return host


@pytest.mark.parametrize(
    "tmcc_id,command",
    [
        (1, TMCC1EngineCommandEnum.SET_ADDRESS),
        (8, TMCC1EngineCommandEnum.SET_ADDRESS),
        (100, TMCC2EngineCommandEnum.SET_ADDRESS),
        (113, TMCC2EngineCommandEnum.SET_ADDRESS),
    ],
)
def test_keypad_set_sends_once_selects_exact_id_and_opens_creation(states, tmcc_id, command):
    host = host_for(states, tmcc_id)
    # The keypad only uses services supplied by this headless host.
    # noinspection PyTypeChecker
    keypad = KeypadView(host)
    keypad.on_keypress(SET_KEY)
    sent = [call.args[0] for call in host.submit_request.call_args_list]
    assert len(sent) == (2 if tmcc_id < 100 else 1)
    assert sent[0].command == command
    assert sent[0].address == tmcc_id
    assert host._scope_tmcc_ids[CommandScope.ENGINE] == tmcc_id
    host.ops_mode.assert_called_once_with(state=states[tmcc_id])
    host.on_info.assert_called_once_with(state=states[tmcc_id], adding=True, awaiting_discovery=True)
    assert states[tmcc_id].comp_data is None


@pytest.mark.parametrize("tmcc_id", [0, 99, 10000])
def test_invalid_keypad_address_does_not_send_or_open(states, tmcc_id):
    host = host_for(states, tmcc_id)
    # Only the public keypad services are required by the headless host.
    # noinspection PyTypeChecker
    KeypadView(host).on_keypress(SET_KEY)
    host.submit_request.assert_not_called()
    host.on_info.assert_not_called()


def test_repeated_set_during_creation_does_not_send_again(states):
    host = host_for(states, 8)
    host._state_info = SimpleNamespace(adding=True)
    host.on_add_engine(8)
    host.submit_request.assert_not_called()
    host.on_info.assert_not_called()


def test_placeholder_does_not_suppress_backend_discovery(states, monkeypatch):
    host = host_for(states, 8)
    host.on_add_engine(8)
    monkeypatch.setattr(ComponentStateStore, "is_built", lambda: True)
    monkeypatch.setattr(ComponentStateStore, "get_state", lambda *_args, **_kwargs: states[8])
    service = EngineDiscoveryService(Mock())
    monkeypatch.setattr(service, "_arm_timeout", lambda: None)
    assert service.request_discovery(8)
    service.stop()


class Field:
    def __init__(self):
        self.value = ""
        self.initial_value = None
        self.is_editing = False
        self.is_changed = True
        self.editable = True
        self.text_bold = False


def overlay_for(state):
    host = SimpleNamespace(
        version="test",
        enable_editing=True,
        popup_manager=Mock(),
        on_state_info_closed=Mock(),
        _keypad_view=SimpleNamespace(entry_mode=Mock()),
        app=SimpleNamespace(warn=Mock()),
    )
    # These tests exercise panel behavior without allocating Tk widgets.
    # noinspection PyTypeChecker
    panel = StateInfoOverlay(host)
    panel.details = {
        key: (SimpleNamespace(text_bold=False), Field()) for key in ("name", "number", "control", "type", "sound")
    }
    panel.clear_btn = Mock()
    panel.close_btn = Mock()
    panel.status_text = Mock()
    panel.begin_add(state)
    return panel, host


def test_creation_footer_and_defaults_replace_clear_and_close(states):
    panel, _host = overlay_for(states[8])
    panel.update(states[8])
    assert panel.clear_btn.text == "Cancel"
    assert panel.clear_btn.on_hold is None
    assert panel.close_btn.text == "Create"
    panel.close_btn.enable.assert_called_once()
    assert panel.details["name"][1].value == "Engine 8"
    assert panel.details["number"][1].value == "8"
    assert panel.details["control"][1].value == "TMCC"
    assert panel.details["type"][1].value == "Diesel"
    assert panel.details["sound"][1].value == "No Sound"


def test_four_digit_footer_disables_create_until_record_discovery(states):
    panel, _host = overlay_for(states[113])
    panel.update(states[113])
    panel.close_btn.disable.assert_called_once()
    assert "Waiting" in panel.status_text.value
    panel.clear_btn.enable.assert_called_once()


def test_cancel_discards_edits_preserves_arriving_metadata_and_returns_to_keypad(states, monkeypatch):
    state = states[8]
    panel, host = overlay_for(state)
    dispatch = Mock()
    monkeypatch.setattr(BaseReq, "process_sync_reqs", dispatch)
    # Invoke real field callbacks and dismissal: neither may persist a creation draft.
    # noinspection PyProtectedMember,PyTypeChecker
    panel._on_road_name_edited(Field(), "Unsaved Name", "Engine 8")
    # noinspection PyProtectedMember,PyTypeChecker
    panel._on_control_edited(Field(), 2, 1)
    populate(state)
    panel.update(state)
    host.locked = nullcontext
    host.image_box = None
    host.acc_overlay = None
    # The headless host supplies the popup manager's close services.
    # noinspection PyTypeChecker
    manager = PopupManager(host)
    host.popup_manager = manager
    overlay = Mock(confirm_close=panel.confirm_close)
    ops_panel = Mock()
    # Seed the state normally captured when the popup covers Engine Ops.
    # noinspection PyProtectedMember
    panel._overlay = overlay
    # noinspection PyProtectedMember
    manager._state.on_close_show = ops_panel
    # noinspection PyProtectedMember
    manager._post_close_actions[id(overlay)] = panel._post_close_action

    panel.clear_btn.on_press()

    overlay.hide.assert_called_once()
    ops_panel.show.assert_not_called()
    dispatch.assert_not_called()
    assert not panel.adding
    assert state.comp_data.road_name == "Pennsylvania"
    host._keypad_view.entry_mode.assert_called_once_with(clear_info=False)


def test_active_editor_survives_background_metadata_updates(states):
    panel, _host = overlay_for(states[8])
    field = panel.details["name"][1]
    field.value = "Typing"
    field.is_editing = True
    populate(states[8])
    panel.update(states[8])
    assert field.value == "Typing"
    assert panel.details["number"][1].value == "0088"


def test_create_button_sends_staged_metadata_and_keeps_engine_ops(states, monkeypatch):
    panel, host = overlay_for(states[8])
    dispatch = Mock()
    monkeypatch.setattr(BaseReq, "process_sync_reqs", dispatch)
    # Avoid allocating a Tk popup; verify the real Create handler requests dismissal.
    close = Mock()
    # Substitute the inherited dismissal hook so the test does not allocate a Tk popup.
    # noinspection PyProtectedMember
    panel._close = close
    # The field callback and button handler are the paths used by the rendered widgets.
    # noinspection PyProtectedMember,PyTypeChecker
    panel._on_sound_edited(Field(), 1, 0)
    assert panel.details["sound"][1].value == "RailSounds"
    dispatch.assert_not_called()
    # noinspection PyProtectedMember,PyTypeChecker
    panel._on_close_button()
    assert len(dispatch.call_args.args[0]) == 6
    assert dispatch.call_args.args[0][-2].data_bytes == b"\x01"
    # Simulate PopupManager invoking the registered post-close hook.
    # noinspection PyProtectedMember
    panel._post_close_action(None)
    host._keypad_view.entry_mode.assert_not_called()
    assert states[8].comp_data is None


def test_invalid_create_stays_open_and_sends_nothing(states, monkeypatch):
    panel, host = overlay_for(states[8])
    dispatch = Mock()
    monkeypatch.setattr(BaseReq, "process_sync_reqs", dispatch)
    close = Mock()
    # Substitute the inherited dismissal hook so the test does not allocate a Tk popup.
    # noinspection PyProtectedMember
    panel._close = close
    # Simulate a field edit followed by the footer's Create command.
    # noinspection PyProtectedMember,PyTypeChecker
    panel._on_road_name_edited(Field(), "", "Engine 8")
    # noinspection PyProtectedMember,PyTypeChecker
    panel._on_close_button()
    dispatch.assert_not_called()
    close.assert_not_called()
    host.app.warn.assert_called_once()
    assert panel.adding


def test_late_metadata_updates_operating_details_in_creation_panel(states):
    panel, _host = overlay_for(states[8])
    panel.details["speed"] = (SimpleNamespace(text_bold=False), Field())
    populate(states[8])
    panel.update(states[8])
    assert panel.details["speed"][1].value == "  0"


def test_existing_engine_set_reuses_record_without_reinitializing(states):
    state = states[8]
    populate(state)
    original = state.comp_data.as_bytes()
    state.initialize = Mock(side_effect=AssertionError("Existing records must be preserved"))
    host = host_for(states, 8)
    host.on_add_engine(8)
    host.on_info.assert_called_once_with(state=state, adding=True, awaiting_discovery=False)
    assert state.comp_data.as_bytes() == original


def test_two_controller_drafts_do_not_share_unsaved_edits(states):
    left, _left_host = overlay_for(states[8])
    right, _right_host = overlay_for(states[8])
    # Exercise the callback used by either embedded EngineGui pane.
    # noinspection PyProtectedMember,PyTypeChecker
    left._on_road_name_edited(Field(), "Left Draft", "Engine 8")
    right.update(states[8])
    assert left.details["name"][1].value == "Left Draft"
    assert right.details["name"][1].value == "Engine 8"
    assert states[8].comp_data is None


def test_queued_response_for_previous_engine_does_not_retarget_creation(states):
    host = host_for(states, 8)
    host._state_info = SimpleNamespace(adding=True)
    host._scope_tmcc_ids[CommandScope.ENGINE] = 8
    host._active_engine_state = states[8]
    # Only the callback's identity guard runs for an unrelated queued response.
    # noinspection PyTypeChecker
    EngineGui.on_new_engine(host, states[9])
    assert host._active_engine_state is states[8]


@pytest.fixture
def real_store(monkeypatch):
    # Isolate the state-store singleton so real deletion and recreation do not affect other tests.
    monkeypatch.setattr(ComponentStateStore, "_instance", None)
    return ComponentStateStore.build()


# The shell initializes the real GUI's private lifecycle state without constructing Tk widgets.
# noinspection PyProtectedMember
def pending_gui(store, state):
    panel, host = overlay_for(state)
    gui = EngineGui.__new__(EngineGui)
    gui._cv = Condition()
    gui.scope = CommandScope.ENGINE
    gui._state_store = store
    gui._state_info = None
    gui._provisional = set()
    gui._scope_tmcc_ids = {CommandScope.ENGINE: 0}
    gui._scope_watchers = {}
    gui._active_engine_state = None
    gui._shutdown_flag = Event()
    gui._message_queue = Queue()
    gui._scoped_callbacks = {CommandScope.ENGINE: Mock()}
    gui.repeat = 1
    gui.clear_throttle = Mock()
    gui.submit_request = Mock()
    gui.ops_mode = Mock()
    gui.on_info = lambda **_kwargs: setattr(gui, "_state_info", panel)
    gui.on_add_engine(state.tmcc_id)
    gui.monitor_state()
    return gui, panel, host


def dispatch_empty_record(gui, state):
    """Run the actual PDI empty-record deletion and its queued GUI subscriber callback."""
    payload = EngineData(None, state.tmcc_id).as_bytes()
    packet = BaseReq(
        state.tmcc_id,
        PdiCommand.BASE_MEMORY,
        scope=CommandScope.ENGINE,
        start=0,
        data_length=PdiReq.scope_record_length(CommandScope.ENGINE),
        data_bytes=payload,
    )
    response = BaseReq(packet.as_bytes)
    assert not response.is_active
    queue = Queue()
    queue.put(response)
    dispatcher = SimpleNamespace(
        _is_running=True,
        _cv=Condition(),
        _queue=queue,
        is_broadcasts_enabled=False,
        is_deletes_enabled=True,
        is_server=False,
        publish=lambda _topic, cleared: gui(cleared),
    )
    # Stop the real dispatch loop after this one packet; no listener thread or socket is needed.
    queue.task_done = lambda: setattr(dispatcher, "_is_running", False)
    # The dispatcher loop uses only the queue and subscriber services supplied above.
    # noinspection PyTypeChecker
    PdiDispatcher.run(dispatcher)
    # Drain the same callbacks the GUI event loop drains, including its deletion notification.
    # noinspection PyProtectedMember
    while not gui._message_queue.empty():
        # noinspection PyProtectedMember
        callback, args = gui._message_queue.get_nowait()
        callback(*args)


# Inspect the watcher binding to ensure future IR/database updates reach the replacement state.
# noinspection PyProtectedMember
def test_empty_base_response_preserves_creation_selection_draft_and_watcher(real_store):
    original = real_store.get_state(CommandScope.ENGINE, 8)
    gui, panel, _host = pending_gui(real_store, original)
    old_watcher = gui._scope_watchers[CommandScope.ENGINE]
    # Exercise the field callback without allocating an EditableText widget.
    # noinspection PyTypeChecker
    panel._on_road_name_edited(Field(), "My Engine", "Engine 8")
    try:
        dispatch_empty_record(gui, original)
        replacement = real_store.get_state(CommandScope.ENGINE, 8, create=False)
        assert original.is_deleted
        assert replacement is not None and replacement is not original
        assert not replacement.is_deleted
        assert replacement.comp_data is None
        assert not replacement.is_comp_data_record
        assert gui.scope_tmcc_id() == 8
        assert gui.active_engine_state is replacement
        assert panel.adding
        assert panel.details["name"][1].value == "My Engine"
        assert panel.details["number"][1].value == "8"
        assert panel.close_btn.text == "Create"
        assert gui._scope_watchers[CommandScope.ENGINE] is not old_watcher
        assert gui._scope_watchers[CommandScope.ENGINE].watched is replacement
        assert len(cast(Mock, gui.submit_request).call_args_list) == 2, "Only SET and its original read may be sent"
        # A second empty response must leave the draft usable as well.
        dispatch_empty_record(gui, replacement)
        assert gui.scope_tmcc_id() == 8
        assert panel.details["name"][1].value == "My Engine"
    finally:
        gui._scope_watchers[CommandScope.ENGINE].shutdown()


# The callback under test is private because it is registered directly on the footer button.
# noinspection PyProtectedMember
def test_create_after_empty_response_uses_replacement_state(real_store, monkeypatch):
    state = real_store.get_state(CommandScope.ENGINE, 8)
    gui, panel, host = pending_gui(real_store, state)
    dispatch = Mock()
    monkeypatch.setattr(BaseReq, "process_sync_reqs", dispatch)
    close = Mock()
    panel._close = close
    try:
        dispatch_empty_record(gui, state)
        replacement = real_store.get_state(CommandScope.ENGINE, 8, create=False)
        panel._on_close_button()
        assert len(dispatch.call_args.args[0]) == 6
        assert dispatch.call_args.args[0][-1] is replacement
        host.app.warn.assert_not_called()
        close.assert_called_once()
    finally:
        gui._scope_watchers[CommandScope.ENGINE].shutdown()


def test_populated_or_unrelated_record_deletion_is_not_an_empty_add_response(states):
    state = states[8]
    panel, _host = overlay_for(state)
    assert panel.awaiting_empty_record(state)
    assert not panel.awaiting_empty_record(states[9])
    assert not panel.awaiting_empty_record(states[113])
    populate(state)
    assert not panel.awaiting_empty_record(state)
    panel.update(state)
    assert not panel.awaiting_empty_record(state)


def test_discovery_requires_real_complete_metadata_and_a_valid_record(states, monkeypatch):
    state = states[113]
    session = EngineAddSession(state)
    assert not session.discovery_complete
    populate(state)
    session.refresh(state)
    assert session.has_complete_metadata
    assert not session.discovery_complete
    monkeypatch.setattr(EngineState, "record_no", property(lambda _state: 7))
    assert session.discovery_complete


def test_successful_discovery_goes_to_engine_ops_without_metadata_writes(states, monkeypatch):
    state = states[8]
    panel, host = overlay_for(state)
    # Supply the popup visibility used by the real completion check without constructing Tk.
    # noinspection PyProtectedMember
    panel._overlay = SimpleNamespace(visible=True)
    dispatch = Mock()
    monkeypatch.setattr(BaseReq, "process_sync_reqs", dispatch)
    # Simulate the inherited popup close hook without constructing a Tk popup.
    # noinspection PyProtectedMember
    panel._close = lambda: panel._post_close_action(None)
    populate(state)
    panel.update(state)
    assert not panel.adding
    dispatch.assert_not_called()
    host._keypad_view.entry_mode.assert_not_called()
    host.on_state_info_closed.assert_called_once()


def test_partial_discovery_keeps_manual_creation_open(states):
    state = states[8]
    panel, _host = overlay_for(state)
    # Supply the popup visibility used by the real completion check without constructing Tk.
    # noinspection PyProtectedMember
    panel._overlay = SimpleNamespace(visible=True)
    close = Mock()
    # Inspect dismissal requests without allocating a Tk popup.
    # noinspection PyProtectedMember
    panel._close = close
    populate(state)
    state.comp_data.sound_type = 255
    panel.update(state)
    assert panel.adding
    close.assert_not_called()
    assert panel.details["name"][1].value == "Pennsylvania"


def test_discovery_does_not_dismiss_user_edits_or_an_active_editor(states):
    state = states[8]
    panel, _host = overlay_for(state)
    # Supply the popup visibility used by the real completion check without constructing Tk.
    # noinspection PyProtectedMember
    panel._overlay = SimpleNamespace(visible=True)
    close = Mock()
    # Replace only the inherited close operation, preserving the real update behavior.
    # noinspection PyProtectedMember
    panel._close = close
    panel.details["name"][1].is_editing = True
    populate(state)
    panel.update(state)
    close.assert_not_called()
    panel.details["name"][1].is_editing = False
    # Commit the deliberate edit using the actual callback with a headless field.
    # noinspection PyProtectedMember,PyTypeChecker
    panel._on_road_name_edited(Field(), "My Name", "Engine 8")
    panel.update(state)
    assert panel.adding
    assert panel.details["name"][1].value == "My Name"
    close.assert_not_called()


def test_existing_complete_record_still_opens_for_explicit_review(states):
    state = states[8]
    populate(state)
    panel, _host = overlay_for(state)
    # Supply the popup visibility used by the real completion check without constructing Tk.
    # noinspection PyProtectedMember
    panel._overlay = SimpleNamespace(visible=True)
    close = Mock()
    # An already-known record is reviewed rather than completing a pending discovery.
    # noinspection PyProtectedMember
    panel._close = close
    panel.update(state)
    assert panel.adding
    assert panel.details["name"][1].value == "Pennsylvania"
    close.assert_not_called()


# Supply headless widget doubles for the real roster opening and configuration methods.
# noinspection PyProtectedMember
def test_reopening_engine_roster_lists_new_engine_with_saved_sort_and_filters():
    scope = CommandScope.ENGINE
    records = []
    rows = []
    gui = EngineGui.__new__(EngineGui)
    gui._cv = Condition()
    gui._route_builder_panel = None
    gui.scope = scope
    gui._state_store = SimpleNamespace(get_all=lambda _scope: records.copy())
    gui.on_scope = Mock()
    gui.show_popup = Mock()
    panel = CatalogPanel(gui, width=700, height=800)
    gui._catalog_panel = panel
    panel._overlay = Mock(title=SimpleNamespace(value=""))
    panel._catalog = Mock(append=rows.append, clear=rows.clear)
    panel._sort_btns = SimpleNamespace(value="0")
    panel._sel_1_btn = SimpleNamespace(value=0)
    panel._sel_2_btn = SimpleNamespace(value=0)
    panel._sel_3_btn = SimpleNamespace(value=0)
    panel._scoped_sort_order[scope] = 2
    panel._scoped_selection[scope] = (1, 0, 0)
    button = Mock(scope=scope)

    gui.on_scope_hold(button)
    assert rows == []

    records.extend(
        [
            SimpleNamespace(tmcc_id=10, name="Steam engine", is_name=True, is_diesel=False, is_steam=True),
            SimpleNamespace(tmcc_id=8, name="John Deere", is_name=True, is_diesel=True, is_steam=False),
        ]
    )
    gui.on_scope_hold(button)

    assert rows == ["8: John Deere"]
    assert panel._sort_btns.value == "2"
