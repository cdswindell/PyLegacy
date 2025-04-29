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

from .gpio_device import GpioDevice
from .i2c.oled import OledDevice, Oled
from ..db.engine_state import EngineState
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..protocol.constants import PROGRAM_NAME, CommandScope


class LaunchStatus(Thread, GpioDevice):
    def __init__(
        self,
        tmcc_id: int | EngineState = 39,
        title: str = "Launch Pad 39A",
        address: int = 0x3C,
        device: OledDevice | str = OledDevice.ssd1309,
    ) -> None:
        self._lock = RLock()
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Launch Pad Status Oled")
        self._oled = Oled(address, device, auto_update=False)
        self._title = title

        self._state_store = ComponentStateStore.get()
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

        self._is_running = True
        self._ev = Event()
        self._state_watcher = None
        self._countdown: int | None = None
        self._countdown_thread = None

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
    def title(self) -> str:
        return self._title

    @property
    def countdown(self) -> int | None:
        return self._countdown

    @countdown.setter
    def countdown(self, value: int) -> None:
        with self._lock:
            self._countdown = value
            if value is None:
                self._oled[2] = "T Minus  --:--"
            elif value <= 0:
                value = abs(value)
                self._oled[2] = f"T Minus -00:{value:02d}"
            else:
                minute = value // 60
                second = value % 60
                self._oled[2] = f"Launch  +{minute:02d}:{second:02d}"
            self.update_display()

    @title.setter
    def title(self, value: str) -> None:
        self._title = value
        self._oled[0] = value
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

    def launch(self, countdown: int = -30) -> None:
        with self._lock:
            if self._countdown_thread:
                self._countdown_thread.reset()
                self._countdown_thread = None
            if countdown:
                countdown = countdown if countdown < 0 else -countdown
                self.countdown = countdown
                self._countdown_thread = CountdownThread(self, countdown)
            else:
                self.countdown = None

    def abort(self) -> None:
        with self._lock:
            if self._countdown_thread:
                self._countdown_thread.reset()
                self._countdown_thread = None
            self._oled[3] = "Abort"
        self.update_display()

    def hold(self) -> None:
        with self._lock:
            if self._countdown_thread:
                self._countdown_thread.hold()
            self._oled[3] = "Holding"
        self.update_display()

    def resume(self) -> None:
        with self._lock:
            self._oled[3] = ""
            if self._countdown_thread:
                self._countdown_thread.resume()
        self.update_display()

    def update_display(self, clear: bool = False) -> None:
        with self._lock:
            if clear is True:
                self.display.clear()
                self._oled[0] = self.title
                self._oled[2] = "T Minus  --:--"
            self.display.refresh_display()

    def on_state_update(self) -> None:
        self.update_display()

    def on_sync(self) -> None:
        if self._sync_state.is_synchronized:
            if self._sync_watcher:
                self._sync_watcher.shutdown()
                self._sync_watcher = None
            self._synchronized = True
            if self._monitored_state is None and self.tmcc_id and self.tmcc_id != 99:
                self._monitored_state = self._state_store.get_state(CommandScope.ENGINE, self.tmcc_id)
            self._monitor_state_updates()
            self.update_display(clear=True)

    def reset(self) -> None:
        with self._lock:
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

    def close(self) -> None:
        self.reset()

    def _monitor_state_updates(self):
        if self._state_watcher:
            self._state_watcher.shutdown()
            self._state_watcher = None

        if self._monitored_state:
            self._state_watcher = StateWatcher(self._monitored_state, self.on_state_update)


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

    @property
    def is_resume(self) -> bool:
        return self._resume

    def reset(self) -> None:
        self._is_running = False
        if self.is_alive():
            self._hold = self._resume = False
            self._ev.set()
            self.join()

    def hold(self) -> None:
        self._hold = True
        self._resume = False
        self._interval = None
        self._ev.set()

    def resume(self) -> None:
        self._hold = False
        self._resume = True
        self._interval = 1
        self._ev.set()

    def run(self) -> None:
        while self._is_running:
            print(f"About to wait: {self._interval} {self._ev.is_set()}")
            while not self._ev.wait(self._interval):
                if not self._ev.is_set():
                    self._countdown += 1
                    self._status.countdown = self._countdown
            if self.is_hold is True:
                print(f"Is hold {self.is_hold} {self.is_resume}")
                self._ev.clear()
                continue
            if self.is_resume is True:
                print(f"Is resume {self.is_hold} {self.is_resume}")
                self._ev.clear()
                self._hold = self._resume = False
                continue

        print("Exiting Countdown Thread")
