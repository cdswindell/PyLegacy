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
    "sinclair operating gas station 30-9101": "Sinclair-Operating-Gas-Station-30-9101.jpg",
}

TITLES = {
    "Sinclair-Operating-Gas-Station-30-9101.jpg": "Sinclair Gas Station",
}


class GasStationGui(AccessoryBase):
    def __init__(
        self,
        power: int,
        alarm: int,
        variant: str = None,
        *,
        aggrigator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a MTH Gas Station.

        :param int power:
            TMCC ID of the ACS2 port used to power the station.

        :param int alarm:
            TMCC ID of the ACS2 port used to trigger the Animation.

        :param str variant:
            Optional; Specifies the variant (Sinclair).
        """
        # identify the accessory
        self._title, self._image = self.get_variant(variant)
        self._power = power
        self._alarm = alarm
        self._variant = variant
        self.power_button = self.car_button = None
        self.power_state = self.car_state = None
        self.car_image = find_file("garage-car.png")
        super().__init__(self._title, self._image, aggrigator=aggrigator)

    @staticmethod
    def get_variant(variant) -> tuple[str, str]:
        if variant is None:
            variant = "mth fire station"
        variant = variant.lower().replace("'", "").replace("-", "")
        for k, v in VARIANTS.items():
            if variant in k:
                title = TITLES[v]
                return title, find_file(v)
        raise ValueError(f"Unsupported fire station: {variant}")

    def get_target_states(self) -> list[S]:
        self.power_state = self._state_store.get_state(CommandScope.ACC, self._power)
        self.car_state = self._state_store.get_state(CommandScope.ACC, self._alarm)
        return [
            self.power_state,
            self.car_state,
        ]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: AccessoryState) -> None:
        with self._cv:
            if state == self.car_state:
                pass
            elif state.is_aux_on:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()
                if state == self.power_state:
                    self.queue_message(lambda: self.car_button.disable())
            else:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()
                if state == self.power_state:
                    self.queue_message(lambda: self.car_button.enable())

    def build_accessory_controls(self, box: Box) -> None:
        max_text_len = len("Conveyor") + 2
        self.power_button = self.make_power_button(self.power_state, "Power", 0, max_text_len, box)

        alarm_box = Box(box, layout="auto", border=2, grid=[1, 0], align="top")
        tb = Text(alarm_box, text="Garage", align="top", size=self.s_16, underline=True)
        tb.width = max_text_len
        self.car_button = PushButton(
            alarm_box,
            image=self.car_image,
            align="top",
            height=self.s_72,
            width=self.s_72,
        )
        self.car_button.when_left_button_pressed = self.when_pressed
        self.car_button.when_left_button_released = self.when_released
        self.register_widget(self.car_state, self.car_button)
        if not self.is_active(self.power_state):
            self.car_button.disable()
