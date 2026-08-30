#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import logging
from tkinter import TclError
from typing import Generic, TYPE_CHECKING, TypeVar

from guizero import App, Box, TitleBox
from guizero.event import EventData

from .accessory_bindings import (
    PANEL_AMC2,
    PANEL_ASC2,
    PANEL_BPC2,
    PANEL_GENERIC,
    PANEL_SENSOR_TRACK,
)
from .amc2_ops_panel import Amc2OpsPanel
from .configured_accessory_adapter import ConfiguredAccessoryAdapter
from .engine_gui_conf import (
    AC_OFF_KEY,
    AC_ON_KEY,
    ACC_PANEL_KEY,
    ASC2_OP_IMAGE,
    AUX1_KEY,
    AUX2_KEY,
    BPC2_OP_IMAGE,
    CLEAR_KEY,
    CREATABLE_SCOPES,
    ENGINE_OFF_KEY,
    ENTER_KEY,
    ENTRY_LAYOUT,
    FIRE_ROUTE_KEY,
    INFO_KEY,
    LCS_NOOP_KEY,
    LCS_PANEL_KEY,
    OP_SCREEN_IMAGE,
    SENSOR_TRACK_OPTS,
    SET_KEY,
    SWITCH_OUT_KEY,
    SWITCH_THRU_KEY,
)
from ..components.checkbox_group import CheckBoxGroup
from ..components.hold_button import HoldButton
from ...db.accessory_state import AccessoryState
from ...db.component_state import ComponentState, LcsProxyState
from ...db.component_state_store import ComponentStateStore
from ...db.engine_state import TrainState
from ...pdi.asc2_req import Asc2Req
from ...pdi.constants import Asc2Action, IrdaAction, PdiCommand
from ...pdi.irda_req import IrdaReq, IrdaSequence
from ...protocol.constants import CommandScope
from ...utils.path_utils import find_file

log = logging.getLogger(__name__)

ACCESSORY_THROTTLE_MIN = -5
ACCESSORY_THROTTLE_MAX = 5
ACCESSORY_THROTTLE_REPEAT_MS = 200

