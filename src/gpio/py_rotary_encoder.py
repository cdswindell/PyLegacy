from threading import Thread, RLock
from time import sleep
from typing import Dict, Callable

from gpiozero import RotaryEncoder

from src.comm.comm_buffer import CommBuffer
from src.gpio.gpio_handler import GpioHandler, log
from src.protocol.command_req import CommandReq
from src.protocol.constants import PROGRAM_NAME


class PyRotaryEncoder(RotaryEncoder):
    def __init__(
        self,
        pin_1: int | str,
        pin_2: int | str,
        command: CommandReq = None,
        wrap: bool = True,
        max_steps: int = 100,
        initial_step: int = 0,
        ramp: Dict[int, int] = None,
        steps_to_data: Callable[[int], int] = None,
        data_to_steps: Callable[[int], int] = None,
        use_steps: bool = False,
    ):
        super().__init__(pin_1, pin_2, wrap=wrap, max_steps=max_steps)
        if initial_step is not None:
            self.steps = initial_step
        self._command = command
        self._action = command.as_action() if command else None
        self._ramp = ramp
        self._steps_to_data = steps_to_data
        self._data_to_steps = data_to_steps
        self._use_steps = use_steps
        self._tmcc_command_buffer = CommBuffer.build()
        self._last_known_data = None
        self._last_rotation_at = GpioHandler.current_milli_time()
        self._last_steps = self.steps
        self._lock = RLock()
        self._pins = (pin_1, pin_2)
        self._handler = PyRotaryEncoderHandler(self)
        GpioHandler.cache_handler(self._handler)
        if command:
            self._handler.start()

    @property
    def pins(self) -> tuple[int, int]:
        return self._pins

    def update_action(
        self,
        command: CommandReq,
        state,
        steps_to_data: Callable[[int], int],
        data_to_steps: Callable[[int], int],
    ) -> None:
        self._steps_to_data = steps_to_data
        self._data_to_steps = data_to_steps
        cur_speed = state.speed if state and state.speed is not None else 0
        self.steps = self._last_steps = data_to_steps(cur_speed)
        self._command = command
        self._action = command.as_action() if command else None
        self._handler.start()

    def update_data(self, new_data) -> None:
        if new_data != self._last_known_data and self._data_to_steps and not self.is_active and self.last_rotated > 5.0:
            with self._lock:
                log.debug(f"{self._last_known_data} -> {self._data_to_steps(new_data)}")
                self.steps = self._data_to_steps(new_data)
                self._last_known_data = new_data
                if self._handler:
                    self._handler.reset_last_known()

    def fire_action(self, cur_step: int = None) -> None:
        if self._action:
            if cur_step is None:
                cur_step = self.steps
            if self._steps_to_data:
                self._last_known_data = data = self._steps_to_data(cur_step)
                print(f"{cur_step} -> {data}")
            else:
                data = 0
            self._action(new_data=data)

    @property
    def last_rotation_at(self) -> int:
        """
        Return the time of the last rotation in millisecond resolution
        """
        return self._last_rotation_at

    @property
    def last_rotated(self) -> float:
        """
        Seconds since the last rotation.
        """
        return (GpioHandler.current_milli_time() - self.last_rotation_at) / 1000.0

    def reset(self) -> None:
        if self._handler:
            self._handler.reset()


class PyRotaryEncoderHandler(Thread):
    def __init__(self, re: PyRotaryEncoder) -> None:
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Rotary Encoder Handler pins: {re.pins}")
        self._re = re
        self._command = None
        self._is_running = True
        self._is_started = False
        self._last_step = None
        self._lock = RLock()
        GpioHandler.cache_handler(self)

    def start(self) -> None:
        with self._lock:
            if self._is_started is False:
                super().start()

    def reset_last_known(self) -> None:
        with self._lock:
            self._last_step = None

    def run(self) -> None:
        with self._lock:
            self._is_started = True
        self._last_step = float("-inf")
        xxx = 5
        while self._is_running:
            with self._lock:
                cur_step = self._re.steps
            if cur_step != self._last_step or (xxx > 0 and cur_step == -self._re.max_steps):
                if cur_step == -self._re.max_steps:
                    xxx -= 1
                else:
                    xxx = 5
                print(cur_step, xxx)
                self._re.fire_action(cur_step)
                self._last_step = self._re.steps
            sleep(0.05)

    def reset(self) -> None:
        self._is_running = False
