from threading import Thread, Event
from typing import List

from RPLCD.i2c import CharLCD
import sys

sys.setswitchinterval(0.001)

SMILEY_CHAR = (
    0b00000,
    0b01010,
    0b01010,
    0b00000,
    0b10001,
    0b10001,
    0b01110,
    0b00000,
)

LCD_PCF8574_ADDRESS = 0x27


class Lcd(CharLCD):
    def __init__(
        self,
        i2c_expander: str = "PCF8574",
        address: int = LCD_PCF8574_ADDRESS,
        port: int = 1,
        rows: int = 4,
        cols: int = 20,
        scroll_speed: float = 0.5,
        dot_size: int = 8,
        char_map: str = "A02",
        auto_linebreaks: bool = False,
        backlight_enabled: bool = True,
    ):
        self._frame_buffer = list()  # need to define before super because super calls clear...
        self._scroller = None  # same here
        super().__init__(
            i2c_expander=i2c_expander,
            address=address,
            port=port,
            cols=cols,
            rows=rows,
            dotsize=dot_size,
            charmap=char_map,
            auto_linebreaks=auto_linebreaks,
            backlight_enabled=backlight_enabled,
        )
        self._rows = rows
        self._cols = cols
        self._scroll_speed = scroll_speed
        self._backlight_enabled = backlight_enabled
        self._auto_linebreaks = auto_linebreaks
        self.cursor_mode = "hide"
        self.clear()

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def frame_buffer(self) -> List[str]:
        return self._frame_buffer

    def add(self, row: str) -> bool:
        if len(self._frame_buffer) < self.rows:
            self._frame_buffer.append(row)
            return True
        return False

    def clear(self) -> None:
        super().clear()
        self.home()
        self.clear_frame_buffer()
        self.cursor_mode = "hide"

    def clear_frame_buffer(self) -> None:
        self.stop_scrolling()
        self._frame_buffer.clear()

    def stop_scrolling(self) -> None:
        if self._scroller is not None:
            """
            Shutdown the scrolling thread and wait for it to finish,
            otherwise, we could have multiple threads trying to
            output to the screen at the same time.
            """
            self._scroller.shutdown()
            self._scroller.join()
            self._scroller = None

    def write_frame_buffer(self, clear_display: bool = True) -> None:
        self.stop_scrolling()
        if clear_display is True:
            super().clear()  # call the super, otherwise frame buffer is cleared
        self.home()  # reposition cursor
        for r, row in enumerate(self._frame_buffer):
            if row:
                self.cursor_pos = (r, 0)
                self.write_string(row.ljust(self.cols)[: self.cols])
        if (
            self._scroll_speed > 0.0
            and len(self._frame_buffer) > 0
            and self._frame_buffer[0]
            and len(self._frame_buffer[0]) > self.cols
        ):
            self._scroller = Scroller(self, self._frame_buffer[0], self._scroll_speed)
        self.cursor_mode = "hide"

    def print(self, c: int | str) -> None:
        if isinstance(c, int) and 0 <= c <= 255:
            self.write(c)
        elif isinstance(c, str) and len(c) == 1:
            self.write(ord(c[0]))
        elif isinstance(c, str):
            self.write_string(c)
        else:
            self.write_string(str(c))


class Scroller(Thread):
    def __init__(self, lcd: Lcd, buffer: str, scroll_speed: float = 0.5) -> None:
        super().__init__(daemon=True)
        self._lcd = lcd
        self._buffer = buffer.strip()
        self._scroll_speed = scroll_speed
        self._exit = Event()
        self.start()

    def shutdown(self) -> None:
        self._exit.set()

    def run(self) -> None:
        s = self._buffer + " " + self._buffer
        try:
            while not self._exit.is_set():
                for i in range(len(self._buffer) + 1):
                    self._lcd.cursor_pos = (0, 0)
                    self._lcd.write_string(s[i : i + self._lcd.cols])
                    self._exit.wait(self._scroll_speed)
                    if self._exit.is_set():
                        return
        finally:
            self._lcd.cursor_pos = (0, 0)
            self._lcd.cursor_mode = "hide"
