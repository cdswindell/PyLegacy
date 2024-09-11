import abc
from abc import ABC

from ..command_base import CommandBase
from ..constants import DEFAULT_BAUDRATE, DEFAULT_PORT, DEFAULT_ADDRESS, TMCC2CommandPrefix
from ..constants import TMCC2ParameterIndex, TMCC2ParameterDataEnum
from ..constants import TMCC2LightingControl, TMCC2EffectsControl, TMCC2DialogControl
from ..constants import CommandScope, TMCC2_PARAMETER_INDEX_PREFIX, LEGACY_PARAMETER_COMMAND_PREFIX


class TMCC2Command(CommandBase, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self,
                 command_scope: CommandScope,
                 address: int = DEFAULT_ADDRESS,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        super().__init__(address, baudrate, port)
        self._command_scope = command_scope

    @property
    def scope(self) -> CommandScope:
        return self._command_scope

    def _encode_address(self, command_op: int) -> bytes:
        return self._encode_command((self.address << 9) | command_op)

    def _command_prefix(self) -> bytes:
        prefix = TMCC2CommandPrefix(self.scope.name)
        return prefix.to_bytes(1, byteorder='big')


class TMCC2FixedParameterCommand(TMCC2Command, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self,
                 command_scope: CommandScope,
                 parameter_index: TMCC2ParameterIndex | int,
                 parameter_data: TMCC2ParameterDataEnum | int,
                 address: int = DEFAULT_ADDRESS,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        super().__init__(command_scope, address, baudrate, port)
        if parameter_index < 0 or parameter_index >= 15:
            raise ValueError('Parameter index must be between 0 and 15')
        if parameter_data < 0 or parameter_data > 0xFF:
            raise ValueError('Parameter data must be between 0 and 255')
        self._parameter_index = parameter_index
        self._parameter_data = parameter_data
        self._command = self._build_command()

    def __repr__(self):
        if isinstance(self._parameter_index, TMCC2ParameterIndex):
            p_idx = f"{self._parameter_index.name} ({hex(self._parameter_index)})"
        else:
            p_idx = f"{hex(self._parameter_index)}"
        if isinstance(self._parameter_data, TMCC2ParameterDataEnum):
            p_data = f"{self._parameter_data.name} ({hex(self._parameter_data)})"
        else:
            p_data = f"{hex(self._parameter_data)}"
        return f"<{self.scope.name} {self.address} {p_idx} {p_data}: 0x{self.command_bytes.hex()}>"

    @property
    def parameter_index(self) -> int:
        return self._parameter_index

    @property
    def _parameter_index_byte(self) -> bytes:
        return (TMCC2_PARAMETER_INDEX_PREFIX | self._parameter_index).to_bytes(1, byteorder='big')

    @property
    def parameter_data(self) -> int:
        return self._parameter_data

    @property
    def _parameter_data_byte(self) -> bytes:
        return self._parameter_data.to_bytes(1, byteorder='big')

    @property
    def _word_2_3_prefix(self) -> bytes:
        e_t = 1 if self.scope == CommandScope.TRAIN else 0
        return ((self.address << 1) + e_t).to_bytes(1, 'big')

    @property
    def _word_1(self) -> bytes:
        return ((self.address << 1) + 1).to_bytes(1, 'big') + self._parameter_index_byte

    @property
    def _word_2(self) -> bytes:
        return self._word_2_3_prefix + self._parameter_data_byte

    @property
    def _word_3(self) -> bytes:
        return self._word_2_3_prefix + self._checksum()

    def _checksum(self) -> bytes:
        """
            Calculate the checksum of a lionel tmcc2 multibyte command. The checksum
            is calculated adding together the second 2 bytes of the parameter index
            and parameter data words, and the 2 byte of the checksum word, and returning
            the 1's complement of that sum mod 256.

            We make use of self.command_scope to determine if the command directed at
            an engine or train.
        """
        cmd_bytes = self._word_1 + self._word_2 + self._word_2_3_prefix
        byte_sum = 0
        for b in cmd_bytes:
            byte_sum += int(b)
        return (~(byte_sum % 256) & 0xFF).to_bytes(1, byteorder='big')  # return 1's complement of sum mod 256

    @property
    def _identifier(self) -> bytes:
        return LEGACY_PARAMETER_COMMAND_PREFIX.to_bytes(1, byteorder='big')

    def _build_command(self) -> bytes:
        return self.command_prefix + self._word_1 + self._identifier + self._word_2 + self._identifier + self._word_3


class TMCC2DialogCommand(TMCC2FixedParameterCommand):
    def __init__(self,
                 command_scope: CommandScope,
                 option: TMCC2DialogControl | int,
                 address: int = DEFAULT_ADDRESS,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if type(option) is int:
            option = TMCC2LightingControl.by_value(option, True)
        super().__init__(command_scope, TMCC2ParameterIndex.DIALOG_CONTROLS, option, address, baudrate, port)


class TMCC2LightingCommand(TMCC2FixedParameterCommand):
    def __init__(self,
                 command_scope: CommandScope,
                 option: TMCC2LightingControl | int,
                 address: int = DEFAULT_ADDRESS,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if type(option) is int:
            option = TMCC2LightingControl.by_value(option, True)
        super().__init__(command_scope, TMCC2ParameterIndex.LIGHTING_CONTROLS, option, address, baudrate, port)


class TMCC2EffectsCommand(TMCC2FixedParameterCommand):
    def __init__(self,
                 command_scope: CommandScope,
                 option: TMCC2EffectsControl | int,
                 address: int = DEFAULT_ADDRESS,
                 baudrate: int = DEFAULT_BAUDRATE,
                 port: str = DEFAULT_PORT) -> None:
        if type(option) is int:
            option = TMCC2EffectsControl.by_value(option, True)
        super().__init__(command_scope, TMCC2ParameterIndex.EFFECTS_CONTROLS, option, address, baudrate, port)
