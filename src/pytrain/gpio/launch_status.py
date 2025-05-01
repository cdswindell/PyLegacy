#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from __future__ import annotations

import atexit
from threading import Thread, Event, RLock
from time import time

from .gpio_device import GpioDevice
from .i2c.oled import OledDevice, Oled
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum, TMCC1HaltCommandEnum
from ..comm.command_listener import CommandDispatcher
from ..protocol.command_req import CommandReq
from ..db.engine_state import EngineState
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..protocol.constants import PROGRAM_NAME, CommandScope


class LaunchStatus(Thread, GpioDevice):
    def __init__(
        self,
        tmcc_id: int | EngineState = 39,
        title: str | None = None,
        address: int = 0x3C,
        device: OledDevice | str = OledDevice.ssd1309,
    ) -> None:
        self._lock = RLock()
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Launch Pad Status")

        if isinstance(tmcc_id, EngineState):
            self._monitored_state = tmcc_id
            self._tmcc_id = tmcc_id.address
            self._scope = tmcc_id.scope
        elif isinstance(tmcc_id, int) and 1 <= tmcc_id <= 99:
            self._tmcc_id = tmcc_id
            self._scope = CommandScope.ENGINE
            self._monitored_state = None
        else:
            raise ValueError(f"Invalid tmcc_id: {tmcc_id}")

        self._state_store = ComponentStateStore.get()
        self._dispatcher = CommandDispatcher.get()
        self._is_running = True
        self._ev = Event()
        self._state_watcher = None
        self._countdown: int | None = None
        self._holding = False
        self._aborted = False
        self._countdown_thread = None
        self._last_cmd = None
        self._last_cmd_time = time()
        self._hidden = False

        self._title = title if title else f"Pad {tmcc_id}"
        self._oled = Oled(address, device, auto_update=False)
        self.display.write(self.title, 0, center=True)
        self.display.write("T Minus  --:--", 1, center=True)

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

    def __call__(self, cmd: CommandReq) -> None:
        try:
            if cmd == self._last_cmd and time() - self._last_cmd_time < 0.5:
                # ignore dupe commands, if received within 0.5 seconds of one another
                return
            last_cmd = self._last_cmd.command if self._last_cmd else None
            if cmd.command == TMCC1EngineCommandEnum.REAR_COUPLER:
                # launch in 15 seconds
                self.launch(15)
            elif cmd.command == TMCC1EngineCommandEnum.FRONT_COUPLER:
                # launch now
                self.launch(0)
            elif cmd.command == TMCC1EngineCommandEnum.NUMERIC:
                if cmd.data == 0:
                    # Num 0: Abort
                    self.abort()
                elif cmd.data == 5:
                    if (
                        last_cmd == TMCC1EngineCommandEnum.AUX1_OPTION_ONE
                        or self.aborted is True
                        or self.countdown is None
                    ):
                        # Aux 1/Num 5: Shutdown
                        self.recycle(False)
                        self.countdown = None
                        self._hide()
                    else:
                        # Num 5: Abort
                        self.abort()
                elif cmd.data == 3 and last_cmd == TMCC1EngineCommandEnum.AUX1_OPTION_ONE:
                    # Aux 1/Num 3: Startup
                    self.countdown = None
                    self._show()
            elif cmd.command == TMCC1HaltCommandEnum.HALT:
                self.abort()
        finally:
            self._last_cmd_time = time()
            self._last_cmd = cmd

    @property
    def title(self) -> str:
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        self._title = value
        self.display.write(value, 0, center=True)
        self.update_display(clear=True)

    @property
    def countdown(self) -> int | None:
        return self._countdown

    @countdown.setter
    def countdown(self, value: int) -> None:
        with self._lock:
            self._countdown = value
            if value is None:
                r1 = "T Minus  --:--"
                self.recycle(False)
            else:
                if value < 0:
                    value = abs(value)
                    prefix = "T Minus -"
                else:
                    prefix = "Launch  +"
                minute = value // 60
                second = value % 60
                r1 = f"{prefix}{minute:02d}:{second:02d}"
            self.display.write(r1, 1, center=True)
            self.update_display()

    @property
    def display(self) -> Oled:
        return self._oled

    @property
    def tmcc_id(self) -> int:
        return self._tmcc_id

    @property
    def is_synchronized(self) -> bool:
        return self._synchronized

    @property
    def state(self) -> EngineState:
        return self._monitored_state

    @property
    def holding(self) -> bool:
        return self._holding

    @property
    def aborted(self) -> bool:
        return self._aborted

    def launch(self, countdown: int = -30) -> None:
        with self._lock:
            self.recycle(False)
            if self._countdown_thread:
                self._countdown_thread.reset()
                self._countdown_thread = None
            if countdown is None:
                self.countdown = None
            else:
                countdown = countdown if countdown < 0 else -countdown
                self.countdown = countdown
                self._countdown_thread = CountdownThread(self, countdown)

    def abort(self) -> None:
        with self._lock:
            if self.countdown is None:
                return
            self._holding = False
            self._aborted = True
            if self._countdown_thread:
                self._countdown_thread.reset()
                self._countdown_thread = None
            self.display.write("** Abort **", 3, center=True, blink=True)
        self.update_display()

    def hold(self) -> None:
        with self._lock:
            if self.countdown is None or self.countdown > 0:
                return
            if self._countdown_thread:
                self._countdown_thread.hold()
            self.display.write("** Hold **", 3, center=True, blink=True)
            self._holding = True
        self.update_display()

    def resume(self) -> None:
        with self._lock:
            if self._holding is False:
                return
            self.display[3] = ""
            if self._countdown_thread:
                self._countdown_thread.resume()
            self._holding = False
        self.update_display()

    def update_display(self, clear: bool = False) -> None:
        with self._lock:
            self._show()
            if clear is True:
                self.display.clear()
                self.display.write(self.title, 0, center=True)
                self.display.write("T Minus  --:--", 1, center=True)
            # self.display.refresh_display()
            self.display.force_display()

    def on_sync(self) -> None:
        if self._sync_state.is_synchronized:
            if self._sync_watcher:
                self._sync_watcher.shutdown()
                self._sync_watcher = None
            self._synchronized = True
            if self._monitored_state is None and self.tmcc_id and self.tmcc_id != 99:
                self._monitored_state = self._state_store.get_state(CommandScope.ENGINE, self.tmcc_id)
            self._dispatcher.subscribe(self, CommandScope.ENGINE, self.tmcc_id)
            self.update_display(clear=True)
            self._hide()

    def reset(self) -> None:
        with self._lock:
            self._dispatcher.unsubscribe(self, CommandScope.ENGINE, self.tmcc_id)
            self._holding = self._aborted = False
            if self._countdown_thread:
                self._countdown_thread.reset()
                self._countdown_thread = None
            self.display.reset()
            self._is_running = False
            self._ev.set()
            if self._sync_watcher:
                self._sync_watcher.shutdown()
                self._sync_watcher = None
            if self._state_watcher:
                self._state_watcher.shutdown()
                self._state_watcher = None

    def recycle(self, refresh_display: bool = True) -> None:
        with self._lock:
            self._holding = self._aborted = False
            self.display[3] = ""
            if refresh_display is True:
                self.update_display(clear=True)

    def close(self) -> None:
        self.reset()

    def _hide(self) -> None:
        with self._lock:
            if self._hidden is False:
                self._hidden = True
                self.display.hide()

    def _show(self) -> None:
        with self._lock:
            if self._hidden is True:
                self._hidden = False
                self.display.show()


