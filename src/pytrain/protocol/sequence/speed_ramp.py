#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
from threading import Event, RLock, Thread
from time import time
from typing import TYPE_CHECKING, Callable

from .ramped_speed_req import labor_delta
from ..command_def import CommandDefEnum
from ..constants import CommandScope, PROGRAM_NAME
from ..multibyte.multibyte_constants import TMCC2EngineCommandEnumEx
from ..tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, tmcc2_speed_to_rpm

if TYPE_CHECKING:  # pragma: no cover
    from ...db.engine_state import EngineState
    from ..command_req import CommandReq

log = logging.getLogger(__name__)

__all__ = [
    "BASE_STEP_DELAY",
    "CLAIMED_HISTORY",
    "DEFAULT_LABOR",
    "DEFAULT_RAMP_LINGER",
    "ECHO_TTL",
    "LEGACY_SPEED_MAX",
    "MAX_RPM",
    "MAX_RPM_BIAS",
    "ORDERED_FAMILIES",
    "TMCC1_ECHO_TOLERANCE",
    "TMCC1_SPEED_MAX",
    "UNSET_MAX_SPEED",
    "EchoFamily",
    "EchoLedger",
    "EchoOutcome",
    "PendingEcho",
    "RampRegistry",
    "RampStep",
    "SPEED_FAMILIES",
    "Sender",
    "SpeedRamp",
    "biased_rpm",
    "default_sender",
    "echo_family",
    "effective_target",
    "labor_delta",
    "next_step",
    "ramp_delay",
    "ramp_increment",
    "rpm_bias_for",
    "rpm_max_speed",
    "speed_ceiling",
]

# the speed ceilings each generation falls back to when the engine's own is unknown
LEGACY_SPEED_MAX: int = 199
TMCC1_SPEED_MAX: int = 31

# the value Lionel uses to mean "this ceiling has never been set"
UNSET_MAX_SPEED: int = 255

# step delay geometry, preserved from RampedSpeedReq
BASE_STEP_DELAY: float = 0.200
LEGACY_MOMENTUM_DELAY: float = 0.010
TMCC1_MOMENTUM_DELAY: float = 0.100

# RPM notches run 0 through 7. A derived bias is held only to the notch range itself:
# a deliberate trim is never silently reduced, and a wider band is safe because
# biased_rpm() clamps every emitted value to 0..MAX_RPM, so nothing illegal can
# reach the wire
MAX_RPM: int = 7
MAX_RPM_BIAS: int = MAX_RPM

# how long a settled ramp lingers, waiting for a retarget, before its thread exits;
# this absorbs a burst of joystick nudges into retargets rather than thread starts
DEFAULT_RAMP_LINGER: float = 0.250

# the effort value an engine that has never reported one is assumed to be at
DEFAULT_LABOR: int = 12

# how long a step the ramp issued stays claimable. A command that reached the Base 3 is
# always echoed back, but the round trip can take a while and a client sees it only
# after the server has broadcast it, so the budget is generous
ECHO_TTL: float = 5.000

# how many already matched values are remembered. Only the most recent one is ever
# accepted again - a command sent two or three times, as the Lionel ecosystem does, is
# not out of sequence - so the rest of the ring is diagnostic: it is what a log line
# needs to explain why an echo was or was not recognized
CLAIMED_HISTORY: int = 64

# a TMCC1 speed round trips through encode_tmcc_speed / decode_tmcc_speed, which can
# shift it by one, so its echoes are matched with a little slack
TMCC1_ECHO_TOLERANCE: int = 1

Sender = Callable[[CommandDefEnum, int, int, CommandScope], None]


class EchoFamily(Enum):
    """
    The command families a ramp issues. Echoes of the four interleave arbitrarily,
    but each family's own order is preserved on the wire, so each gets its own queue.

    SPEED and TARGET both carry a speed, and are deliberately kept apart: TARGET_SPEED
    is declared noop, so CommBuffer never puts it on the rails and the dispatcher hands
    it back in microseconds, while an ABSOLUTE_SPEED makes a real round trip through the
    Base 3 and comes back hundreds of milliseconds later. Two paths that far apart are
    not one ordered stream: sharing a queue let a target announcement overtake a step
    still in flight, and the ramp then took its own echo for another controller's.
    """

    SPEED = auto()  # ABSOLUTE_SPEED, both generations: a Base 3 round trip
    TARGET = auto()  # TARGET_SPEED, both generations: announced in process, never railed
    RPM = auto()  # DIESEL_RPM
    EFFORT = auto()  # ENGINE_LABOR / ENGINE_LABOR_DEFAULT


class EchoOutcome(Enum):
    """What a ramp should do about a command that arrived through engine state."""

    MINE = auto()  # the ramp's own echo: ignore it
    ABSORB = auto()  # a foreign RPM or effort setting: re-baseline and keep ramping
    FOREIGN = auto()  # a foreign throttle command: abort


