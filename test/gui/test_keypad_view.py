from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, Callable

import pytest

import src.pytrain.gui.controller.keypad_view as mod
from src.pytrain.protocol.constants import CommandScope


class DummyTk:
    def __init__(self) -> None:
        self._config: dict[str, Any] = {}
        self._bindings: dict[str, list[Callable]] = {}
        self._after_calls: dict[int, tuple[int, Callable, tuple[Any, ...]]] = {}
        self._next_after_id = 1
        self._focus_owner = None

    def config(self, **kwargs: Any) -> None:
        self._config.update(kwargs)

    def configure(self, **kwargs: Any) -> None:
        self.config(**kwargs)

    def bind(self, event: str, func: Callable, add: str | None = None) -> None:
        _ = add
        self._bindings.setdefault(event, []).append(func)

    def after(self, delay_ms: int, func: Callable, *args: Any) -> int:
        after_id = self._next_after_id
        self._next_after_id += 1
        self._after_calls[after_id] = (delay_ms, func, args)
        return after_id

    def after_cancel(self, after_id: int) -> None:
        self._after_calls.pop(after_id, None)

    def run_after(self, after_id: int) -> None:
        delay_ms, func, args = self._after_calls.pop(after_id)
        _ = delay_ms
        func(*args)

    def focus_set(self) -> None:
        self._focus_owner = self

    def focus_displayof(self):
        return self._focus_owner

    @staticmethod
    def grid_rowconfigure(_row: int, **_kwargs: Any) -> None:
        return

    @staticmethod
    def grid_columnconfigure(_col: int, **_kwargs: Any) -> None:
        return

    @staticmethod
    def grid_propagate(_value: bool) -> None:
        return

    @staticmethod
    def update_idletasks() -> None:
        return

    def winfo_reqheight(self) -> int:
        return int(self._config.get("height", 0))

    def winfo_height(self) -> int:
        return self.winfo_reqheight()


class DummyWidget:
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        self.tk = DummyTk()
        self.visible = kwargs.get("visible", True)
        self.grid = kwargs.get("grid")
        self.border = kwargs.get("border", 0)
        self.align = kwargs.get("align")
        self.layout = kwargs.get("layout")
        self.width = kwargs.get("width")
        self.height = kwargs.get("height")
        self.bg = kwargs.get("bg", "white")
        self.text_color = kwargs.get("color", "black")
        self.enabled = True

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False


class DummyBox(DummyWidget):
    pass


class DummyTitleBox(DummyBox):
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
        self.text_size = kwargs.get("text_size")


class DummyText(DummyWidget):
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
        self.value = kwargs.get("text", "")
        self.font = kwargs.get("font")
        self.size = kwargs.get("size")
        self.bold = kwargs.get("bold", False)

    def clear(self) -> None:
        self.value = ""


class DummyButton(DummyWidget):
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
        self.text = kwargs.get("text")
        self.image = kwargs.get("image")
        self.on_press = None
        self.on_repeat = None
        self.on_hold = None
        self.when_left_button_pressed = None
        self.when_left_button_released = None

    def update_command(self, command: Callable, args: list[Any] | None = None) -> None:
        self.on_press = (command, args or [])


class DummySlider(DummyWidget):
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
        self.command = kwargs.get("command")
        self.value = 0


class DummyCheckBoxGroup(DummyWidget):
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        super().__init__(*_args, **kwargs)
        self.value = kwargs.get("selected")


class DummyAccessoryState:
    def __init__(self, tmcc_id: int = 19, relative_speed: int = 0) -> None:
        self.tmcc_id = tmcc_id
        self.relative_speed = relative_speed
        self.is_sensor_track = False
        self.is_amc2 = False
        self.is_bpc2 = False
        self.is_asc2 = False


@pytest.fixture(autouse=True)
def _patch_widgets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "Box", DummyBox, raising=True)
    monkeypatch.setattr(mod, "TitleBox", DummyTitleBox, raising=True)
    monkeypatch.setattr(mod, "AccessoryState", DummyAccessoryState, raising=True)
    monkeypatch.setattr(mod, "CheckBoxGroup", DummyCheckBoxGroup, raising=True)
    monkeypatch.setattr(mod, "Amc2OpsPanel", lambda _host: SimpleNamespace(build=lambda _parent: None), raising=True)
    monkeypatch.setattr(mod, "find_file", lambda name: name, raising=True)


def _make_slider(
    _parent,
    title: str,
    command: Callable,
    frm: int,
    to: int,
    *,
    visible: bool = True,
    grid=(0, 0),
    level_text: str = "0",
    slider_width: int | None = None,
    slider_height: int | None = None,
    on_release: Callable | None = None,
    **_kwargs: Any,
):
    box = DummyBox(visible=visible, grid=list(grid))
    title_box = DummyTitleBox(box, title)
    level = DummyText(title_box, text=level_text)
    slider = DummySlider(box, visible=visible, width=slider_width, height=slider_height, command=command)
    slider.tk.config(from_=frm, to=to)
    if on_release is not None:
        slider.tk.bind("<ButtonRelease-1>", on_release, add="+")
    return box, title_box, level, slider


