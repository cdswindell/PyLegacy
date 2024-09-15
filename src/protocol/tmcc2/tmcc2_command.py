import abc
from abc import ABC

from ..command_base import CommandBase
from ..command_req import CommandReq, ParameterCommandReq
from ..constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_ADDRESS
from ..command_def import CommandDefEnum
from src.protocol.tmcc2.tmcc2_constants import TMCC2CommandPrefix
from src.protocol.tmcc2.multibyte_constants import TMCC2ParameterEnum, TMCC2DialogControl, TMCC2EffectsControl, TMCC2LightingControl
from ..constants import CommandScope


class TMCC2Command(CommandBase, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self,
                 command: CommandDefEnum,
                 command_req: CommandReq,
                 address: int = 99,
                 data: int = 0,
                 scope: CommandScope = None,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        super().__init__(command, command_req, address, data, scope, baudrate, port)

    def _build_command(self) -> bytes:
        return self._command_req.as_bytes

    def _encode_address(self, command_op: int) -> bytes:
        return self._encode_command((self.address << 9) | command_op)

    def _command_prefix(self) -> bytes:
        prefix = TMCC2CommandPrefix(self.scope.name)
        return prefix.to_bytes(1, byteorder='big')


class TMCC2FixedParameterCommand(TMCC2Command, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self,
                 parameter_enum: TMCC2ParameterEnum,
                 address: int = DEFAULT_ADDRESS,
                 data: int = 0,
                 scope: CommandScope = CommandScope.ENGINE,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        req = ParameterCommandReq(parameter_enum, address, data, scope)
        super().__init__(parameter_enum, req, address, data, scope, baudrate, port)
        if self.bits < 0 or self.bits > 0xFF:
            raise ValueError('Parameter data must be between 0 and 255')
        self._command = self._build_command()


class TMCC2DialogCommand(TMCC2FixedParameterCommand):
    def __init__(self,
                 parameter_enum: TMCC2DialogControl | int,
                 address: int = DEFAULT_ADDRESS,
                 scope: CommandScope = CommandScope.ENGINE,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if type(parameter_enum) is int:
            parameter_enum = TMCC2LightingControl.by_value(parameter_enum, True)
        super().__init__(parameter_enum, address, 0, scope, baudrate, port)


class TMCC2LightingCommand(TMCC2FixedParameterCommand):
    def __init__(self,
                 parameter_enum: TMCC2LightingControl | int,
                 address: int = DEFAULT_ADDRESS,
                 scope: CommandScope = CommandScope.ENGINE,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if type(parameter_enum) is int:
            parameter_enum = TMCC2LightingControl.by_value(parameter_enum, True)
        super().__init__(parameter_enum, address, 0, scope, baudrate, port)


class TMCC2EffectsCommand(TMCC2FixedParameterCommand):
    def __init__(self,
                 parameter_enum: TMCC2EffectsControl | int,
                 address: int = DEFAULT_ADDRESS,
                 scope: CommandScope = CommandScope.ENGINE,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if type(parameter_enum) is int:
            parameter_enum = TMCC2EffectsControl.by_value(parameter_enum, True)
        super().__init__(parameter_enum, address, 0, scope, baudrate, port)
