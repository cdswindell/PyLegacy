import logging
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
        self._is_running = True
        self.start()

    def shutdown(self) -> None:
        self._is_running = False
        with self._state.synchronizer:
            self._state.synchronizer.notify_all()

    def run(self) -> None:
        while self._state is not None and self._is_running:
            print("Waiting for synchronizer lock...")
            with self._state.synchronizer:
                print("Waiting for change notification (releasing lock)...")
                self._state.synchronizer.wait()
                print(f"*** Received change notification: {self._state.last_command}")
                if self._is_running:
                    pass  # self._action()
