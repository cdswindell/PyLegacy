from threading import Thread

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306, ssd1309, ssd1362
from PIL import Image, ImageDraw, ImageFont

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
        font_size: int = 16,
    ) -> None:
        super().__init__()
        Thread.__init__(self, daemon=True)
        TextBuffer.__init__(self, rows, cols)
        self._serial = i2c(port=1, address=address)
        self._device = oled_device.value(self._serial)
        self._image = Image.new(self._device.mode, self._device.size, "black")
        self._canvas = ImageDraw.Draw(self._image)
        self._font_size = font_size
        self._font = ImageFont.truetype(
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            font_size,
            encoding="unic",
        )
        self._font = ImageFont.load_default(font_size)
        self.clear()
        self._is_running = True
        self.start()

    @property
    def font_size(self) -> int:
        return self._font_size

    @font_size.setter
    def font_size(self, font_size: int) -> None:
        self._font_size = font_size
        self._font = ImageFont.load_default(font_size)
        self.clear()
        self.update_display()

    @property
    def size(self) -> tuple[int, int]:
        return self._device.width, self._device.height

    @property
    def height(self) -> int:
        return self._device.height

    @property
    def mode(self) -> str:
        return self._device.mode

    @property
    def width(self) -> int:
        return self._device.width

    def clear(self, notify: bool = False) -> None:
        super().clear(notify)
        self._canvas.rectangle((0, 0, self._device.width, self._device.height), "black")
        self._device.display(self._image)

    def show(self) -> None:
        self._device.show()

    def hide(self) -> None:
        self._device.hide()

    def run(self) -> None:
        while self._is_running:
            with self.synchronizer:
                self.synchronizer.wait()
                if self._is_running:
                    self.update_display()

    def update_display(self):
        with self.synchronizer:
            fs = self.font_size
            for i in self.changed_rows:
                self._canvas.rectangle((0, i * fs, self._device.width - 1, ((i + 1) * fs) - 1), "black")
                self._canvas.text((2, i * fs), self._buffer[i], "white", self._font)
            self._device.display(self._image)
