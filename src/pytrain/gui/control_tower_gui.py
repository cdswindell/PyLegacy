#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

from guizero import Box, Text

from ..db.accessory_state import AccessoryState
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ..utils.path_utils import find_file
from .accessory_base import AccessoryBase, AnimatedButton, PowerButton, S
from .accessory_gui import AccessoryGui

VARIANTS = {
    "192 yellow control tower 6-37996": "192-Control-Tower-6-37996.jpg",
    "192 orange control tower 6-82014": "192-Control-Tower-6-82014.jpg",
    "192r red railroad control tower 6-32988": "192R-Railroad-Control-Tower-6-32988.jpg",
    "nasa mission control tower 2229040": "NASA-Mission-Control-Tower-2229040.jpg",
    "radio control tower 6-24153": "Radio-Control-Tower-6-24153.jpg",
}

TITLES = {
    "192-Control-Tower-6-37996.jpg": "Control Tower",
    "192-Control-Tower-6-82014.jpg": "Control Tower",
    "192R-Railroad-Control-Tower-6-32988.jpg": "Railroad Control Tower",
    "NASA-Mission-Control-Tower-2229040.jpg": "NASA Mission Control Tower",
    "Radio-Control-Tower-6-24153.jpg": "Radio Control Tower",
}


class ControlTowerGui(AccessoryBase):
    def __init__(
        self,
        lights: int,
        motion: int,
        variant: str = None,
        *,
        aggrigator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a Lionel Control Tower.

        :param int lights:
            TMCC ID of the ACS2 port used for lights.

        :param int motion:
            TMCC ID of the ACS2 port used to trigger motion.

        :param str variant:
            Optional; Specifies the variant (NASA, Yellow, Orange, Red, Radio, etc.).
        """
        # identify the accessory
        self._title, self._image = self.get_variant(variant)
        self._lights = lights
        self._motion = motion
        self._variant = variant
        self.lights_button = self.motion_button = None
        self.lights_state = self.motion_state = None
        self.motion_image = find_file("control_tower_animation.gif")
        super().__init__(self._title, self._image, aggrigator=aggrigator)

    @staticmethod
    def get_variant(variant) -> tuple[str, str]:
        if variant is None:
            variant = "NASA"
        variant = ControlTowerGui.normalize(variant)
        for k, v in VARIANTS.items():
            if variant in k:
                title = TITLES[v]
                return title, find_file(v)
        raise ValueError(f"Unsupported control tower: {variant}")

    def get_target_states(self) -> list[S]:
        self.lights_state = self._state_store.get_state(CommandScope.ACC, self._lights)
        self.motion_state = self._state_store.get_state(CommandScope.ACC, self._motion)
        return [
            self.lights_state,
            self.motion_state,
        ]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: AccessoryState) -> None:
        if state == self.motion_state:
            return
        with self._cv:
            # a bit confusing, but sending this command toggles the lights
            if state == self.lights_state:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()
                if state.is_aux_on:
                    self.queue_message(lambda: self.motion_button.disable())
                else:
                    self.queue_message(lambda: self.motion_button.enable())

    def build_accessory_controls(self, box: Box) -> None:
        max_text_len = len("Conveyor") + 2
        self.lights_button = self.make_power_button(self.lights_state, "Lights", 0, max_text_len, box)

        motion_box = Box(box, layout="auto", border=2, grid=[1, 0], align="top")
        tb = Text(motion_box, text="Motion", align="top", size=self.s_16, underline=True)
        tb.width = max_text_len
        self.motion_button = AnimatedButton(
            motion_box,
            image=self.motion_image,
            align="top",
            height=self.s_72,
            width=self.s_72,
        )
        self.motion_button.stop_animation()
        self.motion_button.when_left_button_pressed = self.when_pressed
        self.motion_button.when_left_button_released = self.when_released
        self.register_widget(self.motion_state, self.motion_button)
        if not self.is_active(self.lights_state):
            self.motion_button.disable()

    def set_button_active(self, button: AnimatedButton) -> None:
        with self._cv:
            if isinstance(button, PowerButton):
                super().set_button_active(button)
            else:
                button.start_animation()

    def set_button_inactive(self, button: AnimatedButton) -> None:
        with self._cv:
            if isinstance(button, PowerButton):
                super().set_button_inactive(button)
            else:
                button.image = self.motion_image
                button.height = button.width = self.s_72
                button.stop_animation()
