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
    ) -> None:
        super().__init__()
        Thread.__init__(self, daemon=True)
        TextBuffer.__init__(self, rows, cols)
        self._serial = i2c(port=1, address=address)
        self._device = oled_device.value(self._serial)
        self._image = Image.new(self._device.mode, self._device.size, "black")
        self._canvas = ImageDraw.Draw(self._image)
        self._font = ImageFont.truetype(
            "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
            16,
            encoding="unic",
        )
        self.clear()
        self._is_running = True
        self.start()

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
        self._canvas.rectangle(
            (0, 0, self._device.width, self._device.height),
            "black",
            outline="white",
            width=1,
        )
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
            for i in self.changed_rows:
                self._canvas.rectangle(
                    (0, i * 16, self._device.width, (i + 1) * 16),
                    "black",
                )
                self._canvas.text((2, i * 16), self._buffer[i], "white", self._font)
            self._device.display(self._image)
