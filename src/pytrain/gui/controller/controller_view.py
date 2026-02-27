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
from contextlib import contextmanager
from tkinter import TclError
from typing import Any, Callable, Iterator, Optional, TYPE_CHECKING

from guizero import Box, Slider, Text, TitleBox
from guizero.base import Widget

from .engine_gui_conf import BELL_KEY, ENGINE_OPS_LAYOUT, MOMENTUM, MOM_TB, TRAIN_BRAKE
from ..components.hold_button import HoldButton
from ..guizero_base import LIONEL_BLUE, LIONEL_ORANGE
from ...db.engine_state import EngineState
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
        self._updating_from_state = False

    @contextmanager
    def __updating(self) -> Iterator[None]:
        self._updating_from_state = True
        try:
            yield
        finally:
            self._updating_from_state = False

    # -----------------------------
    # Public API used by EngineGui
    # -----------------------------

    # noinspection PyProtectedMember
    def update_from_state(self, state: EngineState | None, throttle_state: EngineState | None):
        """
        Paint throttle/brake/momentum + direction buttons from the given state.

        `state` is the active engine state (for brake/momentum/direction).
        `throttle_state` is whichever state is allowed to control throttle (engine vs. train vs. None).
        """
        if not isinstance(state, EngineState):
            return

        host = self._host
        with self.__updating():
            # --- Throttle / Speed ---
            if throttle_state:
                if not host.speed.enabled:
                    host.speed.enable()
                if not host.throttle.enabled:
                    host.throttle.enable()
                if host._rr_speed_btn and not host._rr_speed_btn.enabled:
                    host._rr_speed_btn.enable()

                host.speed.value = f"{throttle_state.speed:03d}"

                if host._rr_speed_panel:
                    host._rr_speed_panel.configure(throttle_state)

                # don't fight the user while dragging
                if host.throttle.tk.focus_displayof() != host.throttle.tk:
                    host.throttle.value = throttle_state.target_speed

                # trough color indicates actual vs. target
                if throttle_state.speed != throttle_state.target_speed:
                    host.throttle.tk.config(troughcolor="#4C96C5")
                else:
                    host.throttle.tk.config(troughcolor=LIONEL_BLUE)

                # legacy vs. tmcc throttle range
                if throttle_state.is_legacy:
                    host.throttle.tk.config(from_=195, to=0)
                else:
                    host.throttle.tk.config(from_=31, to=0)
            else:
                if host.speed.enabled:
                    host.speed.disable()
                if host.throttle.enabled:
                    host.throttle.disable()
                if host._rr_speed_btn and host._rr_speed_btn.enabled:
                    host._rr_speed_btn.disable()

            # --- Brake ---
            brake = state.train_brake if state.train_brake is not None else 0
            host.brake_level.value = f"{brake:02d}"
            if host.brake.tk.focus_displayof() != host.brake.tk:
                host.brake.value = brake

            # --- Momentum ---
            momentum = state.momentum if state.momentum is not None else 0
            host.momentum_level.value = f"{momentum:02d}"
            if host.momentum.tk.focus_displayof() != host.momentum.tk:
                host.momentum.value = momentum

            if state.is_legacy:
                host.momentum.tk.config(resolution=1, showvalue=True)
            else:
                host.momentum.tk.config(resolution=4, showvalue=False)

            # --- Direction buttons ---
            if host.engine_ops_cells:
                _, fwd_btn = host.engine_ops_cells[("FORWARD_DIRECTION", "e")]
                fwd_btn.bg = host._active_bg if state.is_forward else host._inactive_bg

                _, rev_btn = host.engine_ops_cells[("REVERSE_DIRECTION", "e")]
                rev_btn.bg = host._active_bg if state.is_reverse else host._inactive_bg

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
        self.populate_keypad(ENGINE_OPS_LAYOUT, keypad_keys)

        # Postprocess some buttons
        self._setup_controller_behaviors()

        # generate key maps
        self.regen_engine_keys_map()

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
        host.throttle_box, host.throttle_title_box, host.speed, host.throttle = self._make_slider(
            sliders,
            title="Speed",
            command=self.on_throttle,  # debounced send handled by on_throttle/_on_throttle_release_event
            frm=195,
            to=0,
            step=1,
            visible=True,
            grid=(1, 0),
            box_border=1,
            title_border=1,
            level_text="000",
            level_width=4,
            level_font="DigitalDream",
            level_size=host.s_18,
            title_text_size=host.s_10,
            slider_width=int(host.button_size / 2),
            slider_height=host.slider_height,
            # We want OUR release handler (which clears focus) instead of default clear_focus binding:
            on_release=self._on_throttle_release_event,
            clear_focus_on_release=False,
        )

        # throttle extras (debounce bookkeeping + any per-slider styling)
        host.throttle.after_id = None  # used to debounce slider updates
        host.throttle.text_color = "black"

        # If you still want takefocus=0 explicitly or any other special Scale options:
        host.throttle.tk.config(takefocus=0)

        # (Optional) If you *still* want an explicit focus_set on press, the helper already binds it,
        # but it doesn't hurt to leave it out. No need to add:
        # host.throttle.tk.bind("<Button-1>", lambda e: host.throttle.tk.focus_set())

        # brake
        host.brake_box, _, host.brake_level, host.brake = self._make_slider(
            sliders,
            "Brake",
            self.on_train_brake,
            frm=0,
            to=7,
        )

        # Allow Tk to compute geometry
        host.app.tk.update_idletasks()

        # Momentum
        host.momentum_box, _, host.momentum_level, host.momentum = self._make_slider(
            sliders,
            "Moment",
            self.on_momentum,  # debounces internally
            frm=0,
            to=7,
            visible=False,
            on_release=self._on_momentum_release_event,  # immediate send + clear focus
        )

        # Horn
        host.horn_box, host.horn_title_box, host.horn_level, host.horn = self._make_slider(
            sliders,
            "Horn",
            self.on_horn,  # quilling loop logic
            frm=0,
            to=15,
            visible=False,
            on_release=self.clear_focus,  # or a horn-specific release handler
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

    def populate_keypad(self, keys: list, keypad_box: Box):
        host = self._host
        row = 0
        for r, kr in enumerate(keys):
            for c, button_info in enumerate(kr):
                if button_info is None:
                    continue
                if isinstance(button_info, tuple):
                    ops = [button_info]
                elif isinstance(button_info, list):
                    ops = button_info
                else:
                    raise AttributeError(f"Invalid button: {button_info}")
                for op in ops:
                    image = label = generator = title_text = None
                    if len(op) > 1 and op[1]:
                        if isinstance(op[1], str):
                            image = find_file(op[1])
                        elif isinstance(op[1], type):
                            generator = op[1]
                    if len(op) > 2 and op[2]:
                        label = str(op[2])
                    if len(op) > 3 and op[3]:
                        title_text = str(op[3])
                    cmd = op[0]

                    # make the key button and it's surrounding cell
                    cell, nb = host.make_keypad_button(
                        keypad_box,
                        label,
                        row,
                        c,
                        visible=True,
                        bolded=True,
                        command=host.on_engine_command,
                        args=[cmd],
                        image=image,
                        generator=generator,
                        titlebox_text=title_text,
                    )

                    # if the key is marked as engine type-specific, save as appropriate
                    self.scope_key(cell, nb, cmd, op)
            row += 1

    def regen_engine_keys_map(self):
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

    def scope_key(self, cell: TitleBox | Box, nb: HoldButton, cmd: str, op: tuple):
        host = self._host
        if len(op) > 4 and op[4]:
            btn_scope = op[4]
            if btn_scope == "e":
                self._engine_btns.add(cell)
            elif btn_scope == "c":
                self._common_btns.add(cell)
            elif btn_scope == "a":
                self._acela_btns.add(cell)
            elif btn_scope == "d":
                self._diesel_btns.add(cell)
            elif btn_scope == "f":
                self._freight_btns.add(cell)
            elif btn_scope == "l":
                self._electric_btns.add(cell)
            elif btn_scope == "p":
                self._passenger_btns.add(cell)
            elif btn_scope == "pf":
                self._passenger_freight_btns.add(cell)
            elif btn_scope == "s":
                self._steam_btns.add(cell)
            elif btn_scope == "t":
                self._transformer_btns.add(cell)
            elif btn_scope == "vo":
                self._vol_btns.add(cell)
            elif btn_scope == "sm":
                self._smoke_btns.add(cell)
            elif btn_scope == "cp":
                self._cplr_btns.add(cell)
            elif btn_scope == "bs":
                self._bos_brk_btns.add(cell)
            key = (cmd, op[4])
        else:
            key = cmd

        if key in host.engine_ops_cells:
            log.warning("Duplicate engine op: %r: %r", key, op)
        host.engine_ops_cells[key] = (key, nb)

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
            # (("AUX3_OPTION_ONE", "l"), host.on_extra),
            (("AUX3_OPTION_ONE", "e"), host.on_extra),
            (("ENGINEER_CHATTER", "e"), host.on_crew_dialog),
            (("ENGINEER_CHATTER", "p"), host.on_conductor_actions),
            (("RING_BELL", "e"), host.on_bell_horn_options),
            (("STEWARD_CHATTER", "p"), host.on_steward_dialogs),
            (("TOWER_CHATTER", "e"), host.on_tower_dialog),
            (("TOWER_CHATTER", "p"), host.on_station_dialogs),
        ]
        for key, callback in holds:
            get_btn(key).on_hold = callback

        # 4. Loco-specific Horn/Whistle control holds
        for loco in ["d", "s", "l"]:
            get_btn(("BLOW_HORN_ONE", loco)).on_hold = self.show_horn_control

    # noinspection PyProtectedMember
    def apply_engine_type(self, state: EngineState | None) -> None:
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

        if not isinstance(state, EngineState):
            # If unknown, show diesel-ish defaults
            self._show_keys_for_type("d")
            if host._rr_speed_box:
                host._rr_speed_box.show()
            if host.horn_title_box:
                host.horn_title_box.text = "Horn"
            return

        # Determine the engine type key (must match your engine_gui_conf tags)
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
        if self._updating_from_state:
            return
        host = self._host
        if host.throttle.after_id is not None:
            host.throttle.tk.after_cancel(host.throttle.after_id)
        host.throttle.after_id = host.throttle.tk.after(200, self.on_throttle_released, int(value))

    # noinspection PyUnusedLocal
    def on_throttle_released(self, value: int) -> None:
        self._host.throttle.after_id = None
        # actual speed command is sent from _on_throttle_release_event

    def _on_throttle_release_event(self, e=None) -> None:
        if self._updating_from_state:
            return
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
        if self._updating_from_state:
            return
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
        if self._updating_from_state:
            return
        try:
            # UI feedback only
            value = int(value)
            self._host.momentum_level.value = f"{value:02d}"
        except (TypeError, ValueError):
            return

    def _on_momentum_release_event(self, e=None) -> None:
        if self._updating_from_state:
            return
        try:
            value = int(self._host.momentum.value)
            self._send_momentum(value)
            self.clear_focus(e)
        except (TypeError, ValueError):
            pass

    def _send_momentum(self, value: int) -> None:
        host = self._host

        # Resolve state
        state = host.active_engine_state or host.active_state
        if not isinstance(state, EngineState):
            return

        if state.is_legacy:
            host.on_engine_command("MOMENTUM", data=value)
        else:
            if value in {0, 1}:
                host.on_engine_command("MOMENTUM_LOW", data=0)
                value = 0
            elif value in {2, 3, 4}:
                host.on_engine_command("MOMENTUM_MEDIUM")
                value = 3
            else:
                host.on_engine_command("MOMENTUM_HIGH")
                value = 7

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

    # type alias for tk config dict
    TkCfg = dict[str, Any]

    def _make_slider(
        self,
        parent: Box,
        title: str,
        command: Callable,
        frm: int,
        to: int,
        *,
        step: int = 1,
        visible: bool = True,
        grid: list[int] | tuple[int, int] = (0, 0),
        box_border: int = 1,
        title_border: int = 1,
        title_text_size: int | None = None,
        level_text: str = "00",
        level_width: int = 3,
        level_font: str = "DigitalDream",
        level_size: int | None = None,
        slider_width: int | None = None,
        slider_height: int | None = None,
        slider_length_div: int = 6,
        focus_on_press: bool = True,
        clear_focus_on_release: bool = True,
        on_release: Optional[Callable] = None,
        tk_config: Optional[TkCfg] = None,
    ) -> tuple[Box, TitleBox, Text, Slider]:
        """
        Slider-agnostic builder used for throttle, brake, momentum, quilling horn, etc.

        - `command` is the guizero Slider command (fires during motion).
        - `on_release` (if provided) is bound to ButtonRelease events.
        - `tk_config` lets callers override/extend tk.Scale configuration cleanly.
        """
        host = self._host

        title_text_size = title_text_size if title_text_size is not None else host.s_10
        level_size = level_size if level_size is not None else host.s_18
        slider_width = slider_width if slider_width is not None else int(host.button_size / 3)
        slider_height = slider_height if slider_height is not None else host.slider_height

        box = Box(
            parent,
            border=box_border,
            grid=list(grid),
            visible=visible,
        )

        tb = TitleBox(box, title, align="top", border=title_border)
        tb.text_size = title_text_size

        level = Text(
            tb,
            text=level_text,
            color="black",
            align="top",
            bold=True,
            size=level_size,
            width=level_width,
            font=level_font,
        )
        level.bg = "black"
        level.text_color = "white"

        s = Slider(
            box,
            align="top",
            horizontal=False,
            step=step,
            width=slider_width,
            height=slider_height,
            command=command,
        )
        s.text_color = "black"

        # Default tk.Scale styling used everywhere, but caller can override via tk_config.
        cfg = dict(
            from_=frm,
            to=to,
            takefocus=0,
            troughcolor=LIONEL_BLUE,
            activebackground=LIONEL_ORANGE,
            bg="lightgrey",
            highlightthickness=1,
            highlightbackground=LIONEL_ORANGE,
            width=slider_width,
            sliderlength=int(slider_height / slider_length_div),
        )
        if tk_config:
            cfg.update(tk_config)

        s.tk.config(**cfg)

        # Common focus/clear bindings
        if focus_on_press:
            s.tk.bind("<Button-1>", lambda e: s.tk.focus_set(), add="+")

        if on_release is not None:
            s.tk.bind("<ButtonRelease-1>", on_release, add="+")
        elif clear_focus_on_release:
            s.tk.bind("<ButtonRelease-1>", self.clear_focus, add="+")

        return box, tb, level, s
