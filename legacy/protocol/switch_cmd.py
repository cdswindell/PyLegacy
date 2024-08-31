from .command_base import CommandBase
from .constants import SwitchState
from .constants import TMCC1_COMMAND_PREFIX
from .constants import TMCC1_SWITCH_THROUGH_COMMAND
from .constants import TMCC1_SWITCH_OUT_COMMAND


class SwitchCmd(CommandBase):
    def __init__(self, switch: int,
                 state: SwitchState = SwitchState.THROUGH,
                 baudrate: int = 9600,
                 port: str = "/dev/ttyUSB0") -> None:
        CommandBase.__init__(self, baudrate, port)
        if switch < 1 or switch > 99:
            raise ValueError("Switch must be between 1 and 99")
        self._switch = switch
        self._state = state

    def fire(self) -> None:
        switch_command = TMCC1_SWITCH_THROUGH_COMMAND if self._state == SwitchState.THROUGH \
            else TMCC1_SWITCH_OUT_COMMAND
        cmd = (TMCC1_COMMAND_PREFIX.to_bytes(1, 'big') +
               ((self._switch << 7) | switch_command).to_bytes(2, 'big'))

        # cue the command to send to the LCS SER2
        self.queue_cmd(cmd)
