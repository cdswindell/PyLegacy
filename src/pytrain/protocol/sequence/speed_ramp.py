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
from ..tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from ..tmcc2.tmcc2_constants import TMCC2EngineCommandEnum, tmcc2_speed_to_rpm

if TYPE_CHECKING:  # pragma: no cover
    from ...db.engine_state import EngineState
    from ..command_req import CommandReq

log = logging.getLogger(__name__)

__all__ = [
    "ABORT_GATE_TIMEOUT",
    "BASE_STEP_DELAY",
    "CLAIMED_HISTORY",
    "DEFAULT_LABOR",
    "DEFAULT_RAMP_LINGER",
    "ECHO_TTL",
    "LEGACY_SPEED_MAX",
    "MAX_RPM",
    "MAX_RPM_BIAS",
    "TMCC1_ECHO_TOLERANCE",
    "TMCC1_SPEED_MAX",
    "UNSET_MAX_SPEED",
    "EchoFamily",
    "EchoLedger",
    "EchoOutcome",
    "PendingEcho",
    "RampRegistry",
    "RampStep",
    "Sender",
    "SpeedRamp",
    "biased_rpm",
    "default_sender",
    "echo_family",
    "effective_target",
    "is_ramp_override",
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

# how long, in seconds, a step issued by the ramp stays claimable. Tune this window
# to allow for the Base 3 round trip and, on clients, the server broadcast delay
ECHO_TTL: float = 2.000

# how many already matched values are remembered. Only the most recent one is ever
# accepted again - a command sent two or three times, as the Lionel ecosystem does, is
# not out of sequence - so the rest of the ring is diagnostic: it is what a log line
# needs to explain why an echo was or was not recognized
CLAIMED_HISTORY: int = 64

# a TMCC1 speed round trips through encode_tmcc_speed / decode_tmcc_speed, which can
# shift it by one, so its echoes are matched with a little slack
TMCC1_ECHO_TOLERANCE: int = 1

# how long an abort waits for a step already under way to finish before sending its own
# commands. An abort runs on the dispatcher thread, holding the engine's condition, and a
# client's send is a synchronous socket round trip: waiting on one indefinitely would
# stall every state reader behind it, so a send that is taking too long degrades to the
# old racy behavior instead
ABORT_GATE_TIMEOUT: float = 0.500

Sender = Callable[[CommandDefEnum, int, int, CommandScope], None]


class EchoFamily(Enum):
    """
    The command families a ramp issues. Echoes of the three interleave arbitrarily,
    but each family's own order is preserved on the wire, so each gets its own queue.
    """

    SPEED = auto()  # ABSOLUTE_SPEED, both generations: a Base 3 round trip
    RPM = auto()  # DIESEL_RPM
    EFFORT = auto()  # ENGINE_LABOR / ENGINE_LABOR_DEFAULT


class EchoOutcome(Enum):
    """What a ramp should do about a command that arrived through engine state."""

    MINE = auto()  # the ramp's own echo: ignore it
    ABSORB = auto()  # a foreign RPM or effort setting: re-baseline and keep ramping
    FOREIGN = auto()  # a foreign throttle command: abort


ECHO_FAMILIES: dict[CommandDefEnum, EchoFamily] = {
    TMCC1EngineCommandEnum.ABSOLUTE_SPEED: EchoFamily.SPEED,
    TMCC2EngineCommandEnum.ABSOLUTE_SPEED: EchoFamily.SPEED,
    TMCC2EngineCommandEnum.DIESEL_RPM: EchoFamily.RPM,
    TMCC2EngineCommandEnum.ENGINE_LABOR: EchoFamily.EFFORT,
    TMCC2EngineCommandEnum.ENGINE_LABOR_DEFAULT: EchoFamily.EFFORT,
}


def echo_family(command: CommandDefEnum) -> EchoFamily | None:
    """The family a command belongs to, or None if a ramp never arbitrates it."""
    return ECHO_FAMILIES.get(command, None)


def is_ramp_override(command: CommandReq) -> bool:
    """Safety commands always supersede duplicate suppression and echo ownership."""
    name = command.command.name
    if name in {
        "HALT",
        "SYSTEM_HALT",
        "EMERGENCY_STOP",
        "STOP_IMMEDIATE",
        "SPEED_STOP_HOLD",
        "RESET",
        "RESET_ONLY",
        "FORWARD_DIRECTION",
        "REVERSE_DIRECTION",
        "TOGGLE_DIRECTION",
        "SHUTDOWN_IMMEDIATE",
        "SHUTDOWN_DELAYED",
        "SHUTDOWN_DELAYED_NOP",
    }:
        return True
    return (name == "ABSOLUTE_SPEED" and command.data == 0) or (name == "NUMERIC" and command.data in {0, 5})


@dataclass(frozen=True)
class PendingEcho:
    """One command the ramp has issued, or is about to, awaiting its own echo."""

    data: int
    sent_at: float


class EchoLedger:
    """
    An ordered record of the commands a ramp has issued, for one feedback stream, so
    that the ramp can tell its own reflection from another controller taking the engine.

    Both a client, through the server broadcast, and a server, through base3_send and
    the dispatcher, see their own commands come back. Base RX echoes have a separate
    ledger: an immediate local report must not retire a delayed RX echo. Reports may lag
    or skip intermediate steps, so any pending speed inside the lag budget can match. A match
    advances past all earlier steps: subsequent reports must move monotonically through
    send order, or repeat the last match. This also follows a deliberate ramp reversal
    without mistaking its decreasing speeds for another controller.

    RPM and effort still require the next pending echo; a deviation there is absorbed
    as a trim rather than stopping the ramp.

    The one documented exception - an LCS Ser2 re-echoing the Base 3's commands seconds
    late and out of order (see CommandDispatcher.run) - cannot reach a ramp: those
    commands are all declared `filtered`, and ComponentStateStore drops filtered
    commands outright on the one configuration where the replay happens, a layout
    listening to both a Base 3 and a Ser2.
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

        A speed may match anywhere in the pending queue, retiring both the matched
        entry and any skipped steps ahead of it. An older report can no longer match,
        even if it is still inside the lag budget. RPM and effort only match the head.

        The single concession there is an exact repeat of the value just matched. The
        Lionel ecosystem sends a command two or three times, and a repeat is not out of
        sequence - nothing newer has been seen since - so it is accepted without
        consuming the entry behind it.
        """
        if data is None:
            return False
        with self._lock:
            self.purge()
            queue = self._pending[family]
            if family is EchoFamily.SPEED:
                for index, entry in enumerate(queue):
                    if abs(entry.data - data) <= tolerance:
                        for _ in range(index + 1):
                            queue.popleft()
                        self._claimed[family].append(entry)
                        return True
            elif queue and abs(queue[0].data - data) <= tolerance:
                self._claimed[family].append(queue.popleft())
                return True
            claimed = self._claimed[family]
            return bool(claimed) and abs(claimed[-1].data - data) <= tolerance

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
    than canceling it and building a new schedule, and every step recomputes its
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
        peer=None,
    ) -> None:
        scope = state.scope
        tmcc_id = state.tmcc_id
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} Speed Ramp {scope.title} {tmcc_id}")
        self._state = state
        self._scope = scope
        self._address = tmcc_id
        self._dialog = dialog
        self._sender = sender if sender is not None else default_sender
        self._peer = peer
        self._use_default_peer = sender is None or sender is default_sender
        self.claim = None
        self._claim_pending = False
        self._claim_acquired = False
        self._claim_released = False
        self._starting = False
        self._linger = linger
        self._delay_scale = delay_scale
        self._lock = RLock()

        # the send gate: every emission is made under it, and so are the abort's own two
        # sends, so that "the ramp was stopped" and "the ramp put a command on the wire"
        # cannot interleave. Once an abort is given, nothing but the abort's sends reach
        # the engine.
        #
        # LOCK ORDER: state.synchronizer -> _wire -> _lock, never the reverse. abort()
        # runs with the engine's condition already held by ComponentState.update, so
        # nothing that reaches for state's lock - _set_ramping, _sync_target_speed - may
        # run while _wire is held, or the two threads deadlock against each other
        self._wire = RLock()
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

        # Independent send-order cursors for local/broadcast feedback and Base RX echoes.
        # Either stream can advance before the other reports an earlier step.
        self._ledger = EchoLedger()
        self._rx_ledger = EchoLedger()

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
        return self._is_running is True and (self._starting or self.is_alive())

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
    def speed_echo_tolerance(self) -> int:
        return 0 if self.is_legacy is True else TMCC1_ECHO_TOLERANCE

    def retarget(self, speed: int, *, dialog: bool = False) -> None:
        """
        Point a running ramp at a new target. Nothing is canceled, and no second
        thread is started; the loop simply wakes and recomputes from where it is.
        """
        with self._lock:
            self._requested_target = speed
            if dialog is True:
                self._dialog = True
        self._wake.set()

    def abort(
        self,
        reason: str = None,
        *,
        target_speed: int = None,
        hard_stop: bool = False,
        yield_speed: int = None,
    ) -> None:
        """
        Stop silently on ordinary takeover. The winning controller owns all settings.

        `yield_speed` remains accepted for EngineState compatibility, but only a hard
        stop may reassert it, and then only as zero. Hard stops also neutralize effort.
        """
        if self._stop_speed_ramp(reason) is False:
            return
        with self._lock:
            settled = self._commanded_speed if target_speed is None else target_speed
        self._set_ramping(False)
        self._sync_target_speed(0 if hard_stop else settled)
        if hard_stop is False:
            self._release_claim()
            return
        acquired = self._wire.acquire(timeout=ABORT_GATE_TIMEOUT)
        try:
            self._yield_road(0 if yield_speed is not None else None)
            self._restore_effort(True)
        finally:
            if acquired is True:
                self._wire.release()
            self._release_claim()

    def _stop_speed_ramp(self, reason: str | None) -> bool:
        """Stop flags only; safe while holding the send gate, with no state lock."""
        with self._lock:
            if self._is_running is False:
                return False
            self._is_running = False
            self._abort_reason = reason
            self._wake.set()
        log.debug(f"Speed ramp aborted {self._scope.title} {self._address}: {reason}")
        return True

    def _yield_road(self, yield_speed: int | None) -> None:
        """Reassert only a standstill, never another controller's positive speed."""
        if yield_speed != 0 or not all(ledger.pending[EchoFamily.SPEED] for ledger in (self._ledger, self._rx_ledger)):
            return
        with self._lock:
            self._commanded_speed = yield_speed
        self._send(self._speed_enum, yield_speed, aborting=True)
        self._last_speed = yield_speed

    def _restore_effort(self, hard_stop: bool) -> None:
        """Only hard stops may restore neutral effort after cancellation."""
        if hard_stop is False or self.is_legacy is False:
            return
        labor = DEFAULT_LABOR
        if labor == self._last_labor:
            # a ramp that never raised effort has nothing to hand back
            return
        self._send(TMCC2EngineCommandEnum.ENGINE_LABOR, labor, aborting=True)
        self._last_labor = labor

    def arbitrate(self, command: CommandReq) -> EchoOutcome:
        """
        Decide what an inbound command means to this ramp: its own echo, a foreign
        trim to absorb, or a foreign throttle command that must stop it.
        """
        if is_ramp_override(command):
            return EchoOutcome.FOREIGN
        with self._lock:
            # No own commands exist during acquisition. Let ordinary traffic update
            # state without treating it as takeover, and never retain it for replay.
            if self._claim_pending:
                return EchoOutcome.MINE
            family = echo_family(command.command)
            if family is None:
                return EchoOutcome.MINE
            data = command.data
            is_speed = family is EchoFamily.SPEED
            tolerance = self.speed_echo_tolerance if is_speed else 0
            ledger = self._rx_ledger if command.is_tmcc_rx else self._ledger
            # Never fall back to the other source's cursor or the requested destination.
            if ledger.claim(family, data, tolerance=tolerance) is True:
                return EchoOutcome.MINE
            return EchoOutcome.FOREIGN if is_speed else EchoOutcome.ABSORB

    def on_state_command(self, command: CommandReq) -> bool:
        """
        Arbitrate one command that reached engine state. Returns True when the ramp must
        *not* be canceled: its own recent, ordered speed echo, and every RPM or
        effort command, foreign or not - a sound trim is not a throttle takeover.
        """
        outcome = self.arbitrate(command)
        if outcome is EchoOutcome.MINE:
            return True
        family = echo_family(command.command)
        if outcome is EchoOutcome.FOREIGN:
            # everything needed to tell an out of sequence echo from a value this ramp
            # never issued: what it is waiting for, what it last matched, and where it is
            ledger = self._rx_ledger if command.is_tmcc_rx else self._ledger
            log.info(
                f"Speed ramp {self._scope.title} {self._address} aborting: out of sequence speed "
                f"{command.data}, commanded {self.commanded_speed}, "
                f"source {'RX' if command.is_tmcc_rx else 'TX/broadcast'}, "
                f"pending steps {ledger.pending[EchoFamily.SPEED]}, "
                f"last matched {ledger.claimed.get(family, ())[-1:]}"
            )
            return False
        if family is EchoFamily.RPM:
            self._absorb_rpm(command.data)
        else:
            self._absorb_labor(command.data)
        return True

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

    def _acquire_claim(self) -> None:
        """Wait in the worker before any emission, without state or registry locks."""
        if self._claim_acquired or self._is_running is False:
            return
        try:
            self._claim_pending = self._peer is not None or self._use_default_peer
            self._set_ramping(True)
            if self._peer is None and self._use_default_peer:
                from .ramp_peer import RampPeer

                self._peer = RampPeer.build()
                if self._peer is None:
                    raise ValueError("Peer service unavailable")
            if self._peer is not None and self._is_running is True:
                self._peer.acquire(self)
            self._claim_acquired = self._is_running
        except Exception as exc:
            self._claim_pending = False
            self.abort(f"peer acquisition failed: {exc}")
            log.warning(f"Speed ramp {self._scope.title} {self._address}: peer acquisition failed: {exc}")
        finally:
            self._claim_pending = False

    def _release_claim(self) -> None:
        with self._lock:
            if self._peer is None or self._claim_released:
                return
            self._claim_released = True
        self._peer.release(self)

    def start(self) -> None:
        self._starting = True
        try:
            if self._is_running is True:
                self._claim_pending = self._peer is not None or self._use_default_peer
                super().start()
        except Exception:
            self._claim_pending = False
            self.abort("ramp startup failed")
            raise
        finally:
            self._starting = False

    def run(self) -> None:
        state = self._state
        try:
            if self._is_running is False:
                return
            self._acquire_claim()
            while self._is_running is True:
                with self._lock:
                    requested = self._requested_target
                    commanded = self._commanded_speed
                self._sync_rpm_map(commanded)
                step = next_step(commanded, requested, state, self._init_labor, self._rpm_bias)
                if step is None:
                    self._settle()
                    if self._peer is not None or self._use_default_peer:
                        with self._lock:
                            if self._commanded_speed == effective_target(self._requested_target, state):
                                self._is_running = False
                                return
                        self._set_ramping(True)
                        continue
                    if self._linger_for_retarget() is False:
                        return
                    self._set_ramping(True)
                    continue
                self._prime_deceleration(step.speed < commanded, requested)
                self._send_step(step)
                if self._pause(step.delay):
                    return
        finally:
            try:
                self._release_claim()
            finally:
                with self._lock:
                    self._is_running = False
                    self._claim_pending = False
                self._set_ramping(False)

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
        # under the send gate, like every other emission: an abort landing here would
        # otherwise put this pair behind the abort's own effort restore, leaving the
        # locomotive holding the notch the restore had just taken back
        with self._wire:
            if self._is_running is False:
                return
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
        # the whole step goes out under the send gate, so an abort cannot interleave its
        # own commands with this one's: either the step completes and the abort's restore
        # follows it, or the abort has already been given and nothing here is sent at all
        with self._wire:
            if self._is_running is False:
                return
            # the commanded speed is taken before the command goes out, for the same
            # reason the ledger records it first: an abort or an echo that lands in
            # between must see the value that is actually on the wire
            with self._lock:
                self._commanded_speed = step.speed
            self._send(self._speed_enum, step.speed)
            self._last_speed = step.speed
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
        with self._wire:
            if self._is_running is False:
                # aborted before the landing: the abort has already squared the target
                # speed and cleared is_ramping, and its sends are the last word
                return
            if target != self._last_speed:
                self._send(self._speed_enum, target)
                self._last_speed = target
            if self.is_legacy is True:
                if state.is_rpm is True:
                    rpm = biased_rpm(target, self._rpm_bias, self._rpm_max_speed)
                    if rpm != self._last_rpm:
                        self._send(TMCC2EngineCommandEnum.DIESEL_RPM, rpm)
                        self._last_rpm = rpm
                self._send(TMCC2EngineCommandEnum.ENGINE_LABOR, self._init_labor)
                self._last_labor = self._init_labor
            self._decelerating = False
        # outside the gate: is_ramping reaches for the engine's condition, which the
        # dispatcher holds while aborting, and taking the two in that order would
        # deadlock against it
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

    def _send(self, command: CommandDefEnum, data: int, *, aborting: bool = False) -> None:
        """Guard every component, including trailing trims after a synchronous stop."""
        if aborting:
            # abort() owns the bounded gate wait; its safety fallback cannot wait again.
            family = echo_family(command)
            if (family is EchoFamily.SPEED and data == 0) or (family is EchoFamily.EFFORT and data == DEFAULT_LABOR):
                self._submit(command, data)
        else:
            with self._wire:
                if self._is_running is False or self._claim_pending:
                    return
                if (self._peer is not None or self._use_default_peer) and not self._claim_acquired:
                    return
                self._submit(command, data)

    def _submit(self, command: CommandDefEnum, data: int) -> None:
        """Record actual submissions before a sender can synchronously echo them."""
        family = echo_family(command)
        if family is not None:
            with self._lock:
                self._ledger.record(family, data)
                self._rx_ledger.record(family, data)
        self._sender(command, self._address, data, self._scope)

    def _set_ramping(self, value: bool) -> None:
        try:
            owner = getattr(self._state, "ramp", None)
            if owner is not None and owner is not self:
                return
            self._state.is_ramping = value
        except AttributeError:  # pragma: no cover
            pass

    def _sync_target_speed(self, target_speed: int) -> None:
        """Record where the engine is headed now that this ramp is no longer driving it."""
        try:
            owner = getattr(self._state, "ramp", None)
            if owner is not None and owner is not self:
                return
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
            if getattr(state, "is_remote_ramping", False) is True:
                raise ValueError("Ramp already owned by another process")
            self._reap()
            ramp = self._ramps.get(key)
            if ramp is not None and ramp.is_active is True:
                state._ramp = ramp
                ramp.retarget(speed, dialog=dialog)
                return ramp
            ramp = SpeedRamp(state, speed, dialog=dialog, sender=sender, **kwargs)
            ramp._starting = True
            self._ramps[key] = ramp
            # Install ownership before the first speed can be sent or echoed back.
            state._ramp = ramp
        # The worker acquires the claim; startup never waits for network acknowledgment.
        try:
            ramp.start()
        except Exception:
            with self._ramps_lock:
                if self._ramps.get(key) is ramp:
                    del self._ramps[key]
            raise
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
        hard_stop: bool = False,
        yield_speed: int = None,
    ) -> None:
        with self._ramps_lock:
            self._reap()
            ramp = self._ramps.pop(self.key_for(state), None)
        if ramp is not None:
            ramp.abort(reason, target_speed=target_speed, hard_stop=hard_stop, yield_speed=yield_speed)

    def abort_all(
        self,
        scope: CommandScope = None,
        reason: str = None,
        *,
        target_speed: int = None,
        hard_stop: bool = False,
    ) -> None:
        """
        Stop every ramp, or every ramp in one scope, leaving the other scope alone.

        There is deliberately no yield here: a scope-wide abort is a HALT or a shutdown,
        which is nobody's request for a particular speed.
        """
        with self._ramps_lock:
            keys = [k for k in self._ramps if scope is None or k[0] == scope]
            ramps = [self._ramps.pop(k) for k in keys]
        for ramp in ramps:
            ramp.abort(reason, target_speed=target_speed, hard_stop=hard_stop)

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
