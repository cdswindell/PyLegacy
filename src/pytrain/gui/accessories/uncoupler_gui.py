#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from guizero import Box

from .accessory_base import AccessoryBase, S
from .accessory_gui import AccessoryGui
from .accessory_type import AccessoryType
from ...db.accessory_state import AccessoryState
from ...utils.path_utils import find_file


class UncouplerGui(AccessoryBase):
    ACCESSORY_TYPE = AccessoryType.UNCOUPLER

    def __init__(
        self,
        uncouple: int,
        variant: str = None,
        *,
        aggregator: AccessoryGui = None,
    ):
        """
        Create a GUI to control Lionel Uncoupling Track.

        :param int uncouple:
            TMCC ID of the ACS2 port used for uncouple action.

        :param str variant:
            Optional; Specifies the variant (only one).
        """

        # identify the accessory
        self._uncouple = uncouple
        self._variant = variant
        self._uncouple_button = None
        self._uncouple_state = None

        # Main title + image + eject image (resolved in bind_variant)
        self._title: str | None = None
        self._image: str | None = None
        self._uncouple_image: str | None = None

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
            tmcc_ids={"uncouple": self._uncouple},
        )

        # Pre-resolve action image (momentary)
        self._uncouple_image = find_file(self.config.image_for("uncouple"))

    def get_target_states(self) -> list[S]:
        self._uncouple_state = self.state_for("uncouple")
        return [self._uncouple_state]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: AccessoryState) -> bool:
        return False

    def build_accessory_controls(self, box: Box) -> None:
        assert self.config is not None
        motion_label = self.config.label_for("uncouple")
        size = self.config.size_for("uncouple")
        max_text_len = len(motion_label) + 2

        self._uncouple_button = self.make_push_button(
            box,
            state=self._uncouple_state,
            label=motion_label,
            col=1,
            text_len=max_text_len,
            image=self._uncouple_image,
            height=size[0],
            width=size[1],
        )
