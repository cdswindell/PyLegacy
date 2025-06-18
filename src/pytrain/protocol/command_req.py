from __future__ import annotations

import sys
from typing import Callable, TypeVar, Set

if sys.version_info >= (3, 11):
    from typing import Self
elif sys.version_info >= (3, 9):
    from typing_extensions import Self

from .constants import (
    DEFAULT_ADDRESS,
    DEFAULT_BAUDRATE,
    DEFAULT_PORT,
    DEFAULT_DURATION_INTERVAL_MSEC,
    MINIMUM_DURATION_INTERVAL_MSEC,
)
from .constants import CommandScope, CommandSyntax
from .tmcc2.tmcc2_constants import TMCC2Enum, TMCC2CommandPrefix, LEGACY_ENGINE_COMMAND_PREFIX
from .tmcc2.tmcc2_constants import TMCC2RouteCommandEnum, TMCC2HaltCommandEnum, TMCC2EngineCommandEnum
from .tmcc2.tmcc2_constants import LEGACY_TRAIN_COMMAND_PREFIX, LEGACY_EXTENDED_BLOCK_COMMAND_PREFIX
from .tmcc2.tmcc2_constants import TMCC2CommandDef
from .command_def import CommandDef, CommandDefEnum
from .tmcc1.tmcc1_constants import TMCC1CommandDef, TMCC1_COMMAND_PREFIX, TMCC1Enum, TMCC1SyncCommandEnum
from .tmcc1.tmcc1_constants import (
    TMCC1HaltCommandEnum,
    TMCC1SwitchCommandEnum,
    TMCC1AuxCommandEnum,
    TMCC1EngineCommandEnum,
)
from .tmcc1.tmcc1_constants import TMCC1CommandIdentifier, TMCC1_TRAIN_COMMAND_PURIFIER
from .tmcc1.tmcc1_constants import TMCC1_TRAIN_COMMAND_MODIFIER
from .tmcc1.tmcc1_constants import TMCC1RouteCommandEnum
from ..utils.validations import Validations

E = TypeVar("E", bound=CommandDefEnum)
R = TypeVar("R", bound="CommandReq")


