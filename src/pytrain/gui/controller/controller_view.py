#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import logging
import tkinter as tk
import time
from contextlib import contextmanager
from tkinter import TclError
from typing import Any, Callable, Iterator, Optional, TYPE_CHECKING

from guizero import Box, Slider, Text, TitleBox
from guizero.base import Widget

from .engine_gui_conf import BELL_KEY, ENGINE_OPS_LAYOUT, MOMENTUM, MOM_TB, TRAIN_BRAKE
from ..components.analog_gauge import AnalogGaugeWidget
from ..components.hold_button import HoldButton
from ..guizero_base import LIONEL_BLUE, LIONEL_ORANGE
from ...db.engine_state import EngineState
from ...utils.path_utils import find_file

log = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui

CAB_1_THROTTLE_REPEAT_MS = 200


def _trace_phase(host: object, phase: str, **fields) -> None:
    trace = getattr(host, "trace_transition_phase", None)
    if callable(trace):
        trace(phase, **fields)


def _slow_ms(host: object) -> float:
    return float(getattr(host, "gui_trace_slow_ms", 350.0))


def _widget_trace_name(widget: Widget) -> str:
    text = getattr(widget, "text", None)
    if isinstance(text, str) and text:
        return text
    value = getattr(widget, "value", None)
    if isinstance(value, str) and value:
        return value
    return type(widget).__name__


def _widget_visible(widget: object | None) -> bool | None:
    if widget is None:
        return None
    return bool(getattr(widget, "visible", False))


def _widget_value(widget: object | None) -> object | None:
    if widget is None:
        return None
    return getattr(widget, "value", None)


def _widget_has_focus(widget: object | None) -> bool | None:
    tk_widget = getattr(widget, "tk", None)
    if tk_widget is None:
        return None
    focus_displayof = getattr(tk_widget, "focus_displayof", None)
    if not callable(focus_displayof):
        return None
    try:
        return focus_displayof() == tk_widget
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None


def _tk_config_value(widget: object | None, key: str) -> object | None:
    tk_widget = getattr(widget, "tk", None)
    if tk_widget is None:
        return None
    cget = getattr(tk_widget, "cget", None)
    if not callable(cget):
        return None
    try:
        return cget(key)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None


