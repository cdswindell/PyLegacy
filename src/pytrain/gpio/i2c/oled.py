from threading import Event, Thread

from luma.core.interface.serial import i2c
from luma.core.virtual import hotspot
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
        cols: int = 25,
        address: int = 0x3C,
        oled_device: OledDevice | str = OledDevice.ssd1309,
        font_size: int = 15,
        x_offset: int = 2,
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
        self._x_offset = x_offset
        self._temp_draw = ImageDraw.Draw(Image.new(self._device.mode, self._device.size, "black"))
        self._hotspots = dict()
        self._is_running = True
        self.start()

    def __repr__(self) -> str:
        return super(TextBuffer, self).__repr__()

    @property
    def font(self):
        return self._font

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

    @property
    def image(self) -> Image:
        return self._image

    def clear(self, notify: bool = False) -> None:
        super().clear(notify)
        self._clear_image()
        self._device.display(self._image)

    def show(self) -> None:
        self._device.show()

    def hide(self) -> None:
        self._device.hide()

    def measure_text(self, text: str) -> tuple[int, int]:
        left, top, right, bottom = self._temp_draw.textbbox((0, 0), text, font=self._font)
        return int(right - left), int(bottom - top)

    def display(self, image: Image) -> None:
        self._device.display(image)

    def stop(self):
        with self.synchronizer:
            for i in self._hotspots:
                if self._hotspots[i]:
                    self._hotspots[i].stop()
                    self._hotspots[i] = None
            self._hotspots.clear()
            self._is_running = False
            self.synchronizer.notify_all()
        self.join()

    def run(self) -> None:
        while self._is_running:
            with self.synchronizer:
                self.synchronizer.wait()
                if self._is_running:
                    self.update_display()

    def pause(self) -> None:
        with self.synchronizer:
            for hs in self._hotspots.values():
                hs.pause()
            self.synchronizer.notify_all()

    def resume(self) -> None:
        with self.synchronizer:
            for hs in self._hotspots.values():
                hs.resume()
            self.synchronizer.notify_all()

    def update_display(self, clear: bool = True, selective: bool = True) -> None:
        with self.synchronizer:
            fs = self.font_size
            if selective is True:
                rows = self.changed_rows
            else:
                rows = range(self.rows)
            for i in rows:
                if clear is True:
                    self._canvas.rectangle((0, (i * fs), self._device.width - 1, ((i + 1) * fs) - 1), "black")
                if i < len(self):
                    if i in self._hotspots:
                        self._hotspots[i].stop()
                        del self._hotspots[i]
                    w, h = self.measure_text(self[i])
                    if w <= self._device.width:
                        self._canvas.text((self._x_offset, (i * fs) - 3), self[i], "white", self._font)
                    else:
                        self._hotspots[i] = ScrollingHotspot(self, self[i], row=i)
            self._device.display(self._image)

    def _clear_image(self) -> None:
        self._canvas.rectangle((0, 0, self._device.width, self._device.height), "black")


class ScrollingHotspot(Thread, hotspot):
    def __init__(self, oled: Oled, text, row: int = 0, scroll_speed=1):
        super().__init__()
        Thread.__init__(self, daemon=True)
        hotspot.__init__(self, oled.width, oled.font_size)
        self.device = oled
        self.width = oled.width
        self.height = oled.font_size
        self.font_size = oled.font_size
        self.row = row
        self.text = text + " " + text
        self.scroll_speed = scroll_speed
        self.font = oled.font
        w, h = oled.measure_text(text)
        self.text_width = w
        self.text_height = h
        self.x_offset = 0
        self._ev = Event()
        self._is_running = True
        self.start()

    def stop(self):
        self._ev.set()
        self._is_running = False
        self.join()

    def render(self, image):
        draw = ImageDraw.Draw(image)
        # Clear the hotspot area
        draw.rectangle(
            (0, self.row * self.font_size, self.width - 1, ((self.row + 1) * self.font_size) - 1),
            fill="black",
        )
        # Draw the scrolling text
        draw.text((self.x_offset, (self.row * self.font_size) - 3), self.text, font=self.font, fill="white")
        # Scroll the text
        self.x_offset -= self.scroll_speed
        if self.x_offset + self.text_width < 0:
            self.x_offset = 0

        return image

    def pause(self) -> None:
        if self.is_alive():
            self.stop()

    def resume(self) -> None:
        if self._is_running is False:
            self._ev.clear()
            self._is_running = True
            Thread(target=self.run, daemon=True).start()

    def run(self) -> None:
        while self._is_running and self._ev.is_set() is False:
            self.device.display(self.render(self.device.image))
            self._ev.wait(0.01)
