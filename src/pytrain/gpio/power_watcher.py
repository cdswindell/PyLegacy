#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from .gpio_device import GpioDevice, P


class PowerWatcher(GpioDevice):
    """
    Controls an LED that indicates power status of the attached Raspberry Pi.

    The PowerWatcher class is designed to manage a single LED that remains
    illuminated as long as the connected Raspberry Pi has power. It creates
    an LED instance configured with the specified GPIO pin and optionally
    sets its cathode configuration. The LED is initialized to indicate an
    "always-on" state and is cached for later control.

    Attributes
    ----------
    power_led : LED
        The initialized LED object indicating power status.

    Parameters
    ----------
    power_on_pin : P
        The GPIO pin used to control the power LED.
    cathode : bool, optional
        Specifies if the LED is cathode-based (default is True).
    """

    def __init__(
        self,
        power_on_pin: P,
        cathode: bool = True,
    ) -> None:
        """
        Illuminates a LED as long as the attached Pi has power
        """
        self.power_led = self.make_led(power_on_pin, cathode=cathode)
        self.power_led.value = 1
        self.cache_device(self.power_led)