ECHO_FAMILIES: dict[CommandDefEnum, EchoFamily] = {
    TMCC1EngineCommandEnum.ABSOLUTE_SPEED: EchoFamily.SPEED,
    TMCC1EngineCommandEnum.TARGET_SPEED: EchoFamily.TARGET,
    TMCC2EngineCommandEnum.ABSOLUTE_SPEED: EchoFamily.SPEED,
    TMCC2EngineCommandEnumEx.TARGET_SPEED: EchoFamily.TARGET,
    TMCC2EngineCommandEnum.DIESEL_RPM: EchoFamily.RPM,
    TMCC2EngineCommandEnum.ENGINE_LABOR: EchoFamily.EFFORT,
    TMCC2EngineCommandEnum.ENGINE_LABOR_DEFAULT: EchoFamily.EFFORT,
}

# the two families that carry a throttle setting: matched with the generation's speed
# tolerance, and a deviation in either is another controller taking the engine
SPEED_FAMILIES: frozenset[EchoFamily] = frozenset({EchoFamily.SPEED, EchoFamily.TARGET})

# the families whose commands travel over the wire and are echoed back in the order they
# were sent, so a value arriving out of that order came from somewhere else. TARGET is
# deliberately not one of them: a TARGET_SPEED is declared noop, never reaches the rails,
# and is handed straight back by the dispatcher, so its reflection has no ordering
# relationship to anything - any target this ramp announced inside the lag budget is its
# own, whichever order they come back in
ORDERED_FAMILIES: frozenset[EchoFamily] = frozenset({EchoFamily.SPEED, EchoFamily.RPM, EchoFamily.EFFORT})


def echo_family(command: CommandDefEnum) -> EchoFamily | None:
    """The family a command belongs to, or None if a ramp never arbitrates it."""
    return ECHO_FAMILIES.get(command, None)


@dataclass(frozen=True)
class PendingEcho:
    """One command the ramp has issued, or is about to, awaiting its own echo."""

    data: int
    sent_at: float


class EchoLedger:
    """
    An ordered record of the commands a ramp has issued, so that the ramp can tell its
    own reflection from another controller taking the engine.

    Both a client, through the server broadcast, and a server, through base3_send and
    the dispatcher, see their own commands come back. A command that reaches the Base 3
    is *always* echoed, and always in the order it was sent, so for the railed families
    the queue is strict: the only value that can be this ramp's own is the next echo it
    is waiting for, and anything else arrived out of sequence, which means it came from
    another controller.

    The one documented exception - an LCS Ser2 re-echoing the Base 3's commands seconds
    late and out of order (see CommandDispatcher.run) - cannot reach a ramp: those
    commands are all declared `filtered`, and ComponentStateStore drops filtered
    commands outright on the one configuration where the replay happens, a layout
    listening to both a Base 3 and a Ser2.

    TARGET_SPEED never travels that path at all, so its queue is matched by membership
    rather than by order; see ORDERED_FAMILIES.
    """

    def __init__(self, ttl: float = ECHO_TTL, history: int = CLAIMED_HISTORY) -> None:
        self._ttl = ttl
        self._lock = RLock()
        self._pending: dict[EchoFamily, deque[PendingEcho]] = {family: deque() for family in EchoFamily}
        self._claimed: dict[EchoFamily, deque[PendingEcho]] = {family: deque(maxlen=history) for family in EchoFamily}

    def record(self, family: EchoFamily, data: int | None) -> None:
        """
        Note a command as issued. This is done *before* it is handed to the sender, so
        that an echo which somehow beats us back is still recognized.
        """
        if data is None:
            return
        with self._lock:
            self.purge()
            self._pending[family].append(PendingEcho(data, time()))

    def claim(self, family: EchoFamily, data: int | None, *, tolerance: int = 0) -> bool:
        """
        Try to account for an inbound value as one of this ramp's own commands.

        For a family that travels over the wire, only the head of the queue can be ours.
        Echoes come back in the order they were sent, so a value that is not the one we
        are waiting for arrived out of sequence, and a value the ramp never issued is not
        in the queue at all: both mean another controller. Matching anywhere in the queue
        is what let a foreign speed be taken for a step this ramp had swept through
        seconds earlier.

        The single concession there is an exact repeat of the value just matched. The
        Lionel ecosystem sends a command two or three times, and a repeat is not out of
        sequence - nothing newer has been seen since - so it is accepted without
        consuming the entry behind it.

        A family that is never railed has no order to be out of, so any value it issued
        inside the lag budget is its own.
        """
        if data is None:
            return False
        with self._lock:
            self.purge()
            queue = self._pending[family]
            if family in ORDERED_FAMILIES:
                if queue and abs(queue[0].data - data) <= tolerance:
                    self._claimed[family].append(queue.popleft())
                    return True
                claimed = self._claimed[family]
                return bool(claimed) and abs(claimed[-1].data - data) <= tolerance
            for index, entry in enumerate(queue):
                if abs(entry.data - data) <= tolerance:
                    del queue[index]
                    self._claimed[family].append(entry)
                    return True
            return any(abs(entry.data - data) <= tolerance for entry in self._claimed[family])

    def purge(self, ttl: float = None) -> None:
        """Drop entries older than the lag budget, claimed or not."""
        ttl = self._ttl if ttl is None else ttl
        cutoff = time() - ttl
        with self._lock:
            for family in EchoFamily:
                queue = self._pending[family]
                while queue and queue[0].sent_at <= cutoff:
                    queue.popleft()
                # entries carry the time the command was sent rather than the time it was
                # matched, so the ring is filtered rather than popped from the head: age
                # is a property of the command, not of when its echo happened to land
                claimed = self._claimed[family]
                if claimed:
                    kept = [entry for entry in claimed if entry.sent_at > cutoff]
                    if len(kept) != len(claimed):
                        claimed.clear()
                        claimed.extend(kept)

    @property
    def pending(self) -> dict[EchoFamily, tuple[int, ...]]:
        """The values still awaiting an echo, in the order they were sent."""
        with self._lock:
            return {family: tuple(entry.data for entry in queue) for family, queue in self._pending.items()}

    @property
    def claimed(self) -> dict[EchoFamily, tuple[int, ...]]:
        """The values already matched, oldest first; the last one is still claimable."""
        with self._lock:
            return {family: tuple(entry.data for entry in queue) for family, queue in self._claimed.items()}


