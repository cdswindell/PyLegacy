from __future__ import annotations

import abc
import threading
from abc import ABC
from collections import defaultdict
from datetime import datetime
from typing import Tuple, TypeVar, Set

from ..comm.comm_buffer import CommBuffer
from ..pdi.asc2_req import Asc2Req
from ..pdi.base_req import BaseReq
from ..pdi.bpc2_req import Bpc2Req
from ..pdi.constants import Asc2Action, PdiCommand, Bpc2Action, IrdaAction
from ..pdi.irda_req import IrdaReq, IrdaSequence
from ..pdi.pdi_req import PdiReq
from ..pdi.stm2_req import Stm2Req
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope, BROADCAST_ADDRESS, CommandSyntax
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandDef as Aux
from ..protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandDef, TMCC1_COMMAND_TO_ALIAS_MAP
from ..protocol.tmcc1.tmcc1_constants import TMCC1SwitchState as Switch, TMCC1HaltCommandDef
from ..protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandDef, TMCC2_COMMAND_TO_ALIAS_MAP

C = TypeVar("C", bound=CommandDefEnum)
E = TypeVar("E", bound=CommandDefEnum)
P = TypeVar("P", bound=PdiReq)
L = TypeVar("L", bound=CommandReq)


DIRECTIONS_SET = {
    TMCC1EngineCommandDef.FORWARD_DIRECTION,
    TMCC2EngineCommandDef.FORWARD_DIRECTION,
    TMCC1EngineCommandDef.REVERSE_DIRECTION,
    TMCC2EngineCommandDef.REVERSE_DIRECTION,
}

MOMENTUM_SET = {
    TMCC1EngineCommandDef.MOMENTUM_LOW,
    TMCC1EngineCommandDef.MOMENTUM_MEDIUM,
    TMCC1EngineCommandDef.MOMENTUM_HIGH,
    TMCC2EngineCommandDef.MOMENTUM_LOW,
    TMCC2EngineCommandDef.MOMENTUM_MEDIUM,
    TMCC2EngineCommandDef.MOMENTUM_HIGH,
    TMCC2EngineCommandDef.MOMENTUM,
}

SPEED_SET = {
    TMCC1EngineCommandDef.ABSOLUTE_SPEED,
    TMCC2EngineCommandDef.ABSOLUTE_SPEED,
    (TMCC1EngineCommandDef.ABSOLUTE_SPEED, 0),
    (TMCC2EngineCommandDef.ABSOLUTE_SPEED, 0),
}

STARTUP_SET = {TMCC2EngineCommandDef.START_UP_IMMEDIATE, TMCC2EngineCommandDef.START_UP_DELAYED}

SHUTDOWN_SET = {
    TMCC1EngineCommandDef.SHUTDOWN_DELAYED,
    (TMCC1EngineCommandDef.NUMERIC, 5),
    TMCC2EngineCommandDef.SHUTDOWN_DELAYED,
    (TMCC2EngineCommandDef.NUMERIC, 5),
    TMCC2EngineCommandDef.SHUTDOWN_IMMEDIATE,
}


