from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.landscape_engine_gui as mod


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
    monkeypatch.setattr(mod.LandscapeEngineGui, "init_complete", lambda _self: None)

    gui = mod.LandscapeEngineGui()

    assert base_init["width"] == 1280
    assert base_init["height"] == 800
    assert base_init["full_screen"] is True
    assert gui.pane_width == 632
    assert gui.pane_height == 800
    assert gui.focused_panel == "left"


def test_build_creates_two_independent_compact_controllers(monkeypatch: pytest.MonkeyPatch) -> None:
    children: list[SimpleNamespace] = []
    widgets: list[_Widget] = []

    def make_widget(master=None, **kwargs):
        widget = _Widget(master, **kwargs)
        widgets.append(widget)
        return widget

    def make_child(**kwargs):
        child = SimpleNamespace(kwargs=kwargs, build_calls=0, destroy_calls=0)
        child.build_gui = lambda: setattr(child, "build_calls", child.build_calls + 1)
        child.destroy_embedded = lambda: setattr(child, "destroy_calls", child.destroy_calls + 1)
        children.append(child)
        return child

    monkeypatch.setattr(mod, "Box", make_widget)
    monkeypatch.setattr(mod, "EngineGui", make_child)
    gui = mod.LandscapeEngineGui.__new__(mod.LandscapeEngineGui)
    gui.width = 1280
    gui.height = 800
    gui._app = SimpleNamespace(tk=_Tk())
    gui._pane_width = 632
    gui._pane_height = 800
    gui._focused_panel = "left"
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
    assert all(child.kwargs["width"] == 632 for child in children)
    assert all(child.kwargs["height"] == 800 for child in children)
    assert all(child.kwargs["scale_by"] == mod.LANDSCAPE_FONT_SCALE for child in children)
    assert all(child.kwargs["button_divisor"] == mod.LANDSCAPE_BUTTON_DIVISOR for child in children)
    assert [child.build_calls for child in children] == [1, 1]
    assert not any(widget.value in {"Left", "Right", "Pair Panels", mod.HALT_KEY} for widget in widgets)
    assert gui.left_root is gui.left_pane
    assert gui.right_root is gui.right_pane


def test_focus_changes_without_altering_other_controller() -> None:
    gui = mod.LandscapeEngineGui.__new__(mod.LandscapeEngineGui)
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


def test_global_halt_sends_immediately_once(monkeypatch: pytest.MonkeyPatch) -> None:
    halt = SimpleNamespace(send_calls=0)
    halt.send = lambda: setattr(halt, "send_calls", halt.send_calls + 1)
    monkeypatch.setitem(mod.KEY_TO_COMMAND, mod.HALT_KEY, halt)
    gui = mod.LandscapeEngineGui.__new__(mod.LandscapeEngineGui)

    gui.on_halt()

    assert halt.send_calls == 1


def test_destroy_gui_tears_down_both_children() -> None:
    gui = mod.LandscapeEngineGui.__new__(mod.LandscapeEngineGui)
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
    gui = mod.LandscapeEngineGui.__new__(mod.LandscapeEngineGui)
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
    gui = mod.LandscapeEngineGui.__new__(mod.LandscapeEngineGui)
    gui._app = SimpleNamespace(tk=SimpleNamespace(after_cancel=lambda poll_id: calls.append(f"cancel:{poll_id}")))
    gui._controller_poll_id = "poll-1"
    gui._input_provider = SimpleNamespace(stop=lambda: calls.append("stop"))
    gui._input_router = SimpleNamespace(clear=lambda: calls.append("clear"))

    gui._stop_controller_input()

    assert calls == ["cancel:poll-1", "stop", "clear"]
    assert gui._controller_poll_id is None


def test_missing_pygame_keeps_touch_gui_available(monkeypatch: pytest.MonkeyPatch) -> None:
    gui = mod.LandscapeEngineGui.__new__(mod.LandscapeEngineGui)
    gui._enable_controller = True
    gui._controller_profile = object()
    gui.left_gui = object()
    gui.right_gui = object()
    gui._app = SimpleNamespace(tk=SimpleNamespace(after=lambda *_args: pytest.fail("poll should not start")))
    monkeypatch.setattr(mod, "DeckInputRouter", lambda *_args, **_kwargs: SimpleNamespace())

    class UnavailableProvider:
        def __init__(self, _profile) -> None:
            return

        @staticmethod
        def start() -> None:
            raise mod.ControllerUnavailable("pygame unavailable")

    monkeypatch.setattr(mod, "SteamDeckInputProvider", UnavailableProvider)

    gui._start_controller_input()

    assert gui._input_provider is None
    assert gui._controller_poll_id is None


def test_linked_car_transfer_uses_other_panel_and_confirms_occupied_target() -> None:
    car = SimpleNamespace(tmcc_id=77, name="Sound Car")
    source = SimpleNamespace(linked_car_states=(car,))
    target = SimpleNamespace(has_active_selection=True, selections=[])
    target.select_component = lambda scope, tmcc_id: target.selections.append((scope, tmcc_id))
    confirmations: list[str] = []
    gui = mod.LandscapeEngineGui.__new__(mod.LandscapeEngineGui)
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
    gui = mod.LandscapeEngineGui.__new__(mod.LandscapeEngineGui)
    gui.left_gui = source
    gui.right_gui = target
    gui._confirm_replace = lambda _message: pytest.fail("empty target must not prompt")

    assert gui.transfer_linked_car("left", missing) is False
    assert gui.transfer_linked_car("left", car) is True
    assert target.selections == [(mod.CommandScope.ENGINE, 77)]
