#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from guizero import Box

from ..guizero_base import GuiZeroBase


class AdminPanel:
    def __init__(self, gui: GuiZeroBase):
        self._gui = gui

    def build(self, body: Box):
        pass