# noinspection PyUnresolvedReferences
class ComponentState(ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, scope: CommandScope = None) -> None:
        self._scope = scope
        self._last_command: CommandReq | None = None
        self._last_updated: datetime | None = None
        self._road_name = None
        self._road_number = None
        self._number = None
        self._address: int | None = None
        self._ev = threading.Event()

        from .component_state_store import DependencyCache

        self._dependencies = DependencyCache.build()

    def __repr__(self) -> str:
        return f"{self.scope.name} {self._address}"

    def __lt__(self, other):
        return self.address < other.address

    def results_in(self, command: CommandReq) -> Set[E]:
        effects = self._dependencies.results_in(command.command, dereference_aliases=True, include_aliases=False)
        if command.is_data:
            # noinspection PyTypeChecker
            effects.update(
                self._dependencies.results_in(
                    (command.command, command.data), dereference_aliases=True, include_aliases=False
                )
            )
        return effects

    def _harvest_effect(self, effects: Set[E]) -> E | Tuple[E, int] | None:
        for effect in effects:
            if isinstance(effect, tuple):
                effect_enum = effect[0]
                effect_data = effect[1]
            else:
                effect_enum = effect
                effect_data = None
            if effect_enum.syntax == self.syntax:
                if effect_data is None:
                    return effect_enum
                else:
                    return effect_enum, effect_data
        return None

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def friendly_scope(self) -> str:
        return self.scope.name.title()

    @property
    def address(self) -> int:
        return self._address

    @property
    def last_command(self) -> CommandReq:
        return self._last_command

    @property
    def last_updated(self) -> datetime:
        return self._last_updated

    @property
    def changed(self) -> threading.Event:
        return self._ev

    @property
    def road_name(self) -> str | None:
        return self._road_name

    @property
    def road_number(self) -> str | None:
        return self._road_number

    @abc.abstractmethod
    def update(self, command: L | P) -> None:
        if command and command.command != TMCC1HaltCommandDef.HALT:
            if self._address is None and command.address != BROADCAST_ADDRESS:
                self._address = command.address
            # invalid states
            elif self._address is None and command.address == BROADCAST_ADDRESS:
                raise AttributeError(
                    f"Received broadcast address for {self.friendly_scope} but component has not "
                    f"been initialized {self}"
                )
            elif command.address not in [self._address, BROADCAST_ADDRESS]:
                raise AttributeError(
                    f"{self.friendly_scope} #{self._address} received update for "
                    f"{command.scope.name.title()} #{command.address}, ignoring"
                )
            if self.scope != command.scope:
                scope = command.scope.name.title()
                raise AttributeError(f"{self.friendly_scope} {self.address} received update for {scope}, ignoring")
            if isinstance(command, BaseReq) and command.status == 0:
                if hasattr(command, "name") and command.name:
                    self._road_name = command.name
                if hasattr(command, "number") and command.number:
                    self._road_number = command.number
            self._last_updated = datetime.now()
            self._last_command = command

    def time_delta(self, recv_time: datetime) -> float:
        return (self._last_updated - recv_time).total_seconds()

    @property
    def syntax(self) -> CommandSyntax:
        return CommandSyntax.LEGACY if self.is_legacy else CommandSyntax.TMCC

    @property
    @abc.abstractmethod
    def is_known(self) -> bool:
        """
        Returns True if component's state is known, False otherwise.
        """
        ...

    @property
    @abc.abstractmethod
    def is_tmcc(self) -> bool:
        """
        Returns True if component responds to TMCC protocol, False otherwise.
        """
        ...

    @property
    @abc.abstractmethod
    def is_legacy(self) -> bool:
        """
        Returns True if component responds to Legacy/TMCC2 protocol, False otherwise.
        """
        ...

    @property
    @abc.abstractmethod
    def is_lcs(self) -> bool:
        """
        Returns True if component is an LCS device, False otherwise.
        """
        ...

    @abc.abstractmethod
    def as_bytes(self) -> bytes:
        """
        Returns the component state as a bytes object representative of the TMCC/Legacy
        byte sequence used to trigger the corresponding action(s) when received by the
        component.

        Used to synchronize component state when client attaches to the server.
        """
        ...


class TmccState(ComponentState, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, scope: CommandScope = None) -> None:
        super().__init__(scope)

    @property
    def is_tmcc(self) -> bool:
        return True

    @property
    def is_legacy(self) -> bool:
        return False

    @property
    def is_lcs(self) -> bool:
        return True


class LcsState(ComponentState, ABC):
    __metaclass__ = abc.ABCMeta

    def __init__(self, scope: CommandScope = None) -> None:
        super().__init__(scope)

    @property
    def is_tmcc(self) -> bool:
        return False

    @property
    def is_legacy(self) -> bool:
        return False

    @property
    def is_lcs(self) -> bool:
        return True


class SwitchState(TmccState):
    """
    Maintain the perceived state of a Switch
    """

    def __init__(self, scope: CommandScope = CommandScope.SWITCH) -> None:
        if scope != CommandScope.SWITCH:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._state: Switch | None = None

    def __repr__(self) -> str:
        name = num = ""
        if self.road_name is not None:
            name = f" {self.road_name}"
        if self.road_number is not None:
            num = f" #{self.road_number} "
        return f"Switch {self.address}: {self._state.name if self._state is not None else 'Unknown'}{name}{num}"

    def update(self, command: L | P) -> None:
        if command:
            super().update(command)
            if command.command == TMCC1HaltCommandDef.HALT:
                return  # do nothing on halt
            if isinstance(command, CommandReq):
                if command.command != Switch.SET_ADDRESS:
                    self._state = command.command
            elif isinstance(command, Asc2Req) or isinstance(command, Stm2Req):
                self._state = Switch.THROUGH if command.is_thru else Switch.OUT
            elif isinstance(command, BaseReq):
                pass
            else:
                print(f"Unhandled Switch State Update received: {command}")
            self.changed.set()

    @property
    def state(self) -> Switch:
        return self._state

    @property
    def is_known(self) -> bool:
        return self._state is not None

    @property
    def is_through(self) -> bool:
        return self._state == Switch.THROUGH

    @property
    def is_out(self) -> bool:
        return self._state == Switch.OUT

    @property
    def is_tmcc(self) -> bool:
        return True

    @property
    def is_legacy(self) -> bool:
        return False

    def as_bytes(self) -> bytes:
        if self.is_known:
            return CommandReq.build(self.state, self.address).as_bytes
        else:
            return bytes()


