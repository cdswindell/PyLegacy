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
from .accessory_base import AccessoryBase, PowerButton, S

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
        self.power_button = self.conveyor_button = self.eject_button = None
        self.power_state = self.conveyor_state = self.eject_state = None
        self.eject_image = find_file("depot-milk-can-eject.jpeg")
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

    def build_accessory_controls(self, panel: Box) -> None:
        max_text_len = len("Conveyor") + 4
        box = Box(panel, layout="grid")
        power_box = Box(box, layout="auto", border=2, grid=[0, 0], align="top")
        tb = Text(power_box, text="Power", align="top", size=self.s_16, underline=True)
        tb.width = max_text_len
        self.power_button = PowerButton(
            power_box,
            image=self.turn_on_button,
            align="top",
            height=self.s_72,
            width=self.s_72,
        )
        self.register_widget(self.power_state, self.power_button)

        conveyor_box = Box(box, layout="auto", border=2, grid=[1, 0], align="top")
        tb = Text(conveyor_box, text="Conveyor", align="top", size=self.s_16, underline=True)
        tb.width = max_text_len
        self.conveyor_button = PowerButton(
            conveyor_box,
            image=self.turn_on_button,
            align="top",
            height=self.s_72,
            width=self.s_72,
        )
        self.register_widget(self.conveyor_state, self.conveyor_button)
        self.app.update()

        eject_box = Box(box, layout="auto", border=2, grid=[2, 0], align="top")
        tb = Text(eject_box, text="Eject", align="top", size=self.s_16, underline=True)
        tb.width = max_text_len
        self.eject_button = PushButton(
            eject_box,
            image=self.eject_image,
            align="top",
            height=self.s_72,
            width=self.s_72,
        )

        for child in box.children:
            child.padding = 5
