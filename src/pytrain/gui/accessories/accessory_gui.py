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

        # Build configured accessories (labels are already disambiguated in ConfiguredAccessorySet.gui_specs())
        # but for the standalone aggregator we want "label -> ConfiguredAccessory".
        self._accessories: list[ConfiguredAccessory] = self._configured.configured_all()
        if not self._accessories:
            raise ValueError("AccessoryGui: no GUIs configured")

        # Build label order using the same logic as gui_specs(), so menu ordering matches.
        # (gui_specs() is already sorted and disambiguated.)
        specs = self._configured.gui_specs()
        self._sorted_guis: list[str] = [s.label for s in specs]

        # Map label -> configured accessory (must be 1:1 with specs labels).
        by_label: dict[str, list] = {lbl: [] for lbl in self._sorted_guis}
        for acc in self._accessories:
            by_label.setdefault(acc.label, []).append(acc)

        # If duplicates exist, gui_specs() disambiguates with instance_id.
        # Rebuild label->acc using the same disambiguation rule.
        self._acc_by_label: dict[str, ConfiguredAccessory] = {}
        if any(len(v) > 1 for v in by_label.values()):
            # Count base labels
            counts: dict[str, int] = {}
            for acc in self._accessories:
                counts[acc.label] = counts.get(acc.label, 0) + 1

            for acc in self._accessories:
                label = acc.label
                if counts.get(label, 0) > 1 and acc.instance_id:
                    label = f"{label} ({acc.instance_id})"
                # first one wins if still collides (shouldn’t, but be defensive)
                self._acc_by_label.setdefault(label, acc)
        else:
            for acc in self._accessories:
                self._acc_by_label[acc.label] = acc

        if not self._acc_by_label:
            raise ValueError("AccessoryGui: no GUIs configured")

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
        acc = self._acc_by_label.get(label)
        if acc is None:
            raise ValueError(f"Invalid GUI label: {label}")

        try:
            # New path: ConfiguredAccessory owns ctor logic (and filters ctor kwargs).
            self._gui = acc.create_gui(aggregator=self)
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