class AccessoryState(TmccState):
    def __init__(self, scope: CommandScope = CommandScope.ACC) -> None:
        if scope != CommandScope.ACC:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._last_aux1_opt1 = None
        self._last_aux2_opt1 = None
        self._aux1_state: Aux | None = None
        self._aux2_state: Aux | None = None
        self._aux_state: Aux | None = None
        self._block_power = False
        self._sensor_track = False
        self._number: int | None = None

    def __repr__(self) -> str:
        aux1 = aux2 = aux_num = ""
        if self._block_power:
            aux = f"Block Power {'ON' if self.aux_state == Aux.AUX1_OPT_ONE else 'OFF'}"
        elif self._sensor_track:
            aux = "Sensor Track"
        else:
            if self.aux_state == Aux.AUX1_OPT_ONE:
                aux = "Aux 1"
            elif self.aux_state == Aux.AUX2_OPT_ONE:
                aux = "Aux 2"
            else:
                aux = "Unknown"
            aux1 = f" Aux1: {self.aux1_state.name if self.aux1_state is not None else 'Unknown'}"
            aux2 = f" Aux2: {self.aux2_state.name if self.aux2_state is not None else 'Unknown'}"
            aux_num = f" Aux Num: {self._number if self._number is not None else 'NA'}"
        name = num = ""
        if self.road_name is not None:
            name = f" {self.road_name}"
        if self.road_number is not None:
            num = f" #{self.road_number} "
        return f"Accessory {self.address}: {aux}{aux1}{aux2}{aux_num}{name}{num}"

    # noinspection DuplicatedCode
    def update(self, command: L | P) -> None:
        if command:
            super().update(command)
            if isinstance(command, CommandReq):
                if command.command != Aux.SET_ADDRESS:
                    if command.command == TMCC1HaltCommandDef.HALT:
                        self._aux1_state = Aux.AUX1_OFF
                        self._aux2_state = Aux.AUX2_OFF
                        self._aux_state = Aux.AUX2_OPT_ONE
                        self._number = None
                    else:
                        if command.command in [Aux.AUX1_OPT_ONE, Aux.AUX2_OPT_ONE]:
                            self._aux_state = command.command
                        if command.command == Aux.AUX1_OPT_ONE:
                            if self._last_aux1_opt1 is None or self.time_delta(self._last_aux1_opt1) > 1:
                                self._aux1_state = (
                                    Aux.AUX1_ON
                                    if (
                                        self._aux1_state is None
                                        or self._aux1_state == Aux.AUX1_OPT_ONE
                                        or self._aux1_state == Aux.AUX1_OFF
                                    )
                                    else Aux.AUX1_OFF
                                )
                            self._last_aux1_opt1 = self.last_updated
                        elif command.command in [Aux.AUX1_ON, Aux.AUX1_OFF, Aux.AUX1_OPT_TWO]:
                            self._aux1_state = command.command
                            self._last_aux1_opt1 = self.last_updated
                        elif command.command == Aux.AUX2_OPT_ONE:
                            if self._last_aux2_opt1 is None or self.time_delta(self._last_aux2_opt1) > 1:
                                self._aux2_state = (
                                    Aux.AUX2_ON
                                    if (
                                        self._aux2_state is None
                                        or self._aux2_state == Aux.AUX2_OPT_ONE
                                        or self._aux2_state == Aux.AUX2_OFF
                                    )
                                    else Aux.AUX2_OFF
                                )
                            self._last_aux2_opt1 = self.last_updated
                        elif command.command in [Aux.AUX2_ON, Aux.AUX2_OFF, Aux.AUX2_OPT_TWO]:
                            self._aux2_state = command.command
                            self._last_aux2_opt1 = self.last_updated
                        if command.command == Aux.NUMERIC:
                            self._number = command.data
            elif isinstance(command, Asc2Req) or isinstance(command, Bpc2Req):
                if command.action in [Asc2Action.CONTROL1, Bpc2Action.CONTROL1, Bpc2Action.CONTROL3]:
                    if command.action in [Bpc2Action.CONTROL1, Bpc2Action.CONTROL3]:
                        self._block_power = True
                    if command.state == 1:
                        self._aux1_state = Aux.AUX1_ON
                        self._aux2_state = Aux.AUX2_ON
                        self._aux_state = Aux.AUX1_OPT_ONE
                    else:
                        self._aux1_state = Aux.AUX1_OFF
                        self._aux2_state = Aux.AUX2_OFF
                        self._aux_state = Aux.AUX2_OPT_ONE
            elif isinstance(command, IrdaReq):
                self._sensor_track = True
            self.changed.set()

    @property
    def is_known(self) -> bool:
        return (
            self._aux_state is not None
            or self._aux1_state is not None
            or self._aux2_state is not None
            or self._number is not None
        )

    @property
    def aux_state(self) -> Aux:
        return self._aux_state

    @property
    def is_aux_on(self) -> bool:
        return self._aux_state == Aux.AUX1_OPT_ONE

    @property
    def is_aux_off(self) -> bool:
        return self._aux_state == Aux.AUX2_OPT_ONE

    @property
    def aux1_state(self) -> Aux:
        return self._aux1_state

    @property
    def aux2_state(self) -> Aux:
        return self._aux2_state

    @property
    def value(self) -> int:
        return self._number

    @property
    def is_tmcc(self) -> bool:
        return True

    @property
    def is_legacy(self) -> bool:
        return False

    def as_bytes(self) -> bytes:
        byte_str = bytes()
        if self._aux_state is not None:
            byte_str += CommandReq.build(self.aux_state, self.address).as_bytes
        if self._aux1_state is not None:
            byte_str += CommandReq.build(self.aux1_state, self.address).as_bytes
            if self._aux2_state is not None:
                byte_str += CommandReq.build(self.aux2_state, self.address).as_bytes
        return byte_str


