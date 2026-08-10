from __future__ import annotations

from concurrent.futures import Future
from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.engine_gui as mod
from src.pytrain.gui.controller.engine_gui_conf import ENTER_KEY
from src.pytrain.protocol.constants import CommandScope


class _ImmediateExecutor:
    @staticmethod
    def submit(_callable) -> Future:
        future = Future()
        future.set_result(None)
        return future


class _Widget:
    def __init__(self, master, **kwargs) -> None:
        self.master = master
        self.kwargs = kwargs
        self.width = kwargs.get("width")
        self.tk = SimpleNamespace(
            winfo_width=lambda: 600,
            winfo_height=lambda: 100,
        )


def test_default_constructor_preserves_standalone_portrait_options(monkeypatch: pytest.MonkeyPatch) -> None:
    base_init: dict[str, object] = {}

    def fake_base_init(_self, **kwargs) -> None:
        base_init.update(kwargs)
        _self.width = 600
        _self.button_size = 100
        _self.title = "Engine/Train Control"
        _self._executor = _ImmediateExecutor()

    accessories = SimpleNamespace(path=None)
    monkeypatch.setattr(mod.GuiZeroBase, "__init__", fake_base_init)
    monkeypatch.setattr(mod.EngineGui, "init_complete", lambda _self: None)
    monkeypatch.setattr(mod.EngineGui, "_accessory_config_signature", lambda _self, _path: ("", False, None, None))
    monkeypatch.setattr(mod, "PopupManager", lambda host: SimpleNamespace(host=host))
    monkeypatch.setattr(mod, "ImagePresenter", lambda host: SimpleNamespace(host=host))
    monkeypatch.setattr(mod, "ControllerView", lambda host: SimpleNamespace(host=host))
    monkeypatch.setattr(mod, "KeypadView", lambda host: SimpleNamespace(host=host))
    monkeypatch.setattr(mod.ConfiguredAccessorySet, "from_file", lambda *_args, **_kwargs: accessories)
    monkeypatch.setattr(mod, "ConfiguredAccessoryAdapterProvider", lambda configured, host: (configured, host))

    gui = mod.EngineGui()

    assert base_init == {
        "title": "Engine GUI",
        "width": None,
        "height": None,
        "enabled_bg": "green",
        "disabled_bg": "white",
        "enabled_text": "black",
        "disabled_text": "lightgrey",
        "active_bg": "green",
        "inactive_bg": "#f7f7f7",
        "scale_by": 1.5,
        "full_screen": True,
        "x_offset": 0,
        "y_offset": 0,
    }
    assert "stand_alone" not in base_init
    assert gui.scope == CommandScope.ENGINE
    assert gui.initial is None
    assert gui.repeat == 2
    assert gui.num_recents == 5
    assert gui.auto_scroll is True
    assert gui.enable_editing is True


def test_standalone_emergency_row_keeps_local_halt_and_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    widgets: list[_Widget] = []

    def make_widget(master, **kwargs):
        widget = _Widget(master, **kwargs)
        widgets.append(widget)
        return widget

    monkeypatch.setattr(mod, "Box", make_widget)
    monkeypatch.setattr(mod, "Text", make_widget)
    monkeypatch.setattr(mod, "HoldButton", make_widget)
    app = SimpleNamespace(tk=SimpleNamespace(update_idletasks=lambda: None))
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._app = app
    gui.width = 600
    gui.text_pad_x = 20
    gui.text_pad_y = 20
    gui.s_20 = 30
    gui._scale_factor = 1.0

    gui.make_emergency_buttons(app)

    assert gui.emergency_box.master is app
    assert gui.halt_btn.kwargs == {
        "text": mod.HALT_KEY,
        "grid": [0, 1],
        "align": "top",
        "width": 11,
        "padx": 20,
        "pady": 20,
        "bg": "red",
        "text_bold": True,
        "text_size": 30,
        "command": gui.on_keypress,
        "args": [mod.HALT_KEY],
    }
    assert gui.reset_btn.kwargs["text"] == "Reset"
    assert gui.reset_btn.kwargs["enabled"] is False
    assert gui.reset_btn.kwargs["on_press"] == (gui.on_engine_command, ["RESET"])
    assert gui.reset_btn.kwargs["on_repeat"] == (gui.on_engine_command, ["RESET"])
    assert gui.reset_btn.kwargs["repeat_interval"] == pytest.approx(0.2)
    assert widgets[0] is gui.emergency_box


def test_halt_command_is_dispatched_immediately_on_calling_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui.scope = CommandScope.ENGINE
    gui._scope_tmcc_ids = {CommandScope.ENGINE: 0}
    halt = SimpleNamespace(send_calls=0)
    halt.send = lambda: setattr(halt, "send_calls", halt.send_calls + 1)
    monkeypatch.setitem(mod.KEY_TO_COMMAND, mod.HALT_KEY, halt)
    gui.submit_request = lambda *_args, **_kwargs: pytest.fail("Halt must not be queued")

    gui.do_command(mod.HALT_KEY)

    assert halt.send_calls == 1


