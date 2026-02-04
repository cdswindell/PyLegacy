#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from guizero import Box, PushButton

from .accessories.accessory_type import AccessoryType
from .accessory_base import AccessoryBase, S
from .accessory_gui import AccessoryGui
from ..db.accessory_state import AccessoryState
from ..utils.path_utils import find_file


class GasStationGui(AccessoryBase):
    ACCESSORY_TYPE = AccessoryType.GAS_STATION

    def __init__(
        self,
        power: int,
        action: int,
        variant: str = None,
        *,
        aggregator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a MTH Gas Station.

        :param int power:
            TMCC ID of the ACS2 port used to power the station.

        :param int action:
            TMCC ID of the ACS2 port used to trigger the Animation.

        :param str variant:
            Optional; Specifies the variant (Sinclair, Texaco, etc.).
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
        self._action_image: str | None = None

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

        # Pre-resolve action image (momentary)
        self._action_image = find_file(self.config.image_for("action", "gas-station-car.png"))

    def get_target_states(self) -> list[S]:
        assert self.config is not None

        self.power_state = self.state_for("power")
        self.action_state = self.state_for("action")
        return [
            self.power_state,
            self.action_state,
        ]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: AccessoryState) -> None:
        if state == self.action_state:
            return  # Action is momentary (press/release handlers)
        with self._cv:
            self.toggle_latch(state)
            self.after_state_change(None, self.power_state)

    def after_state_change(self, button: PushButton | None, state: AccessoryState) -> None:
        if state == self.power_state:
            self.gate_widget_on_power(self.power_state, self.action_button)

    def build_accessory_controls(self, box: Box) -> None:
        assert self.config is not None
        power_label, action_label = self.config.labels_for("power", "action")
        max_text_len = max(len(power_label), len(action_label)) + 2

        self.power_button = self.make_power_button(self.power_state, power_label, 0, max_text_len, box)
        self.action_button = self.make_momentary_button(
            box,
            state=self.action_state,
            label=action_label,
            col=1,
            text_len=max_text_len,
            image=self._action_image,
        )

        # Robust initial gating
        self.after_state_change(None, self.power_state)