@dataclass(frozen=True)
class RampStep:
    """
    One step of a ramp: the absolute speed to send, plus the effort and RPM that
    accompany it. `labor` and `rpm` are None when they do not apply to this step,
    either because the engine cannot accept them or because the step is part of a
    deceleration, where RPM is dropped once up front rather than step by step.
    """

    speed: int
    labor: int | None
    rpm: int | None
    delay: float


# PySimplifyBooleanCheck: the `is True` / `is False` comparisons here and throughout
# SpeedRamp are PyTrain's defensive idiom for values read from live, possibly
# unpopulated engine state; there are over 200 of them across src/, including
# db/engine_state.py:866-867 in the very property this module depends on. They are
# deliberately not simplified.
# noinspection PySimplifyBooleanCheck
def ramp_increment(state: EngineState, is_legacy: bool) -> int:
    """
    How many speed steps a single ramp step covers, read from live momentum.

    TMCC1 always moves one step of its 32; a Legacy engine moves three, easing to
    two at momentum 4 and to one at momentum 6.
    """
    if is_legacy is not True:
        return 1
    momentum = state.momentum if state is not None else None
    if momentum is None:
        return 3
    if momentum >= 6:
        return 1
    if momentum >= 4:
        return 2
    return 3


def ramp_delay(state: EngineState, is_legacy: bool) -> float:
    """
    How long to wait between ramp steps, read from live momentum. A momentum that
    has not been learned yet falls back to the base delay.
    """
    momentum = state.momentum if state is not None else None
    if momentum is None:
        return BASE_STEP_DELAY
    per_notch = LEGACY_MOMENTUM_DELAY if is_legacy is True else TMCC1_MOMENTUM_DELAY
    return BASE_STEP_DELAY + (momentum * per_notch)


def speed_ceiling(state: EngineState) -> int:
    """
    The engine's live operating ceiling: `EngineState.speed_max`, which already
    folds `max_speed` and the operator's `speed_limit` together, with a generation
    appropriate fallback when it is unknown.
    """
    speed_max = state.speed_max if state is not None else None
    if speed_max is None or speed_max == UNSET_MAX_SPEED:
        return LEGACY_SPEED_MAX if (state is not None and state.is_legacy is True) else TMCC1_SPEED_MAX
    return speed_max


def effective_target(requested: int, state: EngineState) -> int:
    """
    Clamp the operator's requested target to the engine's live ceiling. This is the
    single place the speed_limit / max_speed ceiling is applied, so a limit set,
    changed, or cleared mid-ramp is honored on the very next step. The requested
    target itself is never rewritten, so raising or clearing a limit lets a ramp
    resume toward what the operator originally asked for.
    """
    # noinspection PyUnreachableCode
    if requested is None:
        # noinspection PyTypeChecker
        return None
    return max(0, min(requested, speed_ceiling(state)))


def rpm_max_speed(state: EngineState) -> int | None:
    """
    The roster ceiling that shapes the engine's RPM curve, or None to use the base
    table. This is the one place the generation guard lives: a TMCC1 engine's
    `max_speed` is decoded onto the 0-31 scale, which would squeeze the entire RPM
    curve into a 31-step window, and TMCC1 emits no DIESEL_RPM in any case.

    Note this is `max_speed`, the engine's own ceiling, and deliberately not
    `speed_max`: a speed limit changes where a ramp stops, not where the diesel
    notches fall.
    """
    if state is None or state.is_legacy is not True:
        return None
    max_speed = state.max_speed
    if max_speed is None or max_speed <= 0 or max_speed == UNSET_MAX_SPEED:
        return None
    return max_speed


