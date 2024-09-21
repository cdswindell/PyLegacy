from typing import TypeVar

import argparse

from .sequence_req import SequenceReq
from ..constants import CommandScope, OfficialRRSpeeds
from ..tmcc1.tmcc1_constants import TMCC1RRSpeeds, TMCC1EngineCommandDef
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandDef, TMCC2RRSpeeds
from ..tmcc2.tmcc2_param_constants import TMCC2RailSoundsDialogControl
from ...utils.argument_parser import ArgumentParser

T = TypeVar("T", TMCC1RRSpeeds, TMCC2RRSpeeds)


class SpeedReq(SequenceReq):
    def __init__(self,
                 address: int,
                 speed: int | str | T = None,
                 scope: CommandScope = CommandScope.ENGINE,
                 is_tmcc: bool = False) -> None:
        super().__init__(address, scope)
        t, s, e = self._decode_speed(speed, is_tmcc)
        self.add(t, address)
        self.add(s, address, scope=scope, delay=2)
        self.add(e, address, scope=scope, delay=4)

    def _decode_speed(self, speed, is_tmcc):
        base = None
        speed_enum = None
        if isinstance(speed, OfficialRRSpeeds):
            base = f"SPEED_{speed.name}"
            if isinstance(speed, TMCC1RRSpeeds):
                speed_enum = TMCC1EngineCommandDef.by_name(base)
            else:
                speed_enum = TMCC2EngineCommandDef.by_name(base)
            if speed_enum is None:
                raise ValueError(f"Unknown speed type: {speed}")
        elif isinstance(speed, int):
            if is_tmcc:
                for rr_speed in TMCC1RRSpeeds:
                    if speed in rr_speed.value:
                        base = f"SPEED_{rr_speed.name}"
                        speed_enum = TMCC1EngineCommandDef.by_name(base)
                        break
            else:
                for rr_speed in TMCC2RRSpeeds:
                    if speed in rr_speed.value:
                        base = f"SPEED_{rr_speed.name}"
                        speed_enum = TMCC2EngineCommandDef.by_name(base)
                        break
        elif isinstance(speed, str):
            try:
                args = self._command_parser().parse_args(['-' + speed.strip()])
                speed_enum = args.command
                base = speed_enum.name
            except argparse.ArgumentError:
                pass
        if speed_enum is None:
            raise ValueError(f"Unknown speed type: {speed}")

        tower = TMCC2RailSoundsDialogControl.by_name(f"TOWER_{base}")
        engr = TMCC2RailSoundsDialogControl.by_name(f"ENGINEER_{base}")
        return tower, speed_enum, engr

    @staticmethod
    def _command_parser(is_tmcc: bool = False) -> ArgumentParser:
        """
            Parse the first token of the user's input
        """
        cde = TMCC1EngineCommandDef if is_tmcc else TMCC2EngineCommandDef
        command_parser = ArgumentParser(exit_on_error=False)
        group = command_parser.add_mutually_exclusive_group()
        group.add_argument("-stop",
                           action="store_const",
                           const=cde.SPEED_STOP_HOLD,
                           dest="command")
        group.add_argument("-roll",
                           action="store_const",
                           const=cde.SPEED_ROLL,
                           dest="command")
        group.add_argument("-restricted",
                           action="store_const",
                           const=cde.SPEED_RESTRICTED,
                           dest="command")
        group.add_argument("-slow",
                           action="store_const",
                           const=cde.SPEED_SLOW,
                           dest="command")
        group.add_argument("-medium",
                           action="store_const",
                           const=cde.SPEED_MEDIUM,
                           dest="command")
        group.add_argument("-limited",
                           action="store_const",
                           const=cde.SPEED_LIMITED,
                           dest="command")
        group.add_argument("-normal",
                           action="store_const",
                           const=cde.SPEED_NORMAL,
                           dest="command")
        group.add_argument("-highball",
                           action="store_const",
                           const=cde.SPEED_HIGHBALL,
                           dest="command")
        return command_parser
