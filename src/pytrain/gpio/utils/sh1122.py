# -*- coding: utf-8 -*-
# Copyright (c) 2014-20 Richard Hull and contributors
# See LICENSE.rst for details.

import luma.oled.const as const
from luma.core.framebuffer import full_frame
from luma.oled.device.greyscale import greyscale_device

__all__ = ["sh1122"]


# noinspection PyPep8Naming
class ssh1122_const(
    const.common
):  # copying data shit: https://www.displayfuture.com/Display/datasheet/controller/SH1122.pdf
    SET_COL_ADR_LSB = 0x0
    SET_COL_ADR_MSB = 0x10
    SET_DISP_START_LINE = 0x40
    SET_CONTRAST = 0x81
    SET_SEG_REMAP = 0xA0
    SET_ENTIRE_ON = 0xA4
    SET_ENTIRE_OFF = 0xA5
    SET_NORM_INV = 0xA6
    SET_MUX_RATIO = 0xA8
    SET_CTRL_DCDC = 0xAD
    SET_DISP = 0xAE
    SET_ROW_ADR = 0xB0
    SET_COM_OUT_DIR = 0xC0
    SET_DISP_OFFSET = 0xD3
    SET_DISP_CLK_DIV = 0xD5
    SET_PRECHARGE = 0xD9
    SET_VCOM_DESEL = 0xDB
    SET_VSEG_LEVEL = 0xDC
    SET_DISCHARGE_LEVEL = 0x30


# noinspection PyPep8Naming
class sh1122(greyscale_device):
    def __init__(self, serial_interface=None, **kwargs):
        super().__init__(
            ssh1122_const,
            serial_interface,
            256,
            64,
            0,
            "RGB",
            full_frame(),
            nibble_order=0,
            **kwargs,
        )

    def command(self, *args):
        return super().command(*args)

    def _supported_dimensions(self):
        return [(256, 64)]  # I don't know about anything other...

    def _init_sequence(self):
        for cmd in (
            self._const.SET_DISP | 0x00,  # off
            # address setting
            self._const.SET_COL_ADR_LSB,
            self._const.SET_COL_ADR_MSB,  # horizontal
            self._const.SET_ROW_ADR,
            0,
            # resolution and layout
            self._const.SET_DISP_START_LINE | 0x00,
            self._const.SET_SEG_REMAP,
            self._const.SET_MUX_RATIO,
            self.height - 1,
            self._const.SET_COM_OUT_DIR,  # scan from COM0 to COM[N]
            self._const.SET_DISP_OFFSET,
            0x00,
            0b11010101,
            0b11110000,
            # display
            self._const.SET_CONTRAST,
            0x80,  # median
            self._const.SET_ENTIRE_ON,  # output follows RAM contents
            self._const.SET_NORM_INV,  # not inverted
            self._const.SET_DISP | 0x01,
        ):
            self.command(cmd)

    def _set_position(self, top, right, bottom, left):
        pass

    def display(self, image):
        """
        Takes a 1-bit monochrome or 24-bit RGB image and renders it
        to the greyscale OLED display. RGB pixels are converted to 8-bit
        greyscale values using a simplified Luma calculation, based on
        *Y=0.299R+0.587G+0.114B*.
        :param image: the image to render
        :type image: PIL.Image.Image
        """

        assert image.mode == self.mode
        assert image.size == self.size

        image = self.preprocess(image)

        for image, bounding_box in self.framebuffer.redraw(image):
            left, top, right, bottom = bounding_box
            width = right - left
            height = bottom - top

            buf = bytearray(width * height >> 1)

            self._populate(buf, image.getdata())
            self.data(buf)

    def cleanup(self):
        self.command(self._const.SET_ENTIRE_OFF)  # to be absolutely sure
        super().cleanup()  # and this should call DISPLAY OFF command
