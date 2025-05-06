#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

import atexit
from enum import unique
from pathlib import Path
from threading import Event, Thread

from luma.core.interface.serial import i2c, spi
from luma.core.virtual import hotspot
from luma.oled.device import sh1107, ssd1306, ssd1309, ssd1322, ssd1325, ssd1362
from PIL import Image, ImageDraw, ImageFont

from ...protocol.constants import Mixins
from ..utils.sh1122 import sh1122
from ..utils.text_buffer import TextBuffer


def make_font(name: str, size: int) -> ImageFont:
    if name is None or name.strip() == "" or name.strip() == "default" or name.strip() == "Aileron":
        return ImageFont.load_default(size)
    else:
        name = name.replace(" ", "")
        if name.endswith(".ttf") is False:
            name += ".ttf"
        font_path = str(Path(__file__).resolve().parent.joinpath("fonts", name))
        return ImageFont.truetype(font_path, size)


@unique
class OledDevice(Mixins):
    ssd1306 = ssd1306
    ssd1309 = ssd1309
    ssd1322 = ssd1322
    ssd1325 = ssd1325
    ssd1362 = ssd1362
    sh1107 = sh1107
    sh1122 = sh1122


class Oled(Thread, TextBuffer):
    def __init__(
        self,
        address: int = 0x3C,
        device: OledDevice | str = OledDevice.ssd1309,
        font_size: int = 15,
        font_family: str = "DejaVuSansMono-Bold.ttf",
        x_offset: int = 2,
        auto_update: bool = True,
        spi_speed: int = 4000000,
    ) -> None:
        super().__init__()
        if address:
            self._serial = i2c(port=1, address=address)  # i2c bus and address
        else:
            self._serial = spi(device=0, port=0)

        if isinstance(device, str):
            device = OledDevice.by_name(device, raise_exception=True)
        if isinstance(device, OledDevice):
            self._device = device.value(self._serial)  # i2c/spi oled device
        else:
            raise ValueError(f"Unsupported Luma OLED device: {device}")

        # if spi, slow down the bus
        if isinstance(self._serial, spi) and spi_speed and hasattr(self._serial, "_spi"):
            spi_dev = getattr(self._serial, "_spi")
            spi_dev.max_speed_hz = spi_speed

        # set contrast to maximum
        self._device.contrast(255)

        # determine maximum number of rows; we do not change this even if the
        # font/font size is changed later on
        self._rows = rows = int(self._device.height / font_size)
        self._row_height = int(self._device.height / rows)

        Thread.__init__(self, daemon=True)
        TextBuffer.__init__(self, rows, auto_update=auto_update)

        self._image = Image.new(self._device.mode, self._device.size, "black")
        self._canvas = ImageDraw.Draw(self._image)
        self._font_size = font_size
        if font_family is None or font_family == "default":
            self._font = ImageFont.load_default(font_size)
        else:
            self._font = make_font(font_family, font_size)
        self._font_family = self.font.font.family
        self._cols = self._calculate_num_columns()
        self._x_offset = x_offset
        self._temp_draw = ImageDraw.Draw(Image.new(self._device.mode, self._device.size, "black"))
        self._hotspots = dict()
        self._blinks = set()
        self._is_running = True
        self.show()
        self._initial_update = True

        self.start()
        atexit.register(self.close)

    def __repr__(self) -> str:
        return super(TextBuffer, self).__repr__()

    def __setitem__(self, index: int, value: str):
        super().__setitem__(index, value)
        self._blinks.discard(index)

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def x_offset(self) -> int:
        return self._x_offset

    @x_offset.setter
    def x_offset(self, x_offset: int) -> None:
        self._x_offset = x_offset
        self._clear_image()
        self.update_display(clear=False, selective=False)

    @property
    def row_height(self) -> int:
        return self._row_height

    @property
    def font(self):
        return self._font

    @property
    def font_size(self) -> int:
        return self._font_size

    @font_size.setter
    def font_size(self, font_size: int) -> None:
        self._font_size = font_size
        self._font = make_font(self.font_family, font_size)
        rows = int(self._device.height / font_size)
        self._row_height = int(self._device.height / rows)
        self._clear_image()
        self.update_display(clear=False, selective=False)

    @property
    def font_family(self) -> str:
        return self._font_family

    @font_family.setter
    def font_family(self, font_family: str) -> None:
        self._font = make_font(font_family, self.font_size)
        self._font_family = self.font.font.family
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

    def write(
        self,
        c: int | str,
        at: tuple[int, int] | int = None,
        fmt: str = None,
        center: bool = False,
        blink: bool = False,
    ) -> None:
        super().write(c, at, fmt, center)
        row_no = at if isinstance(at, int) else self.row
        if blink is True:
            self._blinks.add(row_no)
        else:
            self._blinks.discard(row_no)

    def clear(self, notify: bool = False) -> None:
        with self.synchronizer:
            for i in self._hotspots:
                if self._hotspots[i]:
                    self._hotspots[i].stop()
                    self._hotspots[i] = None
            self._hotspots.clear()
            super().clear(notify)
            self._clear_image()
            self._device.display(self._image)

    def show(self) -> None:
        self._device.show()

    def hide(self) -> None:
        self._device.hide()

    def measure_text(self, text: str) -> tuple[int, int]:
        left, top, right, bottom = self._canvas.textbbox((0, 0), text, font=self._font)
        return int(right - left), int(bottom - top)

    def display(self, image: Image) -> None:
        self._device.display(image)

    def stop(self):
        with self.synchronizer:
            self.hide()
            for i in self._hotspots:
                if self._hotspots[i]:
                    self._hotspots[i].stop()
                    self._hotspots[i] = None
            self._hotspots.clear()
            self.clear(notify=False)
            self._is_running = False
            self.synchronizer.notify_all()
        self.join()

    def reset(self) -> None:
        self.stop()

    def close(self) -> None:
        self.stop()

    def run(self) -> None:
        while self._is_running is True:
            with self.synchronizer:
                self.synchronizer.wait()
                if self._is_running is True:
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
            if clear is True and selective is False:
                self._image = Image.new(self._device.mode, self._device.size, "black")
                self._canvas = ImageDraw.Draw(self._image)
            fs = self.row_height
            if selective is True:
                rows = self.changed_rows
            else:
                rows = range(self.rows)
            for i in rows:
                if clear is True and selective is True:
                    self._canvas.rectangle((0, (i * fs), self._device.width - 1, ((i + 1) * fs) - 1), "black")
                if i < len(self):
                    if i in self._hotspots:
                        self._hotspots[i].stop()
                        del self._hotspots[i]
                    w, h = self.measure_text(self[i])
                    if w <= self._device.width:
                        if i in self._blinks:
                            self._hotspots[i] = BlinkingHotspot(self, row=i)
                        else:
                            self._canvas.text((self._x_offset, (i * fs) - 3), self[i], "white", self._font)
                    else:
                        self._hotspots[i] = ScrollingHotspot(self, self[i], row=i)
            # Display the constructed image on the display
            self._device.display(self._image)

    def refresh_display(self) -> None:
        with self.synchronizer:
            if self.is_dirty is True or self._initial_update is True:
                if self._initial_update is True:
                    self.update_display(clear=True, selective=False)
                    self._initial_update = False
                else:
                    self.update_display()

    def force_display(self) -> None:
        with self.synchronizer:
            self.update_display(clear=True, selective=False)
            self._device.display(self._image)

    def _clear_image(self) -> None:
        self._canvas.rectangle((0, 0, self._device.width, self._device.height), "black")

    def _calculate_num_columns(self) -> int:
        sample = "The quick brown fox jumps over the lazy dog"
        w, _ = self.measure_text(sample)
        return int(self.width / (w / len(sample)))


