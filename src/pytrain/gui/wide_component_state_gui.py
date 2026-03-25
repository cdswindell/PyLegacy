#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from __future__ import annotations

import logging
import os
import signal
import time
from multiprocessing import get_context
from multiprocessing.process import BaseProcess
from threading import Thread
from typing import Iterable

from .component_state_gui import ComponentStateGui
from ..gpio.gpio_handler import GpioHandler
from ..protocol.constants import PROGRAM_NAME

log = logging.getLogger(__name__)


def _run_wide_pane(
        pane_guis: list[str],
        label: str | None,
        pane_width: int,
        pane_height: int,
        scale_by: float,
        exclude_unnamed: bool,
        x_offset: int,
        y_offset: int,
) -> None:
    from ..gui.accessories_gui import AccessoriesGui
    from ..gui.motors_gui import MotorsGui
    from ..gui.power_district_gui import PowerDistrictsGui
    from ..gui.routes_gui import RoutesGui
    from ..gui.switches_gui import SwitchesGui
    from .systems_gui import SystemsGui

    all_guis = {
        "Accessories": AccessoriesGui,
        "Motors": MotorsGui,
        "Power Districts": PowerDistrictsGui,
        "Routes": RoutesGui,
        "Switches": SwitchesGui,
        f"{PROGRAM_NAME} Administration": SystemsGui,
    }

    gui = None
    stop_flag = False

    def _on_stop(*_args):
        nonlocal stop_flag
        stop_flag = True
        if gui and hasattr(gui, "reset"):
            gui.reset()

    signal.signal(signal.SIGTERM, _on_stop)
    signal.signal(signal.SIGINT, _on_stop)

    if len(pane_guis) == 1:
        gui_name = pane_guis[0]
        gui_cls = all_guis[gui_name]
        gui = gui_cls(
            label=label,
            width=pane_width,
            height=pane_height,
            scale_by=scale_by,
            exclude_unnamed=exclude_unnamed,
            screens=1,
            full_screen=False,
            x_offset=x_offset,
            y_offset=y_offset,
        )
    else:
        pane_gui_map = {name: all_guis[name] for name in pane_guis}
        gui = ComponentStateGui(
            label=label,
            initial=pane_guis[0],
            width=pane_width,
            height=pane_height,
            scale_by=scale_by,
            exclude_unnamed=exclude_unnamed,
            screens=1,
            guis=pane_gui_map,
            full_screen=False,
            x_offset=x_offset,
            y_offset=y_offset,
        )

    while not stop_flag:
        if hasattr(gui, "destroy_complete") and gui.destroy_complete.is_set():
            break
        time.sleep(0.25)

    if gui and hasattr(gui, "reset"):
        gui.reset()