def biased_rpm(speed: int, bias: int, max_speed: int = None) -> int:
    """
    The RPM notch for a speed, offset by the ramp's bias and clamped to 0…MAX_RPM.
    RPM is sourced exclusively through tmcc2_constants.py, so TMCC2_SPEED_TO_RPM
    remains the one hand-edited curve.
    """
    rpm = tmcc2_speed_to_rpm(speed, max_speed)
    return max(0, min(MAX_RPM, rpm + (bias or 0)))


def rpm_bias_for(state: EngineState) -> int:
    """
    The engine's RPM offset from its own curve: an engine at speed 30 reporting RPM
    3 where its table says 2 carries a +1 bias, which the ramp then preserves at
    every step and at settle. Derived from, and so directly comparable with, the
    same map `biased_rpm` emits from.

    A stopped engine is the clearest baseline there is: at a standstill there is no
    curve value to subtract, so its reported RPM *is* the trim, verbatim.

    Zero for an engine that is not RPM capable, or that has not reported a speed or
    an RPM yet, since there is then nothing to compare against; otherwise held to a
    +/- MAX_RPM_BIAS band.
    """
    if state is None or state.is_rpm is not True:
        return 0
    speed = state.speed
    rpm = state.rpm
    # EngineState.speed is annotated -> int but returns None when comp_data has not
    # arrived, so this guard only looks dead to the inspector
    # noinspection PyUnreachableCode
    if speed is None or rpm is None:
        return 0
    if speed == 0:
        bias = rpm
    else:
        bias = rpm - tmcc2_speed_to_rpm(speed, rpm_max_speed(state))
    return max(-MAX_RPM_BIAS, min(MAX_RPM_BIAS, bias))


def next_step(
    commanded: int,
    requested: int,
    state: EngineState,
    init_labor: int,
    rpm_bias: int,
) -> RampStep | None:
    """
    The next step of a ramp, computed entirely from live state, or None when the
    ramp has arrived.

    Because the comparison is the ramp's own commanded speed against the *effective*
    target, a ceiling that drops below the commanded speed naturally yields a
    decrementing step: setting a speed limit of 20 while running at 80 slows the
    engine to 20 with no special case.
    """
    is_legacy = state is not None and state.is_legacy is True
    target = effective_target(requested, state)
    if target is None or commanded is None or commanded == target:
        return None

    increment = ramp_increment(state, is_legacy)
    delay = ramp_delay(state, is_legacy)
    if target > commanded:
        speed = min(commanded + increment, target)
        accelerating = True
    else:
        speed = max(commanded - increment, target)
        accelerating = False

    # effort and RPM are Legacy only commands
    labor = labor_delta(speed, target, init_labor) if is_legacy else None
    if is_legacy and accelerating and state.is_rpm is True:
        rpm = biased_rpm(speed, rpm_bias, rpm_max_speed(state))
    else:
        # on deceleration RPM is dropped once, up front, as RampedSpeedReq does today
        rpm = None
    return RampStep(speed=speed, labor=labor, rpm=rpm, delay=delay)


def default_sender(command: CommandDefEnum, address: int, data: int, scope: CommandScope) -> None:
    """
    The production send path: a single command, straight out, with no delay, so that
    nothing a ramp issues ever enters DelayHandler and nothing can be left queued
    behind an abort.
    """
    from ..command_req import CommandReq

    CommandReq.build(command, address, data, scope).send(delay=0)


