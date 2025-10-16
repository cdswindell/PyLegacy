#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

from threading import Condition, RLock

from guizero.base import Widget
from guizero.event import EventData

from ..protocol.command_req import CommandReq
from ..db.sync_state import SyncState
from ..gui.component_state_gui import ComponentStateGui
from ..gui.state_based_gui import StateBasedGui
from ..protocol.constants import CommandScope, PROGRAM_NAME
from ..protocol.tmcc1.tmcc1_constants import TMCC1SyncCommandEnum


class SystemsGui(StateBasedGui):
    def __init__(
        self,
        label: str = None,
        width: int = None,
        height: int = None,
        aggrigator: ComponentStateGui = None,
        scale_by: float = 1.0,
    ) -> None:
        StateBasedGui.__init__(
            self,
            f"{PROGRAM_NAME} Administration",
            label,
            width,
            height,
            aggrigator,
            scale_by=scale_by,
        )

    def get_target_states(self) -> list[SyncState]:
        pds: list[SyncState] = []
        accs = self._state_store.get_all(CommandScope.SYNC)
        for acc in accs:
            pds.append(acc)
        return pds

    def is_active(self, state: SyncState) -> bool:
        return False

    def switch_state(self, pd: SyncState) -> None:
        pass

    def _make_state_button(
        self,
        pd: SyncState,
        row: int,
        col: int,
    ) -> tuple[list[Widget], int, int]:
        widgets: list[Widget] = []

        # make reboot button
        rb_btn, btn_h, btn_y = super()._make_state_button(pd, row, col)
        rb_btn.text = "Reboot All Nodes"
        safety = PushButtonHoldHelper(self, CommandReq(TMCC1SyncCommandEnum.REBOOT))
        rb_btn.when_left_button_pressed = safety.on_press
        rb_btn.when_left_button_released = safety.on_release
        self.set_button_inactive(rb_btn)
        widgets.append(rb_btn)

        # noinspection PyTypeChecker
        self._state_buttons[pd.tmcc_id] = widgets
        return widgets, btn_h, btn_y


class PushButtonHoldHelper:
    def __init__(
        self,
        gui: SystemsGui,
        command: CommandReq,
        hold_for=5000,
    ) -> None:
        self._gui = gui
        self._command = command
        self._hold_for = hold_for
        self._app = gui.app
        self._tk = gui.app.tk
        self._after_id = None
        self._cv = Condition(RLock())

    def on_press(self, event: EventData) -> None:
        btn = event.widget
        with self._cv:
            # Cancel previously scheduled call if any
            if self._after_id is not None:
                self._tk.after_cancel(self._after_id)
                self._after_id = None
            # Schedule command for required hold time
            self._gui.set_button_active(btn)
            print(f"Scheduling command {self._command} for {self._hold_for}ms")
            self._after_id = self._tk.after(self._hold_for, self.fire)

    def on_release(self, event: EventData) -> None:
        with self._cv:
            btn = event.widget
            self._gui.set_button_inactive(btn)
            if self._after_id is not None:
                print(f"Cancelling command {self._command}")
                self._tk.after_cancel(self._after_id)
                self._after_id = None

    def fire(self):
        with self._cv:
            self._after_id = None
            self._command.send()
