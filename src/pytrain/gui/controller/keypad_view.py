#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import logging
from typing import Generic, TYPE_CHECKING, TypeVar

from guizero import App, Box, TitleBox
from guizero.event import EventData

from .amc2_ops_panel import Amc2OpsPanel
from .configured_accessory_adapter import ConfiguredAccessoryAdapter
from .engine_gui_conf import (
    AC_OFF_KEY,
    AC_ON_KEY,
    AUX1_KEY,
    AUX2_KEY,
    CLEAR_KEY,
    ENGINE_OFF_KEY,
    ENTER_KEY,
    ENTRY_LAYOUT,
    FIRE_ROUTE_KEY,
    SENSOR_TRACK_OPTS,
    SET_KEY,
    SWITCH_OUT_KEY,
    SWITCH_THRU_KEY,
)
from ..components.checkbox_group import CheckBoxGroup
from ...db.accessory_state import AccessoryState
from ...db.component_state import ComponentState, LcsProxyState
from ...db.engine_state import TrainState
from ...pdi.asc2_req import Asc2Req
from ...pdi.constants import Asc2Action, IrdaAction, PdiCommand
from ...pdi.irda_req import IrdaReq, IrdaSequence
from ...protocol.constants import CommandScope
from ...utils.path_utils import find_file

log = logging.getLogger(__name__)

ACCESSORY_THROTTLE_MIN = -5
ACCESSORY_THROTTLE_MAX = 5
ACCESSORY_THROTTLE_REPEAT_MS = 100

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui

S = TypeVar("S", ComponentState, ConfiguredAccessoryAdapter)