# noinspection PySimplifyBooleanCheck
class SpeedRamp(Thread):
    """
    One daemon thread per ramp target, closing the gap between an engine's commanded
    speed and the target the operator asked for.

    The target is the touchstone: a new request retargets this thread in place rather
    than cancelling it and building a new schedule, and every step recomputes its
    increment, delay, effort, and RPM from live engine state. That is what lets
    momentum, a speed limit, or an RPM trim applied mid-ramp take effect on the very
    next step.
    """

    def __init__(
        self,
        state: EngineState,
        target_speed: int,
        *,
        dialog: bool = False,
        sender: Sender = None,
        linger: float = DEFAULT_RAMP_LINGER,
        delay_scale: float = 1.0,
    ) -> None:
        scope = state.scope
        tmcc_id = state.tmcc_id
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Speed Ramp {scope.title} {tmcc_id}")
        self._state = state
        self._scope = scope
        self._address = tmcc_id
        self._dialog = dialog
        self._sender = sender if sender is not None else default_sender
        self._linger = linger
        self._delay_scale = delay_scale
        self._lock = RLock()
        self._wake = Event()
        self._is_running = True
        self._abort_reason: str | None = None

        # the operator's intent, deliberately left unclamped so that raising or
        # clearing a speed limit lets this ramp resume toward it with no new request
        self._requested_target = target_speed

        # what this thread last sent; the lagged Base 3 echo is read exactly once, here
        speed = state.speed
        self._commanded_speed = speed if speed is not None else 0

        # baselines, captured once: they are never resampled on retarget, so a burst
        # of joystick nudges cannot let effort or RPM drift
        labor = state.labor
        self._init_labor = labor if labor is not None else DEFAULT_LABOR
        self._rpm_bias = rpm_bias_for(state)
        self._rpm_max_speed = rpm_max_speed(state)

        # last values actually sent, seeded from what the engine already reports so the
        # ramp does not open by re-announcing a value that is already in effect
        self._last_speed: int | None = None
        self._last_labor: int | None = labor
        self._last_rpm: int | None = state.rpm if state.is_rpm is True else None
        self._decelerating = False

        # the ordered record of what this ramp has issued, so its own lagged echoes
        # cannot be mistaken for another controller's throttle command
        self._ledger = EchoLedger()
        self._ledger.record(EchoFamily.TARGET, self._requested_target)

        # whether the Base 3 has ever reported this ramp's own target back to us; until
        # it has, a record still carrying the engine's previous target is stale news
        # rather than evidence of another controller
        self._target_confirmed = False

    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def scope(self) -> CommandScope:
        return self._scope

    @property
    def tmcc_id(self) -> int:
        return self._address

    @property
    def requested_speed(self) -> int:
        """The operator's target, unclamped."""
        with self._lock:
            return self._requested_target

    @property
    def target_speed(self) -> int:
        """The requested target clamped to the engine's live ceiling."""
        with self._lock:
            return effective_target(self._requested_target, self._state)

    @property
    def commanded_speed(self) -> int:
        """The speed this thread last sent, which is authoritative for the ramp."""
        with self._lock:
            return self._commanded_speed

    @property
    def rpm_bias(self) -> int:
        with self._lock:
            return self._rpm_bias

    @property
    def rpm_max_speed(self) -> int | None:
        """The roster ceiling currently shaping this ramp's RPM curve."""
        with self._lock:
            return self._rpm_max_speed

    @property
    def init_labor(self) -> int:
        with self._lock:
            return self._init_labor

    @property
    def dialog(self) -> bool:
        return self._dialog

    @property
    def is_active(self) -> bool:
        return self._is_running is True and self.is_alive()

    @property
    def abort_reason(self) -> str | None:
        return self._abort_reason

    @property
    def is_legacy(self) -> bool:
        return self._state is not None and self._state.is_legacy is True

    @property
    def echo_ledger(self) -> EchoLedger:
        return self._ledger

    @property
    def is_target_confirmed(self) -> bool:
        """Whether the Base 3 has yet reported this ramp's own target speed back to us."""
        return self._target_confirmed

    @property
    def speed_echo_tolerance(self) -> int:
        return 0 if self.is_legacy is True else TMCC1_ECHO_TOLERANCE

    def retarget(self, speed: int, *, dialog: bool = False) -> None:
        """
        Point a running ramp at a new target. Nothing is cancelled, and no second
        thread is started; the loop simply wakes and recomputes from where it is.
        """
        with self._lock:
            self._requested_target = speed
            if dialog is True:
                self._dialog = True
        # a target delivered through the ramp itself is not foreign: note it before the
        # façade's TARGET_SPEED reaches the wire, so its echo is claimed rather than
        # taken for another controller grabbing the throttle. It goes in the TARGET
        # queue, never among the steps: a target announcement is handed back in process
        # and would otherwise overtake a step still on its way to the Base 3
        self._ledger.record(EchoFamily.TARGET, speed)
        self._wake.set()

    def abort(self, reason: str = None, *, target_speed: int = None, restore_effort: bool = False) -> None:
        """
        Stop the ramp within one step interval, sending nothing further and leaving
        the engine at whatever speed it was last commanded to.

        The target the ramp was chasing will never be reached now, so the state's
        target speed is squared up with where the engine is actually headed:
        `target_speed` when the caller knows it - 0 for a hard stop, the speed another
        controller just commanded when it takes the throttle - and otherwise the speed
        this ramp had reached.

        `restore_effort` is set by the hard stops - a HALT, a reset, an emergency stop,
        a direction change, a shutdown - which take the engine to a standstill and reset
        effort to neutral in state. Effort is the one thing an engine does not return on
        its own, so the command has to go out: without it the locomotive keeps laboring
        at whatever notch the ramp had dialed in, and the next Base 3 record reports
        that notch straight back into the state the abort just cleaned.
        """
        with self._lock:
            if self._is_running is False:
                return
            self._is_running = False
            self._abort_reason = reason
            settled = self._commanded_speed if target_speed is None else target_speed
        # every abort path must clear is_ramping, or encode_target_speed keeps returning
        # None and the engine's target speed stops resyncing with the Base 3. It is also
        # what lets the target speed below be recorded at all
        self._set_ramping(False)
        self._sync_target_speed(settled)
        if restore_effort is True and self.is_legacy is True:
            self._send(TMCC2EngineCommandEnum.ENGINE_LABOR, DEFAULT_LABOR)
            self._last_labor = DEFAULT_LABOR
        log.debug(f"Speed ramp aborted {self._scope.title} {self._address}: {reason}")
        self._wake.set()

    def arbitrate(self, command: CommandReq) -> EchoOutcome:
        """
        Decide what an inbound command means to this ramp: its own echo, a foreign
        trim to absorb, or a foreign throttle command that must stop it.
        """
        family = echo_family(command.command)
        if family is None:
            return EchoOutcome.MINE
        data = command.data
        is_speed = family in SPEED_FAMILIES
        tolerance = self.speed_echo_tolerance if is_speed else 0
        # the ledger goes first, so an echo consumes the entry it belongs to and the
        # queue drains as the ramp runs. Asking the commanded speed first left every
        # step pending for the whole lag budget, and any foreign speed inside that
        # trailing band was then taken for one of them
        if self._ledger.claim(family, data, tolerance=tolerance) is True:
            return EchoOutcome.MINE
        if is_speed and data is not None:
            with self._lock:
                commanded = self._commanded_speed
            # the one genuinely ambiguous case: another controller asking for exactly the
            # speed this ramp is sitting at is indistinguishable from a repeat of our own
            # step, and harmless either way - the engine is already where it wants it
            if commanded is not None and abs(commanded - data) <= tolerance:
                return EchoOutcome.MINE
        return EchoOutcome.FOREIGN if is_speed else EchoOutcome.ABSORB

    def on_state_command(self, command: CommandReq) -> bool:
        """
        Arbitrate one command that reached engine state. Returns True when the ramp must
        *not* be cancelled: its own echo, however late or out of order, and every RPM or
        effort command, foreign or not - a sound trim is not a throttle takeover.
        """
        outcome = self.arbitrate(command)
        if outcome is EchoOutcome.MINE:
            return True
        family = echo_family(command.command)
        if outcome is EchoOutcome.FOREIGN:
            # everything needed to tell an out of sequence echo from a value this ramp
            # never issued: what it is waiting for, what it last matched, and where it is
            log.info(
                f"Speed ramp {self._scope.title} {self._address} aborting: out of sequence speed "
                f"{command.data}, commanded {self.commanded_speed}, "
                f"pending steps {self._ledger.pending[EchoFamily.SPEED]}, "
                f"pending targets {self._ledger.pending[EchoFamily.TARGET]}, "
                f"last matched {self._ledger.claimed[family][-1:]}"
            )
            return False
        if family is EchoFamily.RPM:
            self._absorb_rpm(command.data)
        else:
            self._absorb_labor(command.data)
        return True

    def owns_target_speed(self, target_speed: int | None) -> bool:
        """
        Whether a target speed reported back through engine state is one this ramp asked
        for: the target it is chasing, that target clamped to the engine's live ceiling,
        or any target it announced inside the echo lag budget - a Base 3 record queried
        before a retarget went out can still be in flight when the new target lands.
        """
        if target_speed is None:
            return False
        with self._lock:
            requested = self._requested_target
            if target_speed == requested or target_speed == effective_target(requested, self._state):
                return True
        announced = self._ledger.pending[EchoFamily.TARGET] + self._ledger.claimed[EchoFamily.TARGET]
        return target_speed in announced

    def on_reported_target_speed(self, target_speed: int | None) -> bool:
        """
        Arbitrate the target speed a Base 3 memory record hands back. Returns True when
        the ramp must *not* be cancelled.

        A second PyTrain instance driving this engine directly leaves no TMCC command on
        our wire: it writes the base's own target byte, and the change reaches us only in
        the next record. That record is the sole evidence of the takeover, so it has to
        count as one.

        Nothing is judged until the base has reported this ramp's own target at least
        once. A record queried before the ramp's announcement reached the base still
        carries the engine's previous target, and aborting on one of those would kill a
        ramp within a refresh cycle of starting it.
        """
        if self.owns_target_speed(target_speed) is True:
            self._target_confirmed = True
            return True
        return self._target_confirmed is False

    def _absorb_rpm(self, rpm: int | None) -> None:
        """
        Re-derive the ramp's RPM bias from an operator's trim, against the ramp's own
        commanded speed and its current map - never against the lagged state.speed,
        which would compute the offset at a speed the engine has already left.
        """
        if rpm is None:
            return
        with self._lock:
            bias = rpm - tmcc2_speed_to_rpm(self._commanded_speed, self._rpm_max_speed)
            self._rpm_bias = max(-MAX_RPM_BIAS, min(MAX_RPM_BIAS, bias))
            self._last_rpm = rpm

    def _absorb_labor(self, labor: int | None) -> None:
        """Re-baseline the effort the settle step hands back to the operator."""
        if labor is None:
            return
        with self._lock:
            self._init_labor = labor
            self._last_labor = labor

    def run(self) -> None:
        state = self._state
        try:
            self._set_ramping(True)
            # give the façade's TARGET_SPEED announcement time to reach the wire first
            if self._pause(ramp_delay(state, self.is_legacy)):
                return
            while self._is_running is True:
                with self._lock:
                    requested = self._requested_target
                    commanded = self._commanded_speed
                self._sync_rpm_map(commanded)
                step = next_step(commanded, requested, state, self._init_labor, self._rpm_bias)
                if step is None:
                    self._settle()
                    if self._linger_for_retarget() is False:
                        return
                    self._set_ramping(True)
                    continue
                self._prime_deceleration(step.speed < commanded, requested)
                self._send_step(step)
                if self._pause(step.delay):
                    return
        finally:
            self._is_running = False

    def _pause(self, delay: float) -> bool:
        """
        Wait out one step delay, interruptibly. Returns True when the ramp is done,
        so a retarget or an abort is acted on within one step interval rather than at
        the end of a queued sequence.
        """
        self._wake.wait(delay * self._delay_scale)
        self._wake.clear()
        return self._is_running is False

    def _sync_rpm_map(self, commanded: int) -> None:
        """
        Pick up a roster max_speed changed mid-ramp. A bias is only meaningful relative
        to a curve, so it is re-derived against the new map at the commanded speed,
        which keeps the emitted RPM continuous rather than jumping a notch or more.
        """
        current = rpm_max_speed(self._state)
        with self._lock:
            if current == self._rpm_max_speed:
                return
            if self._state.is_rpm is True:
                emitted = biased_rpm(commanded, self._rpm_bias, self._rpm_max_speed)
                bias = emitted - tmcc2_speed_to_rpm(commanded, current)
                self._rpm_bias = max(-MAX_RPM_BIAS, min(MAX_RPM_BIAS, bias))
            self._rpm_max_speed = current

    def _prime_deceleration(self, decelerating: bool, requested: int) -> None:
        """
        Drop RPM and effort up front when a ramp starts, or turns into, a deceleration,
        exactly as RampedSpeedReq does today, rather than easing them down step by step.
        """
        if decelerating is False:
            self._decelerating = False
            return
        if self._decelerating is True:
            return
        self._decelerating = True
        if self.is_legacy is False:
            return
        target = effective_target(requested, self._state)
        labor = labor_delta(self._commanded_speed, target, self._init_labor)
        if labor != self._last_labor:
            self._send(TMCC2EngineCommandEnum.ENGINE_LABOR, labor)
            self._last_labor = labor
        if self._state.is_rpm is True:
            rpm = biased_rpm(target, self._rpm_bias, self._rpm_max_speed)
            if rpm != self._last_rpm:
                self._send(TMCC2EngineCommandEnum.DIESEL_RPM, rpm)
                self._last_rpm = rpm

    def _send_step(self, step: RampStep) -> None:
        # the commanded speed is taken before the command goes out, for the same reason
        # the ledger records it first: an abort or an echo that lands in between must
        # see the value that is actually on the wire
        with self._lock:
            self._commanded_speed = step.speed
        self._send(self._speed_enum, step.speed)
        self._last_speed = step.speed
        if self._is_running is False:
            # aborted out from under this step: an abort sends nothing further, and its
            # own effort restore has to be the last word on the wire rather than being
            # overwritten by the trailing trim of a step already in flight
            return
        if step.labor is not None and step.labor != self._last_labor:
            self._send(TMCC2EngineCommandEnum.ENGINE_LABOR, step.labor)
            self._last_labor = step.labor
        if step.rpm is not None and step.rpm != self._last_rpm:
            self._send(TMCC2EngineCommandEnum.DIESEL_RPM, step.rpm)
            self._last_rpm = step.rpm

    def _settle(self) -> None:
        """
        Land the ramp: the exact target once, the target's biased RPM, and the effort
        setting the operator had before the ramp began.
        """
        state = self._state
        with self._lock:
            target = effective_target(self._requested_target, state)
            self._commanded_speed = target
        if target != self._last_speed:
            self._send(self._speed_enum, target)
            self._last_speed = target
        if self._is_running is False:
            return
        if self.is_legacy is True:
            if state.is_rpm is True:
                rpm = biased_rpm(target, self._rpm_bias, self._rpm_max_speed)
                if rpm != self._last_rpm:
                    self._send(TMCC2EngineCommandEnum.DIESEL_RPM, rpm)
                    self._last_rpm = rpm
            self._send(TMCC2EngineCommandEnum.ENGINE_LABOR, self._init_labor)
            self._last_labor = self._init_labor
        self._decelerating = False
        self._set_ramping(False)

    def _linger_for_retarget(self) -> bool:
        """
        Hang around briefly after settling, so that the next nudge of a joystick
        retargets this thread instead of starting another one. Returns True when a
        retarget arrived and the loop should carry on.
        """
        if self._pause(self._linger):
            return False
        with self._lock:
            commanded = self._commanded_speed
            requested = self._requested_target
        return next_step(commanded, requested, self._state, self._init_labor, self._rpm_bias) is not None

    def _send(self, command: CommandDefEnum, data: int) -> None:
        family = echo_family(command)
        if family is not None:
            self._ledger.record(family, data)
        self._sender(command, self._address, data, self._scope)

    def _set_ramping(self, value: bool) -> None:
        try:
            self._state.is_ramping = value
        except AttributeError:  # pragma: no cover
            pass

    def _sync_target_speed(self, target_speed: int) -> None:
        """Record where the engine is headed now that this ramp is no longer driving it."""
        try:
            self._state.sync_target_speed(target_speed)
        except AttributeError:
            pass

    @property
    def _speed_enum(self) -> CommandDefEnum:
        return TMCC2EngineCommandEnum.ABSOLUTE_SPEED if self.is_legacy else TMCC1EngineCommandEnum.ABSOLUTE_SPEED


