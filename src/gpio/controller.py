from threading import Thread
from time import sleep
from typing import List

from .keypad import Keypad
from .lcd import Lcd
from ..protocol.constants import PROGRAM_NAME, CommandScope
from ..db.component_state_store import ComponentStateStore


class Controller(Thread):
    def __init__(
        self,
        row_pins: List[int | str],
        column_pins: List[int | str],
        lcd_address: int = 0x27,
        scope: CommandScope = CommandScope.ENGINE,
    ):
        super().__init__(name=f"{PROGRAM_NAME} Controller", daemon=True)
        self._lcd = Lcd(address=lcd_address)
        self._keypad = Keypad(row_pins, column_pins)
        self._key_queue = self._keypad.key_queue
        self._state = ComponentStateStore.build()
        self._scope = scope
        self._is_running = True
        self.start()

    def run(self) -> None:
        self._lcd.reset()
        self._lcd.print(f"{self._scope.friendly}: ")
        while self._is_running:
            key = self._key_queue.wait_for_keypress(60)
            if self._key_queue.is_clear:
                self._change_scope(self._scope)
            elif self._key_queue.is_eol:
                if self._key_queue.keypresses:
                    tmcc_id = int(self._key_queue.keypresses)
                    self._lcd.cursor_pos = (1, 0)
                    state = self._state.get_state(CommandScope.ENGINE, tmcc_id)
                    road_name = state.name if state else "No Information"
                    self._lcd.print(road_name)
            elif key == "A":
                self._change_scope(CommandScope.ENGINE)
            elif key == "B":
                self._change_scope(CommandScope.TRAIN)
            elif key is not None:
                self._lcd.print(key)
            sleep(0.1)

    def reset(self) -> None:
        self._is_running = False
        self._key_queue.reset()
        self._lcd.close(True)
        self._keypad.close()

    def close(self) -> None:
        self.reset()

    def _change_scope(self, scope: CommandScope) -> None:
        self._scope = scope
        self._lcd.reset()
        self._lcd.print(f"{self._scope.friendly}: ")
        self._key_queue.reset()
