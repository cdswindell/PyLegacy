#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from .i2c.oled import OledDevice
from .launch_status import LaunchStatus
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from .gpio_device import GpioDevice, P


class LaunchPad(GpioDevice):
    def __init__(
        self,
        address: int = 39,
        gantry_fwd_pin: P = None,
        gantry_bck_pin: P = None,
        launch_seq_pin: P = None,
        launch_now_pin: P = None,
        launch_t15_pin: P = None,
        abort_pin: P = None,
        siren_pin: P = None,
        klaxon_pin: P = None,
        ground_crew_pin: P = None,
        mission_control_pin: P = None,
        flicker_on_pin: P = None,
        flicker_off_pin: P = None,
        title: str | None = "Launch Pad 39A",
        device: OledDevice | str = None,
        device_address: int = 0x3C,
        repeat_every: float = 0.02,
    ):
        super().__init__()
        # if a device is specified, set up oled display
        if device:
            if title is None and address == 39:
                title = "Pad 39A"
            self._lsd = LaunchStatus(address, title, device_address, device)
        else:
            self._lsd = None
        # use momentary contact switch to move the gantry
        left_cmd, self.gantry_fwd_btn, _ = self.make_button(
            gantry_fwd_pin,
            command=TMCC1EngineCommandEnum.RELATIVE_SPEED,
            address=address,
            data=-1,
            scope=CommandScope.ENGINE,
            hold_repeat=True,
            hold_time=repeat_every,
        )
        self.gantry_fwd_btn.when_pressed = left_cmd.as_action()
        self.gantry_fwd_btn.when_held = left_cmd.as_action()

        right_cmd, self.gantry_bck_btn, _ = self.make_button(
            gantry_bck_pin,
            command=TMCC1EngineCommandEnum.RELATIVE_SPEED,
            address=address,
            data=1,
            scope=CommandScope.ENGINE,
            hold_repeat=True,
            hold_time=repeat_every,
        )
        self.gantry_bck_btn.when_pressed = right_cmd.as_action()
        self.gantry_bck_btn.when_held = right_cmd.as_action()

        # launch sequence
        if launch_seq_pin:
            cmd, self.launch_seq_btn, _ = self.make_button(
                launch_seq_pin,
                command=TMCC1EngineCommandEnum.AUX1_OPTION_ONE,
                address=address,
                scope=CommandScope.ENGINE,
            )
            self.launch_seq_btn.when_pressed = cmd.as_action(duration=4.0)
        else:
            self.launch_seq_btn = None

        # launch sequence
        if launch_now_pin:
            cmd, self.launch_now_btn, _ = self.make_button(
                launch_now_pin,
                command=TMCC1EngineCommandEnum.FRONT_COUPLER,
                address=address,
                scope=CommandScope.ENGINE,
            )
            self.launch_now_btn.when_pressed = cmd.as_action()
        else:
            self.launch_now_btn = None

        # launch T-15
        if launch_t15_pin:
            cmd, self.launch_t15_btn, _ = self.make_button(
                launch_t15_pin,
                command=TMCC1EngineCommandEnum.REAR_COUPLER,
                address=address,
                scope=CommandScope.ENGINE,
            )
            self.launch_t15_btn.when_pressed = cmd.as_action()
        else:
            self.launch_t15_btn = None

        # launch abort
        if abort_pin:
            cmd, self.abort_btn, _ = self.make_button(
                abort_pin,
                command=TMCC1EngineCommandEnum.NUMERIC,
                address=address,
                data=0,
                scope=CommandScope.ENGINE,
            )
            self.abort_btn.when_pressed = cmd.as_action()
        else:
            self.abort_btn = None

        # Siren
        if siren_pin:
            cmd, self.siren_btn, _ = self.make_button(
                siren_pin,
                command=TMCC1EngineCommandEnum.BLOW_HORN_ONE,
                address=address,
                scope=CommandScope.ENGINE,
            )
            self.siren_btn.when_pressed = cmd.as_action()
        else:
            self.siren_btn = None

        # Klaxon
        if klaxon_pin:
            cmd, self.klaxon_btn, _ = self.make_button(
                klaxon_pin,
                command=TMCC1EngineCommandEnum.RING_BELL,
                address=address,
                scope=CommandScope.ENGINE,
            )
            self.klaxon_btn.when_pressed = cmd.as_action()
        else:
            self.klaxon_btn = None

        # ground crew dialog
        if ground_crew_pin:
            cmd, self.ground_crew_btn, _ = self.make_button(
                ground_crew_pin,
                command=TMCC1EngineCommandEnum.NUMERIC,
                address=address,
                data=2,
                scope=CommandScope.ENGINE,
            )
            self.ground_crew_btn.when_pressed = cmd.as_action()
        else:
            self.ground_crew_btn = None

        # mission control dialog
        if mission_control_pin:
            cmd, self.mission_control_btn, _ = self.make_button(
                mission_control_pin,
                command=TMCC1EngineCommandEnum.NUMERIC,
                address=address,
                data=7,
                scope=CommandScope.ENGINE,
            )
            self.mission_control_btn.when_pressed = cmd.as_action()
        else:
            self.mission_control_btn = None

        # smoke/flicker on
        if flicker_on_pin:
            cmd, self.flicker_on_btn, _ = self.make_button(
                flicker_on_pin,
                command=TMCC1EngineCommandEnum.NUMERIC,
                address=address,
                data=9,
                scope=CommandScope.ENGINE,
            )
            self.flicker_on_btn.when_pressed = cmd.as_action()
        else:
            self.flicker_on_btn = None

        # smoke/flicker off
        if flicker_off_pin:
            cmd, self.flicker_off_btn, _ = self.make_button(
                flicker_off_pin,
                command=TMCC1EngineCommandEnum.NUMERIC,
                address=address,
                data=8,
                scope=CommandScope.ENGINE,
            )
            self.flicker_off_btn.when_pressed = cmd.as_action()
        else:
            self.flicker_off_btn = None
