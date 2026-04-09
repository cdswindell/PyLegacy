from __future__ import annotations

from threading import Condition, RLock
from types import SimpleNamespace
from typing import Any

import pytest

import src.pytrain.gui.motors_gui as mod


class _DummyTk:
    def __init__(self, default_height: int = 36) -> None:
        self._height = default_height
        self._y = 0
        self._config: dict[str, Any] = {}

    def configure(self, **kwargs: Any) -> None:
        self._config.update(kwargs)
        if "height" in kwargs and isinstance(kwargs["height"], (int, float)):
            self._height = int(kwargs["height"])

    def config(self, **kwargs: Any) -> None:
        self.configure(**kwargs)

    @staticmethod
    def grid_propagate(_enabled: bool) -> None:
        return

    @staticmethod
    def grid_rowconfigure(_row: int, **_kwargs: Any) -> None:
        return

    @staticmethod
    def grid_columnconfigure(_col: int, **_kwargs: Any) -> None:
        return

    @staticmethod
    def grid_configure(**_kwargs: Any) -> None:
        return

    @staticmethod
    def bind(_event: str, _func, add: str | None = None) -> None:
        _ = add
        return

    @staticmethod
    def focus_displayof():
        return None

    def winfo_reqheight(self) -> int:
        return self._height

    def winfo_height(self) -> int:
        return self._height

    def winfo_y(self) -> int:
        return self._y


class _DummyWidget:
    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.tk = _DummyTk()
        self.bg = _kwargs.get("bg", "white")
        self.text_color = _kwargs.get("text_color", "black")
        self.grid = _kwargs.get("grid")

    def destroy(self) -> None:
        return


class DummyBox(_DummyWidget):
    pass


class DummyText(_DummyWidget):
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
        self.value = kwargs.get("text", "")
        self.text = self.value
        self.font = kwargs.get("font")
        self.size = kwargs.get("size")
        self.width = kwargs.get("width")
        self.bold = kwargs.get("bold", False)


class DummySlider(_DummyWidget):
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
        self.value = 0
        self.height = kwargs.get("height", 0)
        self.width = kwargs.get("width", 0)
        self.command = kwargs.get("command")


class DummyHoldButton(_DummyWidget):
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
        self.text = kwargs.get("text", "")
        self.text_size = kwargs.get("text_size", 12)
        self.text_bold = kwargs.get("text_bold", False)
        self._command = None
        self._args = None

    def update_command(self, command, args: list[Any] | None = None) -> None:
        self._command = command
        self._args = args if args is not None else []


class DummyApp:
    def __init__(self) -> None:
        self.tk = SimpleNamespace(update_idletasks=lambda: None, winfo_screenheight=lambda: 0)

    @staticmethod
    def after(_delay: int, _func) -> None:
        return


class DummyMotor:
    def __init__(self, speed: int) -> None:
        self.speed = speed


class DummyLamp:
    def __init__(self, level: int) -> None:
        self.level = level


class DummyAccessoryState:
    def __init__(self) -> None:
        self.tmcc_id = 91
        self.road_name = "AMC2 Yard"
        self._motors = {1: DummyMotor(30), 2: DummyMotor(0)}
        self._lamps = {
            1: DummyLamp(10),
            2: DummyLamp(0),
            3: DummyLamp(50),
            4: DummyLamp(0),
        }
        self.motor1 = self._motors[1]
        self.motor2 = self._motors[2]

    def get_motor(self, num: int) -> DummyMotor:
        return self._motors[num]

    def get_lamp(self, num: int) -> DummyLamp:
        return self._lamps[num]

    @staticmethod
    def is_motor_on(motor: DummyMotor) -> bool:
        return motor.speed > 0


def _new_gui(height: int) -> mod.MotorsGui:
    gui = mod.MotorsGui.__new__(mod.MotorsGui)
    gui._making_buttons = True
    gui._cv = Condition(RLock())
    gui._output_by_tmcc = {}
    gui._last_non_zero_lamp_level = {}
    gui._lamp_toggle_off = {}
    gui._lamp_force_on = {}
    gui._suspended_slider_callbacks = set()
    gui._scale_by = 1.0
    gui._screen_height = None
    gui.s_20 = 20
    gui.s_18 = 18
    gui.width = 800
    gui.height = height
    gui.y_offset = 100
    gui.btn_box = DummyBox()
    gui._app = DummyApp()
    # Present hidden nav controls with measurable heights so reclaim logic has input.
    gui.by_name = DummyBox()
    gui.by_name.tk.configure(height=40)
    gui.by_number = DummyBox()
    gui.by_number.tk.configure(height=40)
    gui.left_scroll_btn = DummyBox()
    gui.left_scroll_btn.tk.configure(height=40)
    gui.right_scroll_btn = DummyBox()
    gui.right_scroll_btn.tk.configure(height=40)
    return gui


@pytest.fixture(autouse=True)
def _patch_widgets(monkeypatch):
    monkeypatch.setattr(mod, "Box", DummyBox, raising=True)
    monkeypatch.setattr(mod, "Text", DummyText, raising=True)
    monkeypatch.setattr(mod, "Slider", DummySlider, raising=True)
    monkeypatch.setattr(mod, "HoldButton", DummyHoldButton, raising=True)


