#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from guizero import Box, PushButton, Text

from ..db.accessory_state import AccessoryState
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ..utils.path_utils import find_file
from .accessory_base import AccessoryBase, S
from .accessory_gui import AccessoryGui

VARIANTS = {
    "k lineville freight depot k-42418": "K-Lineville-Freight-Depot-K-42418.jpg",
}

TITLES = {
    "K-Lineville-Freight-Depot-K-42418.jpg": "Lineville Freight Depot",
}


class FreightDepotGui(AccessoryBase):
    def __init__(
        self,
        power: int,
        conveyor: int,
        eject: int,
        variant: str = None,
        *,
        aggrigator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a K-Line Freight Depot.

        :param int power:
            TMCC ID of the ACS2 port used to power the freight depot.

        :param int conveyor:
            TMCC ID of the ACS2 port used to control the conveyor belt.

        :param int eject:
            TMCC ID of the ACS2 port used to eject a package.

        :param str variant:
            Optional; Specifies the variant (K-line, ).
        """

        # identify the accessory
        self._title, self._image = self.get_variant(variant)
        self._power = power
        self._conveyor = conveyor
        self._eject = eject
        self._variant = variant
        self.power_button = self.conveyor_button = self.eject_button = None
        self.power_state = self.conveyor_state = self.eject_state = None
        self.eject_image = find_file("Man-With-Handcart.png")
        super().__init__(self._title, self._image, aggrigator=aggrigator)

    @staticmethod
    def get_variant(variant) -> tuple[str, str]:
        if variant is None:
            variant = "K Line"
        variant = FreightDepotGui.normalize(variant)
        for k, v in VARIANTS.items():
            if variant in k:
                title = TITLES[v]
                return title, find_file(v)
        raise ValueError(f"Unsupported freight depot: {variant}")

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

    def switch_state(self, state: AccessoryState) -> None:
        with self._cv:
            if state == self.eject_state:
                pass
            elif state.is_aux_on:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()
                if state == self.power_state:
                    self.queue_message(lambda: self.eject_button.disable())
            else:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()
                if state == self.power_state:
                    self.queue_message(lambda: self.eject_button.enable())

    def build_accessory_controls(self, box: Box) -> None:
        max_text_len = len("Conveyor") + 2
        self.power_button = self.make_power_button(self.power_state, "Power", 0, max_text_len, box)
        self.conveyor_button = self.make_power_button(self.conveyor_state, "Conveyor", 1, max_text_len, box)

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
        self.eject_button.bg = "white"
        self.eject_button.when_left_button_pressed = self.when_pressed
        self.eject_button.when_left_button_released = self.when_released
        self.register_widget(self.eject_state, self.eject_button)
        if not self.is_active(self.power_state):
            self.eject_button.disable()
