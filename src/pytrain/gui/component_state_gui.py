#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

import logging
from threading import Thread, Event

from ..protocol.constants import PROGRAM_NAME
from ..gpio.gpio_handler import GpioHandler

log = logging.getLogger(__name__)


class ComponentStateGui(Thread):
    @classmethod
    def name(cls) -> str:
        return cls.__name__

    def __init__(
        self,
        label: str = None,
        initial: str = "Power Districts",
        width: int = None,
        height: int = None,
        scale_by: float = 1.0,
        exclude_unnamed: bool = False,
    ) -> None:
        from ..gui.accessories_gui import AccessoriesGui
        from ..gui.motors_gui import MotorsGui
        from ..gui.power_district_gui import PowerDistrictsGui
        from ..gui.routes_gui import RoutesGui
        from ..gui.switches_gui import SwitchesGui
        from .systems_gui import SystemsGui

        super().__init__(daemon=True)
        self._ev = Event()
        self._guis = {
            "Accessories": AccessoriesGui,
            "Motors": MotorsGui,
            "Power Districts": PowerDistrictsGui,
            "Routes": RoutesGui,
            "Switches": SwitchesGui,
            f"{PROGRAM_NAME} Administration": SystemsGui,
        }
        # verify requested GUI exists:
        if initial.lower() not in [x.lower() for x in self._guis.keys()]:
            raise ValueError(f"Invalid initial GUI: {initial}")

        # case-correct initial
        for key in self._guis.keys():
            if initial.lower() == key.lower():
                initial = key
                break

        if label is not None:
            label = label.title()

        self.label = label
        if width is None or height is None:
            try:
                from tkinter import Tk

                root = Tk()
                self.width = root.winfo_screenwidth()
                self.height = root.winfo_screenheight()
                root.destroy()
            except Exception as e:
                log.exception("Error determining window size", exc_info=e)
        else:
            self.width = width
            self.height = height
        self._scale_by = scale_by
        self._gui = None
        self._exclude_unnamed = exclude_unnamed
        self.requested_gui = initial

        self.start()

    def run(self) -> None:
        # create the initially requested gui
        self._gui = self._guis[self.requested_gui](
            self.label,
            self.width,
            self.height,
            aggrigator=self,
            scale_by=self._scale_by,
            exclude_unnamed=self._exclude_unnamed,
        )

        # wait for user to request a different GUI
        while True:
            # Wait for request to change GUI
            self._ev.wait()
            self._ev.clear()

            # Close/destroy previous GUI
            GpioHandler.release_handler(self._gui)

            # wait for Gui to be destroyed
            self._gui.destroy_complete.wait(10)
            self._gui.join()
            # clean up state
            self._gui = None

            # create and display new gui
            # TODO: handle push_for argument for the sys admin stuff
            self._gui = self._guis.get(self.requested_gui)(
                self.label,
                self.width,
                self.height,
                aggrigator=self,
                scale_by=self._scale_by,
                exclude_unnamed=self._exclude_unnamed,
            )

    def cycle_gui(self, gui: str):
        if gui in self._guis:
            self.requested_gui = gui
            self._ev.set()

    @property
    def guis(self) -> list[str]:
        return list(self._guis.keys())
