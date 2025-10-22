#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
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
    def get_target_states(self) -> list[S]:
        return [
            self._state_store.get_state(CommandScope.ACC, self._power),
            self._state_store.get_state(CommandScope.ACC, self._conveyor),
            self._state_store.get_state(CommandScope.ACC, self._eject),
        ]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: S) -> bool:
        pass

    def build_accessory_controls(self) -> None:
        pass

    def __init__(self, power: int, conveyor: int, eject: int, variant: str = "Moose Pond"):
        # identify the accessory
        self._title, self._image = self.get_variant(variant)
        self._power = power
        self._conveyor = conveyor
        self._eject = eject
        self._variant = variant
        super().__init__(self._title, self._image)

    @staticmethod
    def get_variant(variant) -> tuple[str, str]:
        variant = variant.lower().replace("'", "")
        for k, v in VARIANTS.items():
            if variant in k:
                title = TITLES[v]
                return title, find_file(v)
        raise ValueError(f"Unknown milk loader: {variant}")
