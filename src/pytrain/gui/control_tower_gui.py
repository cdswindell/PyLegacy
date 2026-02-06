#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from typing import cast

from guizero import Box, PushButton

from .accessories.accessory_type import AccessoryType
from .accessory_base import AccessoryBase, AnimatedButton, PowerButton, S
from .accessory_gui import AccessoryGui
from ..db.accessory_state import AccessoryState
from ..utils.path_utils import find_file


class ControlTowerGui(AccessoryBase):
    ACCESSORY_TYPE = AccessoryType.CONTROL_TOWER

    def __init__(
        self,
        power: int,
        action: int,
        variant: str = None,
        *,
        aggregator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a Lionel Control Tower.

        :param int power:
            TMCC ID of the ACS2 port used for lights/power.

        :param int action:
            TMCC ID of the ACS2 port used to trigger motion.

        :param str variant:
            Optional; Specifies the variant (NASA, Yellow, Orange, Red, Radio, etc.).
        """
        # identify the accessory
        self._power = power
        self._action = action
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
        self._action_image = find_file(self.config.image_for("action", "loaded.png"))

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
            self.after_state_change(None, state)

    def after_state_change(self, button: PushButton | None, state: AccessoryState) -> None:
        if state == self.power_state:
            self.gate_widget_on_power(self.power_state, self.action_button)

    def build_accessory_controls(self, box: Box) -> None:
        assert self.config is not None
        power_label, action_label = self.config.labels_for("power", "action")

        max_text_len = max(len(power_label), len(action_label)) + 2
        self.power_button = self.make_power_button(self.power_state, power_label, 0, max_text_len, box)

        self.action_button = self.make_push_button(
            box,
            state=self.action_state,
            label=action_label,
            col=1,
            text_len=max_text_len,
            image=self._action_image,
            button_cls=AnimatedButton,
        )
        cast(AnimatedButton, self.action_button).stop_animation()

        # Robust initial gating
        self.after_state_change(None, self.power_state)

    def set_button_active(self, button: AnimatedButton) -> None:
        with self._cv:
            if isinstance(button, PowerButton):
                super().set_button_active(button)
            else:
                button.start_animation()

    def set_button_inactive(self, button: AnimatedButton) -> None:
        with self._cv:
            if isinstance(button, PowerButton):
                super().set_button_inactive(button)
            else:
                button.image = self._action_image
                button.height = button.width = self.s_72
                button.stop_animation()
