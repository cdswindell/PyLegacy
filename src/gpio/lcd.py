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
        cols=20,
        rows=4,
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
        self.create_char(0, SMILEY_CHAR)

    def print(self, c: int | str) -> None:
        if isinstance(c, int):
            self.write(c)
        elif isinstance(c, str) and len(c) == 1:
            self.write(ord(c[0]))
        else:
            self.write_string(c)