class ScrollingHotspot(Thread, hotspot):
    """
    Support Scrolling Text
    """

    def __init__(self, oled: Oled, text, row: int = 0):
        super().__init__()
        Thread.__init__(self, daemon=True)
        hotspot.__init__(self, oled.width, oled.font_size)
        self._device = oled
        self._x_offset = oled.x_offset
        # self._font_size = oled.font_size
        self._row_height = oled.row_height
        self._font = oled.font
        self._row = row
        self._text = text + " " + text
        self._scroll_speed = 1
        self._text_width, _ = oled.measure_text(text)
        x, y = oled.measure_text(" ")
        self._text_width += x
        self._ev = Event()
        self._resume_ev = Event()
        self._pause_request = False
        self._is_running = True
        self.start()

    def stop(self):
        self._ev.set()
        self._resume_ev.set()
        self._is_running = False
        self.join()

    def render(self, image):
        draw = ImageDraw.Draw(image)
        # Clear the hotspot area
        draw.rectangle(
            (0, self._row * self._row_height, self.width - 1, ((self._row + 1) * self._row_height) - 1),
            fill="black",
        )
        # Draw the scrolling text
        draw.text((self._x_offset, (self._row * self._row_height) - 3), self._text, font=self._font, fill="white")
        # Scroll the text
        self._x_offset -= self._scroll_speed
        if self._x_offset + self._text_width < 0:
            self._x_offset = self._device.x_offset - 3
        return image

    def pause(self) -> None:
        if self.is_alive() and self._pause_request is False:
            self._pause_request = True

    def resume(self) -> None:
        if self.is_alive() and self._pause_request is True:
            self._pause_request = False
            self._resume_ev.set()

    def run(self) -> None:
        while self._is_running and self._ev.is_set() is False:
            with self._device.synchronizer:
                self._device.display(self.render(self._device.image))
            self._ev.wait(0.01)
            if self._pause_request:
                self._resume_ev.wait()
                self._resume_ev.clear()