def test_engine_command_splits_targets_and_preserves_dispatch_order() -> None:
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui.scope = CommandScope.ENGINE
    gui.repeat = 2
    gui._scope_tmcc_ids = {CommandScope.ENGINE: 17}
    gui._state_store = SimpleNamespace(get_state=lambda *_args: None)
    gui.tmcc_id_text = SimpleNamespace(value="0017")
    dispatched: list[tuple] = []
    gui.do_engine_command = lambda *args: dispatched.append(args)

    gui.on_engine_command("HORN, BELL", data=3, repeat=4)

    assert [call[1] for call in dispatched] == ["HORN", "BELL"]
    assert [call[8] for call in dispatched] == [0.0, 0.1]
    assert all(call[0] == 17 for call in dispatched)
    assert all(call[2] == 3 and call[6] == 4 for call in dispatched)


def test_destroy_gui_releases_standalone_subscriptions_and_widget_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._accessory_config_watcher_future = None
    gui._accessory_overlay_prewarm_generation = 0
    gui.engine_ops_cells = {"key": object()}
    gui.box = object()
    gui.acc_box = object()
    gui._image = object()
    calls: list[object] = []
    gui.clear_cache = lambda: calls.append("clear_cache")
    dispatcher = SimpleNamespace(unsubscribe_delete=lambda target: calls.append(target))
    monkeypatch.setattr(mod.PdiDispatcher, "is_built", staticmethod(lambda: True))
    monkeypatch.setattr(mod.PdiDispatcher, "get", staticmethod(lambda: dispatcher))

    gui.destroy_gui()

    assert calls == [gui, "clear_cache"]
    assert gui.engine_ops_cells == {}
    assert gui.box is None
    assert gui.acc_box is None
    assert gui._image is None


def test_embedded_constructor_uses_parent_root_and_owner_queue(monkeypatch: pytest.MonkeyPatch) -> None:
    base_init: dict[str, object] = {}
    attached: list[object] = []
    app = object()
    pane = object()
    sync_state = object()
    owner = SimpleNamespace(app=app, sync_state=sync_state)

    def fake_base_init(_self, **kwargs) -> None:
        base_init.update(kwargs)
        _self.width = kwargs["width"]
        _self.button_size = 100
        _self.title = "Engine/Train Control"
        _self._executor = _ImmediateExecutor()

    accessories = SimpleNamespace(path=None)
    monkeypatch.setattr(mod.GuiZeroBase, "__init__", fake_base_init)
    monkeypatch.setattr(mod.GuiZeroBase, "attach_to_parent_queue", lambda _self, parent: attached.append(parent))
    monkeypatch.setattr(mod.EngineGui, "init_complete", lambda _self: None)
    monkeypatch.setattr(mod.EngineGui, "_accessory_config_signature", lambda _self, _path: ("", False, None, None))
    monkeypatch.setattr(mod, "PopupManager", lambda host: SimpleNamespace(host=host))
    monkeypatch.setattr(mod, "ImagePresenter", lambda host: SimpleNamespace(host=host))
    monkeypatch.setattr(mod, "ControllerView", lambda host: SimpleNamespace(host=host))
    monkeypatch.setattr(mod, "KeypadView", lambda host: SimpleNamespace(host=host))
    monkeypatch.setattr(mod.ConfiguredAccessorySet, "from_file", lambda *_args, **_kwargs: accessories)
    monkeypatch.setattr(mod, "ConfiguredAccessoryAdapterProvider", lambda configured, host: (configured, host))

    gui = mod.EngineGui(
        width=620,
        height=720,
        stand_alone=False,
        parent=pane,
        parent_gui=owner,
        compact=True,
        show_halt=False,
    )

    assert base_init["stand_alone"] is False
    assert gui.app is app
    assert gui.root is pane
    assert gui.compact is True
    assert gui.show_halt is False
    assert gui.sync_state is sync_state
    assert attached == [owner]


@pytest.mark.parametrize(
    ("stand_alone", "parent", "parent_gui"),
    [
        (True, object(), None),
        (False, None, SimpleNamespace(app=object())),
        (False, object(), None),
    ],
)
def test_invalid_embedded_parent_combinations_are_rejected(stand_alone, parent, parent_gui) -> None:
    with pytest.raises(ValueError):
        mod.EngineGui(stand_alone=stand_alone, parent=parent, parent_gui=parent_gui)


