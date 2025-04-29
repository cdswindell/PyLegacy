#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from gpiozero import PingServer

from ..comm.comm_buffer import CommBuffer
from ..utils.ip_tools import find_base_address
from .gpio_device import GpioDevice, P


class BaseWatcher(GpioDevice):
    """
    BaseWatcher class monitors connectivity to a Lionel Base 3 and controls GPIO devices accordingly.

    This class is designed to interface with a server and orchestrates the behavior of active
    and inactive LEDs based on the server's availability. The class determines the server's
    address if not explicitly provided, uses a PingServer to monitor server activity, and
    associates GPIO-based LEDs to visually reflect the activity status of the server.

    Attributes:
        active_led (Optional[GpioLED]): LED to indicate active server status.
        inactive_led (Optional[GpioLED]): LED to indicate inactive server status.

    Parameters:
        server (str, optional): The Base 3's address to monitor. If None,
            it attempts to find the address automatically.
        active_pin (P, optional): GPIO pin for the active state LED. None if
            not specified.
        inactive_pin (P, optional): GPIO pin for the inactive state LED. None if
            not specified.
        cathode (bool): If True, sets up the LEDs in cathode configuration.
            Defaults to True.
        delay (float): Delay in seconds between Base 3 status checks.
            Defaults to 10.

    Raises:
        ValueError: If the Base 3's address cannot be determined, and no `server`
            parameter is provided.
    """

    def __init__(
        self,
        server: str = None,
        active_pin: P = None,
        inactive_pin: P = None,
        cathode: bool = True,
        delay: float = 10,
    ) -> None:
        # if server isn't specified, try to figure it out
        if server is None:
            server = CommBuffer().base3_address
        if server is None:
            print("Looking for Base 3 on local network...")
            server = find_base_address()
            if server is None:
                raise ValueError("Could not determine base address")

        # set up a ping server, treat it as a device
        ping_server = PingServer(server, event_delay=delay)
        self.cache_device(ping_server)

        # set up active led, if any
        if active_pin:
            self.active_led = self.make_led(active_pin, cathode=cathode)
            self.active_led.value = 1 if ping_server.is_active else 0
            self.cache_device(self.active_led)
        else:
            self.active_led = None

        if inactive_pin:
            self.inactive_led = self.make_led(inactive_pin, cathode=cathode)
            self.inactive_led.value = 0 if ping_server.is_active else 1
            self.cache_device(self.inactive_led)
        else:
            self.inactive_led = None

        # set ping server state change actions
        if self.active_led and self.inactive_led:
            # we have to toggle the LEDs; we need a custom function
            def on_active() -> None:
                self.active_led.on()
                self.inactive_led.off()

            ping_server.when_activated = on_active

            def on_inactive() -> None:
                self.active_led.off()
                self.inactive_led.on()

            ping_server.when_deactivated = on_inactive
        elif self.active_led:
            ping_server.when_activated = self.active_led.on
            ping_server.when_deactivated = self.active_led.off
        elif self.inactive_led:
            ping_server.when_activated = self.inactive_led.off
            ping_server.when_deactivated = self.inactive_led.on
