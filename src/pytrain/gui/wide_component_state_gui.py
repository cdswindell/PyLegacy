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
from tkinter import TclError
from typing import Any, Iterable

from guizero import App, Box, Combo, Text

from .guizero_base import GuiZeroBase
from ..protocol.constants import PROGRAM_NAME

log = logging.getLogger(__name__)
GUI_CLEANUP_EXCEPTIONS = (AttributeError, RuntimeError, TclError, TypeError)
WINDOW_SIZE_EXCEPTIONS = (ImportError, RuntimeError, TclError)


def _safe_destroy(widget: Any) -> None:
    if widget:
        try:
            widget.destroy()
        except GUI_CLEANUP_EXCEPTIONS:
            pass
    return None


class _WidePane:
    """
    Container for one column in `WideComponentStateGui`.

    A pane owns a fixed-width Tk container, optional header controls, and one
    instantiated child GUI per selectable screen name. All child GUIs are
    created eagerly and switched via `hide_gui()` / `show_gui()` to avoid
    rebuilding widgets during runtime.
    """

    def __init__(
        self,
        owner: GuiZeroBase,
        app: App,
        parent: Box,
        all_guis: dict[str, type],
        gui_names: list[str],
        label: str | None,
        pane_width: int,
        pane_height: int,
        scale_by: float,
        exclude_unnamed: bool,
        column: int,
    ) -> None:
        """
        Build pane widgets and instantiate the configured child GUI screens.

        Parameters:
            app: Shared top-level guizero app used by all panes.
            parent: Root container that owns pane columns.
            all_guis: Registry mapping display names to GUI classes.
            gui_names: GUI names available in this pane; first entry is default.
            label: Optional header prefix shown before the selector.
            pane_width: Fixed pane width in pixels.
            pane_height: Fixed pane height in pixels.
            scale_by: Font/layout scaling factor.
            exclude_unnamed: Passed through to child GUIs.
            column: Grid column index for pane placement.
        """
        self._owner = owner
        self._app = app
        self._gui_names = list(gui_names)
        self._guis: dict[str, Any] = {}
        self._active_gui: str | None = None

        self.container = Box(parent, layout="auto", grid=[column, 0], align="left")
        self.container.tk.configure(width=pane_width, height=pane_height)
        self.container.tk.pack_propagate(False)
        parent.tk.grid_columnconfigure(column, weight=1, minsize=pane_width)

        self.header = None

        has_selector = len(self._gui_names) > 1
        child_label = None if has_selector else label

        if has_selector:
            self.header = Box(self.container, layout="auto", align="top")
            self.header.tk.configure(width=pane_width)
            if label:
                txt = Text(self.header, text=f"{label}: ", align="left", bold=True)
                txt.text_size = int(round(20 * scale_by))
            self.combo = Combo(
                self.header,
                options=self._gui_names,
                selected=self._gui_names[0],
                align="right",
                command=self._on_combo_change,
            )
            self.combo.text_size = int(round(20 * scale_by))
            self.combo.text_bold = True
        else:
            self.combo = None

        app.tk.update_idletasks()
        header_height = self.header.tk.winfo_height() if self.header else 0
        content_height = max(1, pane_height - header_height)
        # Reserve a small bottom margin so state grid overflow checks remain conservative.
        inner_gui_height = max(1, content_height - max(4, int(round(6 * scale_by))))

        self.content = Box(self.container, layout="auto", align="top")
        self.content.tk.configure(width=pane_width, height=content_height)
        self.content.tk.pack_propagate(False)

        for gui_name in self._gui_names:
            gui_cls = all_guis[gui_name]
            gui = gui_cls(
                label=child_label,
                width=pane_width,
                height=inner_gui_height,
                scale_by=scale_by,
                exclude_unnamed=exclude_unnamed,
                screens=1,
                stand_alone=False,
                parent=self.content,
                full_screen=False,
                x_offset=0,
                y_offset=0,
            )
            if isinstance(gui, GuiZeroBase):
                gui.attach_to_parent_queue(self._owner)
                if has_selector and hasattr(gui, "_show_title"):
                    gui._show_title = False
                gui._app = app
                gui.build_gui()
                if hasattr(gui, "hide_gui"):
                    gui.hide_gui()
            self._guis[gui_name] = gui

        self.show(self._gui_names[0])

    @property
    def gui_names(self) -> list[str]:
        return list(self._gui_names)

    def _on_combo_change(self, option: str) -> None:
        self.show(option)

    def show(self, gui_name: str) -> None:
        """Activate a child GUI by name, hiding the previously active GUI."""
        if gui_name not in self._guis:
            return
        if self._active_gui == gui_name:
            return

        if self._active_gui is not None:
            current = self._guis[self._active_gui]
            if hasattr(current, "hide_gui"):
                current.hide_gui()
        nxt = self._guis[gui_name]
        if hasattr(nxt, "show_gui"):
            nxt.show_gui()
        self._active_gui = gui_name

    def destroy(self) -> None:
        """Tear down child GUIs and release pane widgets/resources."""
        child_guis = list(self._guis.values())
        for gui in child_guis:
            if isinstance(gui, GuiZeroBase):
                # All child widget destruction happens in the parent Tk thread.
                print(f"Destroying {gui}")
                gui.destroy_gui()
        child_guis.clear()
        self._guis.clear()
        _safe_destroy(self.combo)
        self.combo = None
        _safe_destroy(self.content)
        self.content = None
        _safe_destroy(self.header)
        self.header = None
        _safe_destroy(self.container)
        self.container = None


