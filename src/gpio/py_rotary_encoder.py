import logging
import threading
from typing import Dict, Callable

from gpiozero import RotaryEncoder

from src.comm.comm_buffer import CommBuffer
from src.gpio.gpio_handler import GpioHandler, log
from src.protocol.command_req import CommandReq


class PyRotaryEncoder(RotaryEncoder):
    def __init__(
        self,
        pin_1: int | str,
        pin_2: int | str,
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
        GpioHandler.cache_device(self)
        self._ramp = ramp
        self._steps_to_data = steps_to_data
        self._data_to_steps = data_to_steps
        self._use_steps = use_steps
        self._tmcc_command_buffer = CommBuffer.build()
        self._last_known_data = None
        self._last_rotation_at = GpioHandler.current_milli_time()
        self._last_steps = self.steps
        self._lock = threading.RLock()

    def update_action(
        self,
        cmd: CommandReq,
        state,
        steps_to_data: Callable[[int], int],
        data_to_steps: Callable[[int], int],
    ) -> None:
        self._steps_to_data = steps_to_data
        self._data_to_steps = data_to_steps
        cur_speed = state.speed if state and state.speed is not None else 0
        self.steps = self._last_steps = data_to_steps(cur_speed)

        def func() -> None:
            nonlocal self

            with self._lock:
                step = self.steps
                if step == self.last_steps:
                    # Safeguard to make sure we can stop engine
                    if step == -self.max_steps or self.value == -1:
                        self._last_known_data = cmd.data = 0
                        self.steps = self._last_steps = -self.max_steps
                        self._tmcc_command_buffer.enqueue_command(cmd.as_bytes)
                else:
                    # did we spin clockwise or counter-clockwise?
                    cc = False if step >= self.last_steps else True
                    self._last_steps = step

                    # how fast are we spinning? Work in step space
                    step_mod = -1 if cc is False else 1
                    last_rotated = GpioHandler.current_milli_time() - self.last_rotation_at
                    if self._ramp:
                        for ramp_val, mod in self._ramp.items():
                            if last_rotated <= ramp_val:
                                step_mod = mod if cc is False else -mod
                                break
                    # convert the step to a speed
                    if self._steps_to_data:
                        step += step_mod
                        step = min(max(step, -self.max_steps), self.max_steps)
                        last_step = self.last_steps
                        self._last_steps = self.steps = step
                        data = self._steps_to_data(step)
                        if log.isEnabledFor(logging.DEBUG):
                            v = self.value
                            log.debug(
                                f"os: {last_step:>4} ns: {step:>4} m: {step_mod:>3} nd: {data} {v} {last_rotated}"
                            )
                    else:
                        data = step_mod
                    self._last_known_data = cmd.data = data
                    self._tmcc_command_buffer.enqueue_command(cmd.as_bytes)
                    self._last_rotation_at = GpioHandler.current_milli_time()

        self.when_rotated = func

    def update_data(self, new_data) -> None:
        if new_data != self._last_known_data and self._data_to_steps and not self.is_active and self.last_rotated > 5.0:
            with self._lock:
                self.steps = self._data_to_steps(new_data)
                self._last_known_data = new_data

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

    @property
    def last_steps(self) -> int:
        return self._last_steps
