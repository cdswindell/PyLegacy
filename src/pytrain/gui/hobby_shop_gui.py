#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from guizero import Box

from ..db.accessory_state import AccessoryState
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ..utils.path_utils import find_file
from .accessory_base import AccessoryBase, S
from .accessory_gui import AccessoryGui

VARIANTS = {
    "lionelville hobby shop 6-85294": "Lionelville-Hobby-Shop-6-85294.jpg",
    "madison hobby shop 6-14133": "Madison-Hobby-Shop-6-14133.jpg",
    "midtown models hobby shop 6-32998": "Midtown-Models-Hobby-Shop-6-32998.jpg",
}

TITLES = {
    "Lionelville-Hobby-Shop-6-85294.jpg": "Lionelville Hobby Shop",
    "Madison-Hobby-Shop-6-14133.jpg": "Madison Hobby Shop",
    "Midtown-Models-Hobby-Shop-6-32998.jpg": "Midtown Models Hobby Shop",
}


class HobbyShopGui(AccessoryBase):
    def __init__(
        self,
        power: int,
        motion: int,
        variant: str = None,
        *,
        aggrigator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a Lionel Hobby Shop.

        :param int power:
            TMCC ID of the ACS2 port used to power the hobby shop.

        :param int motion:
            TMCC ID of the ACS2 port used to control the motion.

        :param str variant:
            Optional; Specifies the variant (Lionelville, Madison, Midtown).
        """

        # identify the accessory
        self._title, self._image = self.get_variant(variant)
        self._power = power
        self._motion = motion
        self._variant = variant
        self.power_button = self.motion_button = None
        self.power_state = self.motion_state = None
        super().__init__(self._title, self._image, aggrigator=aggrigator)

    @staticmethod
    def get_variant(variant) -> tuple[str, str]:
        if variant is None:
            variant = "Midtown"
        variant = HobbyShopGui.normalize(variant)
        for k, v in VARIANTS.items():
            if variant in k:
                title = TITLES[v]
                return title, find_file(v)
        raise ValueError(f"Unsupported hobby shop: {variant}")

    def get_target_states(self) -> list[S]:
        self.power_state = self._state_store.get_state(CommandScope.ACC, self._power)
        self.motion_state = self._state_store.get_state(CommandScope.ACC, self._motion)
        return [
            self.power_state,
            self.motion_state,
        ]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux2_on

    def switch_state(self, state: AccessoryState) -> None:
        with self._cv:
            if state.is_aux2_on:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()
                if state == self.power_state and self.motion_button:
                    CommandReq(TMCC1AuxCommandEnum.AUX2_OFF, self.motion_state.tmcc_id).send()
                    self.queue_message(lambda: self.motion_button.disable())
            else:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()
                if state == self.power_state and self.motion_button:
                    self.queue_message(lambda: self.motion_button.enable())

    def build_accessory_controls(self, box: Box) -> None:
        max_text_len = len("Motion") + 2
        self.power_button = self.make_power_button(self.power_state, "Power", 0, max_text_len, box)
        self.motion_button = self.make_power_button(self.motion_state, "Motion", 1, max_text_len, box)
        if not self.is_active(self.power_state):
            CommandReq(TMCC1AuxCommandEnum.AUX2_OFF, self.motion_state.tmcc_id).send()
            self.motion_button.disable()
