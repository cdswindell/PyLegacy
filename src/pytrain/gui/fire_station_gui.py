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

VARIANTS = {
    "mth fire station": "Fire-Station-MTH-30-9157.jpg",
}

TITLES = {
    "Fire-Station-MTH-30-9157.jpg": "MTH Fire Station",
}


class FireStationGui(AccessoryBase):
    def __init__(self, power: int, alarm: int, variant: str = "MTH"):
        # identify the accessory
        self._title, self._image = self.get_variant(variant)
        self._power = power
        self._alarm = alarm
        self._variant = variant
        self.power_button = self.alarm_button = None
        self.power_state = self.alarm_state = None
        self._current_alarm_tk_image = None
        super().__init__(self._title, self._image)

    @staticmethod
    def get_variant(variant) -> tuple[str, str]:
        variant = variant.lower().replace("'", "").replace("-", "")
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
        with self._cv:
            if state == self.alarm_state:
                pass
            elif state.is_aux_on:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()
                if state == self.power_state:
                    self.queue_message(lambda: self.alarm_button.disable())
            else:
                CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()
                if state == self.power_state:
                    self.queue_message(lambda: self.alarm_button.enable())

    def build_accessory_controls(self, box: Box) -> None:
        max_text_len = len("Conveyor") + 2
        self.power_button = self.make_power_button(self.power_state, "Power", 0, max_text_len, box)

        alarm_box = Box(box, layout="auto", border=2, grid=[1, 0], align="top")
        tb = Text(alarm_box, text="Alarm", align="top", size=self.s_16, underline=True)
        tb.width = max_text_len
        self.alarm_button = PushButton(
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
        # Store reference to track the current PhotoImage
        self._current_alarm_tk_image = None

    def post_process_when_pressed(self, button: PushButton, state: AccessoryState) -> None:
        if button == self.alarm_button:
            self.queue_message(lambda: self._twiddle_alarm_button_image())

    # noinspection PyProtectedMember
    def _twiddle_alarm_button_image(self) -> None:
        """
        This method must only be called from the guizero main event loop
        """
        print(f"Twiddling alarm button: {self.alarm_button.image}")
        if self.alarm_button.image == self.alarm_off_image:
            # Switch to animated gif
            self.alarm_button.image = self.alarm_on_image
            self.alarm_button.height = self.alarm_button.width = self.s_72
            # Store reference to the tkinter PhotoImage
            self._current_alarm_tk_image = self.alarm_button.tk.cget("image")
            self.app.after(2500, self._twiddle_alarm_button_image)
        else:
            # Stop the animated GIF by blanking the widget first
            tk_button = self.alarm_button.tk
            # Get the current PhotoImage name
            if self._current_alarm_tk_image:
                try:
                    # Blank the image on the widget
                    tk_button.config(image="")
                    # Delete the PhotoImage to stop animation
                    self.alarm_button._image.blank()
                except (AttributeError, RuntimeError, KeyError) as e:
                    print(f"Warning: Could not blank image: {e}")
            # Now set the static image
            self.alarm_button.image = self.alarm_off_image
            self.alarm_button.height = self.alarm_button.width = self.s_72
            self._current_alarm_tk_image = None
        print(f"Now: {self.alarm_button.image}")
