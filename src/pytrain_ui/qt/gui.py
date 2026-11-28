"""Buttons-file interface and thread-safe observation of the Qt cab selection."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from threading import Condition, Event, current_thread, main_thread

from pytrain.cli.pytrain import PyTrain
from pytrain.db.component_state import ComponentState
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.protocol.constants import CommandScope

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CabSelection:
    """An atomic selection snapshot; revision changes only when the target changes."""

    scope: CommandScope | None = None
    tmcc_id: int | None = None
    revision: int = 0


class QtCabGui:
    """Register a Qt cab against the current PyTrain runtime from buttons.py.

    Selection callbacks execute on the UI thread and must return promptly. Worker
    threads can instead use wait_for_selection_change(), which retains only the
    latest snapshot and needs no queue or thread when nobody is watching.
    """

    def __init__(
        self,
        *,
        tmcc_id: int | None = None,
        scope: CommandScope = CommandScope.ENGINE,
        width: int | None = None,
        height: int | None = None,
        full_screen: bool | None = None,
        deck: bool | None = None,
        controller_profile: str | None = None,
    ) -> None:
        if scope not in {CommandScope.ENGINE, CommandScope.TRAIN}:
            raise ValueError("Initial cab scope must be ENGINE or TRAIN")
        if tmcc_id is not None and not 1 <= tmcc_id <= 9999:
            raise ValueError("TMCC ID must be between 1 and 9999")
        if any(value is not None and value <= 0 for value in (width, height)):
            raise ValueError("Window dimensions must be positive")
        self._initial_id = tmcc_id
        self._initial_scope = scope
        self._width = width
        self._height = height
        self._full_screen = full_screen
        self._deck = deck
        self._controller_profile = controller_profile
        self._condition = Condition()
        self._selection = CabSelection()
        self._subscribers: dict[object, Callable[[CabSelection], None]] = {}
        self._closed = False
        self._started = False
        self._close_requested = Event()
        self._runtime = PyTrain.current()
        self._runtime.register_startup_gui(self.run, self.close)

    @property
    def selection(self) -> CabSelection:
        with self._condition:
            return self._selection

    @property
    def scope(self) -> CommandScope | None:
        return self.selection.scope

    @property
    def tmcc_id(self) -> int | None:
        return self.selection.tmcc_id

    @property
    def active_state(self) -> ComponentState | None:
        """Return the selected record without creating a provisional state."""
        return self._state_for(self.selection)

    @staticmethod
    def _state_for(target: CabSelection) -> ComponentState | None:
        if target.scope is None or target.tmcc_id is None:
            return None
        state = ComponentStateStore.get_state(target.scope, target.tmcc_id, create=False)
        return state if state is not None and not state.is_deleted else None

    @property
    def active_engine_state(self) -> ComponentState | None:
        """Return the selected engine, car, or train, matching EngineGui semantics."""
        target = self.selection
        if target.scope in {CommandScope.ENGINE, CommandScope.TRAIN}:
            return self._state_for(target)
        return None

    def subscribe(self, callback: Callable[[CabSelection], None]) -> Callable[[], None]:
        """Observe future target changes; return an idempotent unsubscribe function."""
        token = object()
        with self._condition:
            if self._closed:
                raise RuntimeError("The cab has closed")
            self._subscribers[token] = callback

        def unsubscribe() -> None:
            with self._condition:
                self._subscribers.pop(token, None)

        return unsubscribe

    def wait_for_selection_change(self, revision: int, timeout: float | None = None) -> CabSelection | None:
        """Wait for a newer snapshot; return None on timeout or after shutdown.

        A revision avoids lost wakeups if selection changes before the wait starts.
        Multiple waiters are notified together; rapid changes may be coalesced.
        """
        with self._condition:
            self._condition.wait_for(lambda: self._selection.revision > revision or self._closed, timeout)
            return self._selection if self._selection.revision > revision else None

    def report_selection(self, scope: str, tmcc_id: int) -> None:
        """Receive an already committed QML selection on the Qt thread."""
        selected_scope = CommandScope[scope] if scope else None
        selected_id = tmcc_id if tmcc_id > 0 else None
        with self._condition:
            if self._closed or (selected_scope, selected_id) == (self._selection.scope, self._selection.tmcc_id):
                return
            target = self._selection = CabSelection(selected_scope, selected_id, self._selection.revision + 1)
            callbacks = tuple(self._subscribers.values())
            self._condition.notify_all()
        for callback in callbacks:
            try:
                callback(target)
            except Exception:
                log.exception("Qt cab selection subscriber failed")

    def close(self) -> None:
        """Request event-loop exit from any thread, including before Qt is ready."""
        self._close_requested.set()

    def run(self) -> int:
        """Start the registered presentation on the main thread; reuse PyTrain."""
        if current_thread() is not main_thread():
            raise RuntimeError("QtCabGui must run on the Python main thread")
        with self._condition:
            if self._started:
                raise RuntimeError("The cab has already started")
            self._started = True
        try:
            from pytrain.utils.host_info import is_steam_deck

            from .app import _run

            deck = is_steam_deck() if self._deck is None else self._deck
            if self._close_requested.is_set():
                return 0
            return _run(
                self._initial_scope,
                self._initial_id or 1,
                [],
                deck=deck,
                width=self._width or (1280 if deck else 720),
                height=self._height or (800 if deck else 1280),
                controller_profile=self._controller_profile,
                full_screen=self._full_screen,
                explicit_target=self._initial_id is not None,
                interface=self,
            )
        finally:
            with self._condition:
                self._closed = True
                self._subscribers.clear()
                self._condition.notify_all()

    @property
    def close_requested(self) -> bool:
        return self._close_requested.is_set()
