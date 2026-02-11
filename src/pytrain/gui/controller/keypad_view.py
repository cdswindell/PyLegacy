#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import logging
from typing import TYPE_CHECKING

from guizero import App, Box, ButtonGroup, TitleBox

from .engine_gui_conf import (
    AC_OFF_KEY,
    AC_ON_KEY,
    AUX1_KEY,
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
from ...utils.path_utils import find_file

log = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui


class KeypadView:
    def __init__(self, host: "EngineGui") -> None:
        self._host = host

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
                    command=host.on_keypress,
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
            command=host.on_keypress,
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
        host.sensor_track_box = cell = TitleBox(app, "Sequence", layout="auto", align="top", visible=False)
        cell.text_size = host.s_10
        host.ops_cells.add(cell)
        host.sensor_track_buttons = bg = ButtonGroup(
            cell,
            align="top",
            options=SENSOR_TRACK_OPTS,
            width=host.emergency_box_width,
            command=host.on_sensor_track_change,
        )
        bg.text_size = host.s_20

        # Make radio buttons larger and add spacing
        indicator_size = int(22 * host.scale_by)
        for widget in bg.tk.winfo_children():
            widget.config(
                font=("TkDefaultFont", host.s_20),
                padx=18,  # Horizontal padding inside each radio button
                pady=6,  # Vertical padding inside each radio button
                anchor="w",
            )
            # Increase the size of the radio button indicator
            widget.tk.eval(f"""
                image create photo radio_unsel_{id(widget)} -width {indicator_size} -height {indicator_size}
                image create photo radio_sel_{id(widget)} -width {indicator_size} -height {indicator_size}
                radio_unsel_{id(widget)} put white -to 0 0 {indicator_size} {indicator_size}
                radio_sel_{id(widget)} put green -to 0 0 {indicator_size} {indicator_size}
            """)
            widget.config(
                image=f"radio_unsel_{id(widget)}",
                selectimage=f"radio_sel_{id(widget)}",
                compound="left",
                indicatoron=False,
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
        host.ac_aux1_btn.when_left_button_pressed = host.when_pressed
        host.ac_aux1_btn.when_left_button_released = host.when_released

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