def test_embedded_emergency_row_can_hide_halt_without_removing_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    widgets: list[_Widget] = []

    def make_widget(master, **kwargs):
        widget = _Widget(master, **kwargs)
        widgets.append(widget)
        return widget

    monkeypatch.setattr(mod, "Box", make_widget)
    monkeypatch.setattr(mod, "Text", make_widget)
    monkeypatch.setattr(mod, "HoldButton", make_widget)
    app = SimpleNamespace(tk=SimpleNamespace(update_idletasks=lambda: None))
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._app = app
    gui.width = 600
    gui.text_pad_x = 20
    gui.text_pad_y = 20
    gui.s_20 = 30
    gui.s_18 = 27
    gui._scale_factor = 1.0
    gui._show_halt = False
    gui._compact = False

    gui.make_emergency_buttons(object())

    assert gui.halt_btn is None
    assert gui.reset_btn.kwargs["text"] == "Reset"
    assert [widget.kwargs.get("text") for widget in widgets].count("Reset") == 1


def test_compact_emergency_row_uses_short_actions_and_minimal_padding(monkeypatch: pytest.MonkeyPatch) -> None:
    widgets: list[_Widget] = []

    def make_widget(master, **kwargs):
        widget = _Widget(master, **kwargs)
        widgets.append(widget)
        return widget

    monkeypatch.setattr(mod, "Box", make_widget)
    monkeypatch.setattr(mod, "Text", make_widget)
    monkeypatch.setattr(mod, "HoldButton", make_widget)
    app = SimpleNamespace(tk=SimpleNamespace(update_idletasks=lambda: None))
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._app = app
    gui.width = 632
    gui.text_pad_x = 20
    gui.text_pad_y = 20
    gui.s_20 = 18
    gui.s_18 = 16
    gui._scale_factor = 1.0
    gui._show_halt = False
    gui._compact = True
    gui._linked_car_transfer = object()

    gui.make_emergency_buttons(object())

    assert gui.reset_btn.kwargs["padx"] == 4
    assert gui.reset_btn.kwargs["pady"] == 4
    assert gui.linked_cars_btn.kwargs["text"] == "Cars..."
    assert gui.linked_cars_btn.kwargs["padx"] == 4
    assert [widget.kwargs.get("text") for widget in widgets].count(" ") == 0


def test_compact_keypad_uses_ascii_enter_label_without_changing_command_value() -> None:
    captured: dict[str, object] = {}
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._compact = True
    gui.on_keypress = lambda _key: None
    gui._build_keypad_button = lambda **kwargs: captured.update(kwargs) or (object(), object())
    gui.ops_cells = set()
    gui.entry_cells = set()

    gui.make_keypad_button(object(), ENTER_KEY, 0, 0)

    assert captured["label"] == ENTER_KEY
    assert captured["args"] == [ENTER_KEY]


def test_compact_image_baseline_is_positive_and_bounded_by_pane() -> None:
    def widget(width: int, height: int):
        return SimpleNamespace(tk=SimpleNamespace(winfo_reqwidth=lambda: width, winfo_reqheight=lambda: height))

    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._app = SimpleNamespace(tk=SimpleNamespace(update_idletasks=lambda: None))
    gui.width = 632
    gui.height = 724
    gui.header = widget(632, 34)
    gui.emergency_box = widget(900, 36)
    gui.emergency_box_width = 900
    gui.emergency_box_height = 36
    gui.info_box = widget(632, 30)
    gui.scope_box = widget(632, 36)
    gui.controller_box = widget(632, 400)

    gui._compute_engine_image_baseline()

    assert gui.avail_image_height == 168
    assert gui.avail_image_width == 632


def test_info_box_height_is_bounded_only_in_compact_mode() -> None:
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui.button_size = 79

    gui._compact = True
    assert gui.info_box_height == 52
    assert gui.fit_info_box_height(68) == 68

    gui._compact = False
    assert gui.info_box_height is None
    assert gui.fit_info_box_height(68) == 68


def test_destroy_embedded_finalizes_child_without_destroying_shared_app() -> None:
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._stand_alone = False
    app = SimpleNamespace(destroy_calls=0, destroy=lambda: setattr(app, "destroy_calls", app.destroy_calls + 1))
    gui._app = app
    calls: list[str] = []
    gui.close = lambda: calls.append("close")
    gui.destroy_gui = lambda: calls.append("destroy_gui")
    gui._finalize_gui_resources = lambda: calls.append("finalize")

    gui.destroy_embedded()

    assert calls == ["close", "destroy_gui", "finalize"]
    assert app.destroy_calls == 0


