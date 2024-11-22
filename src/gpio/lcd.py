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

    def write_frame_buffer(self, clear_display: bool = True) -> None:
        if clear_display is True:
            super().clear()  # call the super, otherwise frame buffer is cleared
        self.home()  # reposition cursor
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
            row = self._frame_buffer[0]
            for i in range(len(row) - self.cols + 1):
                self.cursor_pos = (0, 0)
                self.write_string(row[i : i + self.cols])
                sleep(0.2)

    def print(self, c: int | str) -> None:
        if isinstance(c, int) and 0 <= c <= 255:
            self.write(c)
        elif isinstance(c, str) and len(c) == 1:
            self.write(ord(c[0]))
        elif isinstance(c, str):
            self.write_string(c)
        else:
            self.write_string(str(c))
