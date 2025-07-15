#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

import atexit
from threading import Event, RLock, Thread

from .. import ComponentStateStore, EngineState, TrainState
from ..db.state_watcher import StateWatcher
from ..protocol.constants import DEFAULT_ADDRESS, PROGRAM_NAME, CommandScope
from .gpio_device import GpioDevice
from .i2c.oled import Oled, OledDevice

UP = "\u25b4"
DOWN = "\u25be"
REV = "\u00ab"
FWD = "\u00bb"
BELL = "\u266b"


class EngineStatus(Thread, GpioDevice):
    def __init__(
        self,
        tmcc_id: int | EngineState = DEFAULT_ADDRESS,
        scope: CommandScope = CommandScope.ENGINE,
        address: int = 0x3C,
        device: OledDevice | str = OledDevice.ssd1309,
    ) -> None:
        self._lock = RLock()
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Engine Status Oled")
        self._oled = Oled(address, device, auto_update=False)
        self._state_store = ComponentStateStore.get()
        if isinstance(tmcc_id, EngineState):
            self._monitored_state = tmcc_id
            self._tmcc_id = tmcc_id.address
            self._scope = tmcc_id.scope
        elif isinstance(tmcc_id, int) and 1 <= tmcc_id <= 9999 and scope in [CommandScope.ENGINE, CommandScope.TRAIN]:
            self._tmcc_id = tmcc_id
            self._scope = scope
            self._monitored_state = None
        else:
            raise ValueError(f"Invalid tmcc_id: {tmcc_id} or scope: {scope}")

        self._is_running = True
        self._ev = Event()
        self._railroad = None
        self._last_known_speed = self._monitored_state.speed if self._monitored_state else None
        self._state_watcher = None

        # check for state synchronization
        self._synchronized = False
        self._sync_state = self._state_store.get_state(CommandScope.SYNC, 99)
        if self._sync_state and self._sync_state.is_synchronized is True:
            self._sync_watcher = None
            self.on_sync()
        else:
            self.update_display()
            self._sync_watcher = StateWatcher(self._sync_state, self.on_sync)
        atexit.register(self.close)

    @property
    def display(self) -> Oled:
        return self._oled

    @property
    def tmcc_id(self) -> int:
        return self._tmcc_id

    @tmcc_id.setter
    def tmcc_id(self, value: int) -> None:
        self.update_engine(value, self.scope)

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @scope.setter
    def scope(self, value: CommandScope) -> None:
        self.update_engine(self.tmcc_id, value)

    @property
    def is_synchronized(self) -> bool:
        return self._synchronized

    @property
    def state(self) -> EngineState | TrainState | None:
        return self._monitored_state

    @property
    def railroad(self) -> str:
        if self._railroad is None:
            base_state = self._state_store.get_state(CommandScope.BASE, 0, False)
            if base_state and base_state.base_name:
                self._railroad = base_state.base_name.title()
        return self._railroad if self._railroad is not None else "Loading Engine Roster..."

    def run(self) -> None:
        while self._is_running is True and self._ev.is_set() is False:
            self._ev.wait(10)

    def update_engine(self, tmcc_id: int, scope: CommandScope = CommandScope.ENGINE) -> None:
        self._tmcc_id = tmcc_id
        self._scope = scope
        if tmcc_id is not None and tmcc_id != 99:
            self._monitored_state = self._state_store.get_state(scope, tmcc_id, create=False)
        else:
            self._monitored_state = None
        self._monitor_state_updates()
        self.update_display(clear=True)

    def update_display(self, clear: bool = False) -> None:
        with self._lock:
            if clear:
                self.display.clear()
            cursor = None
            if self._monitored_state:
                is_started = self._monitored_state.is_started
                is_shutdown = self._monitored_state.is_shutdown
                rname = self._monitored_state.road_name if self._monitored_state.road_name else "No Information"
                rnum = f"#{self._monitored_state.road_number} " if self._monitored_state.road_number else ""
                if self.display.cols <= 20:
                    ct = (
                        f" {self._monitored_state.control_type_label}"
                        if self._monitored_state.control_type_label
                        else ""
                    )
                else:
                    ct = ""
                lt = f" {self._monitored_state.engine_type_label}" if self._monitored_state.engine_type_label else ""
                self.display[0] = f"{rnum}{rname}{ct}{lt}"

                tmp = f"{self._scope.label}: "
                row = f"{tmp:<8}"
                row += f"{self._tmcc_id:04}"
                if self.display.cols > 20:
                    if rnum:
                        row += f" {rnum.strip()}"
                if self._monitored_state.control_type_label:
                    if self.display.cols > 15:
                        row += f" {self._monitored_state.control_type_label}"
                    else:
                        row += f" {self._monitored_state.control_type_label[0]}"
                self.display[1] = row

                row = f"Speed: {self._monitored_state.speed:03d}"
                if self.display.cols > 20:
                    row += f"/{self._monitored_state.speed_max:03d}"
                dr = self._monitored_state.direction_label
                if self.display.cols > 15:
                    if dr == "FW":
                        dr = "Fwd"
                    elif dr == "RV":
                        dr = "Rev"
                    else:
                        dr = "---"
                else:
                    if dr == "FW":
                        dr = "F" + FWD
                    elif dr == "RV":
                        dr = "R" + REV
                row += f" {dr}"
                if self.display.cols > 20:
                    row += " Started " + UP if is_started is True else " Shutdown" + DOWN if is_shutdown is True else ""
                elif self.display.cols > 15:
                    row += " Started" if is_started is True else " Off " + DOWN if is_shutdown is True else ""
                else:
                    row += UP if is_started is True else DOWN if is_shutdown is True else " "
                self.display[2] = row

                if self.display.cols > 20:
                    rpm = f" RPM: {self._monitored_state.rpm:1d}:{self._monitored_state.labor:02d}"
                else:
                    rpm = ""
                if self.display.cols > 15:
                    tb = f"TB: {self._monitored_state.train_brake}"
                    mo = f"Mo: {self._monitored_state.momentum}"
                    sm = f"Sm: {self._monitored_state.smoke_label if self._monitored_state.smoke_label else '?'}"
                else:
                    tb = f"B: {self._monitored_state.train_brake}"
                    mo = f"M: {self._monitored_state.momentum}"
                    sm = f"S: {self._monitored_state.smoke_label if self._monitored_state.smoke_label else '?'}"
                row = f"{tb} {mo} {sm}{rpm}"
                self.display[3] = row
                cursor = (1, 8)
            elif self.is_synchronized is True:
                self.display.write(self.railroad, 0, center=True)
                if self._tmcc_id and self._tmcc_id != 99:
                    self.display.write(f"{self.scope.label}: {self._tmcc_id}", 1, center=True)
                    self.display.write("Not Found", 2, center=True)
                    cursor = (1, len(self.display[1]) - len(str(self._tmcc_id)))
                else:
                    # display prompt for Engine/Train
                    self.display.write(f"{self.scope.label}: ?", 1, center=True)
                    cursor = (1, len(self.display[1]) - 1)
            else:
                self.display.write("Synchronizing...", 0, center=True, blink=True)
            self.display.update_display()
            if cursor is not None:
                self.display.cursor_pos = cursor

    def on_sync(self) -> None:
        if self._sync_state.is_synchronized:
            if self._sync_watcher:
                self._sync_watcher.shutdown()
                self._sync_watcher = None
            self._synchronized = True
            if self._monitored_state is None and self.tmcc_id and self.tmcc_id != 99:
                self._monitored_state = self._state_store.get_state(self.scope, self.tmcc_id)
            self._monitor_state_updates()
            self.update_display(clear=True)

    def on_state_update(self) -> None:
        cur_speed = self._monitored_state.speed if self._monitored_state else None
        if cur_speed is not None and self._last_known_speed != cur_speed:
            self._last_known_speed = cur_speed
        self.update_display()

    def reset(self) -> None:
        self.display.reset()
        self._is_running = False
        self._ev.set()
        if self._sync_watcher:
            self._sync_watcher.shutdown()
            self._sync_watcher = None
        if self._state_watcher:
            self._state_watcher.shutdown()
            self._state_watcher = None

    def close(self) -> None:
        self.reset()

    def _monitor_state_updates(self):
        if self._state_watcher:
            self._state_watcher.shutdown()
            self._state_watcher = None

        if self._monitored_state:
            self._state_watcher = StateWatcher(self._monitored_state, self.on_state_update)
