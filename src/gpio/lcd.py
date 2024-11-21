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
        i2c_expander="PCF8574",
        address=0x27,
        port=1,
        rows=4,
        cols=20,
        dotsize=8,
        charmap="A02",
        auto_linebreaks=True,
        backlight_enabled=True,
    ):
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
        self.home()
        self.clear()
        self.create_char(0, SMILEY_CHAR)
        self._rows = rows
        self._cols = cols
        self._row_pos = self._col_pos = 0
        self._backlight_enabled = backlight_enabled
        self._frame_buffer = []

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
        self._frame_buffer.clear()

    def write_frame_buffer(self, clear_display: bool = True) -> None:
        if clear_display is True:
            super().clear()  # call the super, otherwise frame buffer is cleared
        self.home()  # reposition cursor
        for r, row in enumerate(self._frame_buffer):
            self.write_string(row.ljust(self.cols)[: self.cols])
            self.write_string("\r\n")
            self._row_pos = r
            self._col_pos = 0

    def print(self, c: int | str) -> None:
        if isinstance(c, int) and 0 <= c <= 255:
            self.write(c)
        elif isinstance(c, str) and len(c) == 1:
            self.write(ord(c[0]))
        elif isinstance(c, str):
            self.write_string(c)
        else:
            self.write_string(str(c))