# Which purpose-drawn device icon the shared return key wears when it points back to a given
# native LCS panel. Kinds with no icon (a forced-generic Sensor Track or AMC2) fall back to the
# LCS_PANEL_KEY text label.
NATIVE_PANEL_RETURN_ICON = {
    PANEL_BPC2: BPC2_OP_IMAGE,
    PANEL_ASC2: ASC2_OP_IMAGE,
}

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
        # Transient accessory panel override; see set_panel_kind_override. Cleared on any change
        # of selected TMCC ID, any change of scope, and on return to entry mode.
        self._forced_panel_kind: str | None = None
        # Every cell parented to ``keypad_keys`` (numeric, entry, ops and aux cells) plus the
        # accessory throttle box, recorded so ``_reflow_keypad_columns`` can collapse the grid
        # columns that hold no visible cell. See build() / _register_keypad_cell.
        self._keypad_cells: list = []

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

    @property
    def accessory_panel_kind(self) -> str | None:
        """Which accessory panel this pane is displaying.

        One of ``sensor_track``, ``amc2``, ``bpc2``, ``asc2`` or ``generic``, and None when the
        pane is not showing an accessory panel at all -- an engine, a switch, a route, or an
        accessory scope with nothing selected yet.

        The single place that decision is made: ``apply_ops_mode_ui_non_engine`` reads it to
        pick the keys it shows, and the input layer reads it to pick the gamepad context, so the
        panel on screen and the context claiming the pad cannot disagree. Note in particular
        that ``is_lcs_component`` is not consulted -- an LCS port that is none of the four named
        kinds shows the generic panel and is reported as showing it.
        """
        return self._panel_kind_for(self.active_state)

    @property
    def panel_kind_override(self) -> str | None:
        """The accessory panel forced onto the display, if any; None where none is."""
        return self._forced_panel_kind

    def set_panel_kind_override(self, kind: str | None) -> None:
        """Force (or stop forcing) a particular accessory panel for the current selection.

        A single transient flag, deliberately: it lives inside ``_panel_kind_for``, the one
        property both the drawn keys and the gamepad context chain read, so the screen and the
        pad cannot disagree about which panel is up. It is cleared on any change of selected
        TMCC ID, any change of scope, and on return to entry mode, so leaving a device and
        coming back shows its native panel again.
        """
        self._forced_panel_kind = kind

    # noinspection PyUnresolvedReferences
    def _panel_kind_for(self, state: S | None) -> str | None:
        """``accessory_panel_kind`` for a given state, which need not be the active one.

        The ops-mode UI is handed the state it is about to display and asks about that.
        """
        if not self.is_accessory_or_bpc2 or state is None:
            return None
        if self._forced_panel_kind is not None:
            return self._forced_panel_kind
        return self._native_panel_kind_for(state)

    # noinspection PyUnresolvedReferences
    def _native_panel_kind_for(self, state: S | None) -> str | None:
        """The panel a state's own flags call for, ignoring any override in force."""
        if state is None:
            return None
        acc_state = state.state if isinstance(state, ConfiguredAccessoryAdapter) else state
        if isinstance(acc_state, AccessoryState):
            if acc_state.is_sensor_track:
                return PANEL_SENSOR_TRACK
            if acc_state.is_amc2:
                return PANEL_AMC2
            # An ASC2 shows everything a BPC2 does and its own AUX1 key besides, so where both
            # flags read true the more specific one is the panel drawn -- as it is below.
            if acc_state.is_asc2:
                return PANEL_ASC2
            if acc_state.is_bpc2:
                return PANEL_BPC2
            return PANEL_GENERIC
        if isinstance(acc_state, LcsProxyState) and acc_state.is_power_district:
            return PANEL_BPC2
        return None

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

        # Rebuild the reflow roster from scratch; every cell parented to keypad_keys is filed
        # here through make_key so _reflow_keypad_columns can read live occupancy.
        self._keypad_cells = []

        def make_key(*args, **kwargs):
            cell, nb = host.make_keypad_button(*args, **kwargs)
            self._register_keypad_cell(cell)
            return cell, nb

        row = 0
        for r, kr in enumerate(ENTRY_LAYOUT):
            for c, label in enumerate(kr):
                if isinstance(label, tuple):
                    image = find_file(label[1])
                    label = label[0]
                else:
                    image = None

                cell, nb = make_key(
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
        cell, btn = make_key(
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

        cell, btn = make_key(
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

        cell, btn = make_key(
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

        cell, btn = make_key(
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

        cell, btn = make_key(
            keypad_keys,
            SET_KEY,
            row - 2,
            2,
            size=host.s_18,
            visible=False,
            is_ops=True,
            hover=True,
            command=False,
        )
        host.aux_cells.add(cell)
        setattr(cell, "render_grid", [3, row - 4])
        btn.on_press = (host.on_acc_command, ["SET_ADDRESS"])

        cell, btn = make_key(
            keypad_keys,
            None,
            row - 2,
            2,
            size=host.s_18,
            visible=False,
            image=find_file("toggle.jpg"),
            is_ops=True,
            hover=True,
            command=False,
        )
        host.aux_cells.add(cell)
        setattr(cell, "render_grid", [3, row - 3])
        btn.on_press = (host.on_acc_command, ["TOGGLE_DIRECTION"])

        cell, btn = make_key(
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

        cell, btn = make_key(
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
        host.on_key_cell, host.on_btn = make_key(
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

        host.off_key_cell, host.off_btn = make_key(
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
        host.set_key_cell, host.set_btn = make_key(
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
        host.fire_route_cell, host.fire_route_btn = make_key(
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
        host.switch_thru_cell, host.switch_thru_btn = make_key(
            keypad_keys,
            SWITCH_THRU_KEY,
            row,
            0,
            size=host.s_30,
            visible=False,
            is_ops=True,
        )
        host.switch_out_cell, host.switch_out_btn = make_key(
            keypad_keys,
            SWITCH_OUT_KEY,
            row,
            2,
            size=host.s_30,
            visible=False,
            is_ops=True,
        )

        # switch Set Address key; the aux Set key at the same slot only ever renders on the
        # generic accessory panel, so the two cannot be on screen at once.
        host.sw_set_cell, host.sw_set_btn = make_key(
            keypad_keys,
            SET_KEY,
            0,
            3,
            size=host.s_16,
            visible=False,
            is_ops=True,
            hover=True,
            command=False,
        )
        host.sw_set_btn.on_press = (self.on_switch_set_key, [])

        # Info key; the only route to the state info panel on the switch panel, as that scope
        # hides the image box and with it the long-press target.
        host.info_cell, host.info_btn = make_key(
            keypad_keys,
            INFO_KEY,
            2,
            3,
            size=host.s_16,
            visible=False,
            is_ops=True,
            hover=True,
            command=host.on_info,
            args=[],
        )

        # Panel toggle key shown on the BPC2/ASC2 panels. It sits below the "9" key and above
        # the "Off" key (row 3, column 2), so the numeric-pad column carries it rather than the
        # 4th column -- which lets BPC2 collapse its empty 4th column under the reflow. Takes the
        # display to the generic accessory panel -- the only one with Set Address.
        host.acc_generic_cell, host.acc_generic_btn = make_key(
            keypad_keys,
            ACC_PANEL_KEY,
            3,
            2,
            size=host.s_16,
            visible=False,
            is_ops=True,
            hover=True,
            command=host.on_show_generic_acc_panel,
            args=[],
        )

        # ASC2-only keys, stacked in the free 4th column (column 3). "Set" fires ACC SET_ADDRESS
        # so the address can be programmed from the native ASC2 panel; "LCS..." is a visible
        # placeholder whose behavior is specified in a later turn (a no-op for now).
        host.acc_set_cell, host.acc_set_btn = make_key(
            keypad_keys,
            SET_KEY,
            0,
            3,
            size=host.s_16,
            visible=False,
            is_ops=True,
            hover=True,
            command=False,
        )
        host.acc_set_btn.on_press = (self.on_acc_set_key, [])

        host.lcs_noop_cell, host.lcs_noop_btn = make_key(
            keypad_keys,
            LCS_NOOP_KEY,
            1,
            3,
            size=host.s_16,
            visible=False,
            is_ops=True,
            hover=True,
            command=self.on_lcs_noop,
            args=[],
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
            pady=host.sensor_track_row_pady,
            style="radio",
            options=SENSOR_TRACK_OPTS,
            command=self.on_sensor_track_change,
            # The one group in the app that opts into the row cursor: the gamepad steps this
            # list, so it is the one place where "where the pad is" and "what the track is
            # programmed with" are two different things that both have to be shown.
            cursor=True,
        )

        # The Sensor Track panel replaces the whole keypad, so its way to the generic accessory
        # panel goes below the Sequence list rather than in a keypad cell.
        host.sensor_track_generic_btn = HoldButton(
            cell,
            text=ACC_PANEL_KEY,
            align="bottom",
            width="fill",
            text_size=host.s_12,
            command=host.on_show_generic_acc_panel,
            args=[],
        )

        host.amc2_ops_box = Box(app, layout="auto", align="top", visible=False, border=2)
        host.amc2_ops_panel = Amc2OpsPanel(host)
        host.amc2_ops_panel.build(host.amc2_ops_box)
        host.ops_cells.add(host.amc2_ops_box)
        # AMC2 replaces the keypad too; its toggle lives in the panel header, which exposes the
        # button rather than the command so the wiring stays here with every other key.
        amc2_toggle = getattr(host.amc2_ops_panel, "panel_toggle_button", None)
        if amc2_toggle is not None:
            amc2_toggle.update_command(host.on_show_generic_acc_panel, [])

        # BPC2/ASC2 Buttons
        host.ac_on_cell, host.ac_on_btn = make_key(
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

        host.ac_status_cell, host.ac_status_btn = make_key(
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

        host.ac_off_cell, host.ac_off_btn = make_key(
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
        host.ac_aux1_cell, host.ac_aux1_btn = make_key(
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
        host.ac_op_cell, host.ac_op_btn = make_key(
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

        acc_throttle_height = (5 * host.button_size) + (4 * host.grid_pad_by)
        host.acc_throttle_box, host.acc_throttle_title_box, host.acc_throttle_level, host.acc_throttle = (
            host.controller_view.make_slider(
                keypad_keys,
                title="Speed",
                command=self.on_accessory_throttle_change,
                frm=ACCESSORY_THROTTLE_MAX,
                to=ACCESSORY_THROTTLE_MIN,
                visible=False,
                grid=(4, 0, 1, 5),
                box_border=1,
                title_border=1,
                level_text="0",
                level_width=3,
                level_font=getattr(host, "digital_font", "TkDefaultFont"),
                level_size=host.s_18,
                title_text_size=host.s_10,
                slider_width=int(host.button_size / 2),
                slider_height=host.slider_height,
                on_release=self.on_accessory_throttle_release,
                clear_focus_on_release=False,
            )
        )

        host.ops_cells.add(host.acc_throttle_box)
        # The throttle occupies column 4, so it joins the reflow roster too: when hidden its
        # column collapses like any other, when shown (the generic panel) it holds column 4.
        self._register_keypad_cell(host.acc_throttle_box)
        host.acc_throttle_box.tk.config(
            height=acc_throttle_height,
        )

        host.app.tk.update_idletasks()
        title_height = host.acc_throttle_title_box.tk.winfo_reqheight()
        slider_height = max(host.button_size, acc_throttle_height - title_height)
        host.acc_throttle.height = slider_height
        host.acc_throttle.tk.config(resolution=1, showvalue=False)
        host.acc_throttle.text_color = "black"

        # --- set minimum size but allow expansion ---
        # --- Enforce minimum keypad size, but allow expansion ---
        num_rows = 5
        num_cols = 5
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

    def _register_keypad_cell(self, cell) -> None:
        """Files a cell parented to ``keypad_keys`` into the reflow roster.

        The single choke point every keypad cell passes through -- numeric, entry, ops and aux
        cells go through ``make_key`` in build(), and the accessory throttle box is added
        alongside them -- so ``_reflow_keypad_columns`` can read column occupancy from one list.
        """
        if cell is not None and cell not in self._keypad_cells:
            self._keypad_cells.append(cell)

    def _min_keypad_cell_width(self) -> int:
        """The width a single occupied keypad column reserves; the build-time cell width."""
        host = self._host
        return host.button_size + (2 * host.grid_pad_by)

    def _reflow_keypad_columns(self) -> None:
        """Collapses keypad grid columns that hold no visible cell; restores occupied ones.

        Reads each tracked cell's live ``.grid[0]`` and ``.visible`` -- late, so aux cells that
        ``_expand_acc_aux_cells`` relocated to column 3 count as occupancy -- and reconfigures
        ``keypad_keys`` one column at a time: an occupied column gets ``weight=1`` and the
        build-time cell width, an empty one collapses to ``weight=0, minsize=0``. The numeric
        columns 0-2 always hold visible keys, so the rule keeps them and never has to special
        case them. Finally the keypad boxes are tightened to the occupied-column count so the
        numeric pad does not float, leaving a gap where a collapsed column used to be.
        """
        host = self._host
        keypad_keys = host.keypad_keys
        keypad_box = host.keypad_box
        if keypad_keys is None:
            return

        min_cell_width = self._min_keypad_cell_width()

        # Group tracked cells by their live grid column, noting which columns hold a visible one.
        occupied: dict[int, bool] = {}
        max_col = -1
        for cell in self._keypad_cells:
            grid = getattr(cell, "grid", None)
            if not grid:
                continue
            col = int(grid[0])
            max_col = max(max_col, col)
            if getattr(cell, "visible", False):
                occupied[col] = True
            else:
                occupied.setdefault(col, False)

        occupied_cols = 0
        for col in range(max_col + 1):
            if occupied.get(col, False):
                keypad_keys.tk.grid_columnconfigure(col, weight=1, minsize=min_cell_width)
                occupied_cols += 1
            else:
                keypad_keys.tk.grid_columnconfigure(col, weight=0, minsize=0)

        # Tighten the keypad to the occupied columns so it does not leave a right-side gap.
        total_width = occupied_cols * min_cell_width
        keypad_keys.tk.configure(width=total_width)
        if keypad_box is not None:
            keypad_box.tk.configure(width=total_width)

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
            end_range = 9999 if host.scope in {CommandScope.ENGINE, CommandScope.TRAIN} else 98
            if tmcc_id and 2 <= tmcc_id <= end_range and tmcc_id != 99:
                host.on_set_key(host.scope, tmcc_id)
                state = ComponentStateStore.get_state(host.scope, tmcc_id, create=False)
                if state is None:
                    state = ComponentStateStore.get_state(host.scope, tmcc_id, create=True)
                    state.initialize(scope=host.scope, tmcc_id=tmcc_id)
                    host.ops_mode(update_info=True, state=state)
                    host.on_info(state=state)
                    return
        elif key == ENTER_KEY:
            # if a valid (existing) entry was entered, go to ops mode; if it is an undefined,
            # but creatable, component, create it and go to ops mode; otherwise, stay in entry mode
            self._reset_on_keystroke = False
            entered = int(tmcc_id)
            if host.make_recent(host.scope, entered):
                host.ops_mode()
            elif self._can_create(host.scope, entered):
                state = host.create_provisional_component(host.scope, entered)
                host.ops_mode(update_info=True, state=state)
            else:
                self.entry_mode(clear_info=False)
        else:
            host.do_command(key)

        # update information immediately if not in entry mode
        if not self._entry_mode and key.isdigit():
            tmcc_id = int(tmcc_id)
            log.debug(f"on_keypress calling update_component_info; TMCC ID: {tmcc_id}")
            host.update_component_info(tmcc_id, not_found_value="")

    def on_switch_set_key(self) -> None:
        """Fires SET_ADDRESS for the currently displayed switch"""
        host = self._host
        host.on_set_key(CommandScope.SWITCH, host.scope_tmcc_id(CommandScope.SWITCH))

    def on_acc_set_key(self) -> None:
        """Fires ACC SET_ADDRESS for the accessory shown on the native ASC2 panel."""
        host = self._host
        host.on_set_key(CommandScope.ACC, host.scope_tmcc_id(CommandScope.ACC))

    def on_lcs_noop(self, _key: str | None = None) -> None:
        """Placeholder for the native-panel LCS... key; its behavior is a later turn's work."""
        log.debug("LCS... key pressed; no behavior wired yet")

    @staticmethod
    def _can_create(scope: CommandScope, tmcc_id: int) -> bool:
        """
        True if a component of the given scope can be created at the given TMCC ID. Applies
        the same range rule the Set key does; only Accessories and Switches qualify for now.
        """
        if scope not in CREATABLE_SCOPES:
            return False
        return bool(tmcc_id) and 2 <= tmcc_id <= 98 and tmcc_id != 99

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
        if host.acc_throttle is None or host.acc_throttle.value == 0:
            return
        self._accessory_throttle_after_id = host.acc_throttle.tk.after(
            ACCESSORY_THROTTLE_REPEAT_MS, self._repeat_accessory_throttle
        )

    def _send_accessory_throttle(self, value: int) -> None:
        self._host.on_acc_command("RELATIVE_SPEED", value)

    def _set_accessory_throttle_display(self, value: int, update_slider: bool = False) -> None:
        host = self._host
        if host.acc_throttle_level is not None:
            host.acc_throttle_level.value = self._format_accessory_throttle(value)
        if update_slider and host.acc_throttle is not None and host.acc_throttle.value != value:
            host.acc_throttle.value = value

    def _repeat_accessory_throttle(self) -> None:
        self._accessory_throttle_after_id = None
        if self._host.acc_throttle.value == 0:
            return
        self._send_accessory_throttle(self._host.acc_throttle.value)
        self._schedule_accessory_throttle_repeat()

    def on_accessory_throttle_change(self, value) -> None:
        host = self._host
        if host.acc_throttle is None or host.acc_throttle.tk.focus_displayof() != host.acc_throttle.tk:
            return  # don't schedule repeats unless our throttle has focus
        try:
            speed = max(ACCESSORY_THROTTLE_MIN, min(ACCESSORY_THROTTLE_MAX, int(float(value))))
        except (TypeError, ValueError):
            return

        self._set_accessory_throttle_display(speed)
        self._send_accessory_throttle(speed)
        if speed != 0:
            self._schedule_accessory_throttle_repeat()
        else:
            self._cancel_accessory_throttle_repeat()

    def on_accessory_throttle_release(self, _event: EventData = None) -> None:
        self._cancel_accessory_throttle_repeat()
        self._set_accessory_throttle_display(0, update_slider=True)
        self._send_accessory_throttle(0)
        self.clear_focus(_event)

    def update_accessory_throttle_from_state(self, state: AccessoryState | None) -> None:
        host = self._host
        # don't fight the user; if throttle has focus, ignore state changes
        if host.acc_throttle is None or host.acc_throttle.tk.focus_displayof() == host.acc_throttle.tk:
            return
        speed = 0
        if isinstance(state, AccessoryState) and not (
            state.is_sensor_track or state.is_amc2 or state.is_bpc2 or state.is_asc2
        ):
            speed = max(ACCESSORY_THROTTLE_MIN, min(ACCESSORY_THROTTLE_MAX, int(state.relative_speed)))
        self._set_accessory_throttle_display(speed, update_slider=True)

    # noinspection PyUnusedLocal,unused-parameter
    def clear_focus(self, e=None) -> None:
        host = self._host
        # Clears focus from host widgets after idle time
        focus = host.app.tk.focus_get()
        widgets = {getattr(host, n, None) for n in ("acc_throttle",)}
        tks = {w.tk for w in widgets if w is not None}
        if focus in tks:
            host.app.tk.after_idle(self._do_clear_focus)

    def _do_clear_focus(self) -> None:
        host = self._host
        if host.focus_widget is not None:
            host.focus_widget.focus_set()
        for w in (host.acc_throttle,):
            try:
                if w is not None:
                    w.tk.event_generate("<Leave>")
            except (TclError, AttributeError):
                pass

    # noinspection PyProtectedMember
    def entry_mode(self, clear_info: bool = True) -> None:
        """Manages entry mode keypad display and button states"""
        host = self._host
        self._entry_mode = True
        # returning to entry mode ends the life of any forced accessory panel
        self._forced_panel_kind = None
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
        self._reflow_keypad_columns()

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

        # Hide keypad/controller boxes appropriately
        if host.controller_box.visible:
            host.controller_box.hide()
        if host.keypad_box.visible:
            host.keypad_box.hide()
        if host.amc2_ops_box and host.amc2_ops_box.visible:
            host.amc2_ops_box.hide()
        if host.acc_overlay and host.acc_overlay.visible:
            host.acc_overlay.hide()

        host.reset_btn.enable()

        # Show controller UI
        # if not host.controller_keypad_box.visible:
        #     host.controller_keypad_box.show()
        # if not host.controller_box.visible:
        #     host.controller_box.show()

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
        if host.amc2_ops_box and host.amc2_ops_box.visible:
            host.amc2_ops_box.hide()

        if host.scope == CommandScope.ROUTE:
            host.on_new_route()
            host.fire_route_cell.show()
            if not host.keypad_box.visible:
                host.keypad_box.show()
            self._reflow_keypad_columns()
            return

        if host.scope == CommandScope.SWITCH:
            host.on_new_switch()
            host.switch_thru_cell.show()
            host.switch_out_cell.show()
            host.sw_set_cell.show()
            host.info_cell.show()
            if not host.keypad_box.visible:
                host.keypad_box.show()
            self._reflow_keypad_columns()
            return

        # Handles accessory or BPC2 state and UI visibility
        if self.is_accessory_or_bpc2:
            if state is None:
                state = self.active_state

            host.on_new_accessory(state)
            show_keypad = True

            acc_state = state.state if isinstance(state, ConfiguredAccessoryAdapter) else state
            if isinstance(acc_state, AccessoryState):
                # Shows accessory controls based on accessory state. Which panel that is, is
                # decided in one place -- see accessory_panel_kind -- so the keys on screen and
                # the gamepad context claiming them cannot disagree.
                kind = self._panel_kind_for(state)
                if kind == PANEL_SENSOR_TRACK:
                    host.sensor_track_box.show()
                    host.keypad_box.hide()
                    show_keypad = False
                elif kind == PANEL_AMC2:
                    if host.amc2_ops_box and not host.amc2_ops_box.visible:
                        host.amc2_ops_box.show()
                    if host.amc2_ops_panel:
                        host.amc2_ops_panel.update_from_state(acc_state)
                        host.amc2_ops_panel.refresh_layout()
                    host.keypad_box.hide()
                    show_keypad = False
                elif kind in (PANEL_BPC2, PANEL_ASC2):
                    host.ac_off_cell.show()
                    host.ac_status_cell.show()
                    host.ac_on_cell.show()
                    host.acc_generic_cell.show()
                    if kind == PANEL_ASC2:
                        host.ac_aux1_cell.show()
                        # The native ASC2 panel carries its own Set (ACC SET_ADDRESS) and the
                        # placeholder LCS... key in the 4th column; BPC2 gets neither.
                        host.acc_set_cell.show()
                        host.lcs_noop_cell.show()
                        if host.accessories.configured_by_tmcc_id(state.tmcc_id):
                            # acc_generic now holds [2, 3] (below "9"); the configured-accessory
                            # key drops into the free 4th-column slot below the LCS... key.
                            host.ac_op_cell.grid = [3, 2]
                            self.enable_alternate_acc_view(acc_state)
                elif kind == PANEL_GENERIC:
                    for cell in host.aux_cells:
                        if cell and not cell.visible:
                            cell.show()
                    self.activate_accessory_keys()
                    self._expand_acc_aux_cells()
                    # self.update_accessory_throttle_from_state(acc_state)
                    if host.acc_throttle_box and not host.acc_throttle_box.visible:
                        host.acc_throttle_box.show()
                    host.info_cell.show()
                    if self._alternate_acc_view_kind(acc_state) is not None:
                        host.ac_op_cell.grid = [1, 4]
                        self.enable_alternate_acc_view(acc_state)

            if show_keypad and not host.keypad_box.visible:
                host.keypad_box.show()
                host.app.tk.after_idle(host.image_presenter.update, host.scope_tmcc_id())

            self._reflow_keypad_columns()

    def _alternate_acc_view_kind(self, state: S | None) -> str | None:
        """Which other view of this component ``ac_op_btn`` should offer, if any.

        One key, one meaning -- the other view of this ID. Where a panel override is in force
        the other view is the component's own LCS panel, and that wins: the override is an
        explicit request for the generic panel, so the way back to what was left is the one
        thing the key must offer. Otherwise it keeps today's meaning, the configured-accessory
        overlay, and where there is neither there is nothing to offer.
        """
        if state is None:
            return None
        if self._forced_panel_kind is not None:
            native = self._native_panel_kind_for(state)
            if native is not None and native != self._forced_panel_kind:
                return "native"
        if self._host.accessories.configured_by_tmcc_id(state.tmcc_id):
            return "configured"
        return None

    def enable_alternate_acc_view(self, state: S) -> None:
        """Points ``ac_op_btn`` at the other view of this component and shows it."""
        if self._alternate_acc_view_kind(state) == "native":
            self.enable_native_acc_view(self._native_panel_kind_for(state))
        else:
            self.enable_acc_view(state)

    def enable_native_acc_view(self, native_kind: str | None = None) -> None:
        """Turns ``ac_op_btn`` into the way back from a forced generic panel to the LCS one.

        The key wears the purpose-drawn icon of the device it returns to (BPC2 or ASC2) rather
        than the old tiny "LCS" text, which rendered inconsistently. Kinds with no icon fall
        back to that text so the key is never blank.
        """
        host = self._host
        image_name = NATIVE_PANEL_RETURN_ICON.get(native_kind)
        if image_name is not None:
            self._paint_ac_op_icon(image_name)
        else:
            host.ac_op_btn.image = None
            host.ac_op_btn.text = LCS_PANEL_KEY
        host.ac_op_btn.update_command(host.on_show_native_acc_panel, [])
        host.ac_op_btn.enable()
        host.ac_op_cell.show()

    def _paint_ac_op_icon(self, image_name: str) -> None:
        """Dresses ``ac_op_btn`` as a centered B&W icon, clearing any prior text label."""
        host = self._host
        image = find_file(image_name)
        host.ac_op_btn.text = ""
        host.ac_op_btn.image = image
        host.ac_op_btn.images = host.get_image(image, size=host.button_size)
        host.ac_op_btn.tk.config(
            borderwidth=2,
            compound="center",
            width=host.button_size,
            height=host.button_size,
        )

    # noinspection PyTypeChecker
    def enable_acc_view(self, state: S):
        host = self._host
        acc = host.accessory_provider.adapters_for_tmcc_id(state.tmcc_id)
        if acc is None:
            return

        acc = acc[0]
        acc.activate_tmcc_id(state.tmcc_id)

        # The operating-accessory direction wears the accessory's own op icon (from its Operating
        # Accessory definition); the generic operating-screen icon is only a fallback when the
        # accessory defines none.
        image_name = getattr(acc, "op_btn_image_path", None) or OP_SCREEN_IMAGE
        self._paint_ac_op_icon(image_name)
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
        """Sends the Sequence the radio group is now showing.

        The widget-reading half of the pair below: the on-screen group fires this when one of
        its options is clicked, and it does no more than pick the value up and hand it on.
        """
        host = self._host
        tmcc_id = host._scope_tmcc_ids[host.scope]
        # The cursor follows the tap. Touch selects outright, so leaving the cursor where the
        # pad had put it would show a row tinted as "where I am" beside a dot somewhere else
        # meaning "and this is set" -- the two disagreeing about a choice already made.
        self.set_sensor_track_cursor(self.sensor_track_sequence)
        self.send_sensor_track_sequence(tmcc_id, host.sensor_track_buttons.value)

    def send_sensor_track_sequence(self, tmcc_id: int, sequence: int | str) -> None:
        """Writes ``sequence`` to the Sensor Track at ``tmcc_id``.

        Widget-free on purpose, as ``asc2_control`` is: the on-screen group reaches it through
        the change handler above, and the gamepad reaches it through
        ``EngineGui.on_sensor_track_select``, so both send exactly the same request. Taking the
        id and the value as arguments rather than reading them is what lets a revert send the
        pair it is putting back rather than whatever the group happens to show.

        The two callers hand over different types and the normalising is done here rather than
        asked of them: the change handler passes what the group holds, which is a ``str``
        because guizero keeps the selection in a Tk ``StringVar``, while the pad passes the
        ``int`` the stepping returned.
        """
        st_seq = IrdaSequence.by_value(int(sequence))
        IrdaReq(tmcc_id, PdiCommand.IRDA_SET, IrdaAction.SEQUENCE, sequence=st_seq).send(repeat=self._host.repeat)

    @staticmethod
    def sensor_track_values() -> list[int]:
        """The Sequence option values, in the order the group shows them."""
        return [int(opt[1]) for opt in SENSOR_TRACK_OPTS]

    @property
    def sensor_track_sequence(self) -> int | None:
        """The Sequence option the radio dot is on, or None where nothing is selected.

        What the track is *programmed with* -- what an ``IrdaState`` last reported, or what the
        last select wrote -- as against ``sensor_track_cursor``, which is where the pad is
        pointing.

        What "none" looks like has to be read off the widget rather than assumed: the group
        keeps its selection in a Tk ``StringVar``, so it answers with a ``str`` whatever was
        assigned, and the ``value = None`` ``on_new_accessory`` clears it with comes back as
        the string ``"None"``. Anything that does not parse to an option in the list -- that,
        an empty group, a value from outside the list -- is read as nothing selected.

        The one place that normalising is done: two readings of a Tk string is two chances to
        disagree about which option is showing.
        """
        host = self._host
        if self.accessory_panel_kind != PANEL_SENSOR_TRACK:
            return None
        buttons = host.sensor_track_buttons
        if buttons is None:
            return None
        try:
            value = int(buttons.value)
        except (TypeError, ValueError):
            return None
        return value if value in self.sensor_track_values() else None

    def set_sensor_track_sequence(self, sequence: int) -> bool:
        """Moves the radio dot to ``sequence`` and sends nothing. True where it moved.

        The dot is what the track is programmed with, so this is only called where that has
        actually changed -- a select, or a revert putting one back. The cursor is moved with it,
        because after either of those the pad is pointing at exactly what the track now holds
        and a bar left behind elsewhere would claim something is still pending.

        Assigns ``value`` rather than clicking an option, which is what moves the dot without
        sending: the group's command fires on a click, so an assignment is silent -- the same
        assignment ``on_new_accessory`` makes from incoming state. That path assigns the widget
        directly and so does *not* move the cursor, which is the point: a track reporting itself
        must not cancel a step in progress.

        Re-checks that the Sensor Track panel is the one displayed, as ``asc2_control``
        re-checks its own port: the pad's press and the panel it was aimed at are two separate
        moments, and a highlight moved on a panel that is no longer showing one would be a
        change nobody could see.
        """
        host = self._host
        if self.accessory_panel_kind != PANEL_SENSOR_TRACK:
            return False
        buttons = host.sensor_track_buttons
        if buttons is None:
            return False
        try:
            value = int(sequence)
        except (TypeError, ValueError):
            return False
        if value not in self.sensor_track_values():
            return False
        buttons.value = value
        self.set_sensor_track_cursor(value)
        return True

    @property
    def sensor_track_cursor(self) -> int | None:
        """The Sequence option the *cursor* is on, falling back to the programmed one.

        Where the pad is pointing, as against ``sensor_track_sequence``, which is what the
        track is set to. The fallback is what makes a fresh panel behave: with no cursor placed
        yet the pad starts from the option the dot is on, so the first step moves one option
        from there rather than from the top of the list.

        This is the reader a select writes from -- the option stepped to, not the option the
        dot still shows.
        """
        buttons = self._host.sensor_track_buttons
        if self.accessory_panel_kind != PANEL_SENSOR_TRACK or buttons is None:
            return None
        try:
            value = int(getattr(buttons, "cursor", None))
        except (TypeError, ValueError):
            value = None
        if value is not None and value in self.sensor_track_values():
            return value
        return self.sensor_track_sequence

    def set_sensor_track_cursor(self, sequence: int | None) -> bool:
        """Moves the cursor to ``sequence``, or clears it with None. Sends nothing, ever.

        The counterpart of ``set_sensor_track_sequence`` and deliberately its equal: one setter
        for what the track holds, one for where the pad is, and neither able to move the other
        by accident. This one never writes and never moves the dot, which is the whole of A-8.
        """
        host = self._host
        if self.accessory_panel_kind != PANEL_SENSOR_TRACK:
            return False
        buttons = host.sensor_track_buttons
        if buttons is None:
            return False
        if sequence is None:
            buttons.cursor = None
            return True
        try:
            value = int(sequence)
        except (TypeError, ValueError):
            return False
        if value not in self.sensor_track_values():
            return False
        buttons.cursor = value
        return True

    def step_sensor_track_sequence(self, delta: int) -> int | None:
        """Moves the Sequence highlight ``delta`` options and returns the value moved to.

        Clamped rather than wrapping: a step off either end of ``SENSOR_TRACK_OPTS`` moves
        nothing and returns None, so the operator can hold the pad against an end without the
        selection rolling round to the far one.

        An unset group -- no ``IrdaState`` for this Sensor Track yet, so nothing is
        highlighted -- is a state before the list rather than a position in it: the first
        press either way lands on "No Action" and only the second moves off it. Reading it as
        "already on index 0" instead would make that first press either do nothing at all or
        skip "No Action" altogether, depending on which way it went.

        Nothing is written here at all, and the radio dot does not move either: the *cursor*
        moves and stops there. That is A-8 -- an option stepped over must not read as an option
        chosen -- and the write is asked for outright by the select the pad has of its own.
        """
        values = self.sensor_track_values()
        current = self.sensor_track_cursor
        if current is None:
            target = 0
        else:
            target = values.index(current) + int(delta)
            if not 0 <= target < len(values):
                return None
        value = values[target]
        return value if self.set_sensor_track_cursor(value) else None

    # noinspection PyProtectedMember
    def asc2_control(self, pressed: bool) -> None:
        """Sends the `Asc2` momentary control command for the pane's accessory.

        Widget-free on purpose: the on-screen key reaches it through the event handlers
        below, and the gamepad reaches it through ``EngineGui.on_asc2_momentary``, so both
        send exactly the same request.
        """
        host = self._host
        scope = host.scope
        tmcc_id = host._scope_tmcc_ids[scope]
        state = host.state_store.get_state(scope, tmcc_id, False)
        if isinstance(state, AccessoryState) and state.is_asc2:
            values = 1 if pressed else 0
            Asc2Req(state.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=values).send()

    def when_pressed(self, event: EventData) -> None:
        """Sends `Asc2` control command when button pressed"""
        pb = event.widget
        if pb.enabled:
            self.asc2_control(True)

    def when_released(self, event: EventData) -> None:
        """Sends `Asc2` release command when button released"""
        pb = event.widget
        if pb.enabled:
            self.asc2_control(False)
