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
from threading import Event, Thread

from ..gpio.gpio_handler import GpioHandler

log = logging.getLogger(__name__)


class AccessoryGui(Thread):
    @classmethod
    def name(cls) -> str:
        return cls.__name__

    def __init__(
        self, *args, width: int = None, height: int = None, scale_by: float = 1.0, initial: str = None
    ) -> None:
        from ..gui.fire_station_gui import FireStationGui
        from ..gui.milk_loader_gui import MilkLoaderGui

        super().__init__(daemon=True)
        self._ev = Event()
        self._gui_classes = {
            "milk loader": MilkLoaderGui,
            "fire station": FireStationGui,
        }

        # look for tuples in args; they define the guis we want
        self._guis = {}
        for gui in args:
            if isinstance(gui, tuple):
                gui_class = self.get_variant(gui[0])
                gui_args = gui[1:]
                if isinstance(gui_args[-1], str):
                    variant_arg = gui_args[-1].split("=")[-1]
                else:
                    variant_arg = None
                title, _ = gui_class.get_variant(variant_arg)
                self._guis[title] = (gui_class, gui_args)

        # verify requested GUI exists:
        if initial:
            if initial.lower() not in [x.lower() for x in self._guis.keys()]:
                raise ValueError(f"Invalid initial GUI: {initial}")

            # case-correct initial
            for key in self._guis.keys():
                if initial.lower() == key.lower():
                    initial = key
                    break
        else:
            initial = list(self._guis.keys())[0]

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
        self.requested_gui = initial

        self.start()

    def get_variant(self, variant: str):
        if not isinstance(variant, str):
            raise ValueError(f"Invalid GUI variant: {variant}")
        variant = variant.lower().strip().replace("'", "").replace("-", "")
        for k, v in self._gui_classes.items():
            if variant in k:
                return v
        raise ValueError(f"Invalid GUI variant: {variant}")

    def run(self) -> None:
        # create the initially requested gui
        gui = self._guis[self.requested_gui]
        self._gui = gui[0](self.requested_gui, *gui[1:], aggrigator=self)

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
            gui = self._guis[self.requested_gui]
            self._gui = gui[0](self.requested_gui, *gui[1:], aggrigator=self)

    def cycle_gui(self, gui: str):
        if gui in self._guis:
            self.requested_gui = gui
            self._ev.set()

    @property
    def guis(self) -> list[str]:
        return list(self._guis.keys())