def _update_idletasks_ms(host: object) -> float | None:
    app = getattr(host, "app", None)
    tk_root = getattr(app, "tk", None)
    update_idletasks = getattr(tk_root, "update_idletasks", None)
    if not callable(update_idletasks):
        return None
    started = time.perf_counter()
    try:
        update_idletasks()
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    return round((time.perf_counter() - started) * 1000, 2)


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
        self._gauges: dict[str, list[AnalogGaugeWidget]] = {}
        self._updating_from_state = False
        self._last_state = self._last_throttle_state = None

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
    def update(self, state: EngineState | None, throttle_state: EngineState | None):
        """
        Paint throttle/brake/momentum + direction buttons from the given state.

        `state` is the active engine state (for brake/momentum/direction).
        `throttle_state` is whichever state is allowed to control throttle (engine vs. train vs. None).
        """
        if not isinstance(state, EngineState):
            return

        host = self._host
        started = time.perf_counter()
        throttle_state_changed = throttle_state != self._last_throttle_state
        state_changed = state != self._last_state
        with self.__updating():
            # --- Throttle / Speed ---
            if throttle_state:
                if throttle_state_changed:
                    if not host.speed.enabled:
                        host.speed.enable()
                    if not host.throttle.enabled:
                        host.throttle.enable()
                    if host._rr_speed_btn and not host._rr_speed_btn.enabled:
                        host._rr_speed_btn.enable()

                    if throttle_state.is_legacy:
                        host.throttle.tk.config(from_=195, to=0)
                    elif throttle_state.is_cab1:
                        host.throttle.tk.config(from_=3, to=-3)
                        host.throttle.value = 0
                        if host._rr_speed_btn:
                            host._rr_speed_btn.hide()
                    else:
                        host.throttle.tk.config(from_=31, to=0)

                    if host._rr_speed_btn:
                        if throttle_state.is_cab1:
                            host._rr_speed_btn.hide()
                        else:
                            host._rr_speed_btn.show()

                # don't fight the user while dragging
                if host.throttle.tk.focus_displayof() != host.throttle.tk:
                    host.throttle.value = throttle_state.target_speed

                if throttle_state.is_cab1:
                    self._set_cab1_speed()
                else:
                    host.speed.value = f"{throttle_state.speed:03d}"

                # trough color indicates actual vs. target
                if throttle_state.speed != throttle_state.target_speed:
                    host.throttle.tk.config(troughcolor="#4C96C5")
                else:
                    host.throttle.tk.config(troughcolor=LIONEL_BLUE)

                if host._rr_speed_panel:
                    host._rr_speed_panel.configure(throttle_state)
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

            if state != self._last_state:
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

            # --- Gauges ---
            for gauge_type in ["fuel", "water"]:
                gauges = self._gauges.get(gauge_type, [])
                for gauge in gauges:
                    if gauge_type == "fuel":
                        gauge.set_value(state.fuel_level_pct)
                    elif gauge_type == "water":
                        gauge.set_value(state.water_level_pct)
            self._last_throttle_state = throttle_state
            self._last_state = state
        elapsed_ms = (time.perf_counter() - started) * 1000
        slow_ms = _slow_ms(host)
        _trace_phase(
            host,
            "controller.update",
            level=logging.INFO if elapsed_ms >= slow_ms else logging.DEBUG,
            force=elapsed_ms >= slow_ms,
            state_tmcc_id=state.tmcc_id,
            throttle_tmcc_id=throttle_state.tmcc_id if throttle_state else None,
            state_changed=state_changed,
            throttle_state_changed=throttle_state_changed,
            throttle_has_focus=_widget_has_focus(getattr(host, "throttle", None)),
            throttle_widget_value=_widget_value(getattr(host, "throttle", None)),
            throttle_speed=throttle_state.speed if throttle_state else None,
            throttle_target_speed=throttle_state.target_speed if throttle_state else None,
            speed_label_value=_widget_value(getattr(host, "speed", None)),
            rr_speed_btn_visible=_widget_visible(getattr(host, "_rr_speed_btn", None)),
            rr_speed_box_visible=_widget_visible(getattr(host, "_rr_speed_box", None)),
            freight_box_visible=_widget_visible(getattr(host, "_freight_sounds_bell_horn_box", None)),
            throttle_box_visible=_widget_visible(getattr(host, "throttle_box", None)),
            throttle_troughcolor=_tk_config_value(getattr(host, "throttle", None), "troughcolor"),
            elapsed_ms=round(elapsed_ms, 2),
        )
        for k, v in host._scope_buttons.items():
            if k == host.scope:
                log.warning(f"controller on_scope: {k} {v.bg} {v.text_color}")

    def _trace_scope_button_state(self, source: str) -> None:
        host = self._host
        active_button = host._scope_buttons.get(host.scope) if getattr(host, "_scope_buttons", None) else None
        _trace_phase(
            host,
            "scope_button_state",
            source=source,
            active_scope=host.scope.label if host.scope else None,
            active_bg=getattr(active_button, "bg", None),
            active_text_color=getattr(active_button, "text_color", None),
        )

    @staticmethod
    def _engine_type_key_for_state(state: EngineState | None) -> str | None:
        if not isinstance(state, EngineState):
            return None
        if getattr(state, "is_diesel", False):
            return "d"
        if getattr(state, "is_steam", False):
            return "s"
        if getattr(state, "is_passenger", False):
            return "p"
        if getattr(state, "is_freight", False):
            return "f"
        if getattr(state, "is_acela", False):
            return "a"
        if getattr(state, "is_electric", False):
            return "l"
        if getattr(state, "is_crane", False):
            return "r"
        if getattr(state, "is_transformer", False):
            return "t"
        return "d"

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
        host.throttle_box, host.throttle_title_box, host.speed, host.throttle = self.make_slider(
            sliders,
            title="Speed",
            command=self.on_throttle_change,
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
        host.brake_box, _, host.brake_level, host.brake = self.make_slider(
            sliders,
            "Brake",
            self.on_train_brake,
            frm=0,
            to=7,
        )

        # Allow Tk to compute geometry
        host.app.tk.update_idletasks()

        # Momentum
        host.momentum_box, _, host.momentum_level, host.momentum = self.make_slider(
            sliders,
            "Moment",
            self.on_momentum,  # debounces internally
            frm=0,
            to=7,
            visible=False,
            on_release=self._on_momentum_release_event,  # immediate send + clear focus
        )

        # Horn
        host.horn_box, host.horn_title_box, host.horn_level, host.horn = self.make_slider(
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
        horn_btn.on_repeat = horn_btn.on_press
        horn_btn.repeat_interval = horn_btn.hold_threshold = 0.2
        host._freight_sounds_bell_horn_box.hide()

        # --- HIDE IT AGAIN after sizing is complete ---
        host.controller_box.hide()

        # ... create controller_keypad_box, sliders, throttle, brake, etc ...
        # At the end:
        self._focus_widget = focus_widget = tk.Frame(host.app.tk, takefocus=1)
        focus_widget.place(x=-9999, y=-9999, width=1, height=1)

        # keep host.focus_widget used elsewhere, if you want
        host.focus_widget = self._focus_widget

    def _register_gauge(self, label: str, gauge: AnalogGaugeWidget) -> None:
        label = label.lower()
        if label not in self._gauges:
            self._gauges[label] = []
        self._gauges[label].append(gauge)

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
            "r": self._common_btns | self._crane_btns,
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
            elif btn_scope == "r":
                self._crane_btns.add(cell)
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

        # handle gauges
        if isinstance(nb, AnalogGaugeWidget):
            self._register_gauge(nb.label, nb)

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
            (("BOOST_SPEED", "r"), 0.3),
            (("BRAKE_SPEED", "bs"), 0.3),
            (("BRAKE_SPEED", "t"), 0.3),
            (("BRAKE_SPEED", "l"), 0.3),
            (("BRAKE_SPEED", "r"), 0.3),
            (("WATER_INJECTOR", "s"), 0.2),
            (("LET_OFF_LONG", "s"), 0.2),
        ]
        for key, interval in repeats:
            btn = get_btn(key)
            btn.on_repeat = btn.on_press
            btn.repeat_interval = btn.hold_threshold = interval

        # 3. Setup Hold behaviors (Popups)
        holds = [
            (("AUX2_OPTION_ONE", "e"), host.on_lights),
            (("AUX3_OPTION_ONE", "e"), host.on_extra),
            (("ENGINEER_CHATTER", "e"), host.on_crew_dialog),
            (("ENGINEER_CHATTER", "p"), host.on_conductor_actions),
            (("RING_BELL", "e"), host.on_bell_horn_options),
            (("STEWARD_CHATTER", "p"), host.on_steward_dialogs),
            (("TOWER_CHATTER", "e"), host.on_tower_dialog),
            (("TOWER_CHATTER", "p"), host.on_station_dialogs),
            (("START_UP_IMMEDIATE", "e"), (host.on_engine_command, [["START_UP_DELAYED", "START_UP_IMMEDIATE"]])),
            (("SHUTDOWN_IMMEDIATE", "e"), (host.on_engine_command, [["SHUTDOWN_DELAYED", "SHUTDOWN_IMMEDIATE"]])),
        ]
        for key, callback in holds:
            get_btn(key).on_hold = callback

        # 4. Loco-specific Horn/Whistle control holds
        for loco in ["d", "s", "l"]:
            get_btn(("BLOW_HORN_ONE", loco)).on_hold = self.show_horn_control

        # 5. Gauge commands
        for gauge_type in ["fuel", "water"]:
            gauges = self._gauges.get(gauge_type, [])
            for gauge in gauges:
                gauge.command = host.on_engine_command
                gauge.on_hold = host.on_engine_command
                if gauge_type == "fuel":
                    gauge.args = ["ENGINEER_FUEL_LEVEL"]
                    gauge.hold_args = ["ENGINEER_FUEL_REFILLED"]
                elif gauge_type == "water":
                    gauge.args = ["ENGINEER_WATER_LEVEL"]
                    gauge.hold_args = ["ENGINEER_WATER_REFILLED"]

    # noinspection PyProtectedMember
    def apply_engine_type(self, state: EngineState | None) -> None:
        """
        Show/hide controller op keys + aux widgets based on motive type.
        Called from EngineGui.ops_mode() after state is resolved.
        """
        host = self._host
        started = time.perf_counter()
        prior_engine_type = getattr(host, "_last_engine_type", None)
        prior_state = self._last_state
        prior_state_tmcc_id = getattr(prior_state, "tmcc_id", None)
        prior_state_engine_type = self._engine_type_key_for_state(prior_state)
        last_throttle_tmcc_id = getattr(self._last_throttle_state, "tmcc_id", None)
        self._trace_scope_button_state("controller.apply_engine_type:start")

        # default hide/show aux widgets
        if host._freight_sounds_bell_horn_box:
            host._freight_sounds_bell_horn_box.hide()
        if host._rr_speed_box:
            host._rr_speed_box.hide()

        if not isinstance(state, EngineState):
            # If unknown, show diesel-ish defaults
            show_keys_started = time.perf_counter()
            shown_count, hidden_count, skipped = self._show_keys_for_type("d")
            show_keys_ms = round((time.perf_counter() - show_keys_started) * 1000, 2)
            if host._rr_speed_box:
                host._rr_speed_box.show()
            if host.horn_title_box:
                host.horn_title_box.text = "Horn"
            elapsed_ms = (time.perf_counter() - started) * 1000
            self._trace_scope_button_state("controller.apply_engine_type:end")
            _trace_phase(
                host,
                "controller.apply_engine_type",
                level=logging.INFO if elapsed_ms >= _slow_ms(host) else logging.DEBUG,
                force=elapsed_ms >= _slow_ms(host),
                state_tmcc_id=getattr(state, "tmcc_id", None),
                engine_type="d",
                prior_engine_type=prior_engine_type,
                prior_state_tmcc_id=prior_state_tmcc_id,
                prior_state_engine_type=prior_state_engine_type,
                last_throttle_tmcc_id=last_throttle_tmcc_id,
                throttle_has_focus=_widget_has_focus(getattr(host, "throttle", None)),
                throttle_widget_value=_widget_value(getattr(host, "throttle", None)),
                rr_speed_btn_visible=_widget_visible(getattr(host, "_rr_speed_btn", None)),
                rr_speed_box_visible=_widget_visible(getattr(host, "_rr_speed_box", None)),
                freight_box_visible=_widget_visible(getattr(host, "_freight_sounds_bell_horn_box", None)),
                throttle_box_visible=_widget_visible(getattr(host, "throttle_box", None)),
                shown_count=shown_count,
                hidden_count=hidden_count,
                skipped=skipped,
                show_keys_ms=show_keys_ms,
                elapsed_ms=round(elapsed_ms, 2),
            )
            return

        t = self._engine_type_key_for_state(state) or "d"

        show_keys_started = time.perf_counter()
        shown_count, hidden_count, skipped = self._show_keys_for_type(t)
        show_keys_ms = round((time.perf_counter() - show_keys_started) * 1000, 2)

        # Per-type aux behavior
        if t in {"d", "s", "a", "l", "p", "r", "t"}:
            if host._rr_speed_box:
                host._rr_speed_box.show()

        if host.horn_title_box:
            if t == "s":
                host.horn_title_box.text = "Whistle"
            else:
                host.horn_title_box.text = "Horn"

        if t in {"f", "r"}:
            if host._freight_sounds_bell_horn_box:
                host._freight_sounds_bell_horn_box.show()
            # Freight uses the horn-control popup behavior
            self.show_horn_control()

        if t == "t":
            # Transformer mode wants brake shown
            self.toggle_momentum_train_brake(show_btn="brake")
        elapsed_ms = (time.perf_counter() - started) * 1000
        self._trace_scope_button_state("controller.apply_engine_type:end")
        _trace_phase(
            host,
            "controller.apply_engine_type",
            level=logging.INFO if elapsed_ms >= _slow_ms(host) else logging.DEBUG,
            force=elapsed_ms >= _slow_ms(host),
            state_tmcc_id=state.tmcc_id,
            engine_type=t,
            prior_engine_type=prior_engine_type,
            prior_state_tmcc_id=prior_state_tmcc_id,
            prior_state_engine_type=prior_state_engine_type,
            last_throttle_tmcc_id=last_throttle_tmcc_id,
            throttle_has_focus=_widget_has_focus(getattr(host, "throttle", None)),
            throttle_widget_value=_widget_value(getattr(host, "throttle", None)),
            rr_speed_btn_visible=_widget_visible(getattr(host, "_rr_speed_btn", None)),
            rr_speed_box_visible=_widget_visible(getattr(host, "_rr_speed_box", None)),
            freight_box_visible=_widget_visible(getattr(host, "_freight_sounds_bell_horn_box", None)),
            throttle_box_visible=_widget_visible(getattr(host, "throttle_box", None)),
            shown_count=shown_count,
            hidden_count=hidden_count,
            skipped=skipped,
            show_keys_ms=show_keys_ms,
            elapsed_ms=round(elapsed_ms, 2),
        )

    def _show_keys_for_type(self, t: str) -> tuple[int, int, bool]:
        """Internal: show keys for a controller type key."""
        host = self._host
        previous_engine_type = getattr(host, "_last_engine_type", None)

        # Avoid rework if type unchanged
        if previous_engine_type == t:
            _trace_phase(
                host,
                "controller.show_keys_for_type",
                engine_type=t,
                previous_engine_type=previous_engine_type,
                shown_count=0,
                hidden_count=0,
                batched_container_hidden=False,
                container_hide_ms=None,
                container_show_ms=None,
                idletasks_before_ms=_update_idletasks_ms(host),
                idletasks_after_show_ms=None,
                idletasks_after_hide_ms=None,
                show_ms=0.0,
                hide_ms=0.0,
                slowest_show_ms=0.0,
                slowest_show_widget=None,
                slowest_hide_ms=0.0,
                slowest_hide_widget=None,
                skipped=True,
            )
            return 0, 0, True

        btns = self._engine_type_key_map.get(t, set())
        previous_btns = self._engine_type_key_map.get(previous_engine_type, set()) if previous_engine_type else set()
        cells_to_show = btns - previous_btns
        cells_to_hide = previous_btns - btns if previous_engine_type else self._all_engine_btns - btns
        container = getattr(host, "controller_keypad_box", None)
        batched_container_hidden = bool(container is not None and getattr(container, "visible", False))
        container_hide_ms = None
        container_show_ms = None
        if batched_container_hidden and callable(getattr(container, "hide", None)):
            container_hide_started = time.perf_counter()
            container.hide()
            container_hide_ms = round((time.perf_counter() - container_hide_started) * 1000, 2)
        idletasks_before_ms = _update_idletasks_ms(host)
        try:
            shown_count = 0
            show_started = time.perf_counter()
            slowest_show_ms = 0.0
            slowest_show_widget = None
            for cell in cells_to_show:
                cell_started = time.perf_counter()
                cell.show()
                cell_elapsed_ms = (time.perf_counter() - cell_started) * 1000
                if cell_elapsed_ms > slowest_show_ms:
                    slowest_show_ms = cell_elapsed_ms
                    slowest_show_widget = _widget_trace_name(cell)
                shown_count += 1
            show_ms = (time.perf_counter() - show_started) * 1000
            idletasks_after_show_ms = _update_idletasks_ms(host)

            hidden_count = 0
            hide_started = time.perf_counter()
            slowest_hide_ms = 0.0
            slowest_hide_widget = None
            for cell in cells_to_hide:
                cell_started = time.perf_counter()
                cell.hide()
                cell_elapsed_ms = (time.perf_counter() - cell_started) * 1000
                if cell_elapsed_ms > slowest_hide_ms:
                    slowest_hide_ms = cell_elapsed_ms
                    slowest_hide_widget = _widget_trace_name(cell)
                hidden_count += 1
            hide_ms = (time.perf_counter() - hide_started) * 1000
            idletasks_after_hide_ms = _update_idletasks_ms(host)
        finally:
            if batched_container_hidden and callable(getattr(container, "show", None)):
                container_show_started = time.perf_counter()
                container.show()
                container_show_ms = round((time.perf_counter() - container_show_started) * 1000, 2)

        host._last_engine_type = t
        _trace_phase(
            host,
            "controller.show_keys_for_type",
            engine_type=t,
            previous_engine_type=previous_engine_type,
            shown_count=shown_count,
            hidden_count=hidden_count,
            batched_container_hidden=batched_container_hidden,
            container_hide_ms=container_hide_ms,
            container_show_ms=container_show_ms,
            idletasks_before_ms=idletasks_before_ms,
            idletasks_after_show_ms=idletasks_after_show_ms,
            idletasks_after_hide_ms=idletasks_after_hide_ms,
            show_ms=round(show_ms, 2),
            hide_ms=round(hide_ms, 2),
            slowest_show_ms=round(slowest_show_ms, 2),
            slowest_show_widget=slowest_show_widget,
            slowest_hide_ms=round(slowest_hide_ms, 2),
            slowest_hide_widget=slowest_hide_widget,
            skipped=False,
        )
        return shown_count, hidden_count, False

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

    def on_throttle_change(self, value) -> None:
        host = self._host
        state = host.active_engine_state or host.active_state
        if self._updating_from_state or not state.is_cab1:
            return
        if host.throttle is None or host.throttle.tk.focus_displayof() != host.throttle.tk:
            return

        rel_speed = int(float(value))
        self._set_cab1_speed(rel_speed)
        host.on_speed_command(rel_speed)

        if rel_speed != 0:
            self._schedule_cab_1_throttle_repeat()
        else:
            self._cancel_cab_1_throttle_repeat()

    def _set_cab1_speed(self, speed: int = None):
        host = self._host
        speed = speed if speed is not None else host.throttle.value
        if speed > 1:
            host.speed.value = f"+{speed:2d}"
        elif speed < 0:
            host.speed.value = f"-{-speed:2d}"
        else:
            host.speed.value = f" {speed:2d}"

    def _schedule_cab_1_throttle_repeat(self) -> None:
        host = self._host
        self._cancel_cab_1_throttle_repeat()
        if host.throttle is None or host.throttle.value == 0:
            return
        host.throttle.after_id = host.throttle.tk.after(CAB_1_THROTTLE_REPEAT_MS, self._repeat_cab_1_throttle)

    def _repeat_cab_1_throttle(self) -> None:
        host = self._host
        host.throttle.after_id = None
        if host.throttle.value == 0:
            return
        host.on_speed_command(host.throttle.value)
        self._schedule_cab_1_throttle_repeat()

    def _cancel_cab_1_throttle_repeat(self) -> None:
        host = self._host
        after_id = getattr(host.throttle, "after_id", None)
        if after_id is not None:
            try:
                host.throttle.tk.after_cancel(after_id)
            except (TclError, AttributeError):
                pass
            finally:
                host.throttle.after_id = None

    def _on_throttle_release_event(self, e=None) -> None:
        if self._updating_from_state:
            return
        host = self._host
        self._cancel_cab_1_throttle_repeat()

        state = host.active_engine_state or host.active_state
        if not isinstance(state, EngineState):
            return

        # send speed command
        if state.is_cab1:
            host.throttle.value = 0
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

    def make_slider(
        self,
        parent: Box,
        title: str,
        command: Callable,
        frm: int,
        to: int,
        *,
        step: int = 1,
        visible: bool = True,
        grid: list[int] | tuple[int, int] | tuple[int, int, int, int] = (0, 0),
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
            align="top",
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
