#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
#
#
from guizero import Box, ListBox

from ...protocol.constants import CommandScope
from ..guizero_base import GuiZeroBase


class CatalogPanel:
    def __init__(self, gui: GuiZeroBase, width: int, height: int):
        self._gui = gui
        self._width = width
        self._height = height
        self._scope = None
        self._state_store = self._gui.state_store
        self._catalog = None

    def build(self, body: Box) -> None:
        self._catalog = lb = ListBox(
            body,
            items=[],
            scrollbar=True,
        )
        lb.text_size = self._gui.s_20

    def update(self, scope: CommandScope) -> None:
        if self._scope != scope:
            self._catalog.clear()
            for state in self._state_store.get_all(scope):
                self._catalog.append(state.name)
        self._scope = scope

    @property
    def title(self) -> str:
        return self._scope.plural if self._scope else "N/A"
