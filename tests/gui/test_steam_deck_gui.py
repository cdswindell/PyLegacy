from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.steam_deck_gui as mod


class _Tk:
    def __init__(self) -> None:
        self.config: dict[str, object] = {}
        self.bindings: dict[str, object] = {}

    def configure(self, **kwargs) -> None:
        self.config.update(kwargs)

    config = configure

    def bind(self, event, callback) -> None:
        self.bindings[event] = callback

    @staticmethod
    def place(**_kwargs) -> None:
        return

    @staticmethod
    def pack_propagate(_enabled) -> None:
        return

    @staticmethod
    def grid_columnconfigure(*_args, **_kwargs) -> None:
        return

    @staticmethod
    def update_idletasks() -> None:
        return


class _Widget:
    def __init__(self, master=None, **kwargs) -> None:
        self.master = master
        self.kwargs = kwargs
        self.tk = _Tk()
        self.bg = kwargs.get("bg")
        self.value = kwargs.get("text", "")

    def destroy(self) -> None:
        return


def test_landscape_defaults_target_native_steam_deck_size(monkeypatch: pytest.MonkeyPatch) -> None:
    base_init: dict[str, object] = {}

    def fake_base_init(_self, **kwargs) -> None:
        base_init.update(kwargs)
        _self.width = kwargs["width"]
        _self.height = kwargs["height"]

    monkeypatch.setattr(mod.GuiZeroBase, "__init__", fake_base_init)
    monkeypatch.setattr(mod.SteamDeckGui, "init_complete", lambda _self: None)

    gui = mod.SteamDeckGui()

    assert base_init["width"] == 1280
    assert base_init["height"] == 800
    assert base_init["full_screen"] is True
    assert gui.pane_width == 639
    assert gui.pane_height == 800
    # The two panes plus the divider must account for the whole display exactly: any
    # shortfall is white space down the outer edges, and any excess clips a pane.
    assert 2 * gui.pane_width + mod.DIVIDER_WIDTH + mod.HORIZONTAL_MARGIN == mod.STEAM_DECK_WIDTH
    assert gui.focused_panel == "right"


def test_build_creates_two_independent_compact_controllers(monkeypatch: pytest.MonkeyPatch) -> None:
    children: list[SimpleNamespace] = []
    widgets: list[_Widget] = []

    def make_widget(master=None, **kwargs):
        widget = _Widget(master, **kwargs)
        widgets.append(widget)
        return widget

    def make_child(**kwargs):
        child = SimpleNamespace(kwargs=kwargs, build_calls=0, destroy_calls=0, title="My Layout")
        child.build_gui = lambda: setattr(child, "build_calls", child.build_calls + 1)
        child.destroy_embedded = lambda: setattr(child, "destroy_calls", child.destroy_calls + 1)
        children.append(child)
        return child

    monkeypatch.setattr(mod, "Box", make_widget)
    monkeypatch.setattr(mod, "Text", make_widget)
    monkeypatch.setattr(mod, "EngineGui", make_child)
    gui = mod.SteamDeckGui.__new__(mod.SteamDeckGui)
    gui.width = 1280
    gui.height = 800
    gui._app = SimpleNamespace(tk=_Tk())
    gui._pane_width = 632
    gui._pane_height = 800
    gui._focused_panel = "left"
    gui.title = "David's Railroad"
    gui._left_options = {"tmcc_id": 12}
    gui._right_options = {"tmcc_id": 34}
    gui.left_gui = gui.right_gui = None

    gui.build_gui()

    assert len(children) == 2
    assert children[0].kwargs["tmcc_id"] == 12
    assert children[1].kwargs["tmcc_id"] == 34
    assert children[0].kwargs["parent"] is not children[1].kwargs["parent"]
    assert all(child.kwargs["parent_gui"] is gui for child in children)
    assert all(child.kwargs["stand_alone"] is False for child in children)
    assert all(child.kwargs["compact"] is True for child in children)
    assert all(child.kwargs["show_halt"] is True for child in children)
    assert all("linked_car_transfer" not in child.kwargs for child in children)
    assert all(child.kwargs["width"] == 632 for child in children)
    assert all(child.kwargs["height"] == 800 for child in children)
    assert all(child.kwargs["scale_by"] == mod.LANDSCAPE_FONT_SCALE for child in children)
    assert all(child.kwargs["button_divisor"] == mod.LANDSCAPE_BUTTON_DIVISOR for child in children)
    assert all(child.title == "David's Railroad" for child in children)
    assert [child.build_calls for child in children] == [1, 1]
    assert not any(widget.value in {"Left", "Right", "Pair Panels", mod.HALT_KEY} for widget in widgets)
    assert gui.left_root is gui.left_pane
    assert gui.right_root is gui.right_pane


