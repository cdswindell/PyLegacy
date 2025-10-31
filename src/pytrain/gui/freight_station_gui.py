#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from tkinter import Widget

from guizero import Box, PushButton, Text

from ..db.accessory_state import AccessoryState
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ..utils.path_utils import find_file
from .accessory_base import AccessoryBase, PowerButton, S
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
    "pennsylvania railroad prr passenger 30-9152": "Pennsylvania-Railroad-PRR-30-9152.jpg",
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

FREIGHT = {
    "Middletown-Freight-Station-30-9184.jpg",
    "New-York-Central-Freight-Station-30-9151.jpg",
}

PASSENGER = {
    "Middletown-Passenger-Station-30-9125.jpg",
    "Middletown-Military-Station-30-9125.jpg",
    "New-York-Central-Passenger-Station-30-9164.jpg",
    "Pennsylvania-Railroad-PRR-30-9152.jpg",
}

BREWING = {
    "Adolph-Coors-Brewing-Co-30-9161.jpg",
    "Altoona-Brewing-CO-30-90191.jpg",
    "Budweiser-30-9171.jpg",
    "Old-Reading-Brewing-Co-30-90190.jpg",
    "Pittsburgh-Brewing-Co-30-90189.jpg",
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
        self._title, self.image_key = self.get_variant(variant)
        image = find_file(self.image_key)
        self._power = power
        self._platform = platform
        self._variant = variant
        self.power_button = self.platform_button = None
        self.power_state = self.platform_state = None
        self._platform_text = None
        self.brews_image = find_file("brews-waiting.png")
        self.freight_image = find_file("freight-waiting.jpg")
        self.people_image = find_file("passengers-waiting.png")
        self.empty_image = find_file("loaded.png")
        super().__init__(self._title, image, aggrigator=aggrigator)

    @staticmethod
    def get_variant(variant) -> tuple[str, str]:
        if variant is None:
            variant = "Middletown Passenger"
        variant = FreightStationGui.normalize(variant)
        for k, v in VARIANTS.items():
            if variant in k:
                title = TITLES[v]
                return title, v
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
        max_text_len = len("Depart") + 2
        self.power_button = self.make_power_button(self.power_state, "Power", 0, max_text_len, box)
        btn_box = Box(box, layout="auto", border=2, grid=[1, 0], align="top")
        self._platform_text = tb = Text(btn_box, text="Depart", align="top", size=self.s_16, underline=True)
        tb.width = max_text_len
        self.platform_button = button = PushButton(
            btn_box,
            image=self.empty_image,
            align="top",
            height=self.s_72,
            width=self.s_72,
        )
        button.tmcc_id = self.platform_state.tmcc_id
        button.update_command(self.when_platform_button_pressed)
        self.register_widget(self.platform_state, button)
        if not self.is_active(self.power_state):
            self.platform_button.disable()

    @property
    def waiting_image(self) -> str:
        if self.image_key in FREIGHT:
            return self.freight_image
        elif self.image_key in PASSENGER:
            return self.people_image
        elif self.image_key in BREWING:
            return self.brews_image
        raise ValueError(f"Unsupported image: {self.image_key}")

    def when_platform_button_pressed(self) -> None:
        with self._cv:
            if not self.is_active(self.power_state):
                self.queue_message(lambda: self.platform_button.disable())
            else:
                if self.platform_button.image == self.empty_image:
                    self.set_button_active(self.platform_button)
                else:
                    self.set_button_inactive(self.platform_button)
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, self.platform_state.tmcc_id).send()

    # noinspection PyTypeChecker
    def set_button_inactive(self, widget: Widget):
        if isinstance(widget, PowerButton):
            super().set_button_inactive(widget)
        elif widget == self.platform_button:
            self._platform_text.value = "Depart"
            self.platform_button.image = self.empty_image
            self.platform_button.height = self.platform_button.width = self.s_72

    # noinspection PyTypeChecker
    def set_button_active(self, widget: Widget):
        if isinstance(widget, PowerButton):
            super().set_button_active(widget)
        elif widget == self.platform_button:
            self._platform_text.value = "Arrive"
            self.platform_button.image = self.waiting_image
            self.platform_button.height = self.platform_button.width = self.s_72
