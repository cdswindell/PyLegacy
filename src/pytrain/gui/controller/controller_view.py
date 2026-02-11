#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
# controller_view.py

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import TclError
from typing import Callable, TYPE_CHECKING

from guizero import Box, Slider, Text, TitleBox
from guizero.base import Widget

from .engine_gui_conf import BELL_KEY, ENGINE_OPS_LAYOUT, MOMENTUM, MOM_TB, TRAIN_BRAKE
from ..components.hold_button import HoldButton
from ..guizero_base import LIONEL_BLUE, LIONEL_ORANGE
from ...db.engine_state import EngineState, TrainState
from ...utils.path_utils import find_file

log = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui


class ControllerView:
    def __init__(self, host: "EngineGui") -> None:
        self._host = host
        self._focus_widget = None
        self._acela_btns = set()
        self._crane_btns = set()
        self._diesel_btns = set()
        self._electric_btns = set()
        self._engine_btns = set()
        self._freight_btns = set()
        self._passenger_btns = set()
        self._passenger_freight_btns = set()
        self._steam_btns = set()
        self._transformer_btns = set()
        self._vol_btns = set()
        self._smoke_btns = set()
        self._cplr_btns = set()
        self._bos_brk_btns = set()
        self._common_btns = set()
        self._all_engine_btns = set()
        self._engine_type_key_map: dict[str, set[Widget]] = {}
        self._quill_after_id = None

    # -----------------------------
    # Public API used by EngineGui
    # -----------------------------

    # noinspection PyProtectedMember
    def build(self, app) -> None:
        """Create controller widgets if not already built."""
        host = self._host
        if host.controller_box is not None:
            return

        # MOVE: EngineGui.make_controller code here, replacing self -> host
        # Keep assignments to host.* so the rest of EngineGui keeps working.
        # Example:
        host.controller_box = controller_box = Box(app, border=2, align="top", visible=False)
        host.ops_cells.add(controller_box)

        # different engine types have different features
        # define the common keys first
        host.controller_keypad_box = keypad_keys = Box(
            controller_box,
            layout="grid",
            border=0,
            align="left",
        )
        row = 0
        for r, kr in enumerate(ENGINE_OPS_LAYOUT):
            for c, button_info in enumerate(kr):
                if button_info is None:
                    continue
                if isinstance(button_info, tuple):
                    ops = [button_info]
                elif isinstance(button_info, list):
                    ops = button_info
                else:
                    raise AttributeError(f"Invalid engine op: {button_info}")
                for op in ops:
                    image = label = title_text = None
                    if len(op) > 1 and op[1]:
                        image = find_file(op[1])
                    if len(op) > 2 and op[2]:
                        label = str(op[2])
                    if len(op) > 3 and op[3]:
                        title_text = str(op[3])
                    cmd = op[0]

                    # make the key button and it's surrounding cell
                    cell, nb = host.make_keypad_button(
                        keypad_keys,
                        label,
                        row,
                        c,
                        visible=True,
                        bolded=True,
                        command=host.on_engine_command,
                        args=[cmd],
                        image=image,
                        titlebox_text=title_text,
                    )

                    # if the key is marked as engine type-specific, save as appropriate
                    if len(op) > 4 and op[4]:
                        if op[4] == "e":
                            self._engine_btns.add(cell)
                        elif op[4] == "c":
                            self._common_btns.add(cell)
                        elif op[4] == "a":
                            self._acela_btns.add(cell)
                        elif op[4] == "d":
                            self._diesel_btns.add(cell)
                        elif op[4] == "f":
                            self._freight_btns.add(cell)
                        elif op[4] == "l":
                            self._electric_btns.add(cell)
                        elif op[4] == "p":
                            self._passenger_btns.add(cell)
                        elif op[4] == "pf":
                            self._passenger_freight_btns.add(cell)
                        elif op[4] == "s":
                            self._steam_btns.add(cell)
                        elif op[4] == "t":
                            self._transformer_btns.add(cell)

                        elif op[4] == "vo":
                            self._vol_btns.add(cell)
                        elif op[4] == "sm":
                            self._smoke_btns.add(cell)
                        elif op[4] == "cp":
                            self._cplr_btns.add(cell)
                        elif op[4] == "bs":
                            self._bos_brk_btns.add(cell)
                        key = (cmd, op[4])
                    else:
                        key = cmd

                    if key in host.engine_ops_cells:
                        log.warning("Duplicate engine op: %r: %r", key, op)
                    host.engine_ops_cells[key] = (key, nb)
            row += 1

        # Postprocess some buttons
        self._setup_controller_behaviors()

        # assemble key maps
        self._all_engine_btns = (
            self._engine_btns
            | self._common_btns
            | self._acela_btns
            | self._crane_btns
            | self._diesel_btns
            | self._electric_btns
            | self._freight_btns
            | self._passenger_btns
            | self._passenger_freight_btns
            | self._steam_btns
            | self._transformer_btns
            | self._bos_brk_btns
            | self._cplr_btns
            | self._smoke_btns
            | self._vol_btns
        )
        self._common_btns |= self._vol_btns | self._cplr_btns
        self._engine_type_key_map = {
            "a": self._vol_btns | self._engine_btns | self._bos_brk_btns | self._diesel_btns | self._acela_btns,
            "d": self._common_btns | self._engine_btns | self._bos_brk_btns | self._smoke_btns | self._diesel_btns,
            "f": self._common_btns | self._passenger_freight_btns | self._freight_btns,
            "l": self._common_btns | self._engine_btns | self._electric_btns,
            "p": self._common_btns | self._passenger_freight_btns | self._passenger_btns,
            "s": self._common_btns | self._engine_btns | self._bos_brk_btns | self._smoke_btns | self._steam_btns,
            "t": self._transformer_btns,
        }

        # used to make sure brake and throttle get focus when needed
        host.controller_box.show()

        sliders = Box(
            controller_box,
            border=1,
            align="right",
            layout="grid",
        )
        sliders.tk.pack(fill="y", expand=True)

        # throttle
        host.throttle_box = throttle_box = Box(
            sliders,
            border=1,
            grid=[1, 0],
        )

        cell = TitleBox(throttle_box, "Speed", align="top", border=1)
        cell.text_size = host.s_10
        host.speed = speed = Text(
            cell,
            text="000",
            color="black",
            align="top",
            bold=True,
            size=host.s_18,
            width=4,
            font="DigitalDream",
        )
        speed.bg = "black"
        speed.text_color = "white"

        host.throttle = throttle = Slider(
            throttle_box,
            align="top",
            horizontal=False,
            step=1,
            width=int(host.button_size / 2),
            height=host.slider_height,
            command=self.on_throttle,
        )
        throttle.after_id = None  # used to debounce slider updates
        throttle.text_color = "black"
        throttle.tk.config(
            from_=195,
            to=0,
            takefocus=0,
            troughcolor=LIONEL_BLUE,  # deep Lionel blue for the track,
            activebackground=LIONEL_ORANGE,  # bright Lionel orange for the handle
            bg="lightgrey",  # darker navy background
            highlightthickness=1,
            highlightbackground=LIONEL_ORANGE,  # subtle orange outline
            width=int(host.button_size / 2),
            sliderlength=int(host.slider_height / 6),
        )
        throttle.tk.bind("<Button-1>", lambda e: throttle.tk.focus_set())
        throttle.tk.bind("<ButtonRelease-1>", self._on_throttle_release_event, add="+")
        throttle.tk.bind("<ButtonRelease>", self._on_throttle_release_event, add="+")

        # brake
        host.brake_box, _, host.brake_level, host.brake = self._make_slider(
            sliders, "Brake", self.on_train_brake, frm=0, to=7
        )

        # Allow Tk to compute geometry
        host.app.tk.update_idletasks()

        # Momentum
        host.momentum_box, _, host.momentum_level, host.momentum = self._make_slider(
            sliders, "Moment", self.on_momentum, frm=0, to=7, visible=False
        )

        # Horn
        host.horn_box, host.horn_title_box, host.horn_level, host.horn = self._make_slider(
            sliders, "Horn", self.on_horn, frm=0, to=15, visible=False
        )

        # compute rr speed button size
        w = sliders.tk.winfo_width()
        h = (5 * host.button_size) - (host.brake.tk.winfo_height() + host.brake_level.tk.winfo_height()) - 5

        # RR Speeds button
        host._rr_speed_box = rr_box = Box(
            sliders,
            grid=[0, 1, 2, 1],  # spans two columns under sliders
            align="top",
        )

        # RR Speeds button
        host._rr_speed_btn = rr_btn = HoldButton(rr_box, "", command=host.on_rr_speed)
        rr_btn.tk.pack(fill="both", expand=True)

        img, inverted_img = host.get_image(find_file("RR-Speeds.jpg"), size=(w, h))
        rr_btn.tk.config(
            image=img,
            compound="center",
            width=w,
            height=h,
            padx=3,  # small padding
            pady=3,
            borderwidth=2,  # light border
            relief="ridge",  # gives pressable button feel
            highlightthickness=0,
        )
        rr_btn.images = (img, inverted_img)

        # Bell/horn buttons for freight sounds
        host._freight_sounds_bell_horn_box = pair_cell = Box(
            sliders,
            grid=[0, 1, 2, 1],
            border=0,
            align="top",
        )
        # Inner container to hold the two buttons side-by-side
        btn_row = Box(pair_cell, align="top", layout="grid")  # uses pack internally
        btn_row.tk.pack(expand=True)  # Center the *pair* within the TitleBox

        bell_box = TitleBox(
            btn_row,
            "Bell/Horn...",
            grid=[2, 0],
            align="bottom",
        )
        host._bell_btn = bell_btn = HoldButton(
            bell_box,
            BELL_KEY,
            align="bottom",
            text_size=host.s_24,
            text_bold=True,
            command=host.on_engine_command,
            args=[["BELL_ONE_SHOT_DING", "RING_BELL"]],
        )
        bell_btn.tk.pack(fill="both", expand=True)
        bell_btn.on_hold = host.on_bell_horn_options_fs

        # Allow Tk to compute geometry
        host.app.tk.update_idletasks()
        horn_size = int(bell_box.tk.winfo_height() * 0.85)

        # spacer box
        sp_size = int(horn_size * 0.1)
        sp = Box(btn_row, grid=[1, 0], height=sp_size, width=sp_size)
        host.cache(sp)

        # Horn button
        horn_cell = Box(btn_row, grid=[0, 0], border=0, align="bottom")
        horn_pad = Box(horn_cell)
        horn_pad.tk.pack(padx=(1, 1), pady=(1, 0))
        host._horn_btn = horn_btn = HoldButton(
            horn_pad,
            "",
            align="bottom",
            command=host.on_engine_command,
            args=["BLOW_HORN_ONE"],
        )
        image = find_file("horn.jpg")
        horn_btn.image = image
        horn_btn.images = host.get_image(image, size=horn_size)
        horn_btn.tk.config(
            borderwidth=2,
            compound="center",
            width=horn_size,
            height=horn_size,
        )
        host._freight_sounds_bell_horn_box.hide()

        # --- HIDE IT AGAIN after sizing is complete ---
        host.controller_box.hide()

        # ... create controller_keypad_box, sliders, throttle, brake, etc ...
        # At the end:
        self._focus_widget = focus_widget = tk.Frame(host.app.tk, takefocus=1)
        focus_widget.place(x=-9999, y=-9999, width=1, height=1)

        # keep host.focus_widget used elsewhere, if you want
        host.focus_widget = self._focus_widget

    def _setup_controller_behaviors(self):
        """Configures specific button behaviors like repeats, holds, and special toggles."""
        host = self._host

        # Helper to get the HoldButton widget from the dictionary
        def get_btn(k):
            return host.engine_ops_cells[k][1]

        # 1. Toggle Momentum/Train Brake
        mom_tb_btn = get_btn((MOM_TB, "e"))
        mom_tb_btn.text_size = host.s_12
        mom_tb_btn.update_command(self.toggle_momentum_train_brake, [mom_tb_btn])

        # 2. Setup Repeating Commands
        # Logic: Assign current on_press to on_repeat and set the interval
        repeats = [
            (("AUX1_OPTION_ONE", "e"), 0.2),  # Standard repeat
            (("BOOST_SPEED", "bs"), 0.3),
            (("BOOST_SPEED", "t"), 0.3),
            (("BOOST_SPEED", "l"), 0.3),
            (("BRAKE_SPEED", "bs"), 0.3),
            (("BRAKE_SPEED", "t"), 0.3),
            (("BRAKE_SPEED", "l"), 0.3),
            (("WATER_INJECTOR", "s"), 0.2),
            (("LET_OFF_LONG", "s"), 0.2),
        ]
        for key, interval in repeats:
            btn = get_btn(key)
            btn.on_repeat = btn.on_press
            btn.repeat_interval = interval

        # 3. Setup Hold behaviors (Popups)
        holds = [
            (("AUX2_OPTION_ONE", "e"), host.on_lights),
            (("TOWER_CHATTER", "e"), host.on_tower_dialog),
            (("ENGINEER_CHATTER", "e"), host.on_crew_dialog),
            (("ENGINEER_CHATTER", "p"), host.on_conductor_actions),
            (("TOWER_CHATTER", "p"), host.on_station_dialogs),
            (("STEWARD_CHATTER", "p"), host.on_steward_dialogs),
            (("RING_BELL", "e"), host.on_bell_horn_options),
        ]
        for key, callback in holds:
            get_btn(key).on_hold = callback

        # 4. Loco-specific Horn/Whistle control holds
        for loco in ["d", "s", "l"]:
            get_btn(("BLOW_HORN_ONE", loco)).on_hold = self.show_horn_control

    # noinspection PyProtectedMember
    def apply_engine_type(self, state: EngineState | TrainState | None) -> None:
        """
        Show/hide controller op keys + aux widgets based on motive type.
        Called from EngineGui.ops_mode() after state is resolved.
        """
        host = self._host

        # default hide/show aux widgets
        if host._freight_sounds_bell_horn_box:
            host._freight_sounds_bell_horn_box.hide()
        if host._rr_speed_box:
            host._rr_speed_box.hide()

        if not isinstance(state, (EngineState, TrainState)):
            # If unknown, show diesel-ish defaults
            self._show_keys_for_type("d")
            if host._rr_speed_box:
                host._rr_speed_box.show()
            if host.horn_title_box:
                host.horn_title_box.text = "Horn"
            return

        # Determine engine type key (must match your engine_gui_conf tags)
        if getattr(state, "is_diesel", False):
            t = "d"
        elif getattr(state, "is_steam", False):
            t = "s"
        elif getattr(state, "is_passenger", False):
            t = "p"
        elif getattr(state, "is_freight", False):
            t = "f"
        elif getattr(state, "is_acela", False):
            t = "a"
        elif getattr(state, "is_electric", False):
            t = "l"
        elif getattr(state, "is_transformer", False):
            t = "t"
        else:
            t = "d"

        self._show_keys_for_type(t)

        # Per-type aux behavior
        if t in {"d", "s", "a", "l", "p", "t"}:
            if host._rr_speed_box:
                host._rr_speed_box.show()

        if host.horn_title_box:
            if t == "s":
                host.horn_title_box.text = "Whistle"
            else:
                host.horn_title_box.text = "Horn"

        if t == "f":
            if host._freight_sounds_bell_horn_box:
                host._freight_sounds_bell_horn_box.show()
            # Freight uses the horn-control popup behavior
            self.show_horn_control()

        if t == "t":
            # Transformer mode wants brake shown
            self.toggle_momentum_train_brake(show_btn="brake")

    def _show_keys_for_type(self, t: str) -> None:
        """Internal: show keys for a controller type key."""
        host = self._host

        # Avoid rework if type unchanged
        if getattr(host, "_last_engine_type", None) == t:
            return

        btns = self._engine_type_key_map.get(t, set())
        for cell in btns:
            cell.show()

        for cell in self._all_engine_btns - btns:
            cell.hide()

        host._last_engine_type = t

    def show(self) -> None:
        host = self._host
        if host.controller_box and not host.controller_box.visible:
            host.controller_box.show()

    def hide(self) -> None:
        host = self._host
        if host.controller_box and host.controller_box.visible:
            host.controller_box.hide()

    def update_from_state(self, state: EngineState | TrainState | None) -> None:
        """Update throttle/brake/momentum UI based on the active state."""
        # Optionally move the relevant chunk of EngineGui.on_new_engine here.
        # Keep behavior identical; call into host for engine command sending if needed.
        pass

    # -----------------------------
    # Event handlers (moved over)
    # -----------------------------

    # noinspection PyUnusedLocal
    def clear_focus(self, e=None) -> None:
        host = self._host
        # Clears focus from host widgets after idle time
        focus = host.app.tk.focus_get()
        widgets = {getattr(host, n, None) for n in ("throttle", "brake", "momentum", "horn")}
        tks = {w.tk for w in widgets if w is not None}
        if focus in tks:
            if focus == host.horn.tk:
                self._stop_quill()
            host.app.tk.after_idle(self._do_clear_focus)

    def _do_clear_focus(self) -> None:
        host = self._host
        if self._focus_widget is not None:
            self._focus_widget.focus_set()
        for w in (host.throttle, host.brake, host.momentum, host.horn):
            try:
                if w is not None:
                    w.tk.event_generate("<Leave>")
            except (TclError, AttributeError):
                pass

    def _stop_quill(self) -> None:
        host = self._host
        if self._quill_after_id is not None:
            try:
                host.app.tk.after_cancel(self._quill_after_id)
            except (TclError, AttributeError):
                pass
            self._quill_after_id = None
        host.horn.value = 0

    def on_throttle(self, value) -> None:
        host = self._host
        if host.throttle.after_id is not None:
            host.throttle.tk.after_cancel(host.throttle.after_id)
        host.throttle.after_id = host.throttle.tk.after(200, self.on_throttle_released, int(value))

    # noinspection PyUnusedLocal
    def on_throttle_released(self, value: int) -> None:
        host = self._host
        host.throttle.after_id = None
        # actual speed command is sent from _on_throttle_release_event

    def _on_throttle_release_event(self, e=None) -> None:
        host = self._host
        # If a debounced callback is pending, cancel it and send immediately.
        after_id = getattr(host.throttle, "after_id", None)
        if after_id is not None:
            try:
                host.throttle.tk.after_cancel(after_id)
            except (TclError, AttributeError):
                pass
            finally:
                host.throttle.after_id = None
        # send speed command
        host.on_speed_command(host.throttle.value)

        # Now clear focus so the handle deactivates visually.
        self.clear_focus(e)

    def on_train_brake(self, value) -> None:
        host = self._host
        if host.app.tk.focus_get() == host.brake.tk:
            value = int(value)
            host.brake_level.value = f"{value:02d}"
            host.on_engine_command("TRAIN_BRAKE", data=value)

    def on_horn(self, value: int = None) -> None:
        host = self._host
        value = int(value) if value else host.horn.value
        host.horn_level.value = f"{value:02d}"
        if self._quill_after_id is not None:
            try:
                host.app.tk.after_cancel(self._quill_after_id)
            except (TclError, AttributeError):
                pass
            self._quill_after_id = None
        if value > 0:
            self.do_quilling_horn(value)

    def do_quilling_horn(self, value: int) -> None:
        host = self._host
        host.on_engine_command(["QUILLING_HORN", "BLOW_HORN_ONE"], data=value)
        if host.app.tk.focus_get() == host.horn.tk:
            self._quill_after_id = host.app.tk.after(500, self.do_quilling_horn, value)
        else:
            self._stop_quill()

    def on_momentum(self, value) -> None:
        host = self._host
        if host.app.tk.focus_get() == host.momentum.tk:
            # we need state info for this
            if host.active_engine_state:
                state = host.active_engine_state
            else:
                state = host.active_state
            if isinstance(state, EngineState):
                value = int(value)
                if state.is_legacy:
                    host.on_engine_command("MOMENTUM", data=value)
                else:
                    if value in {0, 1}:
                        value = 0
                        host.on_engine_command("MOMENTUM_LOW", data=value)
                    elif value in {2, 3, 4}:
                        value = 3
                        host.on_engine_command("MOMENTUM_MEDIUM")
                    else:
                        value = 7
                        host.on_engine_command("MOMENTUM_HIGH")
                host.momentum_level.value = f"{value:02d}"

    def show_horn_control(self) -> None:
        host = self._host
        for loco_type in ["d", "s", "l"]:
            _, btn = host.engine_ops_cells[("BLOW_HORN_ONE", loco_type)]
            btn.on_hold = self.toggle_momentum_train_brake  # or keep it in view and bind accordingly
        host.momentum_box.hide()
        host.brake_box.hide()
        host.horn_box.show()

    def toggle_momentum_train_brake(self, btn=None, show_btn: str | None = None) -> None:
        host = self._host
        if host.horn_box.visible:
            # hide the horn box
            host.horn_box.hide()
        if show_btn:
            _, btn = host.engine_ops_cells[(MOM_TB, "e")]
            if show_btn == "brake":
                btn.text = MOMENTUM
                host.momentum_box.hide()
                host.brake_box.show()
            else:
                btn.text = TRAIN_BRAKE
                host.brake_box.hide()
                host.momentum_box.show()
        elif btn is None:  # called from horn handler
            # restore what was there before; if the swaped button says "Momentum"
            # then show Train Brake, and vice versa
            _, btn = host.engine_ops_cells[(MOM_TB, "e")]
            if btn.text == MOMENTUM:
                host.momentum_box.hide()
                host.brake_box.show()
            else:
                host.brake_box.hide()
                host.momentum_box.show()
        else:
            if btn.text == MOMENTUM:
                btn.text = TRAIN_BRAKE
                host.brake_box.hide()
                host.momentum_box.show()
            else:
                btn.text = MOMENTUM
                host.momentum_box.hide()
                host.brake_box.show()

        # restore the on_hold handler
        for loco_type in ["d", "s", "l"]:
            _, btn = host.engine_ops_cells[("BLOW_HORN_ONE", loco_type)]
            btn.on_hold = self.show_horn_control

    def _make_slider(
        self,
        sliders: Box,
        title: str,
        command: Callable,
        frm: int,
        to: int,
        step: int = 1,
        visible: bool = True,
    ) -> tuple[Box, TitleBox, Text, Slider]:
        host = self._host

        momentum_box = Box(
            sliders,
            border=1,
            grid=[0, 0],
            visible=visible,
        )

        cell = TitleBox(momentum_box, title, align="top", border=1)
        cell.text_size = host.s_10
        momentum_level = Text(
            cell,
            text="00",
            color="black",
            align="top",
            bold=True,
            size=host.s_18,
            width=3,
            font="DigitalDream",
        )
        momentum_level.bg = "black"
        momentum_level.text_color = "white"

        momentum = Slider(
            momentum_box,
            align="top",
            horizontal=False,
            step=step,
            width=int(host.button_size / 3),
            height=host.slider_height,
            command=command,
        )
        momentum.text_color = "black"
        momentum.tk.config(
            from_=frm,
            to=to,
            takefocus=0,
            troughcolor=LIONEL_BLUE,  # deep Lionel blue for the track,
            activebackground=LIONEL_ORANGE,  # bright Lionel orange for the handle
            bg="lightgrey",  # darker navy background
            highlightthickness=1,
            highlightbackground=LIONEL_ORANGE,  # subtle orange outline
            width=int(host.button_size / 3),
            sliderlength=int(host.slider_height / 6),
        )
        momentum.tk.bind("<Button-1>", lambda e: momentum.tk.focus_set())
        momentum.tk.bind("<ButtonRelease-1>", self.clear_focus, add="+")
        momentum.tk.bind("<ButtonRelease>", self.clear_focus, add="+")

        return momentum_box, cell, momentum_level, momentum
