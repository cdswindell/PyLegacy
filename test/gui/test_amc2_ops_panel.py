from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import src.pytrain.gui.controller.amc2_ops_panel as mod


class _DummyTk:
    def __init__(self, default_height: int = 36) -> None:
        self._height = default_height
        self._config: dict[str, Any] = {}

    def configure(self, **kwargs: Any) -> None:
        self._config.update(kwargs)
        if "height" in kwargs and isinstance(kwargs["height"], (int, float)):
            self._height = int(kwargs["height"])

    def config(self, **kwargs: Any) -> None:
        self.configure(**kwargs)

    @staticmethod
    def bind(_event: str, _func, add: str | None = None) -> None:
        _ = add
        return

    @staticmethod
    def focus_set() -> None:
        return

    @staticmethod
    def grid_columnconfigure(_col: int, **_kwargs: Any) -> None:
        return

    def winfo_height(self) -> int:
        return self._height


class _DummyWidget:
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        self.tk = _DummyTk()
        self.visible = kwargs.get("visible", True)
        self.grid = kwargs.get("grid")
        self.bg = kwargs.get("bg", "white")
        self.text_color = kwargs.get("text_color", "black")

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False


class DummyBox(_DummyWidget):
    pass


class DummyText(_DummyWidget):
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
        self.value = kwargs.get("text", "")
        self.text = self.value
        self.font = kwargs.get("font")
        self.size = kwargs.get("size")
        self.bold = kwargs.get("bold", False)


class DummySlider(_DummyWidget):
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
        self.value = 0
        self.height = kwargs.get("height", 0)
        self.width = kwargs.get("width", 0)
        self.command = kwargs.get("command")
        self.tmcc_id = 0


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


class DummyCheckBoxGroup(_DummyWidget):
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
        self.value = kwargs.get("selected", "0")
        self.command = kwargs.get("command")


class DummyMotor:
    def __init__(self, speed: int) -> None:
        self.speed = speed


class DummyLamp:
    def __init__(self, level: int) -> None:
        self.level = level


class DummyAccessoryState:
    def __init__(self) -> None:
        self.tmcc_id = 44
        self.is_amc2 = True
        self._motors = {1: DummyMotor(35), 2: DummyMotor(0)}
        self._lamps = {
            1: DummyLamp(0),
            2: DummyLamp(60),
            3: DummyLamp(0),
            4: DummyLamp(20),
        }

    def get_motor(self, num: int) -> DummyMotor:
        return self._motors[num]

    def get_lamp(self, num: int) -> DummyLamp:
        return self._lamps[num]

    @staticmethod
    def is_motor_on(motor: DummyMotor) -> bool:
        return motor.speed > 0


def _new_host(state: DummyAccessoryState):
    state_store = SimpleNamespace(
        get_state=lambda scope, tmcc_id, create=False: state if tmcc_id == state.tmcc_id else None
    )
    return SimpleNamespace(
        s_22=22,
        s_18=18,
        s_12=12,
        button_size=110,
        slider_height=330,
        scale_by=1.0,
        state_store=state_store,
        active_state=state,
    )


@pytest.fixture(autouse=True)
def _patch_widgets(monkeypatch):
    monkeypatch.setattr(mod, "Box", DummyBox, raising=True)
    monkeypatch.setattr(mod, "Text", DummyText, raising=True)
    monkeypatch.setattr(mod, "Slider", DummySlider, raising=True)
    monkeypatch.setattr(mod, "HoldButton", DummyHoldButton, raising=True)
    monkeypatch.setattr(mod, "CheckBoxGroup", DummyCheckBoxGroup, raising=True)
    monkeypatch.setattr(mod, "AccessoryState", DummyAccessoryState, raising=True)


def test_build_and_update_from_state_sets_motor_page_values() -> None:
    state = DummyAccessoryState()
    host = _new_host(state)
    panel = mod.Amc2OpsPanel(host)
    parent = DummyBox()

    panel.build(parent)
    panel.show(state)

    motor1 = panel._outputs[("motor", 1)]
    lamp1 = panel._outputs[("lamp", 1)]
    assert motor1.container.visible is True
    assert lamp1.container.visible is False
    assert motor1.slider.value == 35
    assert motor1.toggle_btn.bg == mod.BUTTON_ON_BG


def test_paging_shows_two_controls_per_page() -> None:
    state = DummyAccessoryState()
    host = _new_host(state)
    panel = mod.Amc2OpsPanel(host)
    panel.build(DummyBox())

    panel.next_page()
    assert panel._outputs[("lamp", 1)].container.visible is True
    assert panel._outputs[("lamp", 2)].container.visible is True
    assert panel._outputs[("lamp", 3)].container.visible is True
    assert panel._outputs[("lamp", 4)].container.visible is True
    assert panel._outputs[("motor", 1)].container.visible is False

    # wrap to first page
    panel.next_page()
    assert panel._outputs[("motor", 1)].container.visible is True
    assert panel._outputs[("motor", 2)].container.visible is True
    assert panel._outputs[("lamp", 1)].container.visible is False
    assert panel._outputs[("lamp", 3)].container.visible is False


def test_toggle_lamp_uses_actual_state_level() -> None:
    state = DummyAccessoryState()
    host = _new_host(state)
    panel = mod.Amc2OpsPanel(host)
    panel.build(DummyBox())
    panel.show(state)
    sent: list[tuple[int, int, int]] = []
    panel.set_lamp_state = lambda tmcc_id, lamp, level: sent.append((tmcc_id, lamp, level))

    panel.toggle_lamp_state(1)
    panel.toggle_lamp_state(2)

    assert sent == [(state.tmcc_id, 1, 100), (state.tmcc_id, 2, 0)]


def test_external_light_zero_sets_button_and_trough_off() -> None:
    state = DummyAccessoryState()
    host = _new_host(state)
    panel = mod.Amc2OpsPanel(host)
    panel.build(DummyBox())
    panel.show(state)

    state.get_lamp(2).level = 0
    panel.update_from_state(state)
    output = panel._outputs[("lamp", 2)]

    assert output.toggle_btn.bg == mod.BUTTON_OFF_BG
    assert output.slider.tk._config["troughcolor"] == "lightgrey"
