#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#
#  SPDX-License-Identifier: LPGL
#
from guizero import Box

from .accessory_base import AccessoryBase, S
from .accessory_gui import AccessoryGui
from .accessory_type import AccessoryType
from ...db.accessory_state import AccessoryState
from ...protocol.command_req import CommandReq
from ...protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ...utils.path_utils import find_file


class CulvertGui(AccessoryBase):
    ACCESSORY_TYPE = AccessoryType.CULVERT_HANDLER

    def __init__(
        self,
        action: int,
        variant: str = None,
        *,
        aggregator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a Lionel Command Control Culvert Loader/Unloader.

        :param int action:
            TMCC ID of the culvert loader/unloader.

        :param str variant:
            Optional; Specifies the variant (Moose Pond, Dairymen's League, Mountain View).
        """

        # identify the accessory
        self._action = action
        self._variant = variant
        self._action_button = None
        self._action_state = None
        self._action_image = None
        self._action_label = None

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
            tmcc_ids={"action": self._action},
        )

        # Pre-resolve action image
        self._action_image = find_file(self.config.image_for("action"))
        self._action_label = self.config.label_for("action")

    def get_target_states(self) -> list[S]:
        self._action_state = self.state_for("action")
        return [self._action_state]

    def is_active(self, state: AccessoryState) -> bool:
        return False

    def switch_state(self, state: AccessoryState) -> None:
        pass

    def build_accessory_controls(self, box: Box) -> None:
        assert self.config is not None
        max_text_len = len(self._action_label) + 2

        self._action_button = ab = self.make_push_button(
            box,
            state=self._action_state,
            label=self._action_label,
            image=self._action_image,
            col=1,
            text_len=max_text_len,
            is_momentary=False,
        )
        ab.update_command(self.on_action)

    def on_action(self) -> None:
        CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, self._action).send()
