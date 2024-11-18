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
        num_rows: int = 4,
        num_columns: int = 20,
        scope: CommandScope = CommandScope.ENGINE,
    ):
        super().__init__(name=f"{PROGRAM_NAME} Controller", daemon=True)
        self._lcd = Lcd(address=lcd_address)
        self._keypad = Keypad(row_pins, column_pins)
        self._key_queue = self._keypad.key_queue
        self._state = ComponentStateStore.build()
        self._scope = scope
        self._num_rows = num_rows
        self._num_cols = num_columns
        self._tmcc_id = None
        self._last_scope = None
        self._last_tmcc_id = None
        self._frame_buffer = None
        self._is_running = True
        self.start()

    def run(self) -> None:
        self._lcd.reset()
        self.update_display()
        while self._is_running:
            key = self._key_queue.wait_for_keypress(60)
            if self._key_queue.is_clear:
                self._change_scope(self._scope)
            elif self._key_queue.is_eol:
                if self._key_queue.keypresses:
                    self._tmcc_id = int(self._key_queue.keypresses)
                    self.update_display()
            elif key == "A":
                self._change_scope(CommandScope.ENGINE)
            elif key == "B":
                self._change_scope(CommandScope.TRAIN)
            elif key == "*":
                self._change_scope(CommandScope.TRAIN)
            elif key is not None:
                self._lcd.print(key)
            sleep(0.1)

    def update_display(self):
        self._frame_buffer = []
        row = f"{self._scope.friendly}: "
        tmcc_id_pos = len(row)
        if self._tmcc_id is not None:
            row += f"{self._tmcc_id}"
            state = self._state.get_state(self._scope, self._tmcc_id)
        else:
            state = None
        if state and state.road_number:
            row += f" #{state.road_number}"
        self._frame_buffer.append(row)

        if self._tmcc_id is not None:
            row = state.name if state else "No Information"
        else:
            row = ""
        self._frame_buffer.append(row)
        self.write_to_lcd()
        if self._tmcc_id is None:
            self._lcd.cursor_pos = (0, tmcc_id_pos)

    def write_to_lcd(self) -> None:
        self._lcd.home()
        for row in self._frame_buffer:
            self._lcd.write_string(row.ljust(self._num_cols)[: self._num_cols])
            self._lcd.write_string("\r\n")

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
