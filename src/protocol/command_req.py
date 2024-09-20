import time
from typing import Callable, Dict, Self

from .constants import DEFAULT_ADDRESS, DEFAULT_BAUDRATE, DEFAULT_PORT
from .tmcc2.tmcc2_constants import LEGACY_PARAMETER_COMMAND_PREFIX, TMCC2Enum, TMCC2CommandPrefix
from .tmcc2.tmcc2_constants import TMCC2_SCOPE_TO_FIRST_BYTE_MAP, TMCC2CommandDef
from .tmcc2.tmcc2_param_constants import TMCC2ParameterEnum, TMCC2_PARAMETER_INDEX_PREFIX, TMCC2ParameterIndex, \
    TMCC2RailSoundsEffectsControl
from .tmcc2.tmcc2_param_constants import TMCC2RailSoundsDialogControl, TMCC2EffectsControl
from .tmcc2.tmcc2_param_constants import TMCC2LightingControl, TMCC2ParameterCommandDef

from .constants import CommandScope, CommandSyntax
from .command_def import CommandDef, CommandDefEnum
from .tmcc1.tmcc1_constants import TMCC1CommandDef, TMCC1_COMMAND_PREFIX, TMCC1Enum
from .tmcc1.tmcc1_constants import TMCC1CommandIdentifier, TMCC1RouteCommandDef, TMCC1_TRAIN_COMMAND_PURIFIER
from .tmcc1.tmcc1_constants import TMCC1_TRAIN_COMMAND_MODIFIER
from src.utils.validations import Validations
from ..comm.comm_buffer import CommBuffer


