from threading import Thread

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306, ssd1309, ssd1362
from PIL import ImageFont

from ...protocol.constants import Mixins
from ..utils.text_buffer import TextBuffer


class OledDevice(Mixins):
    ssd1306 = ssd1306
    ssd1309 = ssd1309
    ssd1362 = ssd1362


class Oled(Thread, TextBuffer):
    def __init__(
        self,
        rows: int = 4,
        cols: int = 20,
        address: int = 0x3C,
        oled_device: OledDevice = OledDevice.ssd1309,
    ) -> None:
        super().__init__()
        Thread.__init__(self, daemon=True)
        TextBuffer.__init__(self, rows, cols)
        self._serial = i2c(port=1, address=address)
        self._oled_device = oled_device.value(self._serial)
        self._font = ImageFont.truetype(
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            16,
            encoding="unic",
        )
        self.clear()
        self._is_running = True
        self.start()

    def clear(self, notify: bool = False) -> None:
        super().clear(notify)
        self._oled_device.clear()

    def show(self) -> None:
        self._oled_device.show()

    def run(self) -> None:
        while self._is_running:
            with self.synchronizer:
                self.synchronizer.wait()
                if self._is_running:
                    self.update_display()

    def update_display(self):
        with self.synchronizer:
            with canvas(self._oled_device) as draw:
                for i, row in enumerate(self._buffer):
                    draw.text((i * 16, 2), row, "white", self._font)
