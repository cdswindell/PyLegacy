#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
from unittest import TestCase

from src.pytrain.gpio.gpio_device import GpioDevice
from test.test_base import TestBase


class TestGPIODevice(TestBase, TestCase):
    def test_cannot_instantiate_abstract_class(self) -> None:
        with self.assertRaises(TypeError):
            GpioDevice()
