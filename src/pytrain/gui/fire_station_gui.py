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
from .accessory_base import AccessoryBase, AnimatedButton, PowerButton, S
from .accessory_gui import AccessoryGui

VARIANTS = {
    "mth fire station 30-9157": "Fire-Station-MTH-30-9157.jpg",
}

TITLES = {
    "Fire-Station-MTH-30-9157.jpg": "MTH Fire Station",
}


class FireStationGui(AccessoryBase):
    def __init__(
        self,
        power: int,
        alarm: int,
        variant: str = None,
        *,
        aggrigator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a MTH Fire Station.

        :param int power:
            TMCC ID of the ACS2 port used to power the station.

        :param int alarm:
            TMCC ID of the ACS2 port used to trigger the alarm sequence.

        :param str variant:
            Optional; Specifies the variant (MTH Fire Station).
        """
        # identify the accessory
        self._title, self._image = self.get_variant(variant)
        self._power = power
        self._alarm = alarm
        self._variant = variant
        self.power_button = self.alarm_button = None
        self.power_state = self.alarm_state = None
        super().__init__(self._title, self._image, aggrigator=aggrigator)

    @staticmethod
    def get_variant(variant) -> tuple[str, str]:
        if variant is None:
            variant = "mth fire station"
        variant = FireStationGui.normalize(variant)
        for k, v in VARIANTS.items():
            if variant in k:
                title = TITLES[v]
                return title, find_file(v)
        raise ValueError(f"Unsupported fire station: {variant}")

    def get_target_states(self) -> list[S]:
        self.power_state = self._state_store.get_state(CommandScope.ACC, self._power)
        self.alarm_state = self._state_store.get_state(CommandScope.ACC, self._alarm)
        return [
            self.power_state,
            self.alarm_state,
        ]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: AccessoryState) -> None:
        if state == self.alarm_state:
            return
        with self._cv:
            # a bit confusing, but sending this command toggles the power
            if state == self.power_state:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()
                if state.is_aux_on:
                    self.queue_message(lambda: self.alarm_button.disable())
                else:
                    self.queue_message(lambda: self.alarm_button.enable())

    def build_accessory_controls(self, box: Box) -> None:
        max_text_len = len("Conveyor") + 2
        self.power_button = self.make_power_button(self.power_state, "Power", 0, max_text_len, box)

        alarm_box = Box(box, layout="auto", border=2, grid=[1, 0], align="top")
        tb = Text(alarm_box, text="Alarm", align="top", size=self.s_16, underline=True)
        tb.width = max_text_len
        self.alarm_button = AnimatedButton(
            alarm_box,
            image=self.alarm_off_image,
            align="top",
            height=self.s_72,
            width=self.s_72,
        )
        self.alarm_button.when_left_button_pressed = self.when_pressed
        self.alarm_button.when_left_button_released = self.when_released
        self.register_widget(self.alarm_state, self.alarm_button)
        if not self.is_active(self.power_state):
            self.alarm_button.disable()

    def set_button_active(self, button: PushButton) -> None:
        with self._cv:
            if button == self.alarm_button and self.is_active(self.power_state):
                # Switch to animated gif
                self.alarm_button.image = self.alarm_on_image
                self.alarm_button.height = self.alarm_button.width = self.s_72
                self.app.after(5000, self.deactivate_alarm)
            elif isinstance(button, PowerButton):
                super().set_button_active(button)

    def deactivate_alarm(self) -> None:
        with self._cv:
            self.alarm_button.image = self.alarm_off_image
            self.alarm_button.height = self.alarm_button.width = self.s_72
