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

from guizero import Text
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
        press_for: int = 5,
        exclude_unnamed: bool = True,
    ) -> None:
        StateBasedGui.__init__(
            self,
            f"{PROGRAM_NAME} Administration",
            label,
            width,
            height,
            aggrigator,
            enabled_bg="red",
            scale_by=scale_by,
            exclude_unnamed=exclude_unnamed,
        )
        self._press_for = press_for

    # noinspection PyTypeChecker
    def on_sync(self) -> None:
        if self._sync_state.is_synchronized:
            if self._sync_watcher:
                self._sync_watcher.shutdown()
                self._sync_watcher = None
            self._synchronized = True

            # get all target states; watch for state changes
            accs = self.get_target_states()  # should be just 1
            for acc in accs:
                self._states[acc.tmcc_id] = acc
            self._max_name_len = 12

            # start GUI
            self.start()

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
        self.by_name.hide()
        self.by_number.hide()
        widgets: list[Widget] = []

        # make title label
        ts = int(round(23 * self._scale_by))
        title = Text(
            self.btn_box,
            text=f"Press for {self._press_for} seconds",
            grid=[col, row, 2, 1],
            size=ts,
            bold=True,
            color="red",
        )
        widgets.append(title)

        # make reload button
        row += 1
        btn, btn_h, btn_y = super()._make_state_button(pd, row, col)
        btn.text = "Reload Base 3 State"
        safety = PushButtonHoldHelper(self, btn, CommandReq(TMCC1SyncCommandEnum.RESYNC), self._press_for)
        btn.when_left_button_pressed = safety.on_press
        btn.when_left_button_released = safety.on_release
        self.set_button_inactive(btn)
        widgets.append(btn)

        # make restart button
        row += 1
        btn, btn_h, btn_y = super()._make_state_button(pd, row, col)
        btn.text = "Restart All Nodes"
        safety = PushButtonHoldHelper(self, btn, CommandReq(TMCC1SyncCommandEnum.RESTART), self._press_for)
        btn.when_left_button_pressed = safety.on_press
        btn.when_left_button_released = safety.on_release
        self.set_button_inactive(btn)
        widgets.append(btn)

        # make update button
        row += 1
        btn, btn_h, btn_y = super()._make_state_button(pd, row, col)
        btn.text = f"Update {PROGRAM_NAME} Software"
        safety = PushButtonHoldHelper(self, btn, CommandReq(TMCC1SyncCommandEnum.UPDATE), self._press_for)
        btn.when_left_button_pressed = safety.on_press
        btn.when_left_button_released = safety.on_release
        self.set_button_inactive(btn)
        widgets.append(btn)

        # make upgrade button
        row += 1
        btn, btn_h, btn_y = super()._make_state_button(pd, row, col)
        btn.text = "Upgrade Raspberry Pi Software"
        safety = PushButtonHoldHelper(self, btn, CommandReq(TMCC1SyncCommandEnum.UPGRADE), self._press_for)
        btn.when_left_button_pressed = safety.on_press
        btn.when_left_button_released = safety.on_release
        self.set_button_inactive(btn)
        widgets.append(btn)

        # spacer
        row += 1
        spacer = Text(self.btn_box, text=" ", grid=[col, row], size=ts)
        widgets.append(spacer)

        # make reboot button
        row += 1
        btn, btn_h, btn_y = super()._make_state_button(pd, row, col)
        btn.text = "Reboot All Nodes"
        safety = PushButtonHoldHelper(self, btn, CommandReq(TMCC1SyncCommandEnum.REBOOT), self._press_for)
        btn.when_left_button_pressed = safety.on_press
        btn.when_left_button_released = safety.on_release
        self.set_button_inactive(btn)
        widgets.append(btn)

        # make shutdown button
        row += 1
        btn, btn_h, btn_y = super()._make_state_button(pd, row, col)
        btn.text = "Shutdown All Nodes"
        safety = PushButtonHoldHelper(self, btn, CommandReq(TMCC1SyncCommandEnum.SHUTDOWN), self._press_for)
        btn.when_left_button_pressed = safety.on_press
        btn.when_left_button_released = safety.on_release
        self.set_button_inactive(btn)
        widgets.append(btn)

        # noinspection PyTypeChecker
        self._state_buttons[pd.tmcc_id] = widgets
        return widgets, btn_h, btn_y


class PushButtonHoldHelper:
    def __init__(
        self,
        gui: SystemsGui,
        button: Widget,
        command: CommandReq,
        press_for=5,
    ) -> None:
        self._gui = gui
        self._command = command
        self._button = button
        self._press_for = press_for * 1000
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
            self._after_id = self._tk.after(self._press_for, self.fire)

    def on_release(self, event: EventData) -> None:
        with self._cv:
            btn = event.widget
            self._gui.set_button_inactive(btn)
            if self._after_id is not None:
                self._tk.after_cancel(self._after_id)
                self._after_id = None

    def fire(self):
        with self._cv:
            self._gui.set_button_inactive(self._button)
            self._after_id = None
            self._command.send()
