import time

from .constants import DEFAULT_ADDRESS, DEFAULT_BAUDRATE, DEFAULT_PORT
from .constants import TMCC1CommandDef, TMCC1_COMMAND_PREFIX, TMCC2CommandPrefix, TMCC2CommandDef
from .constants import CommandDefEnum, TMCC1Enum, TMCC2Enum, TMCC1RouteOption
from .constants import TMCC1_TRAIN_COMMAND_PURIFIER, TMCC1_TRAIN_COMMAND_MODIFIER

from .constants import CommandDef, CommandScope, CommandSyntax, TMCC1CommandIdentifier
from .validations import Validations
from ..comm.comm_buffer import CommBuffer


class CommandReq:
    @classmethod
    def send_command(cls,
                     command: CommandDefEnum,
                     address: int,
                     data: int = 0,
                     scope: CommandScope = None,
                     repeat: int = 1,
                     delay: int = 0,
                     baudrate: int = DEFAULT_BAUDRATE,
                     port: str = DEFAULT_PORT
                     ) -> None:
        # build & queue
        cls._vet_request(command, address, data, scope)
        req = CommandReq(command, address=address, data=data, scope=scope)
        cls._enqueue_command(req.as_bytes, repeat, delay, baudrate, port)

    @classmethod
    def send_func(cls,
                  address: int,
                  command: CommandDefEnum,
                  data: int = 0,
                  scope: CommandScope = CommandScope.ENGINE,
                  repeat: int = 1,
                  delay: int = 0,
                  baudrate: int = DEFAULT_BAUDRATE,
                  port: str = DEFAULT_PORT
                  ):
        # build & queue
        cls._vet_request(command, address, data, scope)
        req = CommandReq(command, address=address, data=data, scope=scope)

        def send_func() -> None:
            print(f"cmd: {req} repeat: {repeat} delay: {delay}")
            cls._enqueue_command(req.as_bytes, repeat, delay, baudrate, port)

        return send_func

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
            return TMCC2CommandPrefix(scope.name).as_bytes
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
            raise TypeError(f"Command type not recognized {command}")

        max_val = 99
        syntax = CommandSyntax.TMCC2 if enum_class == TMCC2Enum else CommandSyntax.TMCC1
        if syntax == CommandSyntax.TMCC1 and command == TMCC1RouteOption.ROUTE:
            scope = TMCC1CommandIdentifier.ROUTE
            max_val = 31
        if scope is None:
            scope = CommandDefEnum.scope
        Validations.validate_int(address, min_value=1, max_value=max_val, label=scope.name.capitalize())
        Validations.validate_int(data, label=scope.name.capitalize())

    @classmethod
    def _enqueue_command(cls, cmd: bytes, repeat: int, delay: int, baudrate: int, port: str):
        repeat = Validations.validate_int(repeat, min_value=1, label="repeat")
        delay = Validations.validate_int(delay, min_value=0, label="delay")

        # send command to comm buffer
        buffer = CommBuffer(baudrate=baudrate, port=port)
        for _ in range(repeat):
            if delay > 0 and repeat == 1:
                time.sleep(delay)
            buffer.enqueue_command(cmd)
            if repeat != 1 and delay > 0 and _ != repeat - 1:
                time.sleep(delay)

    def __init__(self,
                 command_def_enum: CommandDefEnum,
                 address: int = DEFAULT_ADDRESS,
                 data: int = 0,
                 scope: CommandScope = None) -> None:
        self._command_def_enum = command_def_enum
        self._command_def = command_def_enum.value  # read only; do not modify
        self._address = address
        self._data = data
        self._scope = scope

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

    @property
    def data(self) -> int:
        return self._data

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def command_def(self) -> CommandDef:
        return self._command_def

    @property
    def bits(self) -> int:
        return self._command_bits

    @property
    def num_data_bits(self) -> int:
        return self.command_def.num_data_bits

    @property
    def syntax(self) -> CommandSyntax:
        return self._command_def.syntax

    @property
    def as_bytes(self) -> bytes:
        if self.scope is None:
            first_byte = self.command_def.first_byte
        else:
            first_byte = self._determine_first_byte(self.command_def, self.scope)
        return first_byte + self._command_bits.to_bytes(2, byteorder='big')

    @property
    def identifier(self) -> int | None:
        return self.command_def.identifier

    def _apply_address(self) -> int:
        if self.syntax == CommandSyntax.TMCC1:
            self._command_bits |= self.address << 7
            if self.scope == CommandScope.TRAIN and self.identifier == TMCC1CommandIdentifier.ENGINE:
                self._command_bits &= TMCC1_TRAIN_COMMAND_PURIFIER
                self._command_bits |= TMCC1_TRAIN_COMMAND_MODIFIER
        elif self.syntax == CommandSyntax.TMCC2:
            self._command_bits |= self.address << 9
        else:
            raise ValueError(f"Command type not recognized {self.syntax}")
        return self._command_bits

    def _apply_data(self, data: int | None = None) -> int:
        """
            For commands that take parameters, such as engine speed and brake level,
            apply the data bits to the command op bytes to form the complete byte
            set to send to the Lionel LCS SER2.
        """
        print(f"num bits {self._command_bits}")
        if self.num_data_bits and data is None:
            print('THIS IS BAD')
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
        filtered_data = data & (2 ** self.num_data_bits - 1)
        if data != filtered_data:
            raise ValueError(f"Invalid data value: {data} (not in range)")
        self._command_bits |= data
        return self._command_bits
