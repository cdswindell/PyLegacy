#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

from __future__ import annotations

import atexit
import logging
import re
from abc import ABC, ABCMeta, abstractmethod
from queue import Empty, Queue
from threading import Condition, Event, RLock, Thread, get_ident
from tkinter import TclError
from typing import Any, Callable, Generic, TypeVar

from guizero import App, Box, Combo, Picture, PushButton, Text
from guizero.base import Widget
from guizero.event import EventData
from PIL import Image

from ..comm.command_listener import CommandDispatcher
from ..db.component_state import ComponentState
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler
from ..pdi.asc2_req import Asc2Req
from ..pdi.constants import Asc2Action, PdiCommand
from ..protocol.constants import CommandScope
from ..utils.path_utils import find_file
from .accessory_gui import AccessoryGui

log = logging.getLogger(__name__)
S = TypeVar("S", bound=ComponentState)

HYPHEN_CLEANUP = re.compile(r"(?<=[A-Za-z])-+(?=[A-Za-z])")
SPACE_CLEANUP = re.compile(r"\s{2,}")


class AccessoryBase(Thread, Generic[S], ABC):
    __metaclass__ = ABCMeta

    @classmethod
    def name(cls) -> str:
        return cls.__name__

    @abstractmethod
    def __init__(
        self,
        title: str,
        image_file: str = None,
        width: int = None,
        height: int = None,
        aggrigator: AccessoryGui = None,
        enabled_bg: str = "green",
        disabled_bg: str = "black",
        enabled_text: str = "black",
        disabled_text: str = "lightgrey",
        scale_by: float = 1.0,
        max_image_width: float = 0.80,
        max_image_height: float = 0.45,
    ) -> None:
        Thread.__init__(self, daemon=True, name=f"{title} GUI")
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
        self.title = title
        self.image_file = image_file
        self._image = None
        self._aggrigator = aggrigator
        self._scale_by = scale_by
        self._max_image_width = max_image_width
        if self.height > 320 and max_image_height == 0.45:
            max_image_height = 0.55
        self._max_image_height = max_image_height
        self._text_size: int = 24
        self.s_72 = self.scale(72, 0.7)
        self.s_16 = self.scale(16, 0.7)

        self._enabled_bg = enabled_bg
        self._disabled_bg = disabled_bg
        self._enabled_text = enabled_text
        self._disabled_text = disabled_text
        self.app = self.box = self.acc_box = self.y_offset = None
        self.aggrigator_combo = None
        self.turn_on_image = find_file("on_button.jpg")
        self.turn_off_image = find_file("off_button.jpg")
        self.alarm_on_image = find_file("Breaking-News-Emoji.gif")
        self.alarm_off_image = find_file("red_light_off.jpg")
        self.left_arrow_image = find_file("left_arrow.jpg")
        self.right_arrow_image = find_file("right_arrow.jpg")
        self._app_counter = 0
        self._message_queue = Queue()

        # States
        self._states = dict[int, S]()
        self._state_buttons = dict[int, Widget | list[Widget]]()
        self._state_watchers = dict[int, StateWatcher]()

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

            # get all target states; watch for state changes
            accs = self.get_target_states()
            for acc in accs:
                self._states[acc.tmcc_id] = acc
                self._state_watchers[acc.tmcc_id] = StateWatcher(acc, self.on_state_change_action(acc.tmcc_id))

            # start GUI
            self.start()

    # noinspection PyTypeChecker
    def update_button(self, tmcc_id: int) -> None:
        with self._cv:
            pd: S = self._states[tmcc_id]
            pb = self._state_buttons.get(tmcc_id, None)
            if pb:
                if self.is_active(pd):
                    self.set_button_active(pb)
                else:
                    self.set_button_inactive(pb)

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

    def on_state_change_action(self, tmcc_id: int) -> Callable:
        def upd():
            if not self._shutdown_flag.is_set():
                self._message_queue.put((self.update_button, [tmcc_id]))

        return upd

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

        # clear any existing state buttons
        if self._state_buttons:
            self._reset_state_buttons()

        self.box = box = Box(app, layout="grid")
        app.bg = box.bg = "white"

        # ts = self._text_size
        row_num = 0
        _ = Text(box, text=" ", grid=[0, row_num, 1, 1], size=6, height=1, bold=True)
        row_num += 1
        ats = int(round(23 * self._scale_by))
        if self._aggrigator:
            # customize label
            cb = self.aggrigator_combo = Combo(
                box,
                options=self._aggrigator.guis,
                selected=self.title,
                grid=[0, row_num],
                command=self.on_combo_change,
            )
            cb.text_size = ats
            cb.text_bold = True
            row_num += 1
        else:
            # customize label
            cb = Combo(
                box,
                options=[self.title],
                selected=self.title,
                grid=[0, row_num],
            )
            cb.text_size = ats
            cb.text_bold = True
            row_num += 1

        self._image = None
        if self.image_file:
            iw, ih = self.get_scaled_jpg_size(self.image_file)
            self._image = Picture(app, image=self.image_file, width=iw, height=ih)

        self.app.update()

        # build state buttons
        self.acc_box = acc_box = Box(self.app, border=2, align="bottom", layout="grid")
        self.build_accessory_controls(acc_box)

        # Display GUI and start event loop; call blocks
        try:
            app.display()
        except TclError:
            # If Tcl is already tearing down, ignore
            pass
        finally:
            # Explicitly drop references to tkinter/guizero objects on the Tk thread
            if self._aggrigator:
                for sw in self._state_watchers.values():
                    sw.shutdown()
                self._state_watchers.clear()
            self.aggrigator_combo = None
            self.box = None
            self.acc_box = None
            self._image = None
            self._state_buttons.clear()
            self._state_buttons = None
            self.app = None
            self._ev.set()

    # noinspection PyTypeChecker
    def register_widget(self, state: S, widget: Widget) -> None:
        with self._cv:
            if state.tmcc_id in self._state_buttons:
                if isinstance(self._state_buttons[state.tmcc_id], list):
                    self._state_buttons[state.tmcc_id].append(widget)
                else:
                    self._state_buttons[state.tmcc_id] = [self._state_buttons[state.tmcc_id], widget]
            else:
                self._state_buttons[state.tmcc_id] = widget
            widget.component_state = state
            self.update_button(state.tmcc_id)

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
        button.update_command(self.switch_state, [state])
        self.register_widget(state, button)
        return button

    def on_combo_change(self, option: str) -> None:
        if option == self.title:
            return  # Noop
        else:
            self._aggrigator.cycle_gui(option)

    # noinspection PyUnusedLocal
    def _reset_state_buttons(self) -> None:
        for pdb in self._state_buttons.values():
            if not isinstance(pdb, list):
                pdb = [pdb]
            for widget in pdb:
                if hasattr(widget, "component_state"):
                    widget.component_state = None
                if hasattr(widget, "when_left_button_pressed"):
                    widget.when_left_button_pressed = None
                if hasattr(widget, "when_left_button_released"):
                    widget.when_left_button_released = None
                widget.hide()
                widget.destroy()
        self._state_buttons.clear()

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
            self.post_process_when_pressed(pb, state)

    def when_released(self, event: EventData) -> None:
        pb = event.widget
        if pb.enabled:
            state = pb.component_state
            if state.is_asc2:
                Asc2Req(state.address, PdiCommand.ASC2_SET, Asc2Action.CONTROL1, values=0).send()
            self.post_process_when_released(pb, state)

    def post_process_when_pressed(self, button: PushButton, state: S) -> None: ...

    def post_process_when_released(self, button: PushButton, state: S) -> None: ...

    @abstractmethod
    def get_target_states(self) -> list[S]: ...

    @abstractmethod
    def is_active(self, state: S) -> bool: ...

    @abstractmethod
    def switch_state(self, state: S) -> bool: ...

    @abstractmethod
    def build_accessory_controls(self, box: Box) -> None: ...


class MomentaryActionHandler(Thread, Generic[S]):
    def __init__(self, widget: PushButton, event: Event, state: S, timeout: float) -> None:
        super().__init__(daemon=True)
        self._widget = widget
        self._ev = event
        self._state = state
        self._timeout = timeout
        self.start()

    def run(self) -> None:
        while not self._ev.wait(self._timeout):
            if not self._ev.is_set():
                print("still pressed")
            else:
                break


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