class EngineState(ComponentState):
    def __init__(self, scope: CommandScope = CommandScope.ENGINE) -> None:
        if scope not in [CommandScope.ENGINE, CommandScope.TRAIN]:
            raise ValueError(f"Invalid scope: {scope}, expected ENGINE or TRAIN")
        super().__init__(scope)
        self._start_stop: CommandDefEnum | None = None
        self._speed: int | None = None
        self._direction: CommandDefEnum | None = None
        self._momentum: int | None = None
        self._is_legacy: bool = False  # assume we are in TMCC mode until/unless we receive a Legacy cmd

    def __repr__(self) -> str:
        speed = direction = start_stop = name = num = mom = ""
        if self._direction in [TMCC1EngineCommandDef.FORWARD_DIRECTION, TMCC2EngineCommandDef.FORWARD_DIRECTION]:
            direction = " FWD"
        elif self._direction in [TMCC1EngineCommandDef.REVERSE_DIRECTION, TMCC2EngineCommandDef.REVERSE_DIRECTION]:
            direction = " REV"

        if self._speed is not None:
            speed = f" Speed: {self._speed}"

        if self._start_stop is not None:
            if self._start_stop in STARTUP_SET:
                start_stop = " Started up"
            elif self._start_stop in SHUTDOWN_SET:
                start_stop = " Shut down"
        if self._momentum is not None:
            mom = f" Momentum: {self._momentum}"
        if self.road_name is not None:
            name = f" {self.road_name}"
        if self.road_number is not None:
            num = f" #{self.road_number}"
        return f"{self.scope.name} {self._address}{start_stop}{speed}{mom}{direction}{name}{num}"

    def is_known(self) -> bool:
        return self._direction is not None or self._start_stop is not None or self._speed is not None

    def update(self, command: L | P) -> None:
        super().update(command)
        if isinstance(command, CommandReq):
            if command.syntax == CommandSyntax.LEGACY:
                self._is_legacy = True

            # get the downstream effects of this command, as they also impact state
            cmd_effects = self.results_in(command)
            # print(f"Update: {command}\nEffects: {cmd_effects}")

            # handle direction
            if command.command in DIRECTIONS_SET:
                self._direction = command.command
            elif cmd_effects & DIRECTIONS_SET:
                self._direction = self._harvest_effect(cmd_effects & DIRECTIONS_SET)

            # handle speed
            if command.command in SPEED_SET:
                self._speed = command.data
            elif cmd_effects & SPEED_SET:
                speed = self._harvest_effect(cmd_effects & SPEED_SET)
                if isinstance(speed, tuple) and len(speed) == 2:
                    self._speed = speed[1]
                else:
                    self._speed = None
                    print(f"**************** What am I supposed to do with {speed}?")

            # handle momentum
            if command.command in MOMENTUM_SET:
                if command.command in [TMCC1EngineCommandDef.MOMENTUM_LOW, TMCC2EngineCommandDef.MOMENTUM_LOW]:
                    self._momentum = 0
                if command.command in [TMCC1EngineCommandDef.MOMENTUM_MEDIUM, TMCC2EngineCommandDef.MOMENTUM_MEDIUM]:
                    self._momentum = 3
                if command.command in [TMCC1EngineCommandDef.MOMENTUM_HIGH, TMCC2EngineCommandDef.MOMENTUM_HIGH]:
                    self._momentum = 7
                elif command.command == TMCC2EngineCommandDef.MOMENTUM:
                    self._momentum = command.data

            # handle startup/shutdown
            if command.command in STARTUP_SET:
                self._start_stop = command.command
            elif command.command in SHUTDOWN_SET:
                self._start_stop = command.command
            elif cmd_effects & STARTUP_SET:
                self._start_stop = self._harvest_effect(cmd_effects & STARTUP_SET)
            elif cmd_effects & SHUTDOWN_SET:
                shutdown = self._harvest_effect(cmd_effects & SHUTDOWN_SET)
                if isinstance(shutdown, CommandDefEnum):
                    self._start_stop = shutdown
                elif command.is_data and (command.command, command.data) in TMCC2_COMMAND_TO_ALIAS_MAP:
                    self._start_stop = TMCC2_COMMAND_TO_ALIAS_MAP[(command.command, command.data)]
                elif command.is_data and (command.command, command.data) in TMCC1_COMMAND_TO_ALIAS_MAP:
                    self._start_stop = TMCC1_COMMAND_TO_ALIAS_MAP[(command.command, command.data)]
        elif (
            isinstance(command, BaseReq)
            and command.status == 0
            and command.pdi_command
            in [
                PdiCommand.BASE_ENGINE,
                PdiCommand.BASE_TRAIN,
                PdiCommand.UPDATE_ENGINE_SPEED,
                PdiCommand.UPDATE_TRAIN_SPEED,
            ]
        ):
            if self._speed is None:
                self._speed = command.speed
        self.changed.set()

    def as_bytes(self) -> bytes:
        byte_str = bytes()
        if self._start_stop is not None:
            byte_str += CommandReq.build(self._start_stop, self.address, scope=self.scope).as_bytes
        if self._direction is not None:
            # the direction state will have encoded in it the syntax (tmcc1 or tmcc2)
            byte_str += CommandReq.build(self._direction, self.address, scope=self.scope).as_bytes
        if self._speed is not None:
            if self.is_tmcc:
                byte_str += CommandReq.build(
                    TMCC1EngineCommandDef.ABSOLUTE_SPEED, self.address, data=self.speed, scope=self.scope
                ).as_bytes
            elif self.is_legacy:
                byte_str += CommandReq.build(
                    TMCC2EngineCommandDef.ABSOLUTE_SPEED, self.address, data=self.speed, scope=self.scope
                ).as_bytes
        return byte_str

    @property
    def speed(self) -> int | None:
        return self._speed

    @property
    def direction(self) -> CommandDefEnum | None:
        return self._direction

    @property
    def stop_start(self) -> CommandDefEnum | None:
        return self._start_stop

    @property
    def is_tmcc(self) -> bool:
        return self._is_legacy is False

    @property
    def is_legacy(self) -> bool:
        return self._is_legacy is True

    @property
    def is_lcs(self) -> bool:
        return False