def test_focus_changes_without_altering_other_controller() -> None:
    gui = mod.SteamDeckGui.__new__(mod.SteamDeckGui)
    gui._focused_panel = "left"
    left_gui = object()
    right_gui = object()
    gui.left_gui = left_gui
    gui.right_gui = right_gui

    gui.focus_panel("right")

    assert gui.focused_panel == "right"
    assert gui.focused_gui is right_gui
    with pytest.raises(ValueError):
        gui.focus_panel("center")


def test_toggle_focus_alternates_between_panels() -> None:
    gui = mod.SteamDeckGui.__new__(mod.SteamDeckGui)
    gui._focused_panel = "left"
    gui.left_gui = object()
    gui.right_gui = object()

    gui.toggle_focus()
    assert gui.focused_panel == "right"

    gui.toggle_focus()
    assert gui.focused_panel == "left"


def test_focus_arrow_points_toward_active_pane() -> None:
    gui = mod.SteamDeckGui.__new__(mod.SteamDeckGui)
    gui._focused_panel = "left"
    gui.left_pane = gui.right_pane = None
    gui.focus_arrow = _Widget()

    gui.focus_panel("left")
    assert gui.focus_arrow.value == mod.FOCUS_ARROW_LEFT

    gui.focus_panel("right")
    assert gui.focus_arrow.value == mod.FOCUS_ARROW_RIGHT


def test_global_halt_sends_immediately_once(monkeypatch: pytest.MonkeyPatch) -> None:
    halt = SimpleNamespace(send_calls=0)
    halt.send = lambda: setattr(halt, "send_calls", halt.send_calls + 1)
    monkeypatch.setitem(mod.KEY_TO_COMMAND, mod.HALT_KEY, halt)
    gui = mod.SteamDeckGui.__new__(mod.SteamDeckGui)

    gui.on_halt()

    assert halt.send_calls == 1


def test_destroy_gui_tears_down_both_children() -> None:
    gui = mod.SteamDeckGui.__new__(mod.SteamDeckGui)
    left = SimpleNamespace(calls=0)
    right = SimpleNamespace(calls=0)
    left.destroy_embedded = lambda: setattr(left, "calls", left.calls + 1)
    right.destroy_embedded = lambda: setattr(right, "calls", right.calls + 1)
    gui.left_gui = left
    gui.right_gui = right
    gui._elements = set()
    gui.clear_cache = lambda: None

    gui.destroy_gui()

    assert left.calls == 1
    assert right.calls == 1
    assert gui.left_gui is None
    assert gui.right_gui is None


def test_controller_poll_routes_actions_on_tk_thread_and_reschedules(monkeypatch: pytest.MonkeyPatch) -> None:
    action = object()
    provider = SimpleNamespace(poll=lambda: [action])
    router = SimpleNamespace(actions=[], ticks=[])
    router.handle = lambda value: router.actions.append(value)
    router.tick = lambda value: router.ticks.append(value)
    scheduled: list[tuple[int, object]] = []
    gui = mod.SteamDeckGui.__new__(mod.SteamDeckGui)
    gui._app = SimpleNamespace(
        tk=SimpleNamespace(after=lambda delay, callback: scheduled.append((delay, callback)) or "a1")
    )
    gui._input_provider = provider
    gui._input_router = router
    gui._controller_poll_id = None
    monkeypatch.setattr(mod.time, "monotonic", lambda: 123.5)

    gui._poll_controller()

    assert router.actions == [action]
    assert router.ticks == [123.5]
    assert scheduled == [(mod.CONTROLLER_POLL_MS, gui._poll_controller)]
    assert gui._controller_poll_id == "a1"


def test_controller_shutdown_cancels_poll_and_clears_input() -> None:
    calls: list[str] = []
    gui = mod.SteamDeckGui.__new__(mod.SteamDeckGui)
    gui._app = SimpleNamespace(tk=SimpleNamespace(after_cancel=lambda poll_id: calls.append(f"cancel:{poll_id}")))
    gui._controller_poll_id = "poll-1"
    gui._input_provider = SimpleNamespace(stop=lambda: calls.append("stop"))
    gui._input_router = SimpleNamespace(clear=lambda: calls.append("clear"))

    gui._stop_controller_input()

    assert calls == ["cancel:poll-1", "stop", "clear"]
    assert gui._controller_poll_id is None


