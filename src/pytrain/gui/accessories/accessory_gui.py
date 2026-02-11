#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import logging
from pathlib import Path
from threading import Event, Thread

from .configured_accessory import (
    ConfiguredAccessorySet,
    DEFAULT_CONFIG_FILE,
    GuiCtorSpec,
    instantiate_gui,
)
from ...gpio.gpio_handler import GpioHandler

log = logging.getLogger(__name__)


class AccessoryGui(Thread):
    @classmethod
    def name(cls) -> str:
        return cls.__name__

    def __init__(
        self,
        *,
        width: int | None = None,
        height: int | None = None,
        scale_by: float = 1.0,
        initial: str | None = None,
        config_file: str | Path = DEFAULT_CONFIG_FILE,
        validate_config: bool = True,
        verify_config: bool = False,
    ) -> None:
        """
        Aggregator that builds its GUI list from accessory_config.json via ConfiguredAccessorySet.
        """
        super().__init__(daemon=True)
        self._ev = Event()

        # Load + index configured accessories
        self._configured = ConfiguredAccessorySet.from_file(
            config_file,
            validate=validate_config,
            verify=verify_config,
        )

        # Build GUI ctor specs (labels are already disambiguated if needed)
        self._specs: list[GuiCtorSpec] = self._configured.gui_specs()
        if not self._specs:
            raise ValueError("AccessoryGui: no GUIs configured")

        self._spec_by_label: dict[str, GuiCtorSpec] = {s.label: s for s in self._specs}
        self._sorted_guis: list[str] = [s.label for s in self._specs]  # already sorted in gui_specs()

        # resolve initial selection (substring match like old behavior)
        if initial:
            chosen = None
            for label in self._sorted_guis:
                if initial.lower() in label.lower():
                    chosen = label
                    break
            if chosen is None:
                raise ValueError(f"Invalid initial GUI: {initial}")
            initial = chosen
        else:
            initial = self._sorted_guis[0]

        # window size (unchanged behavior)
        if width is None or height is None:
            try:
                from tkinter import Tk

                root = Tk()
                self.width = root.winfo_screenwidth()
                self.height = root.winfo_screenheight()
                root.destroy()
            except Exception as e:
                log.exception("Error determining window size", exc_info=e)
                self.width = width or 1024
                self.height = height or 600
        else:
            self.width = width
            self.height = height

        self._scale_by = scale_by
        self._gui = None
        self.requested_gui = initial

        self.start()

    # -------------------------------------------------------------------------
    # Thread loop
    # -------------------------------------------------------------------------

    def _create_gui(self, label: str) -> None:
        spec = self._spec_by_label[label]

        # Most accessory GUIs already accept these args; extras are filtered inside spec.kwargs,
        # but extra_kwargs are *not* filtered, so only pass things you know they accept.
        extra_kwargs = {
            "aggregator": self,
            "width": self.width,
            "height": self.height,
            "scale_by": self._scale_by,
        }

        try:
            self._gui = instantiate_gui(spec, extra_kwargs=extra_kwargs)
        except TypeError as e:
            # Keep error readable and include which GUI label failed.
            raise TypeError(f"Failed to instantiate accessory GUI '{label}': {e}") from None

    def run(self) -> None:
        print(f"Creating GUI: {self.requested_gui}")
        self._create_gui(self.requested_gui)

        while True:
            self._ev.wait()
            self._ev.clear()

            if self._gui is not None:
                GpioHandler.release_handler(self._gui)

                # Preserve your existing shutdown behavior
                self._gui.destroy_complete.wait(10)
                self._gui.join()
                self._gui = None

            self._create_gui(self.requested_gui)

    def cycle_gui(self, gui: str) -> None:
        if gui in self._spec_by_label:
            self.requested_gui = gui
            self._ev.set()

    @property
    def guis(self) -> list[str]:
        return list(self._sorted_guis)
