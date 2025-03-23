#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from ..db.component_state_store import ComponentStateStore
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from .gpio_device import GpioDevice, P
from .state_source import AccessoryStateSource


class PowerDistrict(GpioDevice):
    def __init__(
        self,
        address: int,
        on_pin: P,
        off_pin: P,
        on_led_pin: P = None,
        cathode: bool = True,
        initial_state: TMCC1AuxCommandEnum | bool = None,
    ) -> None:
        """
        Control a power district that responds to TMCC1 accessory commands, such
        as an LCS BP2 configured in "Acc" mode.
        """
        if initial_state is None:
            state = ComponentStateStore.get_state(CommandScope.ACC, address, create=False)
            if state:
                initial_state = state.aux_state
            if initial_state is None:
                # last resort, assume district is off
                initial_state = TMCC1AuxCommandEnum.AUX2_OPT_ONE

        # make the CommandReqs
        on_req, self.on_btn, self.on_led = self.make_button(
            on_pin,
            TMCC1AuxCommandEnum.AUX1_OPT_ONE,
            address,
            led_pin=on_led_pin,
            cathode=cathode,
            initially_on=initial_state == TMCC1AuxCommandEnum.AUX1_OPT_ONE,
        )
        off_req, self.off_btn, self.off_led = self.make_button(
            off_pin,
            TMCC1AuxCommandEnum.AUX2_OPT_ONE,
            address,
            cathode=cathode,
            initially_on=initial_state == TMCC1AuxCommandEnum.AUX2_OPT_ONE,
        )
        # bind actions to buttons
        on_action = on_req.as_action(repeat=2)
        off_action = off_req.as_action(repeat=2)

        self.on_btn.when_pressed = self.with_on_action(on_action, self.on_led)
        self.off_btn.when_pressed = self.with_off_action(off_action, self.on_led)

        if self.on_led:
            # listen for external state changes
            self.cache_handler(AccessoryStateSource(address, self.on_led, aux_state=TMCC1AuxCommandEnum.AUX1_OPT_ONE))