class CommandReq:
    @classmethod
    def build_request(cls,
                      command: CommandDefEnum | None,
                      address: int = DEFAULT_ADDRESS,
                      data: int = 0,
                      scope: CommandScope = None) -> Self:
        cls._vet_request(command, address, data, scope)
        if isinstance(command, TMCC2ParameterEnum):
            req = ParameterCommandReq(command, address, data, scope)
        else:
            req = CommandReq(command, address, data, scope)
        return req

    @classmethod
    def send_command(cls,
                     command: CommandDefEnum,
                     address: int = DEFAULT_ADDRESS,
                     data: int = 0,
                     scope: CommandScope = None,
                     repeat: int = 1,
                     delay: float = 0,
                     baudrate: int = DEFAULT_BAUDRATE,
                     port: str = DEFAULT_PORT,
                     server: str = None
                     ) -> None:
        # build & queue
        req = cls.build_request(command, address, data, scope)
        cls._enqueue_command(req.as_bytes, repeat, delay, baudrate, port, server)

    @classmethod
    def build_action(cls,
                     command: CommandDefEnum | None,
                     address: int = DEFAULT_ADDRESS,
                     data: int = 0,
                     scope: CommandScope = None,
                     repeat: int = 1,
                     delay: float = 0,
                     baudrate: int = DEFAULT_BAUDRATE,
                     port: str = DEFAULT_PORT,
                     server: str = None
                     ) -> Callable:
        # build & return action function
        req = cls.build_request(command, address, data, scope)
        return req.as_action(repeat=repeat, delay=delay, baudrate=baudrate, port=port, server=server)

    @classmethod
    def _determine_first_byte(cls, command: CommandDef, scope: CommandScope) -> bytes:
        """
            Generalized command scopes, such as ENGINE, SWITCH, etc.,
            map to syntax-specific command identifiers defined
            for the TMCC1 and TMCC2 commands
        """
        # otherwise, we need to figure out if we're returning a
        # TMCC1-style or TMCC2-style command prefix
        if isinstance(command, TMCC1CommandDef):
            return TMCC1_COMMAND_PREFIX.to_bytes(1, byteorder='big')
        elif isinstance(command, TMCC2CommandDef):
            validated_scope = cls._validate_requested_scope(command, scope)
            return TMCC2CommandPrefix(validated_scope.name).as_bytes
        raise TypeError(f"Command type not recognized {command}")

    @classmethod
    def _vet_request(cls,
                     command: CommandDefEnum,
                     address: int,
                     data: int,
                     scope: CommandScope,
                     ) -> None:
        if isinstance(command, TMCC1Enum):
            enum_class = TMCC1Enum
        elif isinstance(command, TMCC2Enum):
            enum_class = TMCC2Enum
        else:
            raise TypeError(f"Command def not recognized: '{command}'")

        max_val = 99
        syntax = CommandSyntax.TMCC2 if enum_class == TMCC2Enum else CommandSyntax.TMCC1
        if syntax == CommandSyntax.TMCC1 and command == TMCC1RouteCommandDef.ROUTE:
            scope = TMCC1CommandIdentifier.ROUTE
            max_val = 31
        if scope is None:
            scope = command.scope
        Validations.validate_int(address, min_value=1, max_value=max_val, label=scope.name.capitalize())
        if data is not None:
            Validations.validate_int(data, label=scope.name.capitalize())

    @classmethod
    def _enqueue_command(cls,
                         cmd: bytes,
                         repeat: int,
                         delay: float,
                         baudrate: int,
                         port: str | int,
                         server: str | None,
                         buffer: CommBuffer = None) -> None:
        repeat = Validations.validate_int(repeat, min_value=1, label="repeat")
        delay = Validations.validate_int(delay, min_value=0, label="delay")
        # send command to comm buffer
        if buffer is None:
            # vet server args
            server, port = CommBuffer.parse_server(server, port)
            buffer = CommBuffer.build(baudrate=baudrate, port=port, server=server)
        for _ in range(repeat):
            if delay > 0 and repeat == 1:
                time.sleep(delay)
            buffer.enqueue_command(cmd)
            if repeat != 1 and delay > 0 and _ != repeat - 1:
                time.sleep(delay)

    @staticmethod
    def _validate_requested_scope(command_def: CommandDef, request: CommandScope) -> CommandScope:
        if request in [CommandScope.ENGINE, CommandScope.TRAIN]:
            if command_def.scope in [CommandScope.ENGINE, CommandScope.TRAIN]:
                return request
        # otherwise, return the scope associated with the native command def
        return command_def.scope

    def __init__(self,
                 command_def_enum: CommandDefEnum,
                 address: int = DEFAULT_ADDRESS,
                 data: int = 0,
                 scope: CommandScope = None) -> None:
        self._command_def_enum = command_def_enum
        self._command_def = command_def_enum.value  # read only; do not modify
        self._address = address
        self._data = data
        self._native_scope = self._command_def.scope
        self._scope = self._validate_requested_scope(self._command_def, scope)
        self._buffer: CommBuffer | None = None

        # save the command bits from the def, as we will be modifying them
        self._command_bits = self._command_def.bits

        # apply the given address and data
        self._apply_address()
        self._apply_data()

    def __repr__(self) -> str:
        return f"<{self._command_def_enum.name} 0x{self.bits:04x}: {self.num_data_bits} data bits>"

    @property
    def address(self) -> int:
        return self._address

    @address.setter
    def address(self, new_address: int) -> None:
        if new_address != self._address:
            self._address = new_address
            self._apply_address()

    @property
    def data(self) -> int:
        return self._data

    @data.setter
    def data(self, new_data: int) -> None:
        if new_data != self._data:
            self._data = new_data
            self._apply_data()

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def native_scope(self) -> CommandScope:
        return self._native_scope

    @property
    def command_def(self) -> CommandDef:
        return self._command_def

    @property
    def bits(self) -> int:
        return self._command_bits

    @property
    def is_data(self) -> bool:
        return self.command_def.num_data_bits != 0

    @property
    def num_data_bits(self) -> int:
        return self.command_def.num_data_bits

    @property
    def data_max(self) -> int:
        return self.command_def.data_max

    @property
    def data_min(self) -> int:
        return self.command_def.data_min

    @property
    def syntax(self) -> CommandSyntax:
        return self._command_def.syntax

    @property
    def is_tmcc1(self) -> bool:
        return self._command_def.is_tmcc1

    @property
    def is_tmcc2(self) -> bool:
        return self._command_def.is_tmcc2

    @property
    def identifier(self) -> int | None:
        return self.command_def.identifier

    @property
    def as_bytes(self) -> bytes:
        if self.scope is None:
            first_byte = self.command_def.first_byte
        else:
            first_byte = self._determine_first_byte(self.command_def, self.scope)
        return first_byte + self._command_bits.to_bytes(2, byteorder='big')

    def as_action(self,
                  repeat: int = 1,
                  delay: float = 0,
                  baudrate: int = DEFAULT_BAUDRATE,
                  port: str = DEFAULT_PORT,
                  server: str = None
                  ) -> Callable:
        buffer = CommBuffer.build(baudrate=baudrate, port=port, server=server)

        def send_func(new_address: int = None, new_data: int = None) -> None:
            if new_address and new_address != self.address:
                self.address = new_address
            if self.num_data_bits and new_data and new_data != self.data:
                self.data = new_data
            self._enqueue_command(self.as_bytes,
                                  repeat=repeat,
                                  delay=delay,
                                  baudrate=baudrate,
                                  port=port,
                                  server=server,
                                  buffer=buffer)

        return send_func

    def _apply_address(self, new_address: int = None) -> int:
        if not self.command_def.is_addressable:  # HALT command
            return self._command_bits
        # reset existing address bits, if any
        self._command_bits &= self._command_def.address_mask
        # figure out which address we're using
        the_address = new_address if new_address and new_address > 0 else self._address
        if self.syntax == CommandSyntax.TMCC1:
            self._command_bits |= the_address << 7
            if self.scope == CommandScope.TRAIN and self.identifier == TMCC1CommandIdentifier.ENGINE:
                self._command_bits &= TMCC1_TRAIN_COMMAND_PURIFIER
                self._command_bits |= TMCC1_TRAIN_COMMAND_MODIFIER
        elif self.syntax == CommandSyntax.TMCC2:
            self._command_bits |= the_address << 9
        else:
            raise ValueError(f"Command syntax not recognized {self.syntax}")
        return self._command_bits

    def _apply_data(self, new_data: int = None) -> int:
        """
            For commands that take parameters, such as engine speed and brake level,
            apply the data bits to the command op bytes to form the complete byte
            set to send to the Lionel LCS SER2.
        """
        data = new_data if new_data is not None else self.data
        if self.num_data_bits and data is None:
            raise ValueError("Data is required")
        if self.num_data_bits == 0:
            return self.bits
        elif self.command_def.data_map:
            d_map = self.command_def.data_map
            if data in d_map:
                data = d_map[data]
            else:
                raise ValueError(f"Invalid data value: {data} (not in map)")
        elif data < self.command_def.data_min or data > self.command_def.data_max:
            raise ValueError(f"Invalid data value: {data} (not in range)")
        # sanitize data so we don't set bits we shouldn't
        data_bits = (2 ** self.num_data_bits - 1)
        filtered_data = data & data_bits
        if data != filtered_data:
            raise ValueError(f"Invalid data value: {data} (not in range)")
        # clear out old data
        self._command_bits &= 0xFFFF & ~data_bits
        # set new data
        self._command_bits |= data
        return self._command_bits


