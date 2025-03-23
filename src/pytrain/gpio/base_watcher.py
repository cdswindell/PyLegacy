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
        active_led = None
        if active_pin:
            self.active_led = self.make_led(active_pin, cathode=cathode)
            active_led.value = 1 if ping_server.is_active else 0
            self.cache_device(self.active_led)

        inactive_led = None
        if inactive_pin:
            self.inactive_led = self.make_led(inactive_pin, cathode=cathode)
            inactive_led.value = 0 if ping_server.is_active else 1
            self.cache_device(self.inactive_led)

        # set ping server state change actions
        if self.active_led and self.inactive_led:
            # we have to toggle the leds; we need a custom function
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
