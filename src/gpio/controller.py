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
    ):
        super().__init__(name=f"{PROGRAM_NAME} Controller", daemon=True)
        self._lcd = Lcd(address=lcd_address)
        self._keypad = Keypad(row_pins, column_pins)
        self._key_queue = self._keypad.key_queue
        self._state = ComponentStateStore.build()
        self._is_running = True
        self.start()

    def run(self) -> None:
        self._lcd.reset()
        self._lcd.print("Engine: ")
        while self._is_running:
            while True:
                key = self._key_queue.wait_for_keypress(60)
                if self._key_queue.is_clear:
                    self._lcd.reset()
                    self._lcd.print("Engine: ")
                elif self._key_queue.is_eol:
                    break  # we have an engine
                elif key is not None:
                    self._lcd.print(key)
                sleep(0.5)
            if self._key_queue.is_eol and self._key_queue.keypresses:
                tmcc_id = int(self._key_queue.keypresses)
                state = self._state.get_state(CommandScope.ENGINE, tmcc_id)
                self._lcd.cursor_pos = (1, 0)
                if state:
                    self._lcd.print(state.road_name)
                else:
                    self._lcd.print("No Data")
                print(tmcc_id)

    def reset(self) -> None:
        self._is_running = False
        self._keypad.close()
        self._lcd.close(True)

    def close(self) -> None:
        self.reset()