class TrainState(EngineState):
    def __init__(self, scope: CommandScope = CommandScope.TRAIN) -> None:
        if scope not in [CommandScope.TRAIN]:
            raise ValueError(f"Invalid scope: {scope}, expected TRAIN")
        super().__init__(scope)


class IrdaState(LcsState):
    """
    Maintain the state of a Sensor Track (Irda)
    """

    def __init__(self, scope: CommandScope = CommandScope.IRDA) -> None:
        if scope != CommandScope.IRDA:
            raise ValueError(f"Invalid scope: {scope}")
        super().__init__(scope)
        self._sequence: IrdaSequence | None = None
        self._loco_rl: int | None = 255
        self._loco_lr: int | None = 255

    def __repr__(self) -> str:
        rle = f"{self._loco_rl}" if self._loco_rl and self._loco_rl != 255 else "Any"
        lre = f"{self._loco_lr}" if self._loco_lr and self._loco_lr != 255 else "Any"
        rl = f" When Engine ID (R -> L): {rle}"
        lr = f" When Engine ID (L -> R): {lre}"
        return f"Sensor Track {self.address}: Sequence: {self.sequence_str}{rl}{lr}"

    def update(self, command: P) -> None:
        from .component_state_store import ComponentStateStore

        if command:
            super().update(command)
            if command.pdi_command == PdiCommand.IRDA_RX:
                if command.action == IrdaAction.CONFIG:
                    self._sequence = command.sequence
                    self._loco_rl = command.loco_rl
                    self._loco_lr = command.loco_lr
                elif command.action == IrdaAction.SEQUENCE:
                    self._sequence = command.sequence
                elif command.action == IrdaAction.DATA and CommBuffer.is_server:
                    # change train speed, based on direction of travel
                    if self.sequence in [IrdaSequence.SLOW_SPEED_NORMAL_SPEED, IrdaSequence.NORMAL_SPEED_SLOW_SPEED]:
                        rr_speed = None
                        if command.is_right_to_left:
                            rr_speed = (
                                "SPEED_SLOW"
                                if self.sequence == IrdaSequence.SLOW_SPEED_NORMAL_SPEED
                                else "SPEED_NORMAL"
                            )
                        elif command.is_left_to_right:
                            rr_speed = (
                                "SPEED_NORMAL"
                                if self.sequence == IrdaSequence.SLOW_SPEED_NORMAL_SPEED
                                else "SPEED_SLOW"
                            )
                        if rr_speed:
                            address = None
                            scope = CommandScope.ENGINE
                            if command.train_id:
                                address = command.train_id
                                scope = CommandScope.TRAIN
                            elif command.engine_id:
                                address = command.engine_id
                            state = ComponentStateStore.get_state(scope, address)
                            if state:
                                if state.is_tmcc:
                                    cdef = TMCC1EngineCommandDef(rr_speed)
                                else:
                                    cdef = TMCC2EngineCommandDef(rr_speed)
                                CommandReq.send_request(cdef, address, scope=scope)
            self.changed.set()

    @property
    def is_known(self) -> bool:
        return self._sequence is not None

    @property
    def sequence(self) -> IrdaSequence:
        return self._sequence

    @property
    def sequence_str(self) -> str | None:
        return self.sequence.name.title() if self.sequence else "NA"

    def as_bytes(self) -> bytes:
        if self.is_known:
            return IrdaReq(
                self.address,
                PdiCommand.IRDA_RX,
                IrdaAction.CONFIG,
                sequence=self._sequence,
                loco_rl=self._loco_rl,
                loco_lr=self._loco_lr,
            ).as_bytes
        else:
            return bytes()


