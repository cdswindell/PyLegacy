#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from ..protocol.tmcc1.tmcc1_constants import TMCC1RouteCommandEnum
from .gpio_device import GpioDevice, P


class Route(GpioDevice):
    """
    Class Route is responsible for controlling and firing TMCC2/Legacy routes by managing
    the associated turnouts and utilizing GPIO buttons and LED indications if available.

    This class handles the functionality of throwing all turnouts that are part of a
    specified route to their correct states. It binds actions to GPIO buttons for user
    interaction and optionally controls LED indicators to reflect the route's state.

    Attributes:
        route_btn (Button): Represents the button used to fire the route.
        route_led (Optional[LED]): Represents the LED associated with the route if provided.

    Args:
        address (int): The unique TMCC_ID for the route to be fired.
        btn_pin (P): GPIO pin to which the physical button is connected.
        led_pin (Optional[P]): GPIO pin for a physical LED indicator, if any. Defaults to None.
        cathode (bool): Specifies the cathode-state configuration for the LED. Defaults to True.
    """

    def __init__(
        self,
        address: int,
        btn_pin: P,
        led_pin: P = None,
        cathode: bool = True,
    ) -> None:
        """
        Fire a TMCC2/Legacy Route, throwing all incorporated turnouts to the correct state
        """
        # make the CommandReq
        req, self.route_btn, self.route_led = self.make_button(
            btn_pin,
            TMCC1RouteCommandEnum.FIRE,
            address,
            led_pin=led_pin,
            bind=True,
            cathode=cathode,
        )
        # bind actions to buttons
        self.route_btn.when_pressed = req.as_action(repeat=2)
