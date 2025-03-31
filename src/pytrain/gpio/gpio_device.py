#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from abc import ABC, ABCMeta, abstractmethod
from threading import Thread
from typing import Callable, TypeVar, Union

from gpiozero import LED, Button, Device

from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import DEFAULT_ADDRESS, CommandScope
from .gpio_handler import GpioHandler
from .py_rotary_encoder import PyRotaryEncoder

P = TypeVar("P", bound=Union[int, str, tuple[int], tuple[int, int], tuple[int, int, int]])


class GpioDevice(ABC):
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self):
        pass

    def close(self):
        for k, v in self.__dict__.items():
            if isinstance(v, Device):
                v.close()
            if isinstance(v, PyRotaryEncoder):
                v.close()
                v.reset()

    @staticmethod
    def ramped_speed(step_no: int, max_steps: int = 180) -> int:
        speed = 0
        if step_no < 0:
            mag = -1
            step_no = abs(step_no)
        else:
            mag = 1
        if step_no > 0:
            third = max_steps / 3
            if step_no <= third:
                speed = 1
            elif step_no <= 2 * third:
                speed = 2
            else:
                speed = 3
        print(step_no * mag)
        return speed * mag

    @staticmethod
    def std_step_to_data(step_no: int) -> int:
        return 1 if step_no > 0 else -1 if step_no < 0 else 0

    @staticmethod
    def fast_step_to_data(step_no: int) -> int:
        return 3 if step_no > 0 else -3 if step_no < 0 else 0

    @staticmethod
    def make_button(
        pin: P,
        command: CommandReq | CommandDefEnum = None,
        address: int = DEFAULT_ADDRESS,
        data: int = None,
        scope: CommandScope = None,
        led_pin: P = None,
        hold_repeat: bool = False,
        hold_time: float = 1,
        initially_on: bool = False,
        bind: bool = False,
        cathode: bool = True,
    ) -> Button | tuple[CommandReq, Button, LED]:
        return GpioHandler.make_button(
            pin=pin,
            command=command,
            address=address,
            data=data,
            scope=scope,
            led_pin=led_pin,
            hold_repeat=hold_repeat,
            hold_time=hold_time,
            initially_on=initially_on,
            bind=bind,
            cathode=cathode,
        )

    @staticmethod
    def make_led(
        pin: P,
        initially_on: bool = False,
        cathode: bool = True,
    ) -> LED:
        return GpioHandler.make_led(
            pin=pin,
            initially_on=initially_on,
            cathode=cathode,
        )

    @staticmethod
    def cache_handler(handler: Thread) -> None:
        GpioHandler.GPIO_HANDLER_CACHE.add(handler)

    @staticmethod
    def cache_device(device: Device) -> None:
        """
        Keep devices around after creation so they remain in scope
        """
        GpioHandler.GPIO_DEVICE_CACHE.add(device)

    @staticmethod
    def when_button_pressed(
        pin: P,
        command: CommandReq | CommandDefEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
        led_pin: P = None,
        cathode: bool = True,
    ) -> tuple[CommandReq, Button, LED]:
        return GpioHandler.when_button_pressed(
            pin=pin,
            command=command,
            address=address,
            data=data,
            scope=scope,
            led_pin=led_pin,
            cathode=cathode,
        )

    @staticmethod
    def when_toggle_button_pressed(
        pin: P,
        command: CommandReq | CommandDefEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
        led_pin: P = None,
        initial_state: bool = False,
        auto_timeout: int = None,
        cathode: bool = True,
    ) -> tuple[Button, LED]:
        return GpioHandler.when_toggle_button_pressed(
            pin=pin,
            command=command,
            address=address,
            data=data,
            scope=scope,
            led_pin=led_pin,
            initial_state=initial_state,
            auto_timeout=auto_timeout,
            cathode=cathode,
        )

    @staticmethod
    def with_on_action(action: Callable, led: LED, *impacted_leds: LED) -> Callable:
        return GpioHandler.with_on_action(action, led, *impacted_leds)

    @staticmethod
    def with_off_action(action: Callable, led: LED, *impacted_leds: LED) -> Callable:
        return GpioHandler.with_off_action(action, led, *impacted_leds)

    @staticmethod
    def with_prefix_action(
        prefix: CommandReq,
        command: CommandReq,
    ) -> Callable:
        return GpioHandler.with_prefix_action(prefix, command)
