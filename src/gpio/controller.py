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
        speed_pins: List[int | str] = None,
        fwd_pin: int | str = None,
        rev_pin: int | str = None,
        lcd_address: int = 0x27,
        lcd_rows: int = 4,
        lcd_cols: int = 20,
    ):
        super().__init__(name=f"{PROGRAM_NAME} Controller", daemon=True)
        self._lcd = Lcd(address=lcd_address, rows=lcd_rows, cols=lcd_cols)
        self._keypad = Keypad(row_pins, column_pins)
        self._key_queue = self._keypad.key_queue
        self._state = ComponentStateStore.build()
        self._scope = CommandScope.ENGINE
        self._tmcc_id = None
        self._last_scope = None
        self._last_tmcc_id = None

        self._is_running = True
        self.start()

    def run(self) -> None:
        self._lcd.reset()
        self.update_display()
        while self._is_running:
            key = self._key_queue.wait_for_keypress(60)
            if self._key_queue.is_clear:
                self.change_scope(self._scope)
            elif self._key_queue.is_eol:
                if self._key_queue.keypresses:
                    self._tmcc_id = int(self._key_queue.keypresses)
                    self.update_display()
            elif key == "A":
                self.change_scope(CommandScope.ENGINE)
            elif key == "B":
                self.change_scope(CommandScope.TRAIN)
            elif key == "*":
                self.last_engine()
            elif key is not None:
                self._lcd.print(key)
            sleep(0.1)

    def cache_engine(self):
        if self._tmcc_id and self._scope:
            self._last_scope = self._scope
            self._last_tmcc_id = self._tmcc_id

    def last_engine(self):
        if self._last_scope and self._last_tmcc_id:
            tmp_scope = self._last_scope
            tmp_tmcc_id = self._last_tmcc_id
            self._last_scope = self._scope
            self._last_tmcc_id = self._tmcc_id
            self._scope = tmp_scope
            self._tmcc_id = tmp_tmcc_id
            self._key_queue.reset()
            self.update_display()

    def change_scope(self, scope: CommandScope) -> None:
        self.cache_engine()
        self._scope = scope
        self._tmcc_id = None
        self._key_queue.reset()
        self.update_display()

    def update_display(self):
        self._lcd.reset()
        row = f"{self._scope.friendly}: "
        tmcc_id_pos = len(row)
        if self._tmcc_id is not None:
            row += f"{self._tmcc_id}"
            state = self._state.get_state(self._scope, self._tmcc_id)
        else:
            state = None
        if state and state.road_number:
            row += f" #{state.road_number}"
        self._lcd.add(row)

        if self._tmcc_id is not None:
            row = state.road_name if state and state.road_name else "No Information"
        else:
            row = ""
        self._lcd.add(row)
        self._lcd.write_frame_buffer()
        if self._tmcc_id is None:
            self._lcd.cursor_pos = (0, tmcc_id_pos)

    def reset(self) -> None:
        self._is_running = False
        self._key_queue.reset()
        self._lcd.close(True)
        self._keypad.close()

    def close(self) -> None:
        self.reset()
