from threading import Thread
from time import sleep
from typing import List

from RPLCD.i2c import CharLCD

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


class Lcd(CharLCD):
    def __init__(
        self,
        i2c_expander: str = "PCF8574",
        address: int = 0x27,
        port: int = 1,
        rows: int = 4,
        cols: int = 20,
        scroll: bool = True,
        dotsize: int = 8,
        charmap: str = "A02",
        auto_linebreaks: bool = False,
        backlight_enabled: bool = True,
    ):
        self._frame_buffer = list()  # need to define before super because super calls clear...
        super().__init__(
            i2c_expander=i2c_expander,
            address=address,
            port=port,
            cols=cols,
            rows=rows,
            dotsize=dotsize,
            charmap=charmap,
            auto_linebreaks=auto_linebreaks,
            backlight_enabled=backlight_enabled,
        )
        self.create_char(0, SMILEY_CHAR)
        self._rows = rows
        self._cols = cols
        self._row_pos = self._col_pos = 0
        self._scroll = scroll
        self._scroller = None
        self._backlight_enabled = backlight_enabled
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
        self._row_pos = self._col_pos = 0
        self.clear_frame_buffer()

    def clear_frame_buffer(self) -> None:
        del self._frame_buffer[:]
        self.stop_scrolling()

    def stop_scrolling(self) -> None:
        if self._scroller:
            self._scroller.shutdown()
            self._scroller = None

    def write_frame_buffer(self, clear_display: bool = True) -> None:
        if clear_display is True:
            super().clear()  # call the super, otherwise frame buffer is cleared
        self.home()  # reposition cursor
        self.stop_scrolling()
        for r, row in enumerate(self._frame_buffer):
            if row:
                self.write_string(row.ljust(self.cols)[: self.cols])
                self.write_string("\r\n")
                self._row_pos = r
                self._col_pos = 0
        if (
            self._scroll is True
            and len(self._frame_buffer) > 0
            and self._frame_buffer[0]
            and len(self._frame_buffer[0]) > self.cols
        ):
            self._scroller = Scroller(self, self._frame_buffer[0])

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
    def __init__(self, lcd: Lcd, buffer: str) -> None:
        super().__init__(daemon=True)
        self._lcd = lcd
        self._buffer = buffer
        self._is_running = True
        self.start()

    def shutdown(self) -> None:
        self._is_running = False

    def run(self) -> None:
        while self._is_running:
            padding = " " * 2
            s = padding + self._buffer.strip() + padding
            for i in range(len(s) - self._lcd.cols + 1):
                self._lcd.cursor_pos = (0, 0)
                self._lcd.print(s[i : i + self._lcd.cols])
                sleep(0.3)
