#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#
#  SPDX-License-Identifier: LPGL
#
from __future__ import annotations

import atexit
import logging
import re
import tkinter as tk
from queue import Empty, Queue
from threading import Condition, Event, RLock, Thread, get_ident
from tkinter import TclError
from typing import Any, Callable, Generic, TypeVar, cast

from guizero import App, Box, Combo, Picture, PushButton, Text, TitleBox
from guizero.base import Widget
from guizero.event import EventData
from PIL import Image

from ..comm.command_listener import CommandDispatcher
from ..db.base_state import BaseState
from ..db.component_state import ComponentState
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler
from ..pdi.asc2_req import Asc2Req
from ..pdi.constants import Asc2Action, PdiCommand
from ..protocol.constants import CommandScope
from ..utils.path_utils import find_file

log = logging.getLogger(__name__)
S = TypeVar("S", bound=ComponentState)

HYPHEN_CLEANUP = re.compile(r"(?<=[A-Za-z])-+(?=[A-Za-z])")
SPACE_CLEANUP = re.compile(r"\s{2,}")

LAYOUT = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["C", "0", "E"],
]


class EngineGui(Thread, Generic[S]):
    @classmethod
    def name(cls) -> str:
        return cls.__name__

    def __init__(
        self,
        width: int = None,
        height: int = None,
        enabled_bg: str = "green",
        disabled_bg: str = "black",
        enabled_text: str = "black",
        disabled_text: str = "lightgrey",
        scale_by: float = 1.0,
        bs: int = 50,
        max_image_width: float = 0.80,
        max_image_height: float = 0.45,
    ) -> None:
        Thread.__init__(self, daemon=True, name="Engine GUI")
        self._cv = Condition(RLock())
        self._ev = Event()
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
        self.title = None
        self.image_file = None
        self._base_state = None
        self._engine_tmcc_id = None
        self._engine_state = None
        self._image = None
        self._scale_by = scale_by
        self._max_image_width = max_image_width
        if self.height > 320 and max_image_height == 0.45:
            max_image_height = 0.55
        self._max_image_height = max_image_height
        self.s_20: int = int(round(20 * scale_by))
        self.s_18: int = int(round(18 * scale_by))
        self.s_16: int = int(round(16 * scale_by))
        self.s_12: int = int(round(12 * scale_by))
        self._text_pad_x = 20
        self._text_pad_y = 20
        self.bs = bs
        self.s_72 = self.scale(72, 0.7)

        self._enabled_bg = enabled_bg
        self._disabled_bg = disabled_bg
        self._enabled_text = enabled_text
        self._disabled_text = disabled_text
        self.app = self.box = self.acc_box = self.y_offset = None
        self.turn_on_image = find_file("on_button.jpg")
        self.turn_off_image = find_file("off_button.jpg")
        self.alarm_on_image = find_file("Breaking-News-Emoji.gif")
        self.alarm_off_image = find_file("red_light_off.jpg")
        self.left_arrow_image = find_file("left_arrow.jpg")
        self.right_arrow_image = find_file("right_arrow.jpg")
        self._app_counter = 0
        self._message_queue = Queue()

        # various boxes
        self.emergency_box = self.keypad_box = None

        # various buttons
        self.halt_btn = self.reset_btn = None

        # various fields
        self.tmcc_id_text = self._nbi = None

        # Thread-aware shutdown signaling
        self._tk_thread_id: int | None = None
        self._is_closed = False
        self._shutdown_flag = Event()

        # listen for state changes
        self._dispatcher = CommandDispatcher.get()
        self._state_store = ComponentStateStore.get()
        self._synchronized = False
        self._sync_state = self._state_store.get_state(CommandScope.SYNC, 99)
        if self._sync_state and self._sync_state.is_synchronized is True:
            self._sync_watcher = None
            self.on_sync()
        else:
            self._sync_watcher = StateWatcher(self._sync_state, self.on_sync)

        # Important: don't call tkinter from atexit; only signal
        atexit.register(lambda: self._shutdown_flag.set())

    def close(self) -> None:
        # Only signal shutdown here; actual tkinter destroy happens on the GUI thread
        if not self._is_closed:
            self._is_closed = True
            self._shutdown_flag.set()

    def reset(self) -> None:
        self.close()

    @property
    def destroy_complete(self) -> Event:
        return self._ev

    # noinspection PyTypeChecker
    def on_sync(self) -> None:
        if self._sync_state.is_synchronized:
            if self._sync_watcher:
                self._sync_watcher.shutdown()
                self._sync_watcher = None
            self._synchronized = True
            self._base_state = ComponentStateStore.get().get_state(CommandScope.BASE, 0, False)
            if self._base_state:
                self.title = cast(BaseState, self._base_state).base_name
            else:
                self.title = "My Layout"

            # start GUI
            self.start()

    # noinspection PyTypeChecker
    def set_button_inactive(self, widget: Widget):
        if isinstance(widget, PowerButton):
            widget.image = self.turn_on_image
            widget.height = widget.width = self.s_72
        else:
            widget.bg = self._disabled_bg
            widget.text_color = self._disabled_text

    # noinspection PyTypeChecker
    def set_button_active(self, widget: Widget):
        if isinstance(widget, PowerButton):
            widget.image = self.turn_off_image
            widget.height = widget.width = self.s_72
        else:
            widget.bg = self._enabled_bg
            widget.text_color = self._enabled_text

    def queue_message(self, message: Callable, *args: Any) -> None:
        self._message_queue.put((message, args))

    @staticmethod
    def normalize(text: str) -> str:
        text = text.strip().lower()
        text = HYPHEN_CLEANUP.sub(" ", text)
        text = SPACE_CLEANUP.sub(" ", text)
        return text

    # noinspection PyTypeChecker
    def run(self) -> None:
        self._shutdown_flag.clear()
        self._ev.clear()
        self._tk_thread_id = get_ident()
        GpioHandler.cache_handler(self)
        self.app = app = App(title=self.title, width=self.width, height=self.height)
        app.full_screen = True
        app.when_closed = self.close
        app.bg = "white"

        # poll for shutdown requests from other threads; this runs on the GuiZero/Tk thread
        def _poll_shutdown():
            self._app_counter += 1
            if self._shutdown_flag.is_set():
                try:
                    app.destroy()
                except TclError:
                    pass  # ignore, we're shutting down
                return None
            else:
                try:
                    message = self._message_queue.get_nowait()
                    if isinstance(message, tuple):
                        if message[1] and len(message[1]) > 0:
                            message[0](*message[1])
                        else:
                            message[0]()
                except Empty:
                    pass
            return None

        app.repeat(20, _poll_shutdown)

        ats = int(round(23 * self._scale_by))
        # customize label
        cb = Combo(
            app,
            options=[self.title],
            selected=self.title,
            align="top",
        )
        cb.text_size = ats
        cb.text_bold = True
        _ = Text(app, text=" ", align="top", size=6, height=1, bold=True)

        # Make the emergency buttons, including Halt and Reset
        self.make_emergency_buttons(app)

        # make selection box and keypad
        self.make_keypad(app)

        self._image = None
        if self.image_file:
            iw, ih = self.get_scaled_jpg_size(self.image_file)
            self._image = Picture(app, image=self.image_file, width=iw, height=ih)

        self.app.update()

        # build state buttons
        self.acc_box = Box(self.app, border=2, align="bottom", layout="grid")

        # Display GUI and start event loop; call blocks
        try:
            app.display()
        except TclError:
            # If Tcl is already tearing down, ignore
            pass
        finally:
            # Explicitly drop references to tkinter/guizero objects on the Tk thread
            self.box = None
            self.acc_box = None
            self._image = None
            self.app = None
            self._ev.set()

    def make_keypad(self, app: App):
        self.keypad_box = keypad_box = Box(app, layout="grid", border=2, align="top")
        _ = Text(keypad_box, text=" ", grid=[0, 0, 3, 1], align="top", size=3, height=1, bold=True)

        tmcc_id_box = TitleBox(keypad_box, "Engine TMCC ID", grid=[0, 1, 3, 1])
        tmcc_id_box.text_size = self.s_12

        self.tmcc_id_text = tmcc_id = Text(
            tmcc_id_box,
            text="0000",
            align="top",
            bold=True,
            width="fill",
        )
        tmcc_id.text_color = "blue"
        tmcc_id.text_bold = True
        tmcc_id.text_size = self.s_20
        tmcc_id.width = "20"
        _ = Text(keypad_box, text=" ", grid=[0, 2, 3, 1], align="top", size=3, height=1, bold=True)

        row = 3
        button_size = int(round(self.width / 5))
        for r, kr in enumerate(LAYOUT):
            for c, label in enumerate(kr):
                img = tk.PhotoImage(width=button_size, height=button_size)
                cell = Box(keypad_box, layout="auto", grid=[c, r + row])
                nb = PushButton(
                    cell,
                    text=label,
                    command=self.on_keypress,
                    args=[label],
                )
                nb._img = img
                nb.text_color = "black"
                nb.tk.config(image=img, compound="center")
                nb.tk.config(width=button_size, height=button_size)
                nb.text_size = self.s_20
                nb.text_bold = True
                nb.tk.config(padx=0, pady=0, borderwidth=1, highlightthickness=1)
                # spacing between buttons (in pixels)
                nb.tk.grid_configure(padx=6, pady=6)

    def make_emergency_buttons(self, app: App):
        self.emergency_box = emergency_box = Box(app, layout="grid", border=2, align="top")
        _ = Text(emergency_box, text=" ", grid=[0, 0, 3, 1], align="top", size=3, height=1, bold=True)

        self.halt_btn = halt_btn = PushButton(
            emergency_box,
            text=">> Halt <<",
            grid=[0, 1],
            align="top",
            width=10,
            padx=self._text_pad_x,
            pady=self._text_pad_y,
        )
        halt_btn.bg = "red"
        halt_btn.text_color = "white"
        halt_btn.text_bold = True
        halt_btn.text_size = self.s_20

        _ = Text(emergency_box, text=" ", grid=[1, 1], align="top", size=6, height=1, bold=True)

        self.reset_btn = reset_btn = PushButton(
            emergency_box,
            text="Reset",
            grid=[2, 1],
            align="top",
            width=10,
            padx=self._text_pad_x,
            pady=self._text_pad_y,
            enabled=False,
        )
        reset_btn.bg = "gray"
        reset_btn.text_color = "black"
        reset_btn.text_bold = True
        reset_btn.text_size = self.s_20

        _ = Text(emergency_box, text=" ", grid=[0, 2, 3, 1], align="top", size=3, height=1, bold=True)

    def on_keypress(self, key: str) -> None:
        tmcc_id = self.tmcc_id_text.value
        if key.isdigit():
            tmcc_id = tmcc_id[1:] + key
        elif key == "C":
            tmcc_id = "0000"
        self.tmcc_id_text.value = tmcc_id

    def make_power_button(self, state: S, label: str, col: int, text_len: int, container: Box) -> PowerButton:
        btn_box = Box(container, layout="auto", border=2, grid=[col, 0], align="top")
        tb = Text(btn_box, text=label, align="top", size=self.s_16, underline=True)
        tb.width = text_len
        button = PowerButton(
            btn_box,
            image=self.turn_on_image,
            align="top",
            height=self.s_72,
            width=self.s_72,
        )
        button.tmcc_id = state.tmcc_id
        return button

    def scale(self, value: int, factor: float = None) -> int:
        orig_value = value
        value = max(orig_value, int(value * self.width / 480))
        if factor is not None and self.width > 480:
            value = max(orig_value, int(factor * value))
        return value

    @staticmethod
    def get_jpg_size(image_file: str):
        """
        Retrieves the native width and height of a JPG image.

        Args:
            image_file (str): The path to the JPG image file.

        Returns:
            tuple: A tuple containing the width and height (width, height)
                   in pixels, or (None, None) if an error occurs.
        """
        try:
            with Image.open(image_file) as img:
                width, height = img.size
                return width, height
        except FileNotFoundError as e:
            log.exception(f"Error: Image file not found at {image_file}", exc_info=e)
        except Exception as e:
            log.exception(f"An error occurred: {e}", exc_info=e)
        return None, None

    # noinspection PyTypeChecker
    def get_scaled_jpg_size(self, image_file: str) -> tuple[int, int]:
        iw, ih = self.get_jpg_size(image_file)
        if iw is None or ih is None:
            return None, None
        max_width = int(round(self.width * self._max_image_width))
        max_height = int(round(self.height * self._max_image_height))
        if ih > iw:
            scaled_height = max_height
            scale_factor = max_height / ih
            scaled_width = int(round(iw * scale_factor))
        else:
            scaled_width = max_width
            scale_factor = max_width / iw
            scaled_height = int(round(ih * scale_factor))
            # if the image takes up too much height, do more scaling
            if (scaled_height / self.height) > self._max_image_height:
                scaled_height = int(round(self.height * self._max_image_height))
                scale_factor = scaled_height / ih
                scaled_width = int(round(iw * scale_factor))
        return scaled_width, scaled_height

    def when_pressed(self, event: EventData) -> None:
        pb = event.widget
        if pb.enabled:
            state = pb.component_state
            if state.is_asc2:
                Asc2Req(state.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=1).send()

    def when_released(self, event: EventData) -> None:
        pb = event.widget
        if pb.enabled:
            state = pb.component_state
            if state.is_asc2:
                Asc2Req(state.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=0).send()


class PowerButton(PushButton):
    pass


class AnimatedButton(PushButton):
    def start_animation(self) -> None:
        if self._image_player:
            self._image_player.start()

    def stop_animation(self) -> None:
        if self._image_player:
            self._image_player.stop()

    def _clear_image(self) -> None:
        self.stop_animation()
        super()._clear_image()
