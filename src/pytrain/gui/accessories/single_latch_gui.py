#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#
#
from tkinter import Widget

from guizero import Box, PushButton

from .accessory_base import AccessoryBase, S
from .accessory_gui import AccessoryGui
from .accessory_type import AccessoryType
from ...db.accessory_state import AccessoryState
from ...utils.path_utils import find_file


class SingleLatchGui(AccessoryBase):
    ACCESSORY_TYPE = AccessoryType.SINGLE_LATCH

    def __init__(
        self,
        power: int,
        variant: str = None,
        *,
        aggregator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a Single Latch Accessories.

        :param int power:
            TMCC ID of the ACS2 port used for power.

        :param str variant:
            Optional; Specifies the variant (Hobo Depot).
        """

        # identify the accessory
        self._power = power
        self._variant = variant
        self._power_on_image = None
        self._power_off_image = None
        self._power_button = None
        self._power_state = None

        # Main title + image + eject image (resolved in bind_variant)
        self._title: str | None = None
        self._image: str | None = None
        self._power_label: str | None = None

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
            tmcc_ids={"power": self._power},
        )

        # Pre-resolve action image (momentary)
        self._power_off_image = find_file(self.config.off_image_for("power", "off_button.jpg"))
        self._power_on_image = find_file(self.config.on_image_for("power", "on_button.jpg"))

        self._power_label = self.config.label_for("power")

    def get_target_states(self) -> list[S]:
        self._power_state = self.state_for("power")
        return [self._power_state]

    # noinspection method-may-be-static
    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: AccessoryState) -> bool:
        with self._cv:
            self.toggle_latch(state)
            self.after_state_change(None, state)

    def after_state_change(self, button: PushButton | None, state: AccessoryState) -> None:
        # Updates platform button based on platform state
        if state == self._power_state:
            assert button == self._power_button
            if self.is_active(self._power_state):
                self.set_button_inactive(button)
            else:
                self.set_button_active(button)

    def build_accessory_controls(self, box: Box) -> None:
        assert self.config is not None
        power_label = self.config.label_for("power")
        max_text_len = len(power_label) + 2

        self._power_button = self.make_power_button(
            self._power_state,
            self._power_label,
            1,
            max_text_len,
            box,
            turn_on_image=self._power_on_image,
            turn_off_image=self._power_off_image,
        )

    # noinspection PyTypeChecker
    def set_button_inactive(self, widget: Widget | set[Widget] | None = None):
        if widget is None:
            return
        elif widget == self._power_button:
            self._power_button.image = self._power_off_image
            self._power_button.height = self._power_button.width = self.s_acc
        else:
            super().set_button_inactive(widget)

    # noinspection PyTypeChecker
    def set_button_active(self, widget: Widget | set[Widget] | None = None):
        if widget is None:
            return
        elif widget == self._power_button:
            self._power_button.image = self._power_on_image
            self._power_button.height = self._power_button.width = self.s_acc
        else:
            super().set_button_active(widget)
