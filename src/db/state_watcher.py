import logging
from queue import Queue
from threading import Thread
from typing import Callable

from src.db.component_state import ComponentState
from src.protocol.constants import PROGRAM_NAME

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

    def shutdown(self) -> None:
        self._is_running = False
        with self._state.synchronizer:
            self._state.synchronizer.notify_all()
        if self._notifier:
            self._notifier.shutdown()

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
        self._queue = Queue(32)
        self.start()

    def run(self) -> None:
        while self._is_running:
            data = None
            try:
                if self._queue.empty():
                    data = self._queue.get(block=True)
                else:
                    while not self._queue.empty():
                        self._queue.get(block=False)
                        self._queue.task_done()
                if self._is_running and data is True:
                    print("updating display...", end="")
                    self._watcher.action()
                    print("updating display...done")
            finally:
                if data is not None:
                    self._queue.task_done()

    def shutdown(self) -> None:
        self._is_running = False
        self.update_request(False)

    def update_request(self, request: bool = True):
        self._queue.put(request)
