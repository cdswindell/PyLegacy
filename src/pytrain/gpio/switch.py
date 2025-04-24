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
from ..protocol.tmcc1.tmcc1_constants import TMCC1SwitchCommandEnum
from .gpio_device import GpioDevice, P
from .state_source import SwitchStateSource


class Switch(GpioDevice):
    def __init__(
        self,
        address: int,
        thru_pin: P,
        out_pin: P,
        thru_led_pin: P = None,
        out_led_pin: P = None,
        cathode: bool = True,
        initial_state: TMCC1SwitchCommandEnum = None,
    ) -> None:
        """
        Control a switch/turnout that responds to TMCC1 switch commands, such
        as Lionel Command/Control-equipped turnouts or turnouts connected to
        an LCS ACS 2 configured in "Switch" mode.

        Optionally, manage LEDs to reflect turnout state; through or out.
        Also supports bi-color LEDs with either common cathode or anode.
        """
        if initial_state is None:
            state = ComponentStateStore.get_state(CommandScope.SWITCH, address, create=False)
            if state:
                initial_state = state.state
            if initial_state is None:
                initial_state = TMCC1SwitchCommandEnum.THRU

        # make the CommandReqs
        thru_req, self.thru_btn, self.thru_led = self.make_button(
            thru_pin,
            TMCC1SwitchCommandEnum.THRU,
            address,
            led_pin=thru_led_pin,
            initially_on=initial_state == TMCC1SwitchCommandEnum.THRU,
            cathode=cathode,
        )
        out_req, self.out_btn, self.out_led = self.make_button(
            out_pin,
            TMCC1SwitchCommandEnum.OUT,
            address,
            led_pin=out_led_pin,
            initially_on=initial_state == TMCC1SwitchCommandEnum.OUT,
            cathode=cathode,
        )
        # bind actions to buttons
        thru_action = thru_req.as_action(repeat=2)
        out_action = out_req.as_action(repeat=2)

        self.thru_btn.when_pressed = self.with_on_action(thru_action, self.thru_led, self.out_led)
        self.out_btn.when_pressed = self.with_on_action(out_action, self.out_led, self.thru_led)

        if self.thru_led is not None and self.out_led is not None:
            self.cache_handler(SwitchStateSource(address, self.thru_led, self.out_led))