class WideComponentStateGui(GuiZeroBase):
    """
    Wide-display compositor using a single guizero App.

    Each pane receives a list of GUI names:
      - single item: render that GUI directly
      - multiple items: render all screens in the pane and switch via hide/show
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
        auto_start: bool = True,
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

        pane_hint = self._pane_count_hint(screen_components, screens)
        fallback_width = 800 * pane_hint
        fallback_height = 480

        if width is None or height is None:
            resolved_width = width
            resolved_height = height
            display = os.environ.get("DISPLAY")
            if display:
                try:
                    from tkinter import Tk

                    root = Tk()
                    if resolved_width is None:
                        resolved_width = root.winfo_screenwidth()
                    if resolved_height is None:
                        resolved_height = root.winfo_screenheight()
                    root.destroy()
                except WINDOW_SIZE_EXCEPTIONS as e:
                    log.exception("Error determining window size", exc_info=e)
            else:
                log.warning("DISPLAY is not set; falling back to default pane dimensions")
            self.width = resolved_width if resolved_width is not None else fallback_width
            self.height = resolved_height if resolved_height is not None else fallback_height
        else:
            self.width = width
            self.height = height

        GuiZeroBase.__init__(
            self,
            title=f"{PROGRAM_NAME} Wide Component State",
            width=self.width,
            height=self.height,
            scale_by=scale_by,
            stand_alone=auto_start,
            full_screen=False,
            x_offset=x_offset,
            y_offset=y_offset,
        )
        self.label = label.title() if label is not None else None
        self._exclude_unnamed = exclude_unnamed
        self._root: Box | None = None
        self._panes: list[_WidePane] = []

        self._pane_configs = self._normalize_pane_config(screen_components, screens, initial)
        self.init_complete()

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

    def _create_pane(
        self,
        app: App,
        root: Box,
        pane_guis: list[str],
        pane_width: int,
        pane_height: int,
        column: int,
    ) -> _WidePane:
        pane_label = self.label
        if pane_label is None and len(pane_guis) > 1 and isinstance(self.title, str) and self.title:
            pane_label = self.title
        return _WidePane(
            owner=self,
            app=app,
            parent=root,
            all_guis=self._all_guis,
            gui_names=pane_guis,
            label=pane_label,
            pane_width=pane_width,
            pane_height=pane_height,
            scale_by=self._scale_by,
            exclude_unnamed=self._exclude_unnamed,
            column=column,
        )

    def _build_panes(self, app: App, root: Box) -> None:
        pane_count = len(self._pane_configs)
        if pane_count < 1:
            return

        pane_width = self.width // pane_count
        remainder = self.width % pane_count

        for idx, pane_guis in enumerate(self._pane_configs):
            this_width = pane_width + (1 if idx < remainder else 0)
            pane = self._create_pane(
                app=app,
                root=root,
                pane_guis=pane_guis,
                pane_width=this_width,
                pane_height=self.height,
                column=idx,
            )
            self._panes.append(pane)

    def _destroy_panes(self) -> None:
        while self._panes:
            pane = self._panes.pop()
            pane.destroy()
        self._panes.clear()
        self._pane_configs.clear()
        _safe_destroy(self._root)
        self._root = None

    def build_gui(self) -> None:
        app = self.app
        app.bg = "white"
        self._root = root = Box(app, layout="grid")
        self._build_panes(app, root)

    def destroy_gui(self) -> None:
        self._destroy_panes()

    def calc_image_box_size(self) -> tuple[int, int]:
        return self.height, self.width