# noinspection PyTypeChecker
TMCC2_PARAMETER_ENUM_TO_TMCC2_PARAMETER_INDEX_MAP: Dict[TMCC2ParameterEnum, TMCC2ParameterIndex] = {
    TMCC2RailSoundsDialogControl: TMCC2ParameterIndex.DIALOG_TRIGGERS,
    TMCC2RailSoundsEffectsControl: TMCC2ParameterIndex.EFFECTS_TRIGGERS,
    TMCC2EffectsControl: TMCC2ParameterIndex.EFFECTS_CONTROLS,
    TMCC2LightingControl: TMCC2ParameterIndex.LIGHTING_CONTROLS,
}


class ParameterCommandReq(CommandReq):
    def __init__(self,
                 command_def_enum: TMCC2ParameterEnum,
                 address: int = DEFAULT_ADDRESS,
                 data: int = 0,
                 scope: CommandScope = None) -> None:
        super().__init__(command_def_enum, address, data, scope)

    @property
    def parameter_index(self) -> TMCC2ParameterIndex:
        # noinspection PyTypeChecker
        return TMCC2_PARAMETER_ENUM_TO_TMCC2_PARAMETER_INDEX_MAP[type(self._command_def_enum)]

    @property
    def parameter_index_byte(self) -> bytes:
        return (TMCC2_PARAMETER_INDEX_PREFIX | self.parameter_index).to_bytes(1, byteorder='big')

    @property
    def parameter_data(self) -> TMCC2ParameterCommandDef:
        return TMCC2ParameterCommandDef(self._command_def)

    @property
    def parameter_data_byte(self) -> bytes:
        return self.command_def.bits.to_bytes(1, byteorder='big')

    @property
    def as_bytes(self) -> bytes:
        return (TMCC2_SCOPE_TO_FIRST_BYTE_MAP[self.scope].to_bytes(1, byteorder='big') +
                self._word_1 +
                LEGACY_PARAMETER_COMMAND_PREFIX.to_bytes(1, byteorder='big') +
                self._word_2 +
                LEGACY_PARAMETER_COMMAND_PREFIX.to_bytes(1, byteorder='big') +
                self._word_3)

    @property
    def _word_2_3_prefix(self) -> bytes:
        e_t = 1 if self.scope == CommandScope.TRAIN else 0
        return ((self.address << 1) + e_t).to_bytes(1, 'big')

    @property
    def _word_1(self) -> bytes:
        return ((self.address << 1) + 1).to_bytes(1, 'big') + self.parameter_index_byte

    @property
    def _word_2(self) -> bytes:
        return self._word_2_3_prefix + self.parameter_data_byte

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

    def _apply_address(self, **kwargs) -> int:
        return self.command_def.bits

    def _apply_data(self, **kwargs) -> int:
        return self.command_def.bits
