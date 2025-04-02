from threading import Thread

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.core.sprite_system import framerate_regulator
from luma.core.virtual import viewport
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
        oled_device: OledDevice | str = OledDevice.ssd1309,
        font_size: int = 15,
    ) -> None:
        super().__init__()
        Thread.__init__(self, daemon=True)
        TextBuffer.__init__(self, rows, cols)
        self._serial = i2c(port=1, address=address)  # i2c bus & address
        self._device = oled_device.value(self._serial)  # i2c oled device
        self._image = Image.new(self._device.mode, self._device.size, "black")
        self._canvas = ImageDraw.Draw(self._image)
        self._font_size = font_size
        self._font = ImageFont.load_default(font_size)
        self._is_running = True
        self.start()

    def __repr__(self) -> str:
        return super(TextBuffer, self).__repr__()

    @property
    def font_size(self) -> int:
        return self._font_size

    @font_size.setter
    def font_size(self, font_size: int) -> None:
        self._font_size = font_size
        self._font = ImageFont.load_default(font_size)
        self._clear_image()
        self.update_display(clear=False, selective=False)

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
        self._clear_image()
        self._device.display(self._image)

    def show(self) -> None:
        self._device.show()

    def hide(self) -> None:
        self._device.hide()

    def measure_text(self, text: str) -> tuple[int, int]:
        with canvas(self._device) as draw:
            left, top, right, bottom = draw.textbbox((0, 0), text, font=self._font)
            return right - left, bottom - top

    def run(self) -> None:
        while self._is_running:
            with self.synchronizer:
                self.synchronizer.wait()
                if self._is_running:
                    self.update_display()

    def update_display(self, clear: bool = True, selective: bool = True) -> None:
        with self.synchronizer:
            fs = self.font_size
            if selective is True:
                rows = self.changed_rows
            else:
                rows = range(self.rows)
            for i in rows:
                if clear is True:
                    self._canvas.rectangle((0, i * fs, self._device.width - 1, ((i + 1) * fs) - 1), "black")
                if i < len(self):
                    self._canvas.text((2, i * fs), self._buffer[i], "white", self._font)
            self._device.display(self._image)

    def show_message(self, msg, y_offset=0, scroll_delay=0.03):
        fps = 0 if scroll_delay == 0 else 1.0 / scroll_delay
        regulator = framerate_regulator(fps)
        w, h = self.measure_text(msg)

        x = self._device.width
        virtual = viewport(self._device, width=w + x + x, height=self._font_size)

        with canvas(virtual) as draw:
            draw.text((x, y_offset), msg, font=self._font, fill="white")

        i = 0
        while i <= w + x:
            with regulator:
                virtual.set_position((i, 0))
                i += 1

    def _clear_image(self) -> None:
        self._canvas.rectangle((0, 0, self._device.width, self._device.height), "black")
