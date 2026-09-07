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

    @staticmethod
    def grid_rowconfigure(_row: int, **_kwargs: Any) -> None:
        return

    def grid_configure(self, **kwargs: Any) -> None:
        self._config.update(kwargs)

    def pack_configure(self, **kwargs: Any) -> None:
        self._config.update(kwargs)

    @staticmethod
    def pack_propagate(_flag: bool) -> None:
        return

    def winfo_height(self) -> int:
        return self._height


class _DummyWidget:
    def __init__(self, *_args: Any, **kwargs: Any) -> None:
        self.tk = _DummyTk()
        self.master = _args[0] if _args else None
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
        self.anchor = kwargs.get("anchor", "w")
        self.row_width = kwargs.get("width")


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


def _measurable(width: int):
    """A widget that answers with the width it has been given, as Tk does once it is on screen."""
    return SimpleNamespace(tk=SimpleNamespace(winfo_width=lambda: width))


def _new_host(state: DummyAccessoryState):
    state_store = SimpleNamespace(
        get_state=lambda scope, tmcc_id, create=False: state if tmcc_id == state.tmcc_id else None
    )
    return SimpleNamespace(
        s_22=22,
        s_18=18,
        s_16=16,
        s_12=12,
        button_size=110,
        slider_height=330,
        scale_by=1.0,
        digital_font="Digital dream",
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
    assert motor1.level_box.font == "Digital dream"


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


def test_the_nav_keys_stand_in_a_column_of_the_panel_beside_the_sliders() -> None:
    state = DummyAccessoryState()
    host = _new_host(state)
    panel = mod.Amc2OpsPanel(host)
    panel.build(DummyBox())

    # A column of the panel, spanning the header row and the sliders' row both, so nothing of
    # the selector is drawn above the keys and they read as a column of their own rather than
    # as something the Lights option leads to.
    assert panel._nav_box.master is panel._root
    assert panel._nav_box.grid == [mod.NAV_COLUMN, 0, 1, 2]
    assert panel._header.grid == [mod.SLIDER_COLUMN, 0]
    assert panel._controls.grid == [mod.SLIDER_COLUMN, 1]
    assert [btn.text for btn in panel._nav_buttons.values()] == list(mod.NAV_KEYS)
    # One key to a cell, and the cells down the single column of the box, top to bottom.
    assert [cell.grid for cell in panel._nav_cells] == [[0, 0], [0, 1], [0, 2]]
    # And every slider column is the selector's to be laid out over.
    assert panel._page_selector.grid == [0, 0]


def test_the_nav_keys_are_exposed_for_the_keypad_to_wire() -> None:
    state = DummyAccessoryState()
    host = _new_host(state)
    panel = mod.Amc2OpsPanel(host)
    panel.build(DummyBox())

    assert panel.panel_toggle_button.text == mod.ACC_PANEL_KEY
    assert panel.info_button.text == mod.INFO_KEY
    assert panel.lcs_panel_button.text == mod.LCS_PANEL_KEY


def test_the_nav_column_reserves_everything_its_keys_ask_for() -> None:
    state = DummyAccessoryState()
    host = _new_host(state)
    panel = mod.Amc2OpsPanel(host)
    panel.build(DummyBox())

    # Nothing measurable before the first map, so a key's own square is assumed.
    assert panel._nav_column_width() == 118

    panel._nav_box.tk.winfo_width = lambda: 120

    # Once the keys can be measured, all of what they ask for and the gaps either side of
    # them: a column is given the width it requests whatever it was reserved, so reserving
    # less would not narrow the keys -- it would push them off the right edge.
    assert panel._nav_column_width() == 128


def test_the_panel_measures_the_display_beside_it_and_never_its_own_contents() -> None:
    state = DummyAccessoryState()
    host = _new_host(state)
    panel = mod.Amc2OpsPanel(host)
    panel.build(DummyBox())
    host.width = 639
    host.emergency_box_width = 639

    # Nothing on screen to measure yet, so the width the host was opened at is all there is.
    assert panel._display_width() == 639

    # Once there is: the scope bar has the room the panel has, with what the display spends on
    # itself -- a Deck pane's focus border -- already off it. The panel's own box is not asked,
    # however wide it says it is: what it answers is the width its contents came to, and laying
    # them out in that again is what walked the navigation keys off the right edge.
    host.scope_box = _measurable(633)
    panel._parent.tk.winfo_width = lambda: 999
    assert panel._display_width() == 633

    # And a neighbor wider than the display cannot take the panel with it.
    host.image_box = _measurable(999)
    assert panel._display_width() == 639


def test_the_sliders_are_laid_out_in_what_is_left_after_the_borders_and_the_keys() -> None:
    state = DummyAccessoryState()
    host = _new_host(state)
    panel = mod.Amc2OpsPanel(host)
    panel.build(DummyBox())

    # 400 measured, less the panel's border and its container's (8), the gaps at either edge
    # (16) and the navigation column (118). Handing the columns all 400 is what drew the keys
    # off the right edge of the display.
    assert panel._sliders_width(400, 2) == 258
    # Never below a column's worth apiece, however narrow the panel is said to be.
    assert panel._sliders_width(120, 2) == 120
    assert panel._sliders_width(0, 2) == 0


def test_each_page_option_is_centered_over_its_half_of_the_sliders() -> None:
    state = DummyAccessoryState()
    host = _new_host(state)
    panel = mod.Amc2OpsPanel(host)
    panel.build(DummyBox())

    # Centered in its share rather than drawn from the left edge of the panel: on the Motors
    # page a share is one slider column, so "Motors" stands over Motor #1 and "Lights" over
    # Motor #2.
    assert panel._page_selector.anchor == "center"

    panel._center_page_selector(panel._sliders_width(400, 2))

    # Half of the 258 the sliders have, less what a painted row adds to the width it is given,
    # so the two options together are no wider than the sliders under them.
    assert panel._page_selector.row_width == 123


def test_each_nav_key_is_an_ops_key_square_stacked_from_the_top_of_the_panel() -> None:
    state = DummyAccessoryState()
    host = _new_host(state)
    panel = mod.Amc2OpsPanel(host)
    panel.build(DummyBox())

    # The same square as every other ops key. The cell is what holds the size, as it does for
    # every key in the keypad: a text button's own width is read in characters, so a key sized
    # by its label is as wide as that label is long -- and "Acc..." is not "Info".
    assert len(panel._nav_cells) == len(mod.NAV_KEYS)
    for cell in panel._nav_cells:
        assert cell.tk._config["width"] == host.button_size
        assert cell.tk._config["height"] == host.button_size
        # Stacked from the top of the column, so the first is level with the page selector
        # across from it rather than spread down the sliders' full height.
        assert cell.tk._config["sticky"] == "n"
    for btn in panel._nav_buttons.values():
        assert btn.master in panel._nav_cells
        assert btn.tk._config["compound"] == "center"
    assert panel._nav_box.tk._config["sticky"] == "new"


def test_an_output_label_is_drawn_at_the_largest_size_its_column_has_room_for() -> None:
    state = DummyAccessoryState()
    host = _new_host(state)
    panel = mod.Amc2OpsPanel(host)
    panel.build(DummyBox())
    lamp = panel._outputs[("lamp", 1)]

    # Room to spare -- a Deck pane's quarter -- and the label keeps the size a roomy column
    # gets, which is what it already had there.
    assert panel._toggle_text_size(lamp, 130) == panel._toggle_base_text_size()

    # A Pi's quarter is narrower than "Light #1" at that size, which is why the four ran
    # together edge to edge, so the label is drawn smaller rather than clipped.
    fitted = panel._toggle_text_size(lamp, 92)
    assert fitted < panel._toggle_base_text_size()
    assert fitted >= panel._toggle_min_text_size()

    # However narrow the column is said to be, the label stays readable.
    assert panel._toggle_text_size(lamp, 20) == panel._toggle_min_text_size()


def test_the_lights_labels_are_sized_against_their_own_quarter_of_the_sliders() -> None:
    state = DummyAccessoryState()
    host = _new_host(state)
    panel = mod.Amc2OpsPanel(host)
    panel.build(DummyBox())
    host.width = 480
    host.emergency_box_width = 480
    panel._compute_available_panel_height = lambda: 600

    panel.refresh_layout()

    # Four to a page against two, so a light's label has half the room a motor's does and is
    # the one that has to give, whichever page happens to be showing.
    assert panel._outputs[("motor", 1)].toggle_btn.text_size == panel._toggle_base_text_size()
    assert panel._outputs[("lamp", 1)].toggle_btn.text_size < panel._toggle_base_text_size()


def test_the_page_options_are_left_alone_until_the_panel_has_been_measured() -> None:
    state = DummyAccessoryState()
    host = _new_host(state)
    panel = mod.Amc2OpsPanel(host)
    panel.build(DummyBox())
    built_with = panel._page_selector.row_width

    panel._center_page_selector(0)

    assert panel._page_selector.row_width == built_with
