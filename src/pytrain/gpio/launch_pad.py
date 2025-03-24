#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from .gpio_device import GpioDevice, P


class LaunchPad(GpioDevice):
    def __init__(
        self,
        address: int,
        gantry_chanel: P = 0,
        launch_seq_pin: P = None,
        launch_now_pin: P = None,
        launch_15_pin: P = None,
        abort_pin: P = None,
        siren_pin: P = None,
        klaxon_pin: P = None,
        ground_crew_pin: P = None,
        mission_control_pin: P = None,
        flicker_on_pin: P = None,
        flicker_off_pin: P = None,
    ):
        pass