class RampRegistry:
    """
    The one place a live ramp is looked up, keyed by (scope, tmcc_id), so engine 12
    and train 12 are distinct targets with distinct threads.

    Ramps stay owned by the instance that started them; the registry only keeps the
    handles, retargets rather than restarts, and gives cross-cutting operations - a
    HALT, a shutdown, diagnostics - a single door. Dead threads are reaped on every
    access, so the dictionary cannot grow without bound.
    """

    _instance: RampRegistry | None = None
    _lock = RLock()

    @classmethod
    def build(cls) -> RampRegistry:
        with cls._lock:
            if cls._instance is None:
                cls._instance = RampRegistry()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Abort every ramp and drop the singleton; for shutdown and for tests."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.abort_all(reason="reset")
            cls._instance = None

    def __init__(self) -> None:
        self._ramps: dict[tuple[CommandScope, int], SpeedRamp] = {}
        self._ramps_lock = RLock()

    def ramp_to(
        self,
        state: EngineState,
        speed: int,
        *,
        dialog: bool = False,
        sender: Sender = None,
        **kwargs,
    ) -> SpeedRamp:
        """
        Start a ramp for this target, or point the one already running at the new
        speed. A burst of joystick requests therefore yields one thread and a series
        of retargets, never a thread per nudge.
        """
        key = self.key_for(state)
        with self._ramps_lock:
            self._reap()
            ramp = self._ramps.get(key)
            if ramp is not None and ramp.is_active is True:
                ramp.retarget(speed, dialog=dialog)
                return ramp
            ramp = SpeedRamp(state, speed, dialog=dialog, sender=sender, **kwargs)
            self._ramps[key] = ramp
            # started under the lock so that a concurrent reap cannot mistake a ramp
            # that has not run yet for one that has already finished
            ramp.start()
        return ramp

    def get(self, state: EngineState) -> SpeedRamp | None:
        with self._ramps_lock:
            self._reap()
            return self._ramps.get(self.key_for(state))

    def abort(
        self,
        state: EngineState,
        reason: str = None,
        *,
        target_speed: int = None,
        restore_effort: bool = False,
    ) -> None:
        with self._ramps_lock:
            self._reap()
            ramp = self._ramps.pop(self.key_for(state), None)
        if ramp is not None:
            ramp.abort(reason, target_speed=target_speed, restore_effort=restore_effort)

    def abort_all(
        self,
        scope: CommandScope = None,
        reason: str = None,
        *,
        target_speed: int = None,
        restore_effort: bool = False,
    ) -> None:
        """Stop every ramp, or every ramp in one scope, leaving the other scope alone."""
        with self._ramps_lock:
            keys = [k for k in self._ramps if scope is None or k[0] == scope]
            ramps = [self._ramps.pop(k) for k in keys]
        for ramp in ramps:
            ramp.abort(reason, target_speed=target_speed, restore_effort=restore_effort)

    @property
    def active_ramps(self) -> list[SpeedRamp]:
        with self._ramps_lock:
            self._reap()
            return list(self._ramps.values())

    def __len__(self) -> int:
        with self._ramps_lock:
            self._reap()
            return len(self._ramps)

    @staticmethod
    def key_for(state: EngineState) -> tuple[CommandScope, int]:
        return state.scope, state.tmcc_id

    def _reap(self) -> None:
        """Drop the handles of ramps that have settled and whose threads have exited."""
        dead = [k for k, r in self._ramps.items() if r.is_active is False]
        for key in dead:
            del self._ramps[key]
