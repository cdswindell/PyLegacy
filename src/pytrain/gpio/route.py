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
from ..protocol.tmcc1.tmcc1_constants import TMCC1RouteCommandEnum
from .gpio_device import GpioDevice, P
from .state_source import RouteStateSource


class Route(GpioDevice):
    """
    Class Route is responsible for controlling and firing TMCC2/Legacy routes by managing
    the associated turnouts and using GPIO buttons and LED indications if available.

    This class handles the functionality of throwing all turnouts that are part of a
    specified route to their correct states. It binds actions to GPIO buttons for user
    interaction and optionally controls LED indicators to reflect the route's state.

    Attributes:
        route_btn (Button): Represents the button used to fire the route.
        active_led (Optional[LED]): Represents the LED associated with the route if provided.
        inactive_led (Optional[LED]): Represents the LED associated with the route if provided.

    Args:
        address (int): The unique TMCC_ID for the route to be fired.
        btn_pin (P): GPIO pin to which the physical button is connected.
        active_pin (Optional[P]): GPIO pin for a physical LED indicator, if any. Defaults to None.
        inactive_pin (Optional[P]): GPIO pin for a physical LED indicator, if any. Defaults to None.
        cathode (bool): Specifies the cathode-state configuration for the LED. Defaults to True.
    """

    def __init__(
        self,
        address: int,
        btn_pin: P,
        active_pin: P = None,
        inactive_pin: P = None,
        cathode: bool = True,
    ) -> None:
        """
        Fire a TMCC2/Legacy Route, throwing all incorporated turnouts to the correct state
        """
        self.state = ComponentStateStore.get_state(CommandScope.ROUTE, address, create=False)
        assert self.state

        # make the CommandReq
        req, self.route_btn, self.active_led = self.make_button(
            btn_pin,
            TMCC1RouteCommandEnum.FIRE,
            address,
            led_pin=active_pin,
            bind=False,
            initially_on=self.state.is_active,
            cathode=cathode,
        )

        if inactive_pin:
            self.inactive_led = self.make_led(inactive_pin, initially_on=not self.state.is_active, cathode=cathode)
        else:
            self.inactive_led = None

        # bind actions to buttons
        self.route_btn.when_pressed = req.as_action(repeat=2)

        if self.active_led:
            self.cache_handler(RouteStateSource(address, self.active_led, self.inactive_led))
