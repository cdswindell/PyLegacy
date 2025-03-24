#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from .gpio_device import GpioDevice, P
from .state_source import AccessoryStateSource


class CulvertLoader(GpioDevice):
    def __init__(
        self,
        address: int,
        cycle_pin: P,
        cycle_led_pin: P = None,
        command_control: bool = True,
        cathode: bool = True,
    ) -> None:
        if command_control is True:
            cycle_req, self.cycle_btn, self.cycle_led = self.make_button(
                cycle_pin,
                TMCC1AuxCommandEnum.AUX2_OPT_ONE,
                address,
                led_pin=cycle_led_pin,
                cathode=cathode,
            )
            self.cycle_btn.when_pressed = cycle_req.as_action(repeat=2)
        else:
            raise NotImplementedError
        if self.cycle_led:
            self.cache_handler(AccessoryStateSource(address, self.cycle_led, aux2_state=TMCC1AuxCommandEnum.AUX2_ON))


class CulvertUnloader(CulvertLoader):
    pass
