import logging
from queue import Queue
from threading import Thread
from typing import Callable

from .component_state import ComponentState
from ..protocol.constants import PROGRAM_NAME

log = logging.getLogger(__name__)


class StateWatcher(Thread):
    def __init__(self, state: ComponentState, action: Callable) -> None:
        super().__init__(daemon=True, name=f"{PROGRAM_NAME} State Watcher {state.scope.label} {state.address}")
        self._state = state
        self._action = action
        self._notifier = UpdateNotifier(self)
        self._is_running = True
        self.start()

    def action(self) -> None:
        self._action()

    @property
    def watched(self) -> ComponentState:
        return self._state

    def shutdown(self) -> None:
        self._is_running = False
        if self._notifier:
            self._notifier.shutdown()
        with self._state.synchronizer:
            self._state.synchronizer.notify_all()

    def run(self) -> None:
        while self._state is not None and self._is_running:
            with self._state.synchronizer:
                self._state.synchronizer.wait()
            if self._is_running:
                self._notifier.update_request()


class UpdateNotifier(Thread):
    def __init__(self, watcher: StateWatcher) -> None:
        super().__init__(daemon=True)
        self._watcher = watcher
        self._is_running = True
        self._queue = Queue(64)
        self.start()

    def run(self) -> None:
        while self._is_running:
            # wait for a state change notification, if queue is empty
            if self._queue.empty():
                self._queue.get(block=True)
            # clear out queue, the redisplay we're about to trigger covers them
            with self._queue.mutex:
                self._queue.queue.clear()
                self._queue.all_tasks_done.notify_all()
                self._queue.unfinished_tasks = 0
            if self._is_running:
                self._watcher.action()

    def shutdown(self) -> None:
        self._is_running = False
        self.update_request()

    def update_request(self):
        self._queue.put(True)
