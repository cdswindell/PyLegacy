#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from guizero import Box

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui


class OverlayPanel(metaclass=ABCMeta):
    @abstractmethod
    def __init__(self, gui: "EngineGui", title: str):
        self._gui = gui
        self._title = title
        self._overlay = None

    @abstractmethod
    def build(self, body: Box):
        pass

    @property
    def overlay(self) -> Box:
        if self._overlay is None:
            # noinspection PyProtectedMember
            self._overlay = self._gui._popup.create_popup(self._title, self.build)
        return self._overlay

    @property
    def visible(self) -> bool:
        return self._overlay is not None and self._overlay.visible