def test_make_state_button_hides_level_box_below_480px() -> None:
    gui = _new_gui(height=479)
    state = DummyAccessoryState()

    _widgets, _btn_h, _btn_y = gui._make_state_button(state, row=4, col=0)

    outputs = gui._output_by_tmcc[state.tmcc_id]
    assert len(outputs) == 6
    assert all(output.level_box is None for output in outputs.values())
    assert all(output.slider.grid == [0, 1] for output in outputs.values())


def test_make_state_button_keeps_level_box_at_or_above_480px() -> None:
    gui = _new_gui(height=480)
    state = DummyAccessoryState()

    _widgets, _btn_h, _btn_y = gui._make_state_button(state, row=4, col=0)

    outputs = gui._output_by_tmcc[state.tmcc_id]
    assert len(outputs) == 6
    assert all(output.level_box is not None for output in outputs.values())
    assert all(output.slider.grid == [0, 2] for output in outputs.values())


def test_slider_height_increases_when_level_box_removed() -> None:
    short_gui = _new_gui(height=479)
    short_state = DummyAccessoryState()
    short_gui._make_state_button(short_state, row=4, col=0)
    short_slider = short_gui._output_by_tmcc[short_state.tmcc_id][("motor", 1)].slider

    tall_gui = _new_gui(height=480)
    tall_state = DummyAccessoryState()
    tall_gui._make_state_button(tall_state, row=4, col=0)
    tall_slider = tall_gui._output_by_tmcc[tall_state.tmcc_id][("motor", 1)].slider

    assert short_slider.height > tall_slider.height


def test_toggle_motor_state_off_at_zero_sets_level_to_100() -> None:
    gui = _new_gui(height=600)
    state = DummyAccessoryState()
    gui._make_state_button(state, row=4, col=0)
    gui._state_for_tmcc = lambda tmcc_id: state if tmcc_id == state.tmcc_id else None
    sent: list[tuple[int, int, int | None]] = []
    gui.set_motor_state = lambda tmcc_id, motor, speed=None: sent.append((tmcc_id, motor, speed))

    gui.toggle_motor_state(state.tmcc_id, 2)

    assert sent == [(state.tmcc_id, 2, 100)]
    output = gui._output_by_tmcc[state.tmcc_id][("motor", 2)]
    assert output.slider.value == 100
    assert output.toggle_btn.bg == mod.BUTTON_ON_BG
    assert output.level_box is not None
    assert output.level_box.value == "100"


def test_toggle_motor_state_on_uses_regular_toggle_behavior() -> None:
    gui = _new_gui(height=600)
    state = DummyAccessoryState()
    gui._make_state_button(state, row=4, col=0)
    gui._state_for_tmcc = lambda tmcc_id: state if tmcc_id == state.tmcc_id else None
    sent: list[tuple[int, int, int | None]] = []
    gui.set_motor_state = lambda tmcc_id, motor, speed=None: sent.append((tmcc_id, motor, speed))

    gui.toggle_motor_state(state.tmcc_id, 1)

    assert sent == [(state.tmcc_id, 1, None)]


def test_level_box_uses_screen_height_not_container_height() -> None:
    gui = _new_gui(height=420)
    gui._screen_height = 600
    state = DummyAccessoryState()

    gui._make_state_button(state, row=4, col=0)

    outputs = gui._output_by_tmcc[state.tmcc_id]
    assert all(output.level_box is not None for output in outputs.values())


def test_level_box_hidden_when_screen_height_is_below_threshold() -> None:
    gui = _new_gui(height=600)
    gui._screen_height = 479
    state = DummyAccessoryState()

    gui._make_state_button(state, row=4, col=0)

    outputs = gui._output_by_tmcc[state.tmcc_id]
    assert all(output.level_box is None for output in outputs.values())


def test_lamp_slider_release_to_zero_sets_button_on_and_sends_value() -> None:
    gui = _new_gui(height=600)
    state = DummyAccessoryState()
    gui._make_state_button(state, row=4, col=0)
    gui._making_buttons = False
    sent: list[tuple[int, int, int]] = []
    gui.set_lamp_state = lambda tmcc_id, lamp, level: sent.append((tmcc_id, lamp, level))
    output = gui._output_by_tmcc[state.tmcc_id][("lamp", 1)]

    output.slider.value = 0
    gui._on_slider_release(state.tmcc_id, "lamp", 1)

    assert sent == [(state.tmcc_id, 1, 0)]
    assert output.toggle_btn.bg == mod.BUTTON_ON_BG
    assert output.level_box is not None
    assert output.level_box.value == "000"


def test_external_lamp_change_updates_slider_even_when_focused() -> None:
    gui = _new_gui(height=600)
    state = DummyAccessoryState()
    gui._make_state_button(state, row=4, col=0)
    output = gui._output_by_tmcc[state.tmcc_id][("lamp", 1)]

    output.slider.value = 10
    output.slider.tk.focus_displayof = lambda: output.slider.tk
    state.get_lamp(1).level = 65

    gui.update_button(state)

    assert output.slider.value == 65
    assert output.level_box is not None
    assert output.level_box.value == "065"
