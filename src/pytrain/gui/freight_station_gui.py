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
    "adolph coors brewing co 30-9161": "Adolph-Coors-Brewing-Co-30-9161.jpg",
    "altoona brewing co 30-90191": "Altoona-Brewing-CO-30-90191.jpg",
    "budweiser 30-9171": "Budweiser-30-9171.jpg",
    "middletown freight station 30-9184": "Middletown-Freight-Station-30-9184.jpg",
    "middletown military station 30-9183": "Middletown-Military-Station-30-9183.jpg",
    "middletown passenger station 30-9125": "Middletown-Passenger-Station-30-9125.jpg",
    "new york central freight station 30-9151": "New-York-Central-Freight-Station-30-9151.jpg",
    "new york central passenger station 30-9164": "New-York-Central-Passenger-Station-30-9164.jpg",
    "old reading brewing co 30-90190": "Old-Reading-Brewing-Co-30-90190.jpg",
    "pennsylvania railroad prr 30-9152": "Pennsylvania-Railroad-PRR-30-9152.jpg",
    "pittsburgh brewing co 30-90189": "Pittsburgh-Brewing-Co-30-90189.jpg",
}

TITLES = {
    "Adolph-Coors-Brewing-Co-30-9161.jpg": "Adolph Coors Brewing Co.",
    "Altoona-Brewing-CO-30-90191.jpg": "Altoona Brewing Co.",
    "Budweiser-30-9171.jpg": "Budweiser",
    "Middletown-Freight-Station-30-9184.jpg": "Middletown Freight Station",
    "Middletown-Military-Station-30-9183.jpg": "Middletown Station",
    "Middletown-Passenger-Station-30-9125.jpg": "Middletown Station",
    "New-York-Central-Freight-Station-30-9151.jpg": "New York Central Freight Station",
    "New-York-Central-Passenger-Station-30-9164.jpg": "New York Central Station",
    "Old-Reading-Brewing-Co-30-90190.jpg": "Old Reading Brewing Co.",
    "Pennsylvania-Railroad-PRR-30-9152.jpg": "Pennsylvania Railroad",
    "Pittsburgh-Brewing-Co-30-90189.jpg": "Pittsburgh Brewing Co.",
}


class FreightStationGui(AccessoryBase):
    def __init__(
        self,
        power: int,
        platform: int,
        variant: str = None,
        *,
        aggrigator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a K-Line Freight/Passenger Station.

        :param int power:
            TMCC ID of the ACS2 port used to power the freight depot.

        :param int platform:
            TMCC ID of the ACS2 port used to control the platform.

        :param str variant:
            Optional; Specifies the variant (Middletown, Military, etc.).
        """

        # identify the accessory
        self._title, self._image = self.get_variant(variant)
        self._power = power
        self._platform = platform
        self._variant = variant
        self.power_button = self.platform_button = None
        self.power_state = self.platform_state = None
        super().__init__(self._title, self._image, aggrigator=aggrigator)

    @staticmethod
    def get_variant(variant) -> tuple[str, str]:
        if variant is None:
            variant = "Middletown Passenger"
        variant = variant.lower().replace("'", "").replace("-", "")
        for k, v in VARIANTS.items():
            if variant in k:
                title = TITLES[v]
                return title, find_file(v)
        raise ValueError(f"Unsupported freight/passenger station: {variant}")

    def get_target_states(self) -> list[S]:
        self.power_state = self._state_store.get_state(CommandScope.ACC, self._power)
        self.platform_state = self._state_store.get_state(CommandScope.ACC, self._platform)
        return [
            self.power_state,
            self.platform_state,
        ]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: AccessoryState) -> None:
        with self._cv:
            if state.is_aux_on:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()
                if state == self.power_state:
                    self.queue_message(lambda: self.platform_button.disable())
            else:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()
                if state == self.power_state:
                    self.queue_message(lambda: self.platform_button.enable())

    def build_accessory_controls(self, box: Box) -> None:
        max_text_len = len("Platform") + 2
        self.power_button = self.make_power_button(self.power_state, "Power", 0, max_text_len, box)
        self.platform_button = self.make_power_button(self.platform_state, "Platform", 1, max_text_len, box)
        if not self.is_active(self.power_state):
            self.platform_button.disable()
