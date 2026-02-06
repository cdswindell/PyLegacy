#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#  All Rights Reserved.
#
#  This work is licensed under the terms of the LPGL license.
#  SPDX-License-Identifier: LPGL
#

from guizero import Box, Text
from guizero.event import EventData

from .accessories.accessory_type import AccessoryType
from .accessory_base import AccessoryBase, S
from .accessory_gui import AccessoryGui
from ..db.accessory_state import AccessoryState
from ..protocol.command_req import CommandReq
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ..utils.path_utils import find_file


class SmokeFluidLoaderGui(AccessoryBase):
    ACCESSORY_TYPE = AccessoryType.SMOKE_FLUID_LOADER

    def __init__(
        self,
        tmcc_id: int,
        variant: str = None,
        *,
        aggregator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a Lionel smoke fluid loader.

        :param int tmcc_id:
            TMCC ID of the smoke fluid loader.

        :param str variant:
            Optional; Specifies the variant (Keystone, Advanced).
        """

        # identify the accessory

        self._tmcc_id = tmcc_id
        self._state = None
        self._boom_active_id = None
        self._delta = 0.1

        self._variant = variant
        self._lights_button = self._boom_left_button = self._boom_right_button = self.droplet_button = None
        self._title: str | None = None
        self._image: str | None = None
        self._repeat_interval = 100  # milliseconds

        super().__init__(self._title, self._image, aggregator=aggregator)

    def bind_variant(self) -> None:
        """
        Resolve all metadata (title, main image, op images) via registry + configure_accessory().

        This keeps the public constructor signature stable while moving all metadata
        to your centralized registry/config pipeline.
        """
        self.configure_from_registry(
            self.ACCESSORY_TYPE,
            self._variant,
            tmcc_id=self._tmcc_id,
        )

    def get_target_states(self) -> list[S]:
        self._state = self.state_for_accessory()
        return [self._state]

    def is_active(self, state: AccessoryState) -> bool:
        return False

    # noinspection PyUnusedLocal
    def update_button(self, tmcc_id: int) -> None:
        """
        Sync gui state to accessory state
        """
        with self._cv:
            if self._state.number == 8 and self._lights_button.image != self.turn_on_image:
                self.set_button_inactive(self._lights_button)
            elif self._state.number == 9 and self._lights_button.image != self.turn_off_image:
                self.set_button_active(self._lights_button)

    def switch_state(self, state: AccessoryState) -> None:
        pass

    def toggle_lights(self) -> None:
        with self._cv:
            if self._lights_button.image == self.turn_on_image:
                CommandReq(TMCC1AuxCommandEnum.NUMERIC, self._tmcc_id, data=9).send()
            elif self._lights_button.image == self.turn_off_image:
                CommandReq(TMCC1AuxCommandEnum.NUMERIC, self._tmcc_id, data=8).send()

    def build_accessory_controls(self, box: Box) -> None:
        lights_label, dispense_label = self.config.labels_for("lights", "dispense")
        max_text_len = max(len(lights_label), len(dispense_label)) + 2

        bl_image, br_image, dispense_image = (
            find_file(x) for x in self.config.images_for("boom_left", "boom_right", "dispense")
        )

        col = 0
        self._lights_button = self.make_power_button(self._state, "Lights", col, max_text_len, box)
        self._lights_button.update_command(self.toggle_lights)

        col += 1
        boom_box = Box(box, layout="auto", border=2, grid=[col, 0], align="top")
        _ = Text(boom_box, text="Fluid Boom", align="top", size=self.s_16, underline=True)
        boom_btns = Box(boom_box, layout="grid", align="top")

        self._boom_left_button = left = self.make_push_button(
            boom_btns,
            state=self._state,
            label=None,
            col=0,
            image=bl_image,
            height=self.s_72,
            width=self.s_72,
        )
        left.when_left_button_pressed = self.when_boom_pressed
        left.when_left_button_released = self.when_boom_released

        self._boom_right_button = right = self.make_push_button(
            boom_btns,
            state=self._state,
            label=None,
            col=1,
            image=br_image,
            height=self.s_72,
            width=self.s_72,
        )
        right.when_left_button_pressed = self.when_boom_pressed
        right.when_left_button_released = self.when_boom_released

        col += 1
        self.droplet_button = db = self.make_push_button(
            box,
            state=self._state,
            label=dispense_label,
            col=col,
            text_len=max_text_len,
            image=dispense_image,
            height=self.s_72,
            width=self.s_72,
        )
        db.update_command(
            CommandReq(TMCC1AuxCommandEnum.BRAKE, self._tmcc_id).send,
        )

    def when_boom_pressed(self, event: EventData) -> None:
        with self._cv:
            pb = event.widget
            speed = 2 if pb.image == self.left_arrow_image else -2
            CommandReq(TMCC1AuxCommandEnum.RELATIVE_SPEED, self._tmcc_id, data=speed).send()
            self._boom_active_id = self.app.tk.after(self._repeat_interval, self.when_boom_held, speed, self._delta)

    # noinspection PyUnusedLocal
    def when_boom_released(self, event: EventData) -> None:
        with self._cv:
            if self._boom_active_id:
                self.app.tk.after_cancel(self._boom_active_id)
                self._boom_active_id = None

    def when_boom_held(self, speed: float, delta: float) -> None:
        with self._cv:
            if self._boom_active_id:
                # Adjusts speed within bounds if delta is nonzero
                if delta != 0.0:
                    if speed > 0:
                        speed += delta
                        if speed > 5.0:
                            speed = 5.0
                            delta = 0.0
                    else:
                        speed -= delta
                        if speed < -5.0:
                            speed = -5.0
                            delta = 0.0
                CommandReq(TMCC1AuxCommandEnum.RELATIVE_SPEED, self._tmcc_id, data=int(speed)).send()
                self._boom_active_id = self.app.tk.after(self._repeat_interval, self.when_boom_held, speed, delta)