class BlinkingHotspot(Thread, hotspot):
    """
    Support Blinking Text
    """

    def __init__(self, oled: Oled, row: int = 0, rate: int = 1):
        super().__init__()
        Thread.__init__(self, daemon=True)
        hotspot.__init__(self, oled.width, oled.font_size)
        self._device = oled
        self._x_offset = oled.x_offset
        # self._font_size = oled.font_size
        self._row_height = oled.row_height
        self._font = oled.font
        self._row = row
        self._text = oled[row]
        self._text_width, _ = oled.measure_text(self._text)
        self._ev = Event()
        self._resume_ev = Event()
        self._pause_request = False
        self._is_running = True
        self._rate = rate if rate and rate > 0 else 1
        self._display_cycle = True
        self.start()

    def stop(self):
        self._ev.set()
        self._resume_ev.set()
        self._is_running = False
        self.join()

    def pause(self) -> None:
        if self.is_alive() and self._pause_request is False:
            self._pause_request = True

    def resume(self) -> None:
        if self.is_alive() and self._pause_request is True:
            self._pause_request = False
            self._resume_ev.set()

    def run(self) -> None:
        while self._is_running and self._ev.is_set() is False:
            with self._device.synchronizer:
                self._device.display(self.render(self._device.image))
            self._ev.wait(self._rate)
            if self._ev.is_set() is False:
                self._display_cycle = not self._display_cycle
            if self._pause_request:
                self._resume_ev.wait()
                self._resume_ev.clear()

    def render(self, image):
        draw = ImageDraw.Draw(image)
        if self._display_cycle is False:
            # Clear the hotspot area
            draw.rectangle(
                (0, self._row * self._row_height, self.width - 1, ((self._row + 1) * self._row_height) - 1),
                fill="black",
            )
        else:
            # Draw the text
            draw.text(
                (self._x_offset, (self._row * self._row_height) - 3),
                self._text,
                font=self._font,
                fill="white",
            )
        return image