class WideComponentStateGui:
    """
    Wide-display compositor for state GUIs.

    Each pane receives a set/list of GUI names:
      - single item: render that GUI directly
      - multiple items: render ComponentStateGui with a combo restricted to that set
    """

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @staticmethod
    def _pane_count_hint(screen_components: list[str | Iterable[str]] | None, screens: int | None) -> int:
        if screen_components:
            return max(1, len(screen_components))
        if screens:
            return max(1, screens)
        return 2

    def __init__(
            self,
            label: str = None,
            initial: str = "Power Districts",
            width: int = None,
            height: int = None,
            scale_by: float = 1.0,
            exclude_unnamed: bool = False,
            screens: int | None = None,
            screen_components: list[str | Iterable[str]] | None = None,
            x_offset: int = 0,
            y_offset: int = 0,
            use_subprocesses: bool = True,
    ) -> None:
        from ..gui.accessories_gui import AccessoriesGui
        from ..gui.motors_gui import MotorsGui
        from ..gui.power_district_gui import PowerDistrictsGui
        from ..gui.routes_gui import RoutesGui
        from ..gui.switches_gui import SwitchesGui
        from .systems_gui import SystemsGui

        self._all_guis = {
            "Accessories": AccessoriesGui,
            "Motors": MotorsGui,
            "Power Districts": PowerDistrictsGui,
            "Routes": RoutesGui,
            "Switches": SwitchesGui,
            f"{PROGRAM_NAME} Administration": SystemsGui,
        }
        self.label = label.title() if label is not None else None
        self._scale_by = scale_by
        self._exclude_unnamed = exclude_unnamed
        self._x_offset = x_offset
        self._y_offset = y_offset
        self._use_subprocesses = use_subprocesses

        pane_hint = self._pane_count_hint(screen_components, screens)
        fallback_width = 800 * pane_hint
        fallback_height = 480

        if width is None or height is None:
            self.width = width
            self.height = height
            display = os.environ.get("DISPLAY")
            if display:
                try:
                    from tkinter import Tk

                    root = Tk()
                    if self.width is None:
                        self.width = root.winfo_screenwidth()
                    if self.height is None:
                        self.height = root.winfo_screenheight()
                    root.destroy()
                except Exception as e:
                    log.exception("Error determining window size", exc_info=e)
            else:
                log.warning("DISPLAY is not set; falling back to configured/default pane dimensions")

            if self.width is None:
                self.width = fallback_width
            if self.height is None:
                self.height = fallback_height
        else:
            self.width = width
            self.height = height

        if self.width is None or self.height is None:
            raise ValueError("Unable to determine GUI dimensions; provide width and height explicitly")

        self._pane_configs = self._normalize_pane_config(screen_components, screens, initial)
        self._panes = []
        self._pane_processes: list[BaseProcess] = []
        self._build_panes()
        GpioHandler.cache_handler(self)

    @property
    def panes(self) -> list[object]:
        return list(self._panes)

    def _normalize_gui_name(self, gui_name: str) -> str:
        for known in self._all_guis:
            if gui_name.lower() == known.lower():
                return known
        raise ValueError(f"Invalid GUI name: {gui_name}")

    def _normalize_pane_config(
            self,
            screen_components: list[str | Iterable[str]] | None,
            screens: int | None,
            initial: str,
    ) -> list[list[str]]:
        if screen_components is None:
            screens = 2 if screens is None else screens
            if screens < 1:
                raise ValueError("screens must be >= 1")
            default_gui = self._normalize_gui_name(initial)
            return [[default_gui] for _ in range(screens)]

        if not isinstance(screen_components, (list, tuple)) or len(screen_components) == 0:
            raise ValueError("screen_components must be a non-empty list/tuple")

        panes: list[list[str]] = []
        for pane_def in screen_components:
            if isinstance(pane_def, str):
                pane_values = [pane_def]
            else:
                pane_values = list(pane_def)
            if not pane_values:
                raise ValueError("Each screen set must include at least one component GUI")
            normalized = []
            for name in pane_values:
                canonical = self._normalize_gui_name(str(name))
                if canonical not in normalized:
                    normalized.append(canonical)
            panes.append(normalized)

        if screens is not None and screens != len(panes):
            raise ValueError(f"screens ({screens}) does not match number of screen sets ({len(panes)})")
        return panes

    def _build_panes(self) -> None:
        pane_count = len(self._pane_configs)
        if pane_count == 0:
            return
        if self.width is None or self.height is None:
            raise ValueError("Invalid window dimensions; width/height must be non-null")

        pane_width = self.width // pane_count
        remainder = self.width % pane_count
        x_cursor = self._x_offset

        for idx, pane_guis in enumerate(self._pane_configs):
            this_width = pane_width + (1 if idx < remainder else 0)
            if self._use_subprocesses:
                proc = get_context("spawn").Process(
                    target=_run_wide_pane,
                    args=(
                        pane_guis,
                        self.label,
                        this_width,
                        self.height,
                        self._scale_by,
                        self._exclude_unnamed,
                        x_cursor,
                        self._y_offset,
                    ),
                    daemon=True,
                )
                proc.start()
                self._pane_processes.append(proc)
            else:
                if len(pane_guis) == 1:
                    gui_name = pane_guis[0]
                    gui_cls = self._all_guis[gui_name]
                    pane = gui_cls(
                        label=self.label,
                        width=this_width,
                        height=self.height,
                        scale_by=self._scale_by,
                        exclude_unnamed=self._exclude_unnamed,
                        screens=1,
                        full_screen=False,
                        x_offset=x_cursor,
                        y_offset=self._y_offset,
                    )
                else:
                    pane_gui_map = {name: self._all_guis[name] for name in pane_guis}
                    pane = ComponentStateGui(
                        label=self.label,
                        initial=pane_guis[0],
                        width=this_width,
                        height=self.height,
                        scale_by=self._scale_by,
                        exclude_unnamed=self._exclude_unnamed,
                        screens=1,
                        guis=pane_gui_map,
                        full_screen=False,
                        x_offset=x_cursor,
                        y_offset=self._y_offset,
                    )
                self._panes.append(pane)
            x_cursor += this_width

    def close(self) -> None:
        for proc in self._pane_processes:
            if proc.is_alive():
                proc.terminate()
                proc.join(10)
        self._pane_processes.clear()

        for pane in self._panes:
            if pane is None:
                continue
            if hasattr(pane, "reset"):
                pane.reset()
            if hasattr(pane, "destroy_complete"):
                pane.destroy_complete.wait(10)
            if isinstance(pane, Thread) and pane.is_alive():
                pane.join(10)
            GpioHandler.release_handler(pane)

    def reset(self) -> None:
        self.close()