def test_missing_pygame_keeps_touch_gui_available(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = mod.SteamDeckGui.__new__(mod.SteamDeckGui)
    gui._enable_controller = True
    gui._controller_profile = object()
    gui.left_gui = object()
    gui.right_gui = object()
    gui._app = SimpleNamespace(tk=SimpleNamespace(after=lambda *_args: pytest.fail("poll should not start")))
    monkeypatch.setattr(
        mod, "DeckInputRouter", lambda *_args, **_kwargs: SimpleNamespace(switch_active=lambda _target: False)
    )

    class UnavailableProvider:
        def __init__(self, _profile, **_kwargs) -> None:
            return

        @staticmethod
        def start() -> None:
            raise mod.ControllerUnavailable("pygame unavailable")

    monkeypatch.setattr(mod, "SteamDeckInputProvider", UnavailableProvider)

    gui._start_controller_input()

    assert gui._input_provider is None
    assert gui._controller_poll_id is None


def test_controller_input_tells_the_provider_which_panel_holds_a_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    # A trigger throwing a track switch fires on the squeeze rather than on the release, and
    # only the router can say which panel a binding targets -- so it is the router's
    # resolver the provider is handed.
    router = SimpleNamespace(switch_active=lambda target: target == "left")
    monkeypatch.setattr(mod, "DeckInputRouter", lambda *_args, **_kwargs: router)
    captured: dict[str, object] = {}

    class Provider:
        def __init__(self, _profile, *, switch_active=None) -> None:
            captured["switch_active"] = switch_active

        @staticmethod
        def start() -> None:
            return

    monkeypatch.setattr(mod, "SteamDeckInputProvider", Provider)
    gui = mod.SteamDeckGui.__new__(mod.SteamDeckGui)
    gui._enable_controller = True
    gui._controller_profile = object()
    gui.left_gui = object()
    gui.right_gui = object()
    gui._app = SimpleNamespace(tk=SimpleNamespace(after=lambda *_args: "poll-1"))

    gui._start_controller_input()

    assert captured["switch_active"] is router.switch_active
    assert captured["switch_active"]("left") is True


def test_linked_car_transfer_uses_other_panel_and_confirms_occupied_target() -> None:
    car = SimpleNamespace(tmcc_id=77, name="Sound Car")
    source = SimpleNamespace(linked_car_states=(car,))
    target = SimpleNamespace(has_active_selection=True, selections=[])
    target.select_component = lambda scope, tmcc_id: target.selections.append((scope, tmcc_id))
    confirmations: list[str] = []
    gui = mod.SteamDeckGui.__new__(mod.SteamDeckGui)
    gui.left_gui = source
    gui.right_gui = target
    gui._confirm_replace = lambda message: confirmations.append(message) or False

    assert gui.transfer_linked_car("left", car) is False
    assert target.selections == []
    assert "Sound Car" in confirmations[0]
    gui._confirm_replace = lambda _message: True
    assert gui.transfer_linked_car("left", car) is True
    assert target.selections == [(mod.CommandScope.ENGINE, 77)]


def test_linked_car_transfer_handles_empty_target_and_missing_car() -> None:
    car = SimpleNamespace(tmcc_id=77, name="Sound Car")
    missing = SimpleNamespace(tmcc_id=88, name="Missing Car")
    source = SimpleNamespace(linked_car_states=(car,))
    target = SimpleNamespace(has_active_selection=False, selections=[])
    target.select_component = lambda scope, tmcc_id: target.selections.append((scope, tmcc_id))
    gui = mod.SteamDeckGui.__new__(mod.SteamDeckGui)
    gui.left_gui = source
    gui.right_gui = target
    gui._confirm_replace = lambda _message: pytest.fail("empty target must not prompt")

    assert gui.transfer_linked_car("left", missing) is False
    assert gui.transfer_linked_car("left", car) is True
    assert target.selections == [(mod.CommandScope.ENGINE, 77)]


class _CallableTk:
    """Standalone: _Tk above stores `config` as a dict, shadowing any method of that
    name, and production code calls tk.config(...)."""

    def __init__(self) -> None:
        self.config_calls: list[dict] = []
        self.bindings: dict[str, object] = {}

    def config(self, **kwargs) -> None:
        self.config_calls.append(kwargs)

    configure = config

    def bind(self, event, callback) -> None:
        self.bindings[event] = callback

    @staticmethod
    def place(**_kwargs) -> None:
        return

    @staticmethod
    def pack_propagate(_enabled) -> None:
        return

    @staticmethod
    def pack_configure(**_kwargs) -> None:
        return

    @staticmethod
    def grid_configure(**_kwargs) -> None:
        return

    @staticmethod
    def grid_columnconfigure(*_args, **_kwargs) -> None:
        return

    @staticmethod
    def update_idletasks() -> None:
        return


class _ShowableWidget(_Widget):
    """A widget that tracks show()/hide(), which the controls overlay relies on."""

    def __init__(self, master=None, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.tk = _CallableTk()
        self.visible = kwargs.get("visible", True)
        self.text_size = None

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False


# Records _position_focus_arrow calls; the overlay has to re-tuck the arrow whenever it
# shows or hides, because body.display_widgets() cancels the arrow's place().
positioned: list[bool] = []


def _deck_with_body(monkeypatch: pytest.MonkeyPatch) -> tuple[mod.SteamDeckGui, list[_ShowableWidget]]:
    made: list[_ShowableWidget] = []
    positioned.clear()

    def make(master=None, **kwargs):
        widget = _ShowableWidget(master, **kwargs)
        made.append(widget)
        return widget

    monkeypatch.setattr(mod, "Box", make)
    monkeypatch.setattr(mod, "Text", make)
    monkeypatch.setattr(mod, "PushButton", make)
    monkeypatch.setattr(mod.ControlsPanel, "build", lambda _self, _body: None)
    gui = mod.SteamDeckGui.__new__(mod.SteamDeckGui)
    gui.width = 1280
    gui.height = 800
    gui.body = _ShowableWidget()
    gui._controls_panel = None
    gui._controls_overlay = None
    gui._controller_profile = object()
    monkeypatch.setattr(type(gui), "version", property(lambda _self: "v2.9.3+"), raising=False)
    monkeypatch.setattr(type(gui), "s_20", property(lambda _self: 20), raising=False)
    monkeypatch.setattr(type(gui), "s_18", property(lambda _self: 18), raising=False)
    monkeypatch.setattr(type(gui), "s_10", property(lambda _self: 10), raising=False)
    monkeypatch.setattr(type(gui), "cache", lambda _self, *_w: None)
    monkeypatch.setattr(type(gui), "_position_focus_arrow", lambda _self: positioned.append(True))
    return gui, made


def test_controls_overlay_spans_every_column_of_the_body(monkeypatch: pytest.MonkeyPatch) -> None:
    # body holds the left pane (col 0), the divider (col 1) and the right pane (col 2);
    # spanning all three is what puts the screen across both panes.
    gui, made = _deck_with_body(monkeypatch)

    gui.on_show_controls()

    overlay = made[0]
    assert overlay.master is gui.body
    assert overlay.kwargs["grid"] == [0, 0, 3, 1]
    # No width, height or align: it shrinks to its content and, with no sticky, grid
    # centres it on the display rather than filling the window.
    assert "width" not in overlay.kwargs
    assert "height" not in overlay.kwargs
    assert overlay.kwargs.get("align") is None


def test_controls_overlay_is_built_once_and_reshown(monkeypatch: pytest.MonkeyPatch) -> None:
    gui, made = _deck_with_body(monkeypatch)

    gui.on_show_controls()
    built = len(made)
    gui.close_controls()
    gui.on_show_controls()

    assert len(made) == built, "the overlay must be reused, not rebuilt"
    assert gui.controls_visible is True


def test_close_controls_reports_whether_it_was_open(monkeypatch: pytest.MonkeyPatch) -> None:
    gui, made = _deck_with_body(monkeypatch)

    assert gui.close_controls() is False  # never opened
    gui.on_show_controls()
    assert gui.close_controls() is True
    assert gui.controls_visible is False


def test_paging_only_works_while_the_screen_is_up(monkeypatch: pytest.MonkeyPatch) -> None:
    gui, _made = _deck_with_body(monkeypatch)
    turned: list[bool] = []

    assert gui.page_controls(True) is False  # not built yet
    gui.on_show_controls()
    monkeypatch.setattr(type(gui._controls_panel), "turn_page", lambda _self, forward: turned.append(forward))

    assert gui.page_controls(False) is True
    assert turned == [False]

    gui.close_controls()
    assert gui.page_controls(True) is False


def test_controls_panel_is_not_an_overlay_panel() -> None:
    # OverlayPanels are built by PopupManager, which is pane-bound -- an OverlayPanel
    # could never span both panes. Guards against it being "restored" to one.
    from src.pytrain.gui.controller.overlay_panel import OverlayPanel

    assert not issubclass(mod.ControlsPanel, OverlayPanel)


def test_showing_and_hiding_re_tucks_the_focus_arrow(monkeypatch: pytest.MonkeyPatch) -> None:
    # body.display_widgets() re-grids every child of body when the overlay shows or
    # hides, cancelling the place() that pins the arrow to the top of the divider. Left
    # unrepaired, the arrow floats at mid-screen down the full height of its cell.
    gui, _made = _deck_with_body(monkeypatch)

    gui.on_show_controls()
    assert positioned == [True]

    gui.close_controls()
    assert positioned == [True, True]
