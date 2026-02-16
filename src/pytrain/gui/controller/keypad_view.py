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

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui

S = TypeVar("S", ComponentState, ConfiguredAccessoryAdapter)


class KeypadView(Generic[S]):
    def __init__(self, host: "EngineGui") -> None:
        self._host: "EngineGui" = host
        self._reset_on_keystroke = False
        self._entry_mode = True

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
        setattr(cell, "render_col", 3)
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
        setattr(cell, "render_col", 3)
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

        # --- set minimum size but allow expansion ---
        # --- Enforce minimum keypad size, but allow expansion ---
        num_rows = 5
        num_cols = 3
        min_cell_height = host.button_size + (2 * host.grid_pad_by)
        min_cell_width = host.button_size + (2 * host.grid_pad_by)

        # Allow dynamic expansion if children exceed minsize
        keypad_box.tk.grid_propagate(True)

        # Apply minsize for each row/column
        for r in range(num_rows):
            keypad_box.tk.grid_rowconfigure(r, weight=1, minsize=min_cell_height)

        for c in range(num_cols):
            keypad_box.tk.grid_columnconfigure(c, weight=1, minsize=min_cell_width)

        # (Optional) overall bounding box minimum size
        min_total_height = num_rows * min_cell_height
        min_total_width = num_cols * min_cell_width
        keypad_box.tk.configure(width=min_total_width, height=min_total_height)

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
        host = self._host
        for cell in host.aux_cells:
            if getattr(cell, "render_col", False):
                grid = cell.grid
                grid[0] = 2
                cell.grid = grid

    def _expand_acc_aux_cells(self) -> None:
        """Hides accelerator and auxiliary keys when not in ops mode"""
        host = self._host
        for cell in host.aux_cells:
            if getattr(cell, "render_col", False):
                grid = cell.grid
                grid[0] = int(getattr(cell, "render_col"))
                cell.grid = grid

    # noinspection PyProtectedMember
    def entry_mode(self, clear_info: bool = True) -> None:
        """Manages entry mode keypad display and button states"""
        host = self._host
        self._entry_mode = True
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

    def apply_ops_mode_ui_engine_shell(self) -> None:
        """
        Ops-mode UI changes for engine/train scope that are purely view concerns:
          - hide keypad area (so controller can take over)
          - ensure controller container(s) are visible
          - enable Reset
        """
        host = self._host

        # Hide keypad/controller boxes appropriately
        if host.controller_box.visible:
            host.controller_box.hide()
        if host.keypad_box.visible:
            host.keypad_box.hide()
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

        # reset is only meaningful for engine/train
        if host.reset_btn.enabled:
            host.reset_btn.disable()

        if host.scope == CommandScope.ACC:
            host.reset_acc_overlay()

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
                    for cell in host.aux_cells:
                        if cell and not cell.visible:
                            cell.show()
                    if host.accessories.configured_by_tmcc_id(state.tmcc_id):
                        host.ac_op_cell.grid = [1, 4]
                        self._expand_acc_aux_cells()
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
