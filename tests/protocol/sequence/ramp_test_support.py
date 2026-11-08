"""Lightweight state and recording helpers shared by the ramp tests."""

from dataclasses import dataclass, field
from functools import partial
from threading import Thread
from traceback import format_exception
from typing import Callable

from src.pytrain.db.engine_state import EngineState
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.sequence.speed_ramp import LEGACY_SPEED_MAX, TMCC1_SPEED_MAX, UNSET_MAX_SPEED, SpeedRamp
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum

SPEED_ENUMS = {TMCC1EngineCommandEnum.ABSOLUTE_SPEED, TMCC2EngineCommandEnum.ABSOLUTE_SPEED}


class FakeEngineState:
    """
    Geometry inputs in decoded command units, not Base 3 record units. The default
    speed_max resolution is checked against real states in test_ramp_harness;
    explicit overrides and unusual input combinations remain synthetic test cases.
    """

    def __init__(
        self,
        *,
        is_legacy: bool = True,
        is_rpm: bool = True,
        speed: int | None = 0,
        rpm: int | None = 0,
        labor: int | None = 12,
        momentum: int | None = 0,
        max_speed: int | None = UNSET_MAX_SPEED,
        speed_limit: int | None = UNSET_MAX_SPEED,
        speed_max: int | None = None,
    ) -> None:
        self.is_legacy = is_legacy
        self.is_rpm = is_rpm
        self.speed = speed
        self.rpm = rpm
        self.labor = labor
        self.momentum = momentum
        self.max_speed = max_speed
        self.speed_limit = speed_limit
        self._speed_max = speed_max

    @property
    def speed_max(self) -> int | None:
        if self._speed_max is not None:
            return self._speed_max
        max_speed, speed_limit = self.max_speed, self.speed_limit
        if max_speed and max_speed != 255 and speed_limit and speed_limit != 255:
            ms = min(max_speed, speed_limit)
        elif speed_limit and speed_limit != 255:
            ms = speed_limit
        elif max_speed and max_speed != 255:
            ms = max_speed
        else:
            ms = LEGACY_SPEED_MAX if self.is_legacy is True else TMCC1_SPEED_MAX
        if self.is_legacy is False and ms > TMCC1_SPEED_MAX:
            ms = TMCC1_SPEED_MAX
        return ms