def _new_host() -> SimpleNamespace:
    @contextmanager
    def locked():
        yield

    host = SimpleNamespace()
    host.app = SimpleNamespace(tk=DummyTk())
    host.scope = CommandScope.ACC
    host._scope_tmcc_ids = {CommandScope.ACC: 19}
    host.active_state = DummyAccessoryState()
    host.button_size = 96
    host.slider_height = 320
    host.grid_pad_by = 2
    host.emergency_box_width = 180
    host.s_22 = 22
    host.s_24 = 24
    host.s_30 = 30
    host.s_18 = 18
    host.s_16 = 16
    host.s_19 = 19
    host.s_10 = 10
    host.turn_on_image = "on.jpg"
    host.turn_off_image = "off.jpg"
    host.turn_on_path = "on.jpg"
    host.turn_off_path = "off.jpg"
    host.power_off_path = "off.png"
    host.power_on_path = "on.png"
    host.op_acc_image = "op-acc.jpg"
    host.image_box = DummyBox()
    host.keypad_box = None
    host.keypad_keys = None
    host.entry_cells = set()
    host.ops_cells = set()
    host.aux_cells = set()
    host.numeric_btns = {}
    host.locked = locked
    host.make_keypad_button = lambda *_args, **kwargs: (DummyBox(visible=kwargs.get("visible", True)), DummyButton())
    host.on_acc_command_calls = []
    host.on_acc_command = lambda target, data=None: host.on_acc_command_calls.append((target, data))
    host.on_engine_command = lambda *_args, **_kwargs: None
    host.on_keypress = lambda *_args, **_kwargs: None
    host.on_new_accessory = lambda *_args, **_kwargs: None
    host.on_new_route = lambda: None
    host.on_new_switch = lambda: None
    host.reset_acc_overlay = lambda: None
    host.update_ac_status = lambda _state: None
    host.accessories = SimpleNamespace(configured_by_tmcc_id=lambda _tmcc_id: False)
    host.accessory_provider = SimpleNamespace(adapters_for_tmcc_id=lambda _tmcc_id: None)
    host.acc_overlay = None
    host.amc2_ops_box = DummyBox(visible=False)
    host.amc2_ops_panel = SimpleNamespace(update_from_state=lambda _state: None, refresh_layout=lambda: None)
    host.sensor_track_box = DummyBox(visible=False)
    host.sensor_track_buttons = DummyCheckBoxGroup(selected=None)
    host.reset_btn = DummyButton()
    host.controller_view = SimpleNamespace(make_slider=_make_slider)
    host._controller_view = host.controller_view
    return host


def test_generic_accessory_ops_mode_shows_throttle_and_reflects_state() -> None:
    host = _new_host()
    view = mod.KeypadView(host)
    state = DummyAccessoryState(relative_speed=3)
    host.active_state = state

    view.build()
    view.apply_ops_mode_ui_non_engine(state)

    assert host.acc_throttle_box.visible is True
    assert host.acc_throttle.value == 3
    assert host.acc_throttle_level.value == "+3"


def test_accessory_throttle_repeats_until_release() -> None:
    host = _new_host()
    view = mod.KeypadView(host)
    host.active_state = DummyAccessoryState(relative_speed=0)
    view.build()

    host.acc_throttle.value = 4
    view.on_accessory_throttle_change("4")

    assert host.acc_throttle_level.value == "+4"
    assert host.on_acc_command_calls == [("RELATIVE_SPEED", 4)]
    assert len(host.acc_throttle.tk._after_calls) == 1
    first_after_id = next(iter(host.acc_throttle.tk._after_calls))

    host.acc_throttle.tk.run_after(first_after_id)
    assert host.on_acc_command_calls == [("RELATIVE_SPEED", 4), ("RELATIVE_SPEED", 4)]
    assert len(host.acc_throttle.tk._after_calls) == 1

    view.on_accessory_throttle_release()

    assert host.acc_throttle.value == 0
    assert host.acc_throttle_level.value == "0"
    assert host.on_acc_command_calls[-1] == ("RELATIVE_SPEED", 0)
    assert host.acc_throttle.tk._after_calls == {}


def test_external_accessory_throttle_update_repaints_slider() -> None:
    host = _new_host()
    view = mod.KeypadView(host)
    state = DummyAccessoryState(relative_speed=-2)
    host.active_state = state
    view.build()

    view.update_accessory_throttle_from_state(state)

    assert host.acc_throttle.value == -2
    assert host.acc_throttle_level.value == "-2"
