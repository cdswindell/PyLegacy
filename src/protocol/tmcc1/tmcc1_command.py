import abc
from abc import ABC

from .tmcc1_constants import TMCC1_COMMAND_PREFIX

from ..command_base import CommandBase
from ..command_req import CommandReq
from ..constants import DEFAULT_BAUDRATE, DEFAULT_PORT
from ..constants import CommandScope
from ..command_def import CommandDefEnum


class TMCC1Command(CommandBase, ABC):
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

    def __repr__(self):
        name = self._command_def_enum.name
        data = f" [{self._command_req.data}] " if self._command_req.num_data_bits else ""
        entity = {self._command_req.scope.name.title(): self._command_req.scope.name}
        return f"<{name}: {entity} {self.address} {data}: 0x{self.command_bytes.hex()}>"

    def _encode_address(self, command_op: int) -> bytes:
        return self._encode_command((self.address << 7) | command_op)

    def _command_prefix(self) -> bytes:
        return TMCC1_COMMAND_PREFIX.to_bytes(1, "big")

    def _build_command(self) -> bytes:
        return self._command_req.as_bytes
