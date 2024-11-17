from threading import Thread
from typing import List

from .keypad import Keypad
from .lcd import Lcd
from ..protocol.constants import PROGRAM_NAME


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
        self._is_running = True
        self.start()

    def run(self) -> None:
        self._lcd.reset()
        self._lcd.print("Engine: ")
        while self._is_running:
            while True:
                key = self._key_queue.wait_for_keypress()
                if key:
                    self._lcd.print(key)
                elif self._key_queue.is_clear:
                    self._lcd.reset()
                    self._lcd.print("Engine: ")
                elif self._key_queue.is_eol:
                    break  # we have an engine
            tmcc_id = self._key_queue.keypresses
            print(tmcc_id)