class CommandReq:
    @classmethod
    def build(
        cls,
        command: E | bytes,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
    ) -> Self:
        if isinstance(command, bytes):
            return cls.from_bytes(bytes(command))
        cls._vet_request(command, address, data, scope)
        # we have to do these imports here to avoid cyclic dependencies
        from .sequence.sequence_constants import SequenceCommandEnum
        from ..protocol.multibyte.multibyte_constants import TMCC2MultiByteEnum

        if isinstance(command, SequenceCommandEnum):
            from .sequence.sequence_req import SequenceReq

            return SequenceReq.build(command, address, data, scope)
        elif isinstance(command, TMCC2MultiByteEnum):
            from ..protocol.multibyte.param_command_req import MultiByteReq

            return MultiByteReq.build(command, address, data, scope)
        elif isinstance(command, CommandDefEnum):
            return CommandReq(command, address, data, scope)
        else:
            raise TypeError(f"Command type not recognized {command}")

    @classmethod
    def from_bytes(cls, param: bytes, from_tmcc_rx: bool = False, is_tmcc4: bool = False) -> Self:
        if not param:
            raise ValueError("Command requires at least 3 bytes")
        if len(param) < 3:
            raise ValueError(f"Command requires at least 3 bytes {param.hex(':')}")
        first_byte = int(param[0])
        cmd_req = None
        if first_byte in TMCC4_FIRST_BYTE_TO_INTERPRETER:
            cmd_req = TMCC4_FIRST_BYTE_TO_INTERPRETER[first_byte](param)
        elif is_tmcc4 is False and first_byte in TMCC_FIRST_BYTE_TO_INTERPRETER:
            cmd_req = TMCC_FIRST_BYTE_TO_INTERPRETER[first_byte](param)
        if cmd_req is not None:
            if from_tmcc_rx is True:
                cmd_req._is_tmcc_rx = True
            if is_tmcc4 is True or cmd_req.address > 99:
                cmd_req._is_tmcc4 = True
            return cmd_req
        raise ValueError(f"Command bytes not understood {param.hex(':')}")

    @classmethod
    def send_request(
        cls,
        command: CommandDefEnum,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
        repeat: int = 1,
        delay: float = 0,
        duration: float = 0,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ) -> CommandReq:
        # build_req & queue
        req = cls.build(command, address, data, scope)
        cls._enqueue_command(req.as_bytes, repeat, delay, duration, baudrate, port, server, request=req)
        return req

    @classmethod
    def build_action(
        cls,
        command: E | None,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
        repeat: int = 1,
        delay: float = 0,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ) -> Callable:
        # build_req & return action function
        req = cls.build(command, address, data, scope)
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
            return TMCC1_COMMAND_PREFIX.to_bytes(1, byteorder="big")
        elif isinstance(command, TMCC2CommandDef):
            validated_scope = cls._validate_requested_scope(command, scope)
            return TMCC2CommandPrefix(validated_scope.name).as_bytes
        raise TypeError(f"Command type not recognized {command}")

    @classmethod
    def _vet_request(
        cls,
        command: CommandDefEnum,
        address: int,
        data: int,
        scope: CommandScope,
    ) -> None:
        from .sequence.sequence_constants import SequenceCommandEnum

        if isinstance(command, TMCC1Enum):
            enum_class = TMCC1Enum
        elif isinstance(command, TMCC2Enum) or isinstance(command, SequenceCommandEnum):
            enum_class = TMCC2Enum
        else:
            raise TypeError(f"Command def not recognized: '{command}'")

        syntax = CommandSyntax.LEGACY if enum_class == TMCC2Enum else CommandSyntax.TMCC
        min_val = 0 if scope in {CommandScope.ENGINE} and syntax == CommandSyntax.LEGACY else 1
        max_val = 9999 if scope in {CommandScope.ENGINE} and syntax == CommandSyntax.LEGACY else 99
        if syntax == CommandSyntax.TMCC and command == TMCC1RouteCommandEnum.FIRE:
            scope = TMCC1CommandIdentifier.ROUTE
            max_val = 31
        if scope is None:
            scope = command.scope
        if command.command_def.is_addressable:
            Validations.validate_int(address, min_value=min_val, max_value=max_val, label=scope.name.title())
        if data is not None and command.command_def.is_data:
            Validations.validate_int(data, label=scope.name.title())

    @classmethod
    def _enqueue_command(
        cls,
        cmd: bytes,
        repeat: int,
        delay: float,
        duration: float,
        baudrate: int,
        port: str | int,
        server: str | None,
        buffer=None,
        request: CommandReq | None = None,
        trigger_effects: bool = True,
        interval: int = None,
    ) -> None:
        repeat = Validations.validate_int(repeat, min_value=1, label="repeat")
        delay = Validations.validate_float(delay, min_value=0, label="delay")
        duration = Validations.validate_float(duration, min_value=0, label="duration", allow_none=True)
        interval = Validations.validate_int(
            interval, min_value=MINIMUM_DURATION_INTERVAL_MSEC, label="interval", allow_none=True
        )

        if request and request.command_def.is_aux1_prefixed is True:
            prefix_bytes = CommandReq(
                TMCC1EngineCommandEnum.AUX1_OPTION_ONE,
                address=request.address,
                scope=request.scope,
            ).as_bytes
        else:
            prefix_bytes = None

        # send command to comm buffer
        if buffer is None:
            from ..comm.comm_buffer import CommBuffer

            buffer = CommBuffer.build(baudrate=baudrate, port=port, server=server)
        delay = 0 if delay is None else delay
        duration = 0 if duration is None else duration
        for rep_no in range(repeat):
            if prefix_bytes:
                buffer.enqueue_command(prefix_bytes, delay)
            buffer.enqueue_command(cmd, delay)
            # does this command cause any other state changes?
            if rep_no == 0 and request and trigger_effects is True:
                for effect in cls.results_in(request):
                    if isinstance(effect, CommandDefEnum):
                        effect_cmd = CommandReq.build(effect, request.address, 0, request.scope)
                    elif isinstance(effect, tuple):
                        effect_cmd = CommandReq.build(effect[0], request.address, effect[1], request.scope)
                    else:
                        continue  # we shouldn't ever get here
                    buffer.enqueue_command(effect_cmd.as_bytes, delay)
            if duration > 0:
                # convert duration into milliseconds, then queue a command to fire
                # every 100 msec for the duration
                interval = interval if interval else DEFAULT_DURATION_INTERVAL_MSEC
                for d in range(interval, int(round(duration * 1000)), interval):
                    buffer.enqueue_command(cmd, delay + (d / 1000.0))

    @staticmethod
    def results_in(command: CommandReq) -> Set[E]:
        from ..db.component_state_store import DependencyCache

        dependencies = DependencyCache.build()
        effects = dependencies.results_in(command.command, dereference_aliases=True, include_aliases=False)
        if command.is_data:
            # noinspection PyTypeChecker
            effects.update(
                dependencies.results_in(
                    (command.command, command.data), dereference_aliases=True, include_aliases=False
                )
            )
        # remove the triggering command, and its alias, if it exists
        if effects:
            if command.command in effects:
                effects.remove(command.command)
            if command.is_data and (command.command, command.data) in effects:
                # noinspection PyTypeChecker
                effects.remove((command.command, command.data))
            if command.command.is_alias and command.command.alias in effects:
                alias = command.command.alias
                # noinspection PyTypeChecker
                effects.remove(alias)
                if isinstance(alias, tuple) and alias[0] in effects:
                    effects.remove(alias[0])
        return effects

    @staticmethod
    def _validate_requested_scope(command_def: CommandDef, request: CommandScope) -> CommandScope:
        if request in {CommandScope.ENGINE, CommandScope.TRAIN}:
            if command_def.scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
                return request
        # otherwise, return the scope associated with the native command def
        return command_def.scope

    def __init__(
        self,
        command_def_enum: E,
        address: int = DEFAULT_ADDRESS,
        data: int = 0,
        scope: CommandScope = None,
    ) -> None:
        self._command_def_enum: E = command_def_enum
        self._command_name = self._command_def_enum.name
        # noinspection PyTypeChecker
        self._command_def: TMCC2CommandDef = command_def_enum.value  # read-only; do not modify
        if self._command_def.is_addressable:
            self._address = address
        else:
            self._address = 0
        if self._command_def.is_data:
            self._data = data
        else:
            self._data = 0
        self._native_scope = self._command_def.scope
        self._scope = self._validate_requested_scope(self._command_def, scope)
        from ..comm.comm_buffer import CommBuffer

        self._buffer: CommBuffer | None = None
        self._message_processor = None
        self._is_tmcc_rx = False
        self._is_tmcc4 = False

        # save the command bits from the def, as we will be modifying them
        self._command_bits: int = self._command_def.bits

        # apply the given address and data
        self._apply_address()
        self._apply_data()

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __call__(self, message: CommandReq) -> None:
        """
        Allows CommandReqs to receive messages from channels
        this request is subscribed to
        """
        if self._message_processor:
            self._message_processor(message)

    def __repr__(self) -> str:
        if self.is_data:
            data = f" {self.data}"
        else:
            data = ""
        rx = " (RX)" if self.is_tmcc_rx else ""
        return f"[{self.scope.name} {self.address} {self.command_name}{data}{rx} (0x{self.as_bytes.hex()})]"

    @property
    def address(self) -> int:
        if self.command_def.is_addressable:
            return self._address
        else:
            return DEFAULT_ADDRESS

    @address.setter
    def address(self, new_address: int) -> None:
        if self.command_def.is_addressable and new_address != self._address:
            self._address = new_address
            self._apply_address()

    @property
    def data(self) -> int:
        return self._data

    @data.setter
    def data(self, new_data: int) -> None:
        if self.is_data and new_data != self._data:
            self._data = new_data
            self._apply_data()

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @scope.setter
    def scope(self, new_scope: CommandScope) -> None:
        if new_scope != self._scope:
            # can only change scope for Engine and Train commands, and then, just from the one to the other
            if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
                if new_scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
                    self._scope = new_scope
                    self._apply_scope()
                    return
            raise AttributeError(f"Scope {new_scope} not supported for {self}")

    @property
    def is_halt(self) -> bool:
        return self.command == TMCC1HaltCommandEnum.HALT

    @property
    def is_system_halt(self) -> bool:
        return self.command in [TMCC2HaltCommandEnum.HALT, TMCC2EngineCommandEnum.SYSTEM_HALT]

    @property
    def command(self) -> E:
        return self._command_def_enum

    @property
    def command_name(self) -> str:
        return self._command_name

    @property
    def command_def(self) -> TMCC2CommandDef:
        return self._command_def

    @property
    def native_scope(self) -> CommandScope:
        return self._native_scope

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
        return self._command_def.is_tmcc1 is True

    @property
    def is_tmcc2(self) -> bool:
        return self._command_def.is_tmcc2 is True

    @property
    def identifier(self) -> int | None:
        return self.command_def.identifier

    @property
    def is_tmcc_rx(self) -> bool:
        return self._is_tmcc_rx

    @property
    def is_filtered(self) -> bool:
        return self.command_def.is_filtered is True and self.is_tmcc_rx is False

    @property
    def is_force_state_update(self) -> bool:
        """
        For the most part, the Base 3 doesn't broadcast received commands to other receivers.
        This prevents the PyTrain server and attached clients from maintaining accurate state
        for 4-digit engines. To compensate, we echo all commands to 4-digit engines after we
        send them to the Base 3.

        This method is used to determine if a command should be force-broadcast to all clients.
        """
        if isinstance(self.command_def, TMCC2CommandDef):
            return self.command_def.is_d4_broadcast is False and self.address > 99
        return False

    def send(
        self,
        repeat: int = 1,
        delay: float = 0,
        duration: float = 0,
        interval: int = None,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
    ) -> None:
        interval = self.command_def.interval if self.command_def.interval else interval
        self._enqueue_command(
            self.as_bytes,
            repeat,
            delay,
            duration,
            baudrate,
            port,
            server,
            request=self,
            interval=interval,
        )

    @property
    def as_bytes(self) -> bytes:
        if self.scope is None:
            first_byte = self.command_def.first_byte
        else:
            first_byte = self._determine_first_byte(self.command_def, self.scope)
        byte_str = first_byte + self._command_bits.to_bytes(2, byteorder="big")
        if self.address > 99:
            byte_str += str(self.address).zfill(4).encode()
        return byte_str

    def as_action(
        self,
        repeat: int = 1,
        delay: float = 0,
        duration: float = 0,
        interval: int = DEFAULT_DURATION_INTERVAL_MSEC,
        baudrate: int = DEFAULT_BAUDRATE,
        port: str = DEFAULT_PORT,
        server: str = None,
        address: int = None,
        data: int = None,
    ) -> Callable:
        from ..comm.comm_buffer import CommBuffer

        buffer = CommBuffer.build(baudrate=baudrate, port=port, server=server)

        def send_func(new_address: int = None, new_data: int = None, trigger_effects: bool = True) -> None:
            if new_address and new_address != self.address:
                self.address = new_address
            elif address and address != self.address:
                self.address = address
            if self.num_data_bits:
                if new_data is not None and new_data != self.data:
                    self.data = new_data
                elif data is not None and data != self.data:
                    self.data = data

            self._enqueue_command(
                self.as_bytes,
                repeat=repeat,
                delay=delay,
                duration=duration,
                interval=interval,
                baudrate=baudrate,
                port=port,
                server=server,
                buffer=buffer,
                request=self,
                trigger_effects=trigger_effects,
            )

        return send_func

    def _apply_address(self, new_address: int = None) -> int:
        if not self.command_def.is_addressable:  # HALT command
            return self._command_bits
        # reset existing address bits, if any
        self._command_bits &= self._command_def.address_mask
        # figure out which address we're using
        the_address = new_address if new_address and new_address > 0 else self._address
        if self.syntax == CommandSyntax.TMCC:
            self._command_bits |= the_address << 7
            if self.scope == CommandScope.TRAIN and self.identifier == TMCC1CommandIdentifier.ENGINE:
                self._command_bits &= TMCC1_TRAIN_COMMAND_PURIFIER
                self._command_bits |= TMCC1_TRAIN_COMMAND_MODIFIER
        elif self.syntax == CommandSyntax.LEGACY:
            if 1 <= the_address <= 99:
                self._command_bits |= the_address << 9
        else:
            raise ValueError(f"Command syntax not recognized {self.syntax}")
        return self._command_bits

    def _apply_data(self, new_data: int = None) -> int:
        """
        For commands that take parameters, such as engine speed and brake level,
        apply the data bits to the command action bytes to form the complete byte
        set to send to the Lionel LCS SER2.
        """
        data = new_data if new_data is not None else self.data
        if self.num_data_bits and data is None:
            raise ValueError("Data is required")
        if self.num_data_bits == 0:
            return self.bits
        elif self.command_def.data_map:
            if data in self.command_def.data_map:
                data = self.command_def.data_map[data]
            else:
                raise ValueError(f"Invalid data: {data} (not in map)")
        elif data < self.command_def.data_min or data > self.command_def.data_max:
            raise ValueError(f"Invalid: {data} not in range {self.command_def.data_min}-{self.command_def.data_max}")
        # sanitize data so we don't set bits we shouldn't
        data_bits = 2**self.num_data_bits - 1
        filtered_data = data & data_bits
        if data != filtered_data:
            raise ValueError(f"Invalid data: {data} (not in range)")
        # clear out old data
        self._command_bits &= 0xFFFF & ~data_bits
        # set new data
        self._command_bits |= data
        return self._command_bits

    def _apply_scope(self, new_scope: CommandScope = None) -> int:
        scope = new_scope if new_scope is not None else self.scope
        if self.syntax == CommandSyntax.TMCC and self.identifier == TMCC1CommandIdentifier.ENGINE:
            self._command_bits &= TMCC1_TRAIN_COMMAND_PURIFIER
            if scope == CommandScope.TRAIN:
                self._command_bits |= TMCC1_TRAIN_COMMAND_MODIFIER
        elif self.syntax == CommandSyntax.LEGACY:
            pass
        else:
            raise ValueError(f"Command syntax not recognized {self.syntax}")
        return self._command_bits

    # noinspection PyUnresolvedReferences
    @classmethod
    def build_tmcc1_command_req(cls, param: bytes) -> Self:
        value = int.from_bytes(param[1:3], byteorder="big")
        for tmcc_enum in [
            TMCC1HaltCommandEnum,
            TMCC1SwitchCommandEnum,
            TMCC1AuxCommandEnum,
            TMCC1RouteCommandEnum,
            TMCC1EngineCommandEnum,
            TMCC1SyncCommandEnum,
        ]:
            scope = None
            cmd_enum = tmcc_enum.by_value(value)
            if (
                cmd_enum is None
                and tmcc_enum == TMCC1EngineCommandEnum
                and (value & TMCC1_TRAIN_COMMAND_MODIFIER) == TMCC1_TRAIN_COMMAND_MODIFIER
            ):
                # check if this is a TRAIN command and if so, clear out the
                # train bits and look again; only do this for engine commands
                cmd_enum = tmcc_enum.by_value(value & TMCC1_TRAIN_COMMAND_PURIFIER)
                if cmd_enum:
                    scope = CommandScope.TRAIN
            if cmd_enum:
                # build_req the request and return
                data = cmd_enum.value.data_from_bytes(param[1:3])
                address = cmd_enum.value.address_from_bytes(param[1:3])
                return CommandReq.build(cmd_enum, address, data, scope)
        raise ValueError(f"Invalid tmcc1 command: {param.hex(':')}")

    @classmethod
    def build_tmcc2_command_req(cls, param: bytes, is_tmcc4: bool = False) -> R:
        if len(param) == 3 or (len(param) == 7 and param[1] in {0x00, 0x01}):
            value = int.from_bytes(param[1:3], byteorder="big")
            for tmcc_enum in [TMCC2HaltCommandEnum, TMCC2EngineCommandEnum, TMCC2RouteCommandEnum]:
                cmd_enum = tmcc_enum.by_value(value)
                if cmd_enum is not None:
                    scope = cmd_enum.scope
                    if int(param[0]) == LEGACY_TRAIN_COMMAND_PREFIX:
                        scope = CommandScope.TRAIN
                    # build_req the request and return
                    data = cmd_enum.value.data_from_bytes(param[1:3])
                    if len(param) == 7 and param[1] in {0x00, 0x01}:
                        # TODO: this code looks fragile; should rethink
                        addr_str = ""
                        for i in range(3, 7):
                            addr_str += chr(param[i])
                        address = int(addr_str)
                    else:
                        address = cmd_enum.value.address_from_bytes(param[1:3])
                    return CommandReq.build(cmd_enum, address, data, scope)
            raise ValueError(f"Invalid tmcc2 command: {param.hex(':')}")
        else:
            from ..protocol.multibyte.multibyte_command_req import MultiByteReq

            return MultiByteReq.from_bytes(param, is_tmcc4=is_tmcc4)

    @classmethod
    def build_tmcc4_command_req(cls, param: bytes) -> R:
        return cls.build_tmcc2_command_req(param, is_tmcc4=True)


TMCC4_FIRST_BYTE_TO_INTERPRETER = {
    LEGACY_ENGINE_COMMAND_PREFIX: CommandReq.build_tmcc4_command_req,
}

TMCC_FIRST_BYTE_TO_INTERPRETER = {
    TMCC1_COMMAND_PREFIX: CommandReq.build_tmcc1_command_req,
    LEGACY_ENGINE_COMMAND_PREFIX: CommandReq.build_tmcc2_command_req,
    LEGACY_TRAIN_COMMAND_PREFIX: CommandReq.build_tmcc2_command_req,
    LEGACY_EXTENDED_BLOCK_COMMAND_PREFIX: CommandReq.build_tmcc2_command_req,
}
