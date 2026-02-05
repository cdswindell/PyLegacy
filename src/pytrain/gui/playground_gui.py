#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from typing import cast

from guizero import Box

from .accessories.accessory_type import AccessoryType
from .accessory_base import AccessoryBase, AnimatedButton, S
from .accessory_gui import AccessoryGui
from ..db.accessory_state import AccessoryState
from ..utils.path_utils import find_file


class PlaygroundGui(AccessoryBase):
    ACCESSORY_TYPE = AccessoryType.PLAYGROUND

    def __init__(
        self,
        motion: int,
        variant: str = None,
        *,
        aggregator: AccessoryGui = None,
    ):
        """
        Create a GUI to control Lionel Plug n Play Playground Accessories.

        :param int motion:
            MCC ID of the ACS2 port used for action motion.

        :param str variant:
            Optional; Specifies the variant (Tree Swing).
        """

        # identify the accessory
        self._motion = motion
        self._variant = variant
        self._motion_button = None
        self._motion_state = None

        # Main title + image + eject image (resolved in bind_variant)
        self._title: str | None = None
        self._image: str | None = None
        self._motion_image: str | None = None
        self._motion_label: str | None = None

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
            tmcc_ids={"motion": self._motion},
        )

        # Pre-resolve action image (momentary)
        self._motion_image = find_file(self.config.image_for("motion"))
        self._motion_label = self.config.label_for("motion")

    def get_target_states(self) -> list[S]:
        self._motion_state = self.state_for("motion")
        return [self._motion_state]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: AccessoryState) -> None:
        pass

    def build_accessory_controls(self, box: Box) -> None:
        assert self.config is not None
        motion_label = self.config.label_for("motion")
        max_text_len = len(motion_label) + 2

        self._motion_button = self.make_momentary_button(
            box,
            state=self._motion_state,
            label=motion_label,
            col=1,
            text_len=max_text_len,
            image=self._motion_image,
            button_cls=AnimatedButton,
        )
        cast(AnimatedButton, self._motion_button).stop_animation()
