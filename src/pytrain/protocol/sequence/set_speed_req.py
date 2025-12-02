#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from ...db.comp_data import CompData
from ..constants import DEFAULT_ADDRESS, CommandScope
from .abs_speed_rpm import AbsoluteSpeedRpm
from .sequence_constants import SequenceCommandEnum


class SetSpeedReq(AbsoluteSpeedRpm):
    """Request to set the speed of a Lionel Legacy engine or train."""

    def __init__(
        self,
        address: int = DEFAULT_ADDRESS,
        scope: CommandScope = CommandScope.ENGINE,
        data: int = 0,
    ) -> None:
        super().__init__(address, scope, data, SequenceCommandEnum.SET_SPEED_RPM)
        self.add(CompData.generate_update_req("target_speed", self.state, data))


SequenceCommandEnum.SET_SPEED_RPM.value.register_cmd_class(SetSpeedReq)
