import abc
from abc import ABC

from .tmcc2_constants import TMCC2CommandPrefix
from ..command_base import CommandBase
from ..command_def import CommandDefEnum
from ..command_req import CommandReq
from ..constants import CommandScope
from ..constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_ADDRESS
from ..multibyte.multibyte_constants import TMCC2ParameterEnum
from ..multibyte.param_command_req import ParameterCommandReq


class TMCC2Command(CommandBase, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        command: CommandDefEnum,
        command_req: CommandReq,
        address: int = 99,
        data: int = 0,
        scope: CommandScope = None,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ) -> None:
        super().__init__(command, command_req, address, data, scope, baudrate, port, server)

    def _build_command(self) -> bytes:
        return self._command_req.as_bytes

    def _encode_address(self, command_op: int) -> bytes:
        return self._encode_command((self.address << 9) | command_op)

    def _command_prefix(self) -> bytes:
        prefix = TMCC2CommandPrefix(self.scope.name)
        return prefix.to_bytes(1, byteorder="big")


class TMCC2FixedParameterCommand(TMCC2Command, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(
        self,
        parameter_enum: TMCC2ParameterEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = CommandScope.ENGINE,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ) -> None:
        if scope is None or scope not in [CommandScope.ENGINE, CommandScope.TRAIN]:
            raise ValueError(f"Scope must be ENGINE or TRAIN ({scope})")
        if address < 1 or address > 9999:
            raise ValueError(f"{scope.name.title()} must be between 1 and 99")
        req = ParameterCommandReq(parameter_enum, address, data, scope)
        super().__init__(parameter_enum, req, address, data, scope, baudrate, port, server)
        if self.bits < 0 or self.bits > 0xFF:
            raise ValueError("Parameter data must be between 0 and 255")
        self._command = self._build_command()
