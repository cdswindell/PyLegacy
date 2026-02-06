#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from guizero import Box, PushButton

from .accessory_base import AccessoryBase, S
from .accessory_gui import AccessoryGui
from .accessory_type import AccessoryType
from ...db.accessory_state import AccessoryState


class HobbyShopGui(AccessoryBase):
    ACCESSORY_TYPE = AccessoryType.HOBBY_SHOP

    def __init__(
        self,
        power: int,
        action: int,
        variant: str = None,
        *,
        aggregator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a Lionel Hobby Shop.

        :param int power:
            TMCC ID of the ACS2 port used to power the hobby shop.

        :param int action:
            TMCC ID of the ACS2 port used to control the action.

        :param str variant:
            Optional; Specifies the variant (Lionelville, Madison, Midtown).
        """

        # identify the accessory
        self._power = int(power)
        self._action = int(action)
        self._variant = variant
        self.power_button = self.action_button = None
        self.power_state = self.action_state = None

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
            tmcc_ids={"power": self._power, "action": self._action},
        )

    def get_target_states(self) -> list[S]:
        assert self.config is not None

        self.power_state = self.state_for("power")
        self.action_state = self.state_for("action")
        return [
            self.power_state,
            self.action_state,
        ]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux2_on

    def switch_state(self, state: AccessoryState) -> None:
        with self._cv:
            self.toggle_latch(state)
            self.after_state_change(None, state)

    def after_state_change(self, button: PushButton | None, state: AccessoryState) -> None:
        if state == self.power_state:
            self.gate_widget_on_power(self.power_state, self.action_button)

    def build_accessory_controls(self, box: Box) -> None:
        assert self.config is not None
        power_label, action_label = self.config.labels_for("power", "action")
        max_text_len = max(len(power_label), len(action_label)) + 2

        self.power_button = self.make_power_button(self.power_state, power_label, 0, max_text_len, box)
        self.action_button = self.make_power_button(self.action_state, action_label, 1, max_text_len, box)

        # Robust initial gating
        self.after_state_change(None, self.power_state)
