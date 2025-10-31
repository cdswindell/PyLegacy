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
    "atlantic gas station 30 91003": "Atlantic-Gas-Station-30-91003.jpg",
    "bp gas station 30-9181": "BP-Gas-Station-30-9181.jpg",
    "citgo gas station 30-9113": "Citgo-Gas-Station-30-9113.jpg",
    "esso gas station 30-9106": "Esso-Gas-Station-30-9106.jpg",
    "gulf gas station 30-9168": "Gulf-Gas-Station-30-9168.jpg",
    "mobile gas station 30-9124": "Mobile-Gas-Station-30-9124.jpg",
    "route 66 gas station 30-91002": "Route-66-Gas-Station-30-91002.jpg",
    "shell gas station 30-9182": "Shell-Gas-Station-30-9182.jpg",
    "sinclair gas station 30-9101": "Sinclair-Gas-Station-30-9101.jpg",
    "sunoco gas station 30-9154": "Sunoco-Gas-Station-30-9154.jpg",
    "texaco gas station 30-91001": "Texaco-Gas-Station-30-91001.jpg",
    "tidewater oil gas station 30-9181": "Tidewater-Oil-Gas-Station-30-9181.jpg",
}

TITLES = {
    "Atlantic-Gas-Station-30-91003.jpg": "Atlantic Gas Station",
    "BP-Gas-Station-30-9181.jpg": "BP Gas Station",
    "Citgo-Gas-Station-30-9113.jpg": "Citgo Gas Station",
    "Esso-Gas-Station-30-9106.jpg": "Esso Gas Station",
    "Gulf-Gas-Station-30-9168.jpg": "Gulf Gas Station",
    "Mobile-Gas-Station-30-9124.jpg": "Mobile Gas Station",
    "Route-66-Gas-Station-30-91002.jpg": "Route 66 Gas Station",
    "Shell-Gas-Station-30-9182.jpg": "Shell Gas Station",
    "Sinclair-Gas-Station-30-9101.jpg": "Sinclair Gas Station",
    "Sunoco-Gas-Station-30-9154.jpg": "Sunoco Gas Station",
    "Texaco-Gas-Station-30-91001.jpg": "Texaco Gas Station",
    "Tidewater-Oil-Gas-Station-30-9181.jpg": "Tidewater Oil Gas Station",
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
            Optional; Specifies the variant (Sinclair, Texaco, etc.).
        """
        # identify the accessory
        self._title, self._image = self.get_variant(variant)
        self._power = power
        self._alarm = alarm
        self._variant = variant
        self.power_button = self.car_button = None
        self.power_state = self.car_state = None
        self.car_image = find_file("gas-station-car.png")
        super().__init__(self._title, self._image, aggrigator=aggrigator)

    @staticmethod
    def get_variant(variant) -> tuple[str, str]:
        if variant is None:
            variant = "sinclair"
        variant = GasStationGui.normalize(variant)
        for k, v in VARIANTS.items():
            if variant in k:
                title = TITLES[v]
                return title, find_file(v)
        raise ValueError(f"Unsupported gas station: {variant}")

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
        if state == self.car_state:
            return
        with self._cv:
            # a bit confusing, but sending this command toggles the power
            if state == self.power_state:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()
                if state.is_aux_on:
                    self.queue_message(lambda: self.car_button.disable())
                else:
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
        self.car_button.bg = "white"
        self.car_button.when_left_button_pressed = self.when_pressed
        self.car_button.when_left_button_released = self.when_released
        self.register_widget(self.car_state, self.car_button)
        if not self.is_active(self.power_state):
            self.car_button.disable()