SCOPE_TO_STATE_MAP: [CommandScope, ComponentState] = {
    CommandScope.SWITCH: SwitchState,
    CommandScope.ACC: AccessoryState,
    CommandScope.ENGINE: EngineState,
    CommandScope.TRAIN: TrainState,
    CommandScope.IRDA: IrdaState,
}


class SystemStateDict(defaultdict):
    """
    Maintains a dictionary of CommandScope to ComponentStateDict
    """

    def __missing__(self, key: CommandScope | Tuple[CommandScope, int]) -> ComponentStateDict:
        """
        generate a ComponentState object for the dictionary, based on the key
        """
        if isinstance(key, CommandScope) and key in SCOPE_TO_STATE_MAP:
            scope = key
        else:
            raise KeyError(f"Invalid scope key: {key}")
        # create the component state dict for this key
        self[key] = ComponentStateDict(scope)
        return self[key]


class ComponentStateDict(defaultdict):
    def __init__(self, scope: CommandScope):
        super().__init__(None)  # base class doesn't get a factory
        if scope not in SCOPE_TO_STATE_MAP:
            raise ValueError(f"Invalid scope: {scope}")
        self._scope = scope

    @property
    def scope(self) -> CommandScope:
        return self._scope

    def __missing__(self, key: int) -> ComponentState:
        """
        generate a ComponentState object for the dictionary, based on the key
        """
        if not isinstance(key, int) or key < 1 or key > 99:
            raise KeyError(f"Invalid ID: {key}")
        value: ComponentState = SCOPE_TO_STATE_MAP[self._scope](self._scope)
        value._address = key
        self[key] = value
        return self[key]
