#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
import random

from ..constants import DEFAULT_ADDRESS, CommandScope
from ..multibyte.multibyte_constants import TMCC2RailSoundsDialogControl
from .sequence_constants import SequenceCommandEnum
from .sequence_req import SequenceReq


class StewardChatterReq(SequenceReq):
    """Request for random steward chatter from a StationSounds car."""

    def __init__(
        self,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = CommandScope.ENGINE,
    ) -> None:
        super().__init__(SequenceCommandEnum.STEWARD_CHATTER, address, scope)
        s_enum = self._dialog
        self.add(s_enum, address, data, scope)

    @property
    def _dialog(self) -> TMCC2RailSoundsDialogControl:
        return random.choice(
            [
                TMCC2RailSoundsDialogControl.STEWARD_WELCOME_ABOARD,
                TMCC2RailSoundsDialogControl.STEWARD_FIRST_SEATING,
                TMCC2RailSoundsDialogControl.STEWARD_SECOND_SEATING,
                TMCC2RailSoundsDialogControl.STEWARD_LOUNGE_CAR_OPEN,
            ]
        )

    def _on_before_send(self) -> None:
        pass


SequenceCommandEnum.STEWARD_CHATTER.value.register_cmd_class(StewardChatterReq)