def test_embedded_build_uses_pane_root_and_relative_popup_position(monkeypatch: pytest.MonkeyPatch) -> None:
    roots: list[tuple[str, object]] = []
    font_requests: list[tuple[str, str]] = []
    pane = SimpleNamespace(tk=SimpleNamespace(winfo_rootx=lambda: 100, winfo_rooty=lambda: 200))
    app_tk = SimpleNamespace(after_idle=lambda _func: None, after=lambda *_args: None)
    app = SimpleNamespace(tk=app_tk)
    combo = SimpleNamespace(
        tk=SimpleNamespace(children={}),
        _selected=object(),
        text_size=None,
        text_bold=False,
    )
    monkeypatch.setattr(mod, "Combo", lambda root, **_kwargs: roots.append(("header", root)) or combo)
    monkeypatch.setattr(
        mod,
        "resolve_font_family",
        lambda _root, preferred, fallback: font_requests.append((preferred, fallback)) or fallback,
    )
    monkeypatch.setattr(
        mod.PdiDispatcher,
        "get",
        staticmethod(lambda: SimpleNamespace(subscribe_delete=lambda _target: None)),
    )
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._app = app
    gui._parent = pane
    gui.title = "Engine/Train Control"
    gui.s_24 = 24
    gui.get_options = lambda: []
    gui.make_emergency_buttons = lambda root: roots.append(("emergency", root))
    gui.make_info_box = lambda root: roots.append(("info", root))
    gui.make_scope = lambda root: roots.append(("scope", root))
    gui._engine_buttons_future = _ImmediateExecutor.submit(None)
    gui._keypad_view = SimpleNamespace(build=lambda root: roots.append(("keypad", root)))
    gui._controller_view = SimpleNamespace(build=lambda root: roots.append(("controller", root)))
    gui._popup = SimpleNamespace(
        is_combo_hackable=False,
        get_or_create=lambda *_args: None,
        preload_images=lambda: None,
    )
    gui._compute_engine_image_baseline = lambda: None
    gui.avail_image_height = 300
    gui.avail_image_width = 500
    gui.image_box = SimpleNamespace(tk=SimpleNamespace(config=lambda **_kwargs: None))
    gui.info_box = SimpleNamespace(
        tk=SimpleNamespace(
            winfo_rootx=lambda: 110,
            winfo_rooty=lambda: 220,
            winfo_reqheight=lambda: 30,
        )
    )
    gui._sensor_track_id = None
    gui.initial = None
    gui.power_on_path = None
    gui.power_off_path = None
    gui.turn_off_image = None
    gui.op_acc_image = None
    gui._start_accessory_overlay_prewarm = lambda: None
    gui._start_accessory_config_watcher = lambda: None

    gui.build_gui()

    assert roots == [
        ("header", pane),
        ("emergency", pane),
        ("info", pane),
        ("keypad", pane),
        ("controller", pane),
        ("scope", pane),
    ]
    assert font_requests == [("DigitalDream", "DigitalDream")]
    assert gui.digital_font == "DigitalDream"
    assert gui.popup_position == (10, 50)


def test_linked_car_contract_is_read_only_and_selects_through_public_transition() -> None:
    car_one = SimpleNamespace(tmcc_id=11)
    car_two = SimpleNamespace(tmcc_id=12)
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._train_linked_queue = [car_one, car_two]
    gui.scope = CommandScope.TRAIN
    gui._scope_tmcc_ids = {CommandScope.TRAIN: 44, CommandScope.ENGINE: 0}
    calls: list[tuple] = []
    gui.on_scope = lambda scope: calls.append(("scope", scope))
    gui.update_component_info = lambda tmcc_id: calls.append(("select", tmcc_id))

    linked = gui.linked_car_states
    gui.select_component(CommandScope.ENGINE, 12)

    assert linked == (car_one, car_two)
    assert isinstance(linked, tuple)
    assert calls == [("scope", CommandScope.ENGINE), ("select", 12)]


def test_active_selection_only_reflects_current_scope() -> None:
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui.scope = CommandScope.ENGINE
    gui._scope_tmcc_ids = {CommandScope.ENGINE: 0, CommandScope.TRAIN: 44}

    assert gui.has_active_selection is False
    gui._scope_tmcc_ids[CommandScope.ENGINE] = 9
    assert gui.has_active_selection is True


def test_missing_linked_car_states_do_not_break_train_selection() -> None:
    train = SimpleNamespace(is_deleted=False, num_train_linked=1, link_tmcc_ids=[77])
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._active_train_state = None
    gui._train_linked_queue = []
    gui._state_store = SimpleNamespace(get_state=lambda *_args: None)
    gui.scope = CommandScope.TRAIN
    gui._scope_buttons = {CommandScope.ENGINE: SimpleNamespace(bg="white")}
    gui.linked_cars_btn = SimpleNamespace(enabled=True)
    calls: list[str] = []
    gui._setup_train_link_gui = lambda _state: calls.append("setup")
    gui._tear_down_link_gui = lambda: calls.append("teardown")
    gui._request_options_rebuild = lambda: None
    gui.on_new_engine = lambda *_args, **_kwargs: None

    gui.on_new_train(train)

    assert calls == ["teardown"]