class RampEngineState(FakeEngineState):
    """The geometry double with the worker's state interface and real ramp status logic."""

    is_ramp_active = EngineState.is_ramp_active

    def __init__(
        self, *, scope: CommandScope = CommandScope.ENGINE, tmcc_id: int = 12, is_d4: bool = False, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.scope = scope
        self.tmcc_id = tmcc_id
        # The effective property value, not a D4 metadata flag or an address heuristic.
        self.is_d4 = is_d4
        self._ramp: SpeedRamp | None = None
        self.is_ramping = False
        self.is_remote_ramping = False
        self.target_speed: int | None = None

    @property
    def ramp(self) -> SpeedRamp | None:
        return self._ramp

    @ramp.setter
    def ramp(self, value: SpeedRamp | None) -> None:
        self._ramp = value

    def sync_target_speed(self, target_speed: int) -> None:
        """Stands in for EngineState.sync_target_speed, which every abort path calls."""
        self.target_speed = target_speed


class Recorder:
    """A recording send path: the ramp's command stream, with a hook to poke it mid-flight."""

    def __init__(self, hook: Callable[["Recorder", int], None] | None = None) -> None:
        self.sent: list[tuple] = []
        self.hook = hook

    def __call__(self, command, address: int, data: int, scope: CommandScope) -> None:
        self.sent.append((command, address, data, scope))
        if self.hook is not None:
            self.hook(self, len(self.sent))

    def of(self, command) -> list[int]:
        return [data for cmd, _, data, _ in self.sent if cmd == command]

    @property
    def speeds(self) -> list[int]:
        return [data for cmd, _, data, _ in self.sent if cmd in SPEED_ENUMS]

    @property
    def rpms(self) -> list[int]:
        return self.of(TMCC2EngineCommandEnum.DIESEL_RPM)

    @property
    def labors(self) -> list[int]:
        return self.of(TMCC2EngineCommandEnum.ENGINE_LABOR)

    @property
    def commands(self) -> list:
        return [cmd for cmd, _, _, _ in self.sent]


def build_ramp(state: RampEngineState, target: int, recorder: Recorder, **kwargs) -> SpeedRamp:
    """A ramp whose waits collapse to nothing, so the loop can be driven synchronously."""
    kwargs.setdefault("linger", 0.0)
    kwargs.setdefault("delay_scale", 0.0)
    # This lightweight state double intentionally implements only the ramp's state interface.
    # noinspection PyTypeChecker
    return SpeedRamp(state, target, sender=recorder, **kwargs)


def run_ramp(
    state: RampEngineState, target: int, recorder: Recorder | None = None, **kwargs
) -> tuple[SpeedRamp, Recorder]:
    recorder = recorder if recorder is not None else Recorder()
    ramp = build_ramp(state, target, recorder, **kwargs)
    ramp.run()
    return ramp, recorder


@dataclass
class OwnedWorker:
    worker: Thread
    abort: Callable[[], None] | None = None
    releases: list[Callable[[], None]] = field(default_factory=list)


@dataclass(frozen=True)
class WorkerCleanupFailure:
    worker: Thread
    phase: str
    error: Exception


class RampCleanupError(RuntimeError):
    """Preserve every cleanup failure and its traceback using Python 3.10-compatible APIs."""

    def __init__(self, failures: list[WorkerCleanupFailure]) -> None:
        self.failures = tuple(failures)
        diagnostics = [
            f"{failure.worker.name} (ident={failure.worker.ident}): {failure.phase}\n"
            + "".join(format_exception(type(failure.error), failure.error, failure.error.__traceback__))
            for failure in self.failures
        ]
        super().__init__("Ramp worker cleanup failed:\n" + "\n".join(diagnostics))


class RampWorkers:
    """Own test workers independently of registry membership, including failed cleanup."""

    def __init__(self) -> None:
        self._owned: dict[Thread, OwnedWorker] = {}

    @property
    def workers(self) -> tuple[Thread, ...]:
        return tuple(self._owned)

    def track(
        self,
        worker: Thread,
        *,
        release: Callable[[], None] | None = None,
        abort: Callable[[], None] | None = None,
    ) -> Thread:
        if worker not in self._owned:
            if abort is None and isinstance(worker, SpeedRamp):
                abort = partial(worker.abort, "test cleanup")
            self._owned[worker] = OwnedWorker(worker, abort)
        if release is not None:
            self._owned[worker].releases.append(release)
        return worker

    def cleanup(self, timeout: float = 1.0) -> None:
        errors: list[WorkerCleanupFailure] = []
        failed: set[Thread] = set()

        # Pass the handle explicitly so each cleanup phase identifies its own worker.
        # noinspection PyShadowingNames
        def attempt(worker: Thread, phase: str, action: Callable[[], None]) -> None:
            try:
                action()
            except Exception as exc:
                errors.append(WorkerCleanupFailure(worker, phase, exc))
                failed.add(worker)

        owned = tuple(self._owned.values())
        for entry in owned:
            if entry.abort is not None:
                attempt(entry.worker, "abort", entry.abort)
        for entry in owned:
            for release in entry.releases:
                attempt(entry.worker, "release gate", release)
        for entry in owned:
            worker = entry.worker
            if worker.ident is not None:
                attempt(worker, "join", lambda: worker.join(timeout=timeout))

            def verify_stopped() -> None:
                if worker.is_alive():
                    raise AssertionError(f"Worker survived cleanup after a {timeout}-second join")

            attempt(worker, "verify termination", verify_stopped)
        for entry in owned:
            if entry.worker not in failed:
                del self._owned[entry.worker]
        if errors:
            raise RampCleanupError(errors)
