#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from guizero import Box

from .. import TMCC1AuxCommandEnum
from ..db.accessory_state import AccessoryState
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..utils.path_utils import find_file
from .accessory_base import AccessoryBase, S
from .accessory_gui import AccessoryGui

VARIANTS = {
    "advanced smoke fluid loader 6-37821": "Advanced-Smoke-Fluid-Loader-6-37821.jpg",
    "keystone smoke fluid loader 6-83634": "Keystone-Smoke-Fluid-Loader-6-83634.jpg",
}

TITLES = {
    "Advanced-Smoke-Fluid-Loader-6-37821.jpg": "Advanced Fluid Co.",
    "Keystone-Smoke-Fluid-Loader-6-83634.jpg": "Keystone Fluid Co.",
}


class SmokeFluidLoaderGui(AccessoryBase):
    def __init__(
        self,
        tmcc_id: int,
        variant: str = None,
        *,
        aggrigator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a K-Line/Lionel Milk Loader.

        :param int tmcc_id:
            TMCC ID of the smoke fluid loader.

        :param str variant:
            Optional; Specifies the variant (Moose Pond, Dairymen's League, Mountain View).
        """

        # identify the accessory
        self._title, self._image = self.get_variant(variant)
        self._tmcc_id = tmcc_id
        self.fluid_loader_state = None

        self._variant = variant
        self.lights_button = self._boom_left_button = self._boom_right_button = self.droplet_button = None
        self.droplet_image = find_file("depot-milk-can-eject.jpeg")
        super().__init__(self._title, self._image, aggrigator=aggrigator)

    @staticmethod
    def get_variant(variant) -> tuple[str, str]:
        if variant is None:
            variant = "Keystone"
        variant = variant.lower().replace("'", "").replace("-", "")
        for k, v in VARIANTS.items():
            if variant in k:
                title = TITLES[v]
                return title, find_file(v)
        raise ValueError(f"Unsupported smoke fluid loader: {variant}")

    def get_target_states(self) -> list[S]:
        self.fluid_loader_state = self._state_store.get_state(CommandScope.ACC, self._tmcc_id)
        return [self.fluid_loader_state]

    def is_active(self, state: AccessoryState) -> bool:
        return False

    # noinspection PyUnusedLocal
    def update_button(self, tmcc_id: int) -> None:
        """
        Sync gui state to accessory state
        """
        with self._cv:
            print(self.fluid_loader_state)
            if self.fluid_loader_state.number == 8 and self.lights_button.image != self.turn_on_image:
                self.set_button_inactive(self.lights_button)
            elif self.fluid_loader_state.number == 9 and self.lights_button.image != self.turn_off_image:
                self.set_button_active(self.lights_button)

    def switch_state(self, state: AccessoryState) -> None:
        pass

    def toggle_lights(self) -> None:
        with self._cv:
            if self.lights_button.image == self.turn_on_image:
                CommandReq(TMCC1AuxCommandEnum.NUMERIC, self._tmcc_id, data=9).send()
            elif self.lights_button.image == self.turn_off_image:
                CommandReq(TMCC1AuxCommandEnum.NUMERIC, self._tmcc_id, data=8).send()

    def build_accessory_controls(self, box: Box) -> None:
        max_text_len = len("Droplet") + 2
        col = 0
        self.lights_button = self.make_power_button(self.fluid_loader_state, "Lights", col, max_text_len, box)
        self.lights_button.update_command(self.toggle_lights)
        col += 1
