from __future__ import annotations

from concurrent.futures import Future
from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.engine_gui as mod
from src.pytrain.gui.controller.engine_gui_conf import ENTER_KEY
from src.pytrain.gui.controller.steam_deck_input import HORN_COMMAND
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


class _ImmediateExecutor:
    @staticmethod
    def submit(_callable) -> Future:
        future = Future()
        future.set_result(None)
        return future


class _Widget:
    def __init__(self, master, *_args, **kwargs) -> None:
        self.master = master
        self.kwargs = kwargs
        self.width = kwargs.get("width")
        self.pack_configs = []
        self.grid_configs = []
        self.grid_columns = []
        self.grid_propagates = []
        self.tk = SimpleNamespace(
            winfo_width=lambda: 600,
            winfo_height=lambda: 100,
            config=lambda **_kwargs: None,
            pack_configure=lambda **config: self.pack_configs.append(config),
            pack_propagate=lambda _value: None,
            grid_propagate=lambda _value: self.grid_propagates.append(_value),
            grid_columnconfigure=lambda column, **config: self.grid_columns.append((column, config)),
            grid_configure=lambda **config: self.grid_configs.append(config),
        )

    def hide(self) -> None:
        pass


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
    assert gui.reset_btn.kwargs["repeat_interval"] == pytest.approx(0.1)
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


def _horn_gui() -> "mod.EngineGui":
    # A bare EngineGui with only the state ``do_engine_command`` touches for the
    # horn path, plus a recording ``submit_request`` so we can inspect the
    # resolved command.
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui.scope = CommandScope.ENGINE
    gui.repeat = 1
    gui._scope_tmcc_ids = {CommandScope.ENGINE: 5}
    gui.submitted = []
    gui.submit_request = lambda cmd, repeat=None, delay=0.0: gui.submitted.append(cmd)
    return gui


def test_horn_command_sounds_quilling_horn_with_intensity_for_legacy_engine() -> None:
    # The trackpad/trigger horn sends the ``HORN_COMMAND`` fallback list with the
    # drag intensity. A Legacy (TMCC2) engine must resolve it to the Quilling
    # Horn, honoring the 0..15 intensity.
    gui = _horn_gui()
    state = SimpleNamespace(is_legacy=True, tmcc_id=5, scope=CommandScope.ENGINE)

    gui.on_engine_command(HORN_COMMAND, data=15, state=state)

    assert len(gui.submitted) == 1
    assert gui.submitted[0].command is TMCC2EngineCommandEnum.QUILLING_HORN
    assert gui.submitted[0].data == 15


def test_horn_command_falls_back_to_blow_horn_for_non_legacy_engine() -> None:
    # A non-Legacy (TMCC1/Cab-1) engine has no Quilling Horn, so the fallback
    # list must fall through to the plain Blow Horn (the intensity is ignored).
    gui = _horn_gui()
    state = SimpleNamespace(is_legacy=False, tmcc_id=5, scope=CommandScope.ENGINE)

    gui.on_engine_command(HORN_COMMAND, data=15, state=state)

    assert len(gui.submitted) == 1
    assert gui.submitted[0].command is TMCC1EngineCommandEnum.BLOW_HORN_ONE


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
    assert gui.emergency_box.pack_configs == [{"fill": "x", "expand": False}]
    # The emergency box is a grid container, so it must disable grid propagation
    # (not just pack propagation) to hold its full width and let the column
    # weights stretch the action buttons across the whole row.
    assert gui.emergency_box.grid_propagates == [False]
    assert gui.reset_btn.grid_configs == [{"sticky": "ew"}]
    assert gui.linked_cars_btn.grid_configs == [{"sticky": "ew"}]


def test_compact_info_text_expands_vertically_within_road_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "Box", _Widget)
    monkeypatch.setattr(mod, "TitleBox", _Widget)
    monkeypatch.setattr(mod, "Text", _Widget)
    monkeypatch.setattr(mod, "ScrollingText", _Widget)
    monkeypatch.setattr(mod, "Picture", _Widget)
    # A detector is attached to the image and to the container owning the margin
    # beside it; the latter passes a should_start region predicate.
    monkeypatch.setattr(mod, "SwipeDetector", lambda _widget, should_start=None, bind_directly=False: SimpleNamespace())
    app = SimpleNamespace(tk=SimpleNamespace(after=lambda *_args: None))
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._compact = True
    gui.button_size = 79
    gui.scope = SimpleNamespace(title="Road Number")
    gui.s_10 = 9
    gui.s_12 = 11
    gui.s_18 = 16
    gui.s_20 = 18
    gui.auto_scroll = True
    gui._bind_image_long_press = lambda: None

    gui.make_info_box(app)

    assert gui.tmcc_id_text.pack_configs == [{"fill": "both", "expand": True}]
    assert gui.name_text.pack_configs == [{"fill": "both", "expand": True}]


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
    gui._compact = True
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

    assert gui.avail_image_height == 108
    assert gui.avail_image_width == 324


def test_compact_image_box_is_three_times_wider_and_height_limited() -> None:
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui._compact = True
    gui.height = 800

    assert gui.fit_image_box_size(available_height=260, available_width=632) == (120, 360)
    assert gui.fit_image_box_size(available_height=260, available_width=200) == (66, 198)
    assert gui.fit_image_box_size(available_height=-1, available_width=632) == (0, 0)

    gui._compact = False
    assert gui.fit_image_box_size(available_height=260, available_width=632) == (260, 632)


def test_compact_image_scaling_preserves_source_aspect_ratio() -> None:
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui.calc_image_box_size = lambda: (120, 360)

    gui._compact = True
    assert gui._calc_scaled_image_size(600, 300) == (240, 120)

    gui._compact = False
    assert gui._calc_scaled_image_size(600, 300) == (360, 120)


def test_info_box_height_is_bounded_only_in_compact_mode() -> None:
    gui = mod.EngineGui.__new__(mod.EngineGui)
    gui.button_size = 79
    gui.width = 632
    gui.s_16 = 14
    gui.s_18 = 16
    gui.s_20 = 18

    gui._compact = True
    assert gui.info_box_height == 44
    assert gui.fit_info_box_height(68) == 44
    assert gui.fit_info_id_width(actual_width=1, required_width=84) == 84
    assert gui.fit_emergency_box_width(500) == 632
    assert gui.info_id_text_size == 16
    assert gui.info_name_text_size == 16

    gui._compact = False
    assert gui.info_box_height is None
    assert gui.fit_info_box_height(68) == 68
    assert gui.fit_info_id_width(actual_width=1, required_width=84) == 1
    assert gui.fit_emergency_box_width(500) == 500
    assert gui.info_id_text_size == 18
    assert gui.info_name_text_size == 16


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
    gui._compact = True
    gui.title = "Engine/Train Control"
    gui.s_24 = 24
    gui.get_options = lambda: []
    gui.make_emergency_buttons = lambda root: roots.append(("emergency", root))
    gui.make_info_box = lambda root: roots.append(("info", root))
    gui.make_scope_box = lambda root: roots.append(("scope_box", root))
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
        ("scope_box", pane),
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
