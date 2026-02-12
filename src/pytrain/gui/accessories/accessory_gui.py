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

from .configured_accessory import ConfiguredAccessory, ConfiguredAccessorySet, DEFAULT_CONFIG_FILE
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
        Standalone accessory GUI aggregator that builds its menu from accessory_config.json
        via ConfiguredAccessorySet.

        NOTE: ConfiguredAccessorySet now assigns each ConfiguredAccessory a resolved, unique,
        user-facing label (stored on _label). AccessoryGui uses that directly.
        """
        super().__init__(daemon=True)
        self._ev = Event()

        self._configured = ConfiguredAccessorySet.from_file(
            config_file,
            validate=validate_config,
            verify=verify_config,
        )

        self._accessories: list[ConfiguredAccessory] = self._configured.configured_all()
        if not self._accessories:
            raise ValueError("AccessoryGui: no GUIs configured")

        # Labels are already resolved + unique (via ConfiguredAccessorySet._rebuild_indexes)
        self._sorted_guis: list[str] = sorted([a.label for a in self._accessories])

        # Map label -> accessory (should be 1:1). Be defensive in case uniqueness breaks.
        self._acc_by_label: dict[str, ConfiguredAccessory] = {}
        for a in self._accessories:
            lbl = a.label
            if lbl in self._acc_by_label:
                # This should not happen if _rebuild_indexes ensures uniqueness.
                # Keep it readable if it does.
                raise ValueError(f"AccessoryGui: duplicate resolved label {lbl!r} in config")
            self._acc_by_label[lbl] = a

        # Resolve initial selection (substring match like old behavior)
        if initial:
            needle = initial.lower()
            chosen = next((lbl for lbl in self._sorted_guis if needle in lbl.lower()), None)
            if chosen is None:
                raise ValueError(f"Invalid initial GUI: '{initial}'")
            initial = chosen
        else:
            initial = self._sorted_guis[0]

        # Window size (unchanged behavior)
        if width is None or height is None:
            try:
                from tkinter import Tk

                root = Tk()
                self.width = root.winfo_screenwidth()
                self.height = root.winfo_screenheight()
                root.destroy()
            except (ImportError, RuntimeError) as e:
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
        acc = self._acc_by_label.get(label)
        if acc is None:
            raise ValueError(f"Invalid GUI label: {label}")

        try:
            # ConfiguredAccessory owns ctor logic (and filters ctor kwargs).
            self._gui = acc.create_gui(aggregator=self)
            self._gui.menu_label = acc.label
            # TODO: clean this up by moving gui creation into this module
        except TypeError as e:
            raise TypeError(f"Failed to instantiate accessory GUI '{label}': {e}") from None

    def run(self) -> None:
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
        if gui in self._acc_by_label:
            self.requested_gui = gui
            self._ev.set()

    @property
    def guis(self) -> list[str]:
        return list(self._sorted_guis)
