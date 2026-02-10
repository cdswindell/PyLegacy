#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import atexit
import io
import logging
from abc import ABC, ABCMeta, abstractmethod
from concurrent.futures import Future, ThreadPoolExecutor
from io import BytesIO
from queue import Empty, Queue
from threading import Condition, Event, RLock, Thread, get_ident
from tkinter import TclError
from typing import Any, Callable, TypeVar

# noinspection PyPackageRequirements
from PIL import Image, ImageOps, ImageTk
from guizero import App, Box
from guizero.base import Widget

from ..comm.command_listener import CommandDispatcher
from ..db.base_state import BaseState
from ..db.component_state_store import ComponentStateStore
from ..db.prod_info import ProdInfo
from ..db.state_watcher import StateWatcher
from ..db.sync_state import SyncState
from ..gpio.gpio_handler import GpioHandler
from ..protocol.command_def import CommandDefEnum
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope, PROGRAM_NAME

log = logging.getLogger(__name__)
E = TypeVar("E", bound=CommandDefEnum)
LIONEL_ORANGE = "#FF6600"
LIONEL_BLUE = "#003366"


class GuiZeroBase(Thread, ABC):
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(
        self,
        title: str = f"{PROGRAM_NAME} GUI",
        width: int = None,
        height: int = None,
        enabled_bg: str = "green",
        disabled_bg: str = "white",
        enabled_text: str = "black",
        disabled_text: str = "lightgrey",
        active_bg: str = "green",
        inactive_bg: str = "white",
        scale_by: float = 1.5,
        repeat: int = 2,
        stand_alone: bool = True,  # if True, launch GUI, if False, being called by another GUI
    ) -> None:
        Thread.__init__(self, daemon=True, name=title)
        self._cv = Condition(RLock())
        self._ev = Event()
        self._stand_alone = stand_alone
        # Determines screen dimensions when width/height unspecified
        if stand_alone and (width is None or height is None):
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
        self._scale_by = scale_by
        self.repeat = repeat

        # standard colors
        self._enabled_bg = enabled_bg
        self._disabled_bg = disabled_bg
        self._enabled_text = enabled_text
        self._disabled_text = disabled_text
        self._active_bg = active_bg
        self._inactive_bg = inactive_bg

        # font sizes
        self.s_72 = self.scale(72, 0.7)
        self.s_30: int = int(round(30 * scale_by))
        self.s_24: int = int(round(24 * scale_by))
        self.s_22: int = int(round(22 * scale_by))
        self.s_20: int = int(round(20 * scale_by))
        self.s_18: int = int(round(18 * scale_by))
        self.s_16: int = int(round(16 * scale_by))
        self.s_14: int = int(round(14 * scale_by))
        self.s_12: int = int(round(12 * scale_by))
        self.s_10: int = int(round(10 * scale_by))
        self.s_8: int = int(round(8 * scale_by))
        self.s_6: int = int(round(6 * scale_by))
        self.s_4: int = int(round(4 * scale_by))
        self.s_2: int = int(round(2 * scale_by))
        self.s_1: int = int(round(1 * scale_by))

        self.text_pad_x = 20
        self.text_pad_y = 20

        # standard widget sizes
        self.button_size = int(round(self.width / 6))
        self.titled_button_size = int(round((self.width / 6) * 0.80))

        # prod info support
        self._prod_info_cache = {}
        self._pending_prod_infos = set()
        self._executor = ThreadPoolExecutor(max_workers=3)

        # widget_cache
        self._elements = set()

        # cache for widget size info
        self.size_cache = {}

        # image cache
        self._image_cache = {}

        # queue task for gui main thread
        self.app = None
        self._app_counter = 0
        self._message_queue = Queue()

        # Thread-aware shutdown signaling
        self._tk_thread_id: int | None = None
        self._is_closed = False
        self._init_complete_flag = Event()
        self._shutdown_flag = Event()

        # listen for state changes
        self._dispatcher = CommandDispatcher.get()
        self._state_store = ComponentStateStore.get()
        if stand_alone:
            self._synchronized = False
            self._sync_state = self._state_store.get_state(CommandScope.SYNC, 99)
            self._sync_watcher = StateWatcher(self._sync_state, self._on_initial_sync)
        else:
            self._synchronized = self._sync_state = self._sync_watcher = None
        atexit.register(lambda: self._shutdown_flag.set())

    @abstractmethod
    def build_gui(self) -> None: ...

    @abstractmethod
    def destroy_gui(self) -> None: ...

    @abstractmethod
    def calc_image_box_size(self) -> tuple[int, int | Any]: ...

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

    @property
    def version(self) -> str:
        return self._dispatcher.version

    @property
    def sync_state(self) -> SyncState:
        return self._sync_state

    @property
    def state_store(self) -> ComponentStateStore:
        return self._state_store

    def cache(self, *widgets: Widget | Box) -> None:
        if not widgets:
            return
        for widget in widgets:
            self._elements.add(widget)

    # noinspection PyUnresolvedReferences
    def init_complete(self) -> None:
        if isinstance(self._sync_state, SyncState):
            # in the event the base state is already synchronized, notify the watcher
            # so it starts the main GUI thread
            with self._sync_state.synchronizer:
                self._sync_state.synchronizer.notify_all()
        self._init_complete_flag.set()

    def _on_initial_sync(self) -> None:
        """Handles initial synchronization; starts GUI thread"""
        if self._sync_state.is_synchronized:
            if self._sync_watcher:
                self._sync_watcher.shutdown()
                self._sync_watcher = None
            self._synchronized = True
            self._base_state = self._state_store.get_state(CommandScope.BASE, 0, False)
            if isinstance(self._base_state, BaseState):
                self.title = self._base_state.base_name
            else:
                self.title = "My Layout"

            # start GUI; heavy lifting done in run()
            self._init_complete_flag.wait()
            self.start()

    def queue_message(self, message: Callable, *args: Any) -> None:
        self._message_queue.put((message, args))

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
                # Process pending messages in the queue
                try:
                    message = self._message_queue.get_nowait()
                    if isinstance(message, tuple):
                        if message[1] and len(message[1]) > 0:
                            message[0](*message[1])
                        else:
                            message[0]()
                        # app.tk.update_idletasks()
                except Empty:
                    pass
            return None

        self.build_gui()

        # start the event watcher; look for shutdown and requests from other threads
        app.repeat(20, _poll_shutdown)

        # Display GUI and start event loop; call blocks
        try:
            app.display()
        except TclError:
            # If Tcl is already tearing down, ignore
            pass
        finally:
            self.destroy_gui()
            self.app = None
            self._ev.set()

    @staticmethod
    def do_tmcc_request(command: E, address: int = None, data: int = None, scope: CommandScope = None) -> None:
        try:
            req = CommandReq.build(command, address, data, scope)
            if req:
                req.send()
        except Exception as e:
            log.exception(f"Error sending command {command}", exc_info=e)

    def scale(self, value: int, factor: float = None) -> int:
        orig_value = value
        value = max(orig_value, int(value * self.width / 480))
        if factor is not None and self.width > 480:
            value = max(orig_value, int(factor * value))
        return value

    def set_button_inactive(self, widget: Widget):
        widget.bg = self._disabled_bg
        widget.text_color = self._disabled_text

    # noinspection PyTypeChecker
    def set_button_active(self, widget: Widget):
        widget.bg = self._enabled_bg
        widget.text_color = self._enabled_text

    @staticmethod
    def add_hover_action(btn: Widget, hover_color: str = "#e0e0e0", background: str = "#f7f7f7") -> None:
        btn.tk.config(
            borderwidth=3,
            relief="raised",
            highlightthickness=1,
            highlightbackground="black",
            activebackground=hover_color,
            background=background,
        )

    def sizeof(self, widget: Widget) -> tuple[int, int]:
        return self.size_cache.get(widget, None) or (widget.tk.winfo_reqwidth(), widget.tk.winfo_reqheight())

    # Example lazy loader pattern for images
    def get_scaled_image(
        self,
        source: str | io.BytesIO,
        preserve_height: bool = False,
        force_lionel: bool = False,
    ) -> ImageTk.PhotoImage:
        pil_img = Image.open(source)
        orig_width, orig_height = pil_img.size
        scaled_width, scaled_height = self._calc_scaled_image_size(
            orig_width, orig_height, preserve_height, force_lionel
        )
        img = ImageTk.PhotoImage(pil_img.resize((scaled_width, scaled_height)))
        return img

    def get_image(
        self,
        path,
        size=None,
        inverse: bool = True,
        scale: bool = False,
        preserve_height: bool = False,
    ):
        if path not in self._image_cache:
            img = None
            if scale:
                normal_tk = self.get_scaled_image(path, preserve_height=preserve_height)
            else:
                img = Image.open(path)
                if size:
                    img = img.resize(size)
                normal_tk = ImageTk.PhotoImage(img)
            if inverse and img:
                inverted = ImageOps.invert(img.convert("RGB"))
                inverted.putalpha(img.split()[-1])
                inverted_tk = ImageTk.PhotoImage(inverted)
                self._image_cache[path] = (normal_tk, inverted_tk)
            else:
                self._image_cache[path] = normal_tk
        return self._image_cache[path]

    def get_titled_image(self, path):
        return self.get_image(path, size=(self.titled_button_size, self.titled_button_size))

    def _calc_scaled_image_size(
        self,
        orig_width: int,
        orig_height: int,
        preserve_height: bool = False,
        force_lionel: bool = False,
    ) -> tuple[int, int]:
        available_height, available_width = self.calc_image_box_size()
        if force_lionel:
            scaled_width, scaled_height = self._calc_scaled_image_size(300, 100)
        else:
            # Calculate scaling to fit available space
            width_scale = available_width / orig_width
            height_scale = available_height / orig_height
            scale = min(width_scale, height_scale)
            if preserve_height:
                scaled_width = int(orig_width * scale)
                scaled_height = int(orig_height * height_scale)
            else:
                scaled_width = int(orig_width * width_scale)
                scaled_height = int(orig_height * scale)
        return scaled_width, scaled_height

    def _request_prod_info(self, bt_id: str) -> ProdInfo | None:
        prod_info = "N/A"
        if bt_id:
            try:
                prod_info = ProdInfo.by_btid(bt_id)
                log.debug(f"ProdInfo.by_btid returned {prod_info}")
            except ValueError as ve:
                state = self._state_store.by_bluetooth_id(int(bt_id, 16))
                if state:
                    log.info(f"Product info for engine {state.address} ({bt_id}) is unavailable: {ve}")
                else:
                    log.info(f"Product info for engine btid: {bt_id} is unavailable: {ve}")
            except Exception as e:
                log.exception(e, exc_info=e)
        return prod_info

    def _fetch_prod_info(self, bt_id: str, callback: Callable, tmcc_id: int) -> ProdInfo | None:
        """Fetch product info in a background thread, then schedule UI update."""
        prod_info = None
        do_request_prod_info = False
        with self._cv:
            if tmcc_id not in self._pending_prod_infos:
                self._pending_prod_infos.add(tmcc_id)
                do_request_prod_info = True  # don't hold lock for long
        if do_request_prod_info:
            prod_info = self._request_prod_info(bt_id)
            self._prod_info_cache[tmcc_id] = prod_info
            self._pending_prod_infos.discard(tmcc_id)
            # now get image
            if isinstance(prod_info, ProdInfo):
                img = self.get_scaled_image(BytesIO(prod_info.image_content))
                self._image_cache[(CommandScope.ENGINE, tmcc_id)] = img
        # Schedule the UI update on the main thread
        log.debug(f"get_prod_info: Scheduling UI update for tmcc_id {tmcc_id}")
        self.queue_message(callback, tmcc_id)
        return prod_info

    def get_prod_info(self, bt_id: str, callback: Callable, tmcc_id: int) -> ProdInfo | None:
        prod_info = self._prod_info_cache.get(tmcc_id, None)
        # Attempts to retrieve or schedule production info
        if prod_info is None and bt_id:
            if tmcc_id not in self._pending_prod_infos:
                future = self._executor.submit(self._fetch_prod_info, bt_id, callback, tmcc_id)
                self._prod_info_cache[tmcc_id] = future
        elif isinstance(prod_info, Future) and prod_info.done() and isinstance(prod_info.result(), ProdInfo):
            prod_info = self._prod_info_cache[tmcc_id] = prod_info.result()
            self._pending_prod_infos.discard(tmcc_id)
        elif isinstance(prod_info, ProdInfo):
            pass
        else:
            prod_info = "N/A"
            if bt_id is None:
                self._prod_info_cache[tmcc_id] = prod_info
        return prod_info
