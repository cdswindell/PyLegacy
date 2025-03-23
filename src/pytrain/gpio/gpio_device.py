#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from threading import Thread
from typing import Callable, TypeVar, Union

from gpiozero import LED, Button, Device

from .. import CommandDefEnum, CommandReq, GpioHandler
from ..protocol.constants import DEFAULT_ADDRESS, CommandScope
from .py_rotary_encoder import PyRotaryEncoder

P = TypeVar("P", bound=Union[int, str, tuple[int], tuple[int, int], tuple[int, int, int]])


class GpioDevice:
    def close(self):
        for k, v in self.__dict__.items():
            if isinstance(v, Device):
                v.close()
            if isinstance(v, PyRotaryEncoder):
                v.reset()

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
    def cache_handler(handler: Thread) -> None:
        GpioHandler.GPIO_HANDLER_CACHE.add(handler)

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
    def with_prefix_action(
        prefix: CommandReq,
        command: CommandReq,
    ) -> Callable:
        return GpioHandler.with_prefix_action(prefix, command)