class KeypadView(Generic[S]):
    def __init__(self, host: "EngineGui") -> None:
        self._host: "EngineGui" = host
        self._reset_on_keystroke = False
        self._entry_mode = True
        self._numeric_keys = True
        self._accessory_throttle_after_id: int | None = None
        self._accessory_throttle_value = 0
        self._accessory_throttle_total_height = 0

    @property
    def active_state(self) -> ComponentState | None:
        return self._host.active_state

    @property
    def reset_on_keystroke(self) -> bool:
        return self._reset_on_keystroke

    @reset_on_keystroke.setter
    def reset_on_keystroke(self, value: bool) -> None:
        self._reset_on_keystroke = value

    @property
    def is_entry_mode(self) -> bool:
        return self._entry_mode

    # @is_entry_mode.setter
    # def is_entry_mode(self, value: bool) -> None:
    #     self._entry_mode = value

    # noinspection PyUnresolvedReferences
    @property
    def is_engine_or_train(self) -> bool:
        host = self._host
        return (
            host.scope == CommandScope.ENGINE
            or (host.scope == CommandScope.TRAIN and self.active_state is None)
            or (
                host.scope == CommandScope.TRAIN
                and isinstance(self.active_state, TrainState)
                and not self.active_state.is_power_district
            )
        )

    # noinspection PyUnresolvedReferences
    @property
    def is_accessory_or_bpc2(self) -> bool:
        host = self._host
        return host.scope == CommandScope.ACC or (
            isinstance(self.active_state, LcsProxyState) and self.active_state.is_power_district
        )

    def build(self, app: App = None):
        host = self._host

        app = app or host.app
        host.keypad_box = keypad_box = Box(
            app,
            border=2,
            align="top",
        )
        host.keypad_keys = keypad_keys = Box(
            keypad_box,
            layout="grid",
            border=0,
            align="top",
        )

        row = 0
        for r, kr in enumerate(ENTRY_LAYOUT):
            for c, label in enumerate(kr):
                if isinstance(label, tuple):
                    image = find_file(label[1])
                    label = label[0]
                else:
                    image = None

                cell, nb = host.make_keypad_button(
                    keypad_keys,
                    label,
                    row,
                    c,
                    size=host.s_22 if label.isdigit() else host.s_24,
                    visible=True,
                    bolded=True,
                    command=self.on_keypress,
                    args=[label],
                    image=image,
                    hover=True,
                )

                if label == CLEAR_KEY:
                    host.clear_key_cell = cell
                    host.entry_cells.add(cell)
                elif label == ENTER_KEY:
                    host.entry_cells.add(cell)
                    host.enter_key_cell = cell
                elif label == SET_KEY:
                    host.set_key_cell = cell
                elif label.isdigit():
                    assert int(label) not in host.numeric_btns
                    host.numeric_btns[int(label)] = nb
            row += 1

        # fill in last row; contents depends on scope
        # accessory keys
        cell, btn = host.make_keypad_button(
            keypad_keys,
            None,
            row - 1,
            0,
            size=0,
            image=find_file("front-coupler.jpg"),
            visible=False,
            is_ops=True,
            hover=True,
            command=False,
        )
        host.aux_cells.add(cell)
        btn.on_press = (host.on_acc_command, ["FRONT_COUPLER"])
        btn.on_repeat = btn.on_press

        cell, btn = host.make_keypad_button(
            keypad_keys,
            None,
            row,
            0,
            size=0,
            image=find_file("rear-coupler.jpg"),
            visible=False,
            is_ops=True,
            hover=True,
            command=False,
        )
        host.aux_cells.add(cell)
        btn.on_press = (host.on_acc_command, ["REAR_COUPLER"])
        btn.on_repeat = btn.on_press

        cell, btn = host.make_keypad_button(
            keypad_keys,
            None,
            row - 1,
            2,
            size=0,
            image=find_file("boost.jpg"),
            visible=False,
            is_ops=True,
            hover=True,
            command=False,
        )
        host.aux_cells.add(cell)
        btn.on_press = (host.on_acc_command, ["BOOST"])
        btn.on_repeat = btn.on_press

        cell, btn = host.make_keypad_button(
            keypad_keys,
            None,
            row,
            2,
            size=0,
            image=find_file("brake.jpg"),
            visible=False,
            is_ops=True,
            hover=True,
            command=False,
        )
        host.aux_cells.add(cell)
        btn.on_press = (host.on_acc_command, ["BRAKE"])
        btn.on_repeat = btn.on_press

        cell, btn = host.make_keypad_button(
            keypad_keys,
            AUX1_KEY,
            row - 1,
            2,
            size=host.s_18,
            visible=False,
            is_ops=True,
            hover=True,
            command=False,
        )
        host.aux_cells.add(cell)
        setattr(cell, "render_grid", [3, row - 1])
        setattr(cell, "reset_grid", [2, row - 1])
        btn.on_press = (host.on_acc_command, ["AUX1_OPT_ONE"])
        btn.on_repeat = btn.on_press

        cell, btn = host.make_keypad_button(
            keypad_keys,
            AUX2_KEY,
            row,
            2,
            size=host.s_18,
            visible=False,
            is_ops=True,
            hover=True,
            command=False,
        )
        host.aux_cells.add(cell)
        setattr(cell, "render_grid", [3, row])
        setattr(cell, "reset_grid", [2, row])
        btn.on_press = (host.on_acc_command, ["AUX2_OPT_ONE"])
        btn.on_repeat = btn.on_press

        # ASC2/BPC2 keys
        host.on_key_cell, host.on_btn = host.make_keypad_button(
            keypad_keys,
            None,
            row,
            0,
            visible=True,
            bolded=True,
            is_entry=True,
            image=host.turn_on_image,
            command=False,
        )
        host.on_btn.on_press = (host.on_engine_command, ["START_UP_IMMEDIATE"], {"do_ops": True})
        host.on_btn.on_hold = (host.on_engine_command, [["START_UP_DELAYED", "START_UP_IMMEDIATE"]], {"do_ops": True})

        host.off_key_cell, host.off_btn = host.make_keypad_button(
            keypad_keys,
            ENGINE_OFF_KEY,
            row,
            1,
            visible=True,
            bolded=True,
            is_entry=True,
            image=host.turn_off_image,
        )
        host.off_btn.on_press = (host.on_engine_command, ["SHUTDOWN_IMMEDIATE"])
        host.off_btn.on_hold = (host.on_engine_command, [["SHUTDOWN_DELAYED", "SHUTDOWN_IMMEDIATE"]])

        # set button
        host.set_key_cell, host.set_btn = host.make_keypad_button(
            keypad_keys,
            SET_KEY,
            row,
            2,
            size=host.s_16,
            visible=True,
            bolded=True,
            command=self.on_keypress,
            args=[SET_KEY],
            is_entry=True,
            hover=True,
        )

        # fire route button
        host.fire_route_cell, host.fire_route_btn = host.make_keypad_button(
            keypad_keys,
            FIRE_ROUTE_KEY,
            row,
            1,
            size=host.s_30,
            visible=False,
            is_ops=True,
            hover=True,
        )

        # switch button
        host.switch_thru_cell, host.switch_thru_btn = host.make_keypad_button(
            keypad_keys,
            SWITCH_THRU_KEY,
            row,
            0,
            size=host.s_30,
            visible=False,
            is_ops=True,
        )
        host.switch_out_cell, host.switch_out_btn = host.make_keypad_button(
            keypad_keys,
            SWITCH_OUT_KEY,
            row,
            2,
            size=host.s_30,
            visible=False,
            is_ops=True,
        )

        # Sensor Track Buttons
        host.sensor_track_box = cell = TitleBox(app, "Sequence", layout="auto", align="top", visible=False, border=2)
        cell.text_size = host.s_10

        host.ops_cells.add(cell)
        host.sensor_track_buttons = CheckBoxGroup(
            cell,
            size=host.s_19,
            width=host.emergency_box_width,
            align="top",
            pady=6,
            style="radio",
            options=SENSOR_TRACK_OPTS,
            command=self.on_sensor_track_change,
        )

        host.amc2_ops_box = Box(app, layout="auto", align="top", visible=False, border=2)
        host.amc2_ops_panel = Amc2OpsPanel(host)
        host.amc2_ops_panel.build(host.amc2_ops_box)
        host.ops_cells.add(host.amc2_ops_box)

        # BPC2/ASC2 Buttons
        host.ac_on_cell, host.ac_on_btn = host.make_keypad_button(
            keypad_keys,
            AC_ON_KEY,
            row,
            0,
            0,
            image=host.turn_on_image,
            visible=False,
            is_ops=True,
            titlebox_text="On",
        )

        host.ac_status_cell, host.ac_status_btn = host.make_keypad_button(
            keypad_keys,
            None,
            row,
            1,
            image=host.power_off_path,
            visible=False,
            is_ops=True,
            titlebox_text="Status",
            command=False,
        )

        host.ac_off_cell, host.ac_off_btn = host.make_keypad_button(
            keypad_keys,
            AC_OFF_KEY,
            row,
            2,
            0,
            image=host.turn_off_image,
            visible=False,
            is_ops=True,
            titlebox_text="Off",
        )

        # Acs2 Momentary Action Button
        host.ac_aux1_cell, host.ac_aux1_btn = host.make_keypad_button(
            keypad_keys,
            AUX1_KEY,
            row - 1,
            0,
            host.s_18,
            visible=False,
            is_ops=True,
            command=False,
        )
        host.ac_aux1_btn.when_left_button_pressed = self.when_pressed
        host.ac_aux1_btn.when_left_button_released = self.when_released

        # operating accessory controls key
        host.ac_op_cell, host.ac_op_btn = host.make_keypad_button(
            keypad_keys,
            None,
            row - 1,
            2,
            0,
            image=host.op_acc_image,
            visible=False,
            is_ops=True,
            command=False,
        )
        host.ac_op_btn.disable()

        accessory_slider_rows = len(ENTRY_LAYOUT) + 1
        accessory_total_height = accessory_slider_rows * (host.button_size + (2 * host.grid_pad_by))
        self._accessory_throttle_total_height = accessory_total_height
        bootstrap_slider_height = max(host.button_size, accessory_total_height - int(round(host.button_size * 0.9)))
        host.acc_throttle_box, host.acc_throttle_title_box, host.acc_throttle_level, host.acc_throttle = (
            host.controller_view.make_slider(
                keypad_keys,
                title="Speed",
                command=self.on_accessory_throttle_change,
                frm=ACCESSORY_THROTTLE_MAX,
                to=ACCESSORY_THROTTLE_MIN,
                visible=False,
                grid=(4, 0),
                box_border=1,
                title_border=1,
                level_text="0",
                level_width=3,
                level_font="DigitalDream",
                level_size=host.s_18,
                title_text_size=host.s_10,
                slider_width=int(host.button_size / 2),
                slider_height=bootstrap_slider_height,
                on_release=self.on_accessory_throttle_release,
                clear_focus_on_release=False,
            )
        )
        host.ops_cells.add(host.acc_throttle_box)
        host.acc_throttle_box.grid = [4, 0, 1, accessory_slider_rows]
        host.acc_throttle_box.tk.grid_configure(sticky="ns")
        host.app.tk.after_idle(self._fit_accessory_throttle_height)
        host.acc_throttle.tk.config(resolution=1, showvalue=False)
        host.acc_throttle.text_color = "black"

        self._configure_keypad_grid(expanded=False)

    def on_keypress(self, key: str) -> None:
        host = self._host

        num_chars = 4 if host.scope in {CommandScope.ENGINE, CommandScope.TRAIN} else 2
        tmcc_id = host.tmcc_id_text.value
        # Updates TMCC ID based on key press
        if key.isdigit():
            if int(tmcc_id) and self._reset_on_keystroke:
                host.update_component_info(0)
                tmcc_id = "0" * num_chars
            tmcc_id = tmcc_id[1:] + key
            host.tmcc_id_text.value = tmcc_id
        elif key == CLEAR_KEY:
            self._reset_on_keystroke = False
            tmcc_id = "0" * num_chars
            host.tmcc_id_text.value = tmcc_id
            self.entry_mode()
        elif key == SET_KEY:
            self._reset_on_keystroke = False
            tmcc_id = int(host.tmcc_id_text.value)
            host.on_set_key(host.scope, tmcc_id)
        elif key == ENTER_KEY:
            # if a valid (existing) entry was entered, go to ops mode,
            # otherwise, stay in entry mode
            self._reset_on_keystroke = False
            if host.make_recent(host.scope, int(tmcc_id)):
                host.ops_mode()
            else:
                self.entry_mode(clear_info=False)
        else:
            host.do_command(key)

        # update information immediately if not in entry mode
        if not self._entry_mode and key.isdigit():
            tmcc_id = int(tmcc_id)
            log.debug(f"on_keypress calling update_component_info; TMCC ID: {tmcc_id}")
            host.update_component_info(tmcc_id, not_found_value="")

    def _collapse_acc_aux_cells(self) -> None:
        """Hides accelerator and auxiliary keys when not in ops mode"""
        for cell in self._host.aux_cells:
            grid = getattr(cell, "reset_grid", False)
            if grid:
                cell.grid = grid

    def _expand_acc_aux_cells(self) -> None:
        """Hides accelerator and auxiliary keys when not in ops mode"""
        host = self._host
        for cell in host.aux_cells:
            grid = getattr(cell, "render_grid", False)
            if grid:
                cell.grid = grid

    def activate_numeric_keys(self) -> None:
        host = self._host
        with host.locked():
            if not self._numeric_keys:
                for digit, btn in host.numeric_btns.items():
                    btn.on_press = (host.on_keypress, [str(digit)])
                self._numeric_keys = True

    def activate_accessory_keys(self) -> None:
        host = self._host
        with host.locked():
            if self._numeric_keys:
                for digit, btn in host.numeric_btns.items():
                    btn.on_press = (host.on_acc_command, ["NUMERIC", int(digit)])
                self._numeric_keys = False

    @staticmethod
    def _format_accessory_throttle(value: int) -> str:
        if value > 0:
            return f"+{value}"
        return str(value)

    def _cancel_accessory_throttle_repeat(self) -> None:
        host = self._host
        if self._accessory_throttle_after_id is not None and host.acc_throttle is not None:
            host.acc_throttle.tk.after_cancel(self._accessory_throttle_after_id)
            self._accessory_throttle_after_id = None

    def _schedule_accessory_throttle_repeat(self) -> None:
        host = self._host
        self._cancel_accessory_throttle_repeat()
        if host.acc_throttle is None or self._accessory_throttle_value == 0:
            return
        self._accessory_throttle_after_id = host.acc_throttle.tk.after(
            ACCESSORY_THROTTLE_REPEAT_MS, self._repeat_accessory_throttle
        )

    def _send_accessory_throttle(self, value: int) -> None:
        self._host.on_acc_command("RELATIVE_SPEED", value)

    def _configure_keypad_grid(self, *, expanded: bool) -> None:
        host = self._host
        keypad_keys = host.keypad_keys
        if keypad_keys is None:
            return

        num_rows = len(ENTRY_LAYOUT) + 1
        max_cols = 5
        entry_cols = len(ENTRY_LAYOUT[0])
        min_cell_height = host.button_size + (2 * host.grid_pad_by)
        min_cell_width = host.button_size + (2 * host.grid_pad_by)

        for r in range(num_rows):
            keypad_keys.tk.grid_rowconfigure(r, weight=1, minsize=min_cell_height)

        for c in range(max_cols):
            is_active_col = expanded or c < entry_cols
            keypad_keys.tk.grid_columnconfigure(
                c,
                weight=1 if is_active_col else 0,
                minsize=min_cell_width if is_active_col else 0,
            )

        if expanded:
            keypad_keys.tk.grid_propagate(False)
            keypad_keys.tk.configure(
                width=max_cols * min_cell_width,
                height=num_rows * min_cell_height,
            )
        else:
            keypad_keys.tk.grid_propagate(True)
            keypad_keys.tk.configure(
                width=entry_cols * min_cell_width,
                height=1,
            )

    def _fit_accessory_throttle_height(self) -> None:
        host = self._host
        if (
            host.acc_throttle_box is None
            or host.acc_throttle is None
            or host.acc_throttle_title_box is None
            or not host.acc_throttle_box.visible
        ):
            return

        host.app.tk.update_idletasks()
        total_height = self._accessory_throttle_total_height or (
            (len(ENTRY_LAYOUT) + 1) * (host.button_size + (2 * host.grid_pad_by))
        )
        host.acc_throttle_box.tk.configure(height=total_height)
        title_height = max(
            int(host.acc_throttle_title_box.tk.winfo_height()),
            int(host.acc_throttle_title_box.tk.winfo_reqheight()),
        )
        slider_height = max(host.button_size, total_height - title_height - 2)
        host.acc_throttle.height = slider_height
        host.acc_throttle.tk.config(
            length=slider_height,
            sliderlength=max(16, int(slider_height / 6)),
        )

    def _set_accessory_throttle_display(self, value: int, update_slider: bool = False) -> None:
        host = self._host
        if host.acc_throttle_level is not None:
            host.acc_throttle_level.value = self._format_accessory_throttle(value)
        if update_slider and host.acc_throttle is not None and host.acc_throttle.value != value:
            host.acc_throttle.value = value

    def _repeat_accessory_throttle(self) -> None:
        self._accessory_throttle_after_id = None
        if self._accessory_throttle_value == 0:
            return
        self._send_accessory_throttle(self._accessory_throttle_value)
        self._schedule_accessory_throttle_repeat()

    def on_accessory_throttle_change(self, value) -> None:
        host = self._host
        if host.acc_throttle is None:
            return
        try:
            speed = max(ACCESSORY_THROTTLE_MIN, min(ACCESSORY_THROTTLE_MAX, int(float(value))))
        except (TypeError, ValueError):
            return

        self._accessory_throttle_value = speed
        self._set_accessory_throttle_display(speed)
        if speed != 0:
            self._send_accessory_throttle(speed)
            self._schedule_accessory_throttle_repeat()
        else:
            self._cancel_accessory_throttle_repeat()

    def on_accessory_throttle_release(self, _event: EventData = None) -> None:
        self._cancel_accessory_throttle_repeat()
        self._accessory_throttle_value = 0
        self._set_accessory_throttle_display(0, update_slider=True)
        self._send_accessory_throttle(0)

    def update_accessory_throttle_from_state(self, state: AccessoryState | None) -> None:
        host = self._host
        if host.acc_throttle is None:
            return
        speed = 0
        if isinstance(state, AccessoryState) and not (
            state.is_sensor_track or state.is_amc2 or state.is_bpc2 or state.is_asc2
        ):
            speed = max(ACCESSORY_THROTTLE_MIN, min(ACCESSORY_THROTTLE_MAX, int(state.relative_speed)))
        self._set_accessory_throttle_display(speed)
        if host.acc_throttle.tk.focus_displayof() != host.acc_throttle.tk and host.acc_throttle.value != speed:
            host.acc_throttle.value = speed

    # noinspection PyProtectedMember
    def entry_mode(self, clear_info: bool = True) -> None:
        """Manages entry mode keypad display and button states"""
        host = self._host
        self._entry_mode = True
        self._configure_keypad_grid(expanded=False)
        if clear_info:
            host.update_component_info(0)
        else:
            self._reset_on_keystroke = True
            host.image_box.hide()
        self._entry_mode = True
        for cell in host.entry_cells:
            if not cell.visible:
                cell.show()
        for cell in host.ops_cells:
            if cell.visible:
                cell.hide()
        self._collapse_acc_aux_cells()
        self.activate_numeric_keys()
        self.scope_power_btns()
        self.scope_set_btn()
        if host.acc_overlay and host.acc_overlay.visible:
            host.acc_overlay.hide()
        if not host.keypad_box.visible:
            host.keypad_box.show()
        if host.scope in {CommandScope.ENGINE, CommandScope.TRAIN} and host._scope_tmcc_ids[host.scope]:
            host.reset_btn.enable()
        else:
            host.reset_btn.disable()

    def enter_ops_mode_base(self) -> None:
        """
        Common ops-mode transition work that is purely keypad/view state:
          - flip entry-mode flag
          - hide entry/ops cells (caller will selectively re-show ops cells)
        """
        host = self._host
        self._entry_mode = False

        for cell in host.entry_cells:
            if cell.visible:
                cell.hide()

        for cell in host.ops_cells:
            if cell.visible:
                cell.hide()

        self._collapse_acc_aux_cells()
        self.activate_numeric_keys()

    def apply_ops_mode_ui_engine_shell(self) -> None:
        """
        Ops-mode UI changes for engine/train scope that are purely view concerns:
          - hide keypad area (so controller can take over)
          - ensure controller container(s) are visible
          - enable Reset
        """
        host = self._host
        self._configure_keypad_grid(expanded=False)

        # Hide keypad/controller boxes appropriately
        if host.controller_box.visible:
            host.controller_box.hide()
        if host.keypad_box.visible:
            host.keypad_box.hide()
        if host.acc_throttle_box and host.acc_throttle_box.visible:
            host.acc_throttle_box.hide()
        if host.amc2_ops_box and host.amc2_ops_box.visible:
            host.amc2_ops_box.hide()
        if host.sensor_track_box and host.sensor_track_box.visible:
            host.sensor_track_box.hide()
        if host.acc_overlay and host.acc_overlay.visible:
            host.acc_overlay.hide()

        host.reset_btn.enable()

        # Show controller UI
        if not host.controller_keypad_box.visible:
            host.controller_keypad_box.show()
        if not host.controller_box.visible:
            host.controller_box.show()

    def apply_ops_mode_ui_non_engine(self, state: S | None = None) -> None:
        """
        All non-engine/train ops-mode UI decisions.
        EngineGui should call this only when NOT engine/train.
        """
        host = self._host
        self._configure_keypad_grid(expanded=False)
        if host.controller_box and host.controller_box.visible:
            host.controller_box.hide()
        if host.sensor_track_box and host.sensor_track_box.visible:
            host.sensor_track_box.hide()
        if host.acc_throttle_box and host.acc_throttle_box.visible:
            host.acc_throttle_box.hide()

        # reset is only meaningful for engine/train
        if host.reset_btn.enabled:
            host.reset_btn.disable()

        if host.scope == CommandScope.ACC:
            host.reset_acc_overlay()
        if host.amc2_ops_box and host.amc2_ops_box.visible:
            host.amc2_ops_box.hide()

        if host.scope == CommandScope.ROUTE:
            host.on_new_route()
            host.fire_route_cell.show()
            if not host.keypad_box.visible:
                host.keypad_box.show()
            return

        if host.scope == CommandScope.SWITCH:
            host.on_new_switch()
            host.switch_thru_cell.show()
            host.switch_out_cell.show()
            if not host.keypad_box.visible:
                host.keypad_box.show()
            return

        # Handles accessory or BPC2 state and UI visibility
        if self.is_accessory_or_bpc2:
            if state is None:
                state = self.active_state

            host.on_new_accessory(state)
            show_keypad = True

            acc_state = state.state if isinstance(state, ConfiguredAccessoryAdapter) else state
            if isinstance(acc_state, AccessoryState):
                # Shows accessory controls based on accessory state
                if acc_state.is_sensor_track:
                    host.sensor_track_box.show()
                    host.keypad_box.hide()
                    show_keypad = False
                elif acc_state.is_amc2:
                    if host.amc2_ops_box and not host.amc2_ops_box.visible:
                        host.amc2_ops_box.show()
                    if host.amc2_ops_panel:
                        host.amc2_ops_panel.update_from_state(acc_state)
                        host.amc2_ops_panel.refresh_layout()
                    host.keypad_box.hide()
                    show_keypad = False
                elif acc_state.is_bpc2 or acc_state.is_asc2:
                    host.ac_off_cell.show()
                    host.ac_status_cell.show()
                    host.ac_on_cell.show()
                    if acc_state.is_asc2:
                        host.ac_aux1_cell.show()
                        if host.accessories.configured_by_tmcc_id(state.tmcc_id):
                            host.ac_op_cell.grid = [2, 3]
                            self.enable_acc_view(acc_state)
                else:
                    self._configure_keypad_grid(expanded=True)
                    for cell in host.aux_cells:
                        if cell and not cell.visible:
                            cell.show()
                    self.activate_accessory_keys()
                    self._expand_acc_aux_cells()
                    self.update_accessory_throttle_from_state(acc_state)
                    if host.acc_throttle_box and not host.acc_throttle_box.visible:
                        host.acc_throttle_box.show()
                    host.app.tk.after_idle(self._fit_accessory_throttle_height)
                    if host.accessories.configured_by_tmcc_id(state.tmcc_id):
                        host.ac_op_cell.grid = [1, 4]
                        self.enable_acc_view(acc_state)

            if show_keypad and not host.keypad_box.visible:
                host.keypad_box.show()

    # noinspection PyTypeChecker
    def enable_acc_view(self, state: S):
        host = self._host
        acc = host.accessory_provider.adapters_for_tmcc_id(state.tmcc_id)
        if acc is None:
            return

        acc = acc[0]
        acc.activate_tmcc_id(state.tmcc_id)

        image = find_file(acc.op_btn_image_path)
        host.ac_op_btn.image = image
        host.ac_op_btn.images = host.get_image(image, size=host.button_size)
        host.ac_op_btn.tk.config(
            borderwidth=2,
            compound="center",
            width=host.button_size,
            height=host.button_size,
        )

        host.ac_op_btn.update_command(host.on_configured_accessory, [acc])
        host.ac_op_btn.enable()
        host.ac_op_cell.show()

    # noinspection PyProtectedMember
    def scope_keypad(self, force_entry_mode: bool = False, clear_info: bool = True):
        host = self._host
        # if tmcc_id associated with scope is 0, then we are in entry mode;
        # show keypad with appropriate buttons
        tmcc_id = host._scope_tmcc_ids[host.scope]
        if tmcc_id == 0 or force_entry_mode:
            self.entry_mode(clear_info=clear_info)
            self.scope_power_btns()
            if not host.keypad_box.visible:
                host.keypad_box.show()
        if host.scope != CommandScope.ACC and host.acc_overlay and host.acc_overlay.visible:
            host.reset_acc_overlay()

    def scope_power_btns(self):
        host = self._host
        if self.is_engine_or_train:
            host.on_key_cell.show()
            host.off_key_cell.show()
        else:
            host.on_key_cell.hide()
            host.off_key_cell.hide()

    def scope_set_btn(self) -> None:
        host = self._host
        if host.scope in {CommandScope.ROUTE}:
            host.set_btn.hide()
        else:
            host.set_btn.show()

    # noinspection PyProtectedMember
    def on_sensor_track_change(self) -> None:
        host = self._host
        tmcc_id = host._scope_tmcc_ids[host.scope]
        st_seq = IrdaSequence.by_value(int(host.sensor_track_buttons.value))
        IrdaReq(tmcc_id, PdiCommand.IRDA_SET, IrdaAction.SEQUENCE, sequence=st_seq).send(repeat=host.repeat)

    # noinspection PyProtectedMember
    def when_pressed(self, event: EventData) -> None:
        """Sends `Asc2` control command when button pressed"""
        host = self._host
        pb = event.widget
        if pb.enabled:
            scope = host.scope
            tmcc_id = host._scope_tmcc_ids[scope]
            state = host.state_store.get_state(scope, tmcc_id, False)
            if isinstance(state, AccessoryState) and state.is_asc2:
                Asc2Req(state.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=1).send()

    # noinspection PyProtectedMember
    def when_released(self, event: EventData) -> None:
        """Sends `Asc2` release command when button released"""
        host = self._host
        pb = event.widget
        if pb.enabled:
            scope = host.scope
            tmcc_id = host._scope_tmcc_ids[scope]
            state = host.state_store.get_state(scope, tmcc_id, False)
            if isinstance(state, AccessoryState) and state.is_asc2:
                Asc2Req(state.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=0).send()
