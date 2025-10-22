#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from guizero import Box, PushButton, Text

from ..db.accessory_state import AccessoryState
from ..protocol.constants import CommandScope
from ..utils.path_utils import find_file
from .accessory_base import AccessoryBase, S

VARIANTS = {
    "dairymens league 6-14291": "Dairymens-League-6-14291.jpg",
    "moose pond creamery 6-22660": "Moose-Pond-Creamery-6-22660.jpg",
    "mountain view creamery 6-21675": "Mountain-View-Creamery-6-21675.jpg",
}

TITLES = {
    "Dairymens-League-6-14291.jpg": "Dairymen's League",
    "Moose-Pond-Creamery-6-22660.jpg": "Moose Pond Creamery",
    "Mountain-View-Creamery-6-21675.jpg": "Mountain View Creamery",
}


class MilkLoaderGui(AccessoryBase):
    def __init__(self, power: int, conveyor: int, eject: int, variant: str = "Moose Pond"):
        # identify the accessory
        self._title, self._image = self.get_variant(variant)
        self._power = power
        self._conveyor = conveyor
        self._eject = eject
        self._variant = variant
        self.power_button = None
        self.power_state = self.conveyor_state = self.eject_state = None
        super().__init__(self._title, self._image)

    @staticmethod
    def get_variant(variant) -> tuple[str, str]:
        variant = variant.lower().replace("'", "")
        for k, v in VARIANTS.items():
            if variant in k:
                title = TITLES[v]
                return title, find_file(v)
        raise ValueError(f"Unsupported milk loader: {variant}")

    def get_target_states(self) -> list[S]:
        self.power_state = self._state_store.get_state(CommandScope.ACC, self._power)
        self.conveyor_state = self._state_store.get_state(CommandScope.ACC, self._conveyor)
        self.eject_state = self._state_store.get_state(CommandScope.ACC, self._eject)
        return [
            self.power_state,
            self.conveyor_state,
            self.eject_state,
        ]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: S) -> bool:
        pass

    def build_accessory_controls(self, box: Box) -> None:
        power_box = Box(box, layout="grid", border=2, align="left")
        _ = Text(power_box, text="Power", grid=[0, 0], size=self.s_16, underline=True)
        self.power_button = PushButton(
            power_box,
            image=self.on_button,
            grid=[0, 1],
            height=self.s_72,
            width=self.s_72,
        )
