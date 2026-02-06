#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from typing import cast

from guizero import Box

from .accessory_base import AccessoryBase, AnimatedButton, PowerButton, S
from .accessory_gui import AccessoryGui
from .accessory_type import AccessoryType
from ...db.accessory_state import AccessoryState
from ...utils.path_utils import find_file


class ConstructionGui(AccessoryBase):
    ACCESSORY_TYPE = AccessoryType.CONSTRUCTION

    def __init__(
        self,
        action: int,
        variant: str = None,
        *,
        aggregator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a K-Line Backhoe Construction Scene.

        :param int action:
            TMCC ID of the culvert loader/unloader.

        :param str variant:
            Optional; Specifies the variant (Backhoe).
        """

        # identify the accessory
        self._action = action
        self._variant = variant
        self._action_button = None
        self._action_state = None

        # Main title + image + eject image (resolved in bind_variant)
        self._title: str | None = None
        self._image: str | None = None
        self._action_image: str | None = None
        self._action_label: str | None = None

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
            tmcc_ids={"action": self._action},
        )

        # Pre-resolve action image (momentary)
        self._action_image = find_file(self.config.image_for("action"))
        self._action_label = self.config.label_for("action")

    def get_target_states(self) -> list[S]:
        self._action_state = self.state_for("action")
        return [self._action_state]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: AccessoryState) -> None:
        pass

    def build_accessory_controls(self, box: Box) -> None:
        assert self.config is not None
        action_label = self.config.label_for("action")
        max_text_len = len(action_label) + 2

        self._action_button = self.make_push_button(
            box,
            state=self._action_state,
            label=action_label,
            col=1,
            text_len=max_text_len,
            image=self._action_image,
            button_cls=AnimatedButton,
        )
        cast(AnimatedButton, self._action_button).stop_animation()

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
