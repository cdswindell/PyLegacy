#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from guizero import Box, PushButton, Text

from .accessories.accessory_type import AccessoryType
from .accessory_base import AccessoryBase, AnimatedButton, PowerButton, S
from .accessory_gui import AccessoryGui
from ..db.accessory_state import AccessoryState


class FireStationGui(AccessoryBase):
    ACCESSORY_TYPE = AccessoryType.FIRE_STATION

    def __init__(
        self,
        power: int,
        alarm: int,
        variant: str = None,
        *,
        aggregator: AccessoryGui = None,
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
        self._power = power
        self._alarm = alarm
        self._variant = variant
        self.power_button = self.alarm_button = None
        self.power_state = self.alarm_state = None

        # Main title + image + eject image (resolved in bind_variant)
        self._title: str | None = None
        self._image: str | None = None

        super().__init__(self._title, self._image, aggregator=aggregator)

    def bind_variant(self) -> None:
        """
        Resolve all metadata (title, main image, op images) via registry + configure_accessory().

        This keeps the public constructor signature stable while moving all metadata
        to your centralized registry/config pipeline.
        """
        self.configure_from_registry(
            self.ACCESSORY_TYPE,
            self._variant,
            tmcc_ids={"power": self._power, "alarm": self._alarm},
        )

    def get_target_states(self) -> list[S]:
        assert self.config is not None

        self.power_state = self.state_for("power")
        self.alarm_state = self.state_for("alarm")
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
            self.toggle_latch(state)
            self.after_state_change(None, self.power_state)

    def after_state_change(self, button: PushButton | None, state: AccessoryState) -> None:
        if state == self.power_state:
            self.gate_widget_on_power(self.power_state, self.alarm_button)

    def build_accessory_controls(self, box: Box) -> None:
        assert self.config is not None
        power_label, alarm_label = self.config.labels_for("power", "alarm")

        max_text_len = max(len(power_label), len(alarm_label)) + 2
        self.power_button = self.make_power_button(self.power_state, power_label, 0, max_text_len, box)

        alarm_box = Box(box, layout="auto", border=2, grid=[1, 0], align="top")
        tb = Text(alarm_box, text=alarm_label, align="top", size=self.s_16, underline=True)
        tb.width = max_text_len

        height, width = self.config.size_for("alarm", self.s_72)
        self.alarm_button = AnimatedButton(
            alarm_box,
            image=self.alarm_off_image,
            align="top",
            height=height,
            width=width,
        )
        self.alarm_button.when_left_button_pressed = self.when_pressed
        self.alarm_button.when_left_button_released = self.when_released
        self.register_widget(self.alarm_state, self.alarm_button)

        # Robust initial gating
        self.after_state_change(None, self.power_state)

    def set_button_active(self, button: PushButton) -> None:
        with self._cv:
            if button == self.alarm_button and self.is_active(self.power_state):
                # Switch to animated GIF
                self.alarm_button.image = self.alarm_on_image
                self.alarm_button.height = self.alarm_button.width = self.s_72
                self.app.after(5000, self.deactivate_alarm)
            elif isinstance(button, PowerButton):
                super().set_button_active(button)

    def deactivate_alarm(self) -> None:
        with self._cv:
            self.alarm_button.image = self.alarm_off_image
            self.alarm_button.height = self.alarm_button.width = self.s_72