class CountdownThread(Thread):
    def __init__(self, status: LaunchStatus, countdown: int = -30) -> None:
        super().__init__(daemon=True, name="Countdown Thread")
        self._status = status
        self._countdown = countdown
        self._hold = False
        self._resume = False
        self._ev = Event()
        self._interval = 1
        self._is_running = True
        self.start()

    @property
    def countdown(self) -> int:
        return self._countdown

    @property
    def is_hold(self) -> bool:
        return self._hold

    def hold(self) -> None:
        if self._countdown and self._countdown < 0 and self._hold is False and self._resume is False:
            self._hold = True
            self._resume = False
            self._interval = None
            self._ev.set()

    def resume(self) -> None:
        if self._countdown and self._countdown < 0 and self._hold is True and self._resume is False:
            self._hold = False
            self._resume = True
            self._interval = 1
            self._ev.set()

    def reset(self) -> None:
        self._is_running = False
        if self.is_alive():
            self._hold = self._resume = False
            self._ev.set()
            self.join()

    def run(self) -> None:
        while self._is_running:
            while not self._ev.wait(self._interval):
                self._countdown += 1
                self._status.countdown = self._countdown
            if self.is_hold is True:
                self._ev.clear()
                continue
            if self._resume is True:
                self._ev.clear()
                self._hold = self._resume = False
                continue
