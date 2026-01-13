#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import logging
from abc import ABC, ABCMeta, abstractmethod
from queue import Empty, Queue
from threading import Condition, Event, RLock, Thread, get_ident
from tkinter import TclError
from typing import Any, Callable, cast

from guizero import App
from guizero.base import Widget

from ..comm.command_listener import CommandDispatcher
from ..db.base_state import BaseState
from ..db.component_state_store import ComponentStateStore
from ..db.state_watcher import StateWatcher
from ..gpio.gpio_handler import GpioHandler
from ..protocol.constants import PROGRAM_NAME, CommandScope

log = logging.getLogger(__name__)


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
    ) -> None:
        Thread.__init__(self, daemon=True, name=title)
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
        self._synchronized = False
        self._sync_state = self._state_store.get_state(CommandScope.SYNC, 99)
        self._sync_watcher = StateWatcher(self._sync_state, self._on_initial_sync)

    @abstractmethod
    def build_gui(self) -> None: ...

    @abstractmethod
    def destroy_gui(self) -> None: ...

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

    # noinspection PyUnresolvedReferences
    def init_complete(self) -> None:
        if self._sync_state:
            # in the event the base state is already synchronized, notify the watcher
            # so it starts the main GUI thread
            with self._sync_state.synchronizer:
                self._sync_state.synchronizer.notify_all()
        self._init_complete_flag.set()

    def _on_initial_sync(self) -> None:
        if self._sync_state.is_synchronized:
            if self._sync_watcher:
                self._sync_watcher.shutdown()
                self._sync_watcher = None
            self._synchronized = True
            self._base_state = self._state_store.get_state(CommandScope.BASE, 0, False)
            if self._base_state:
                self.title = cast(BaseState, self._base_state).base_name
            else:
                self.title = "My Layout"

            # start GUI; heavy lifting done in run()
            self._init_complete_flag.wait()
            self.start()

    def set_button_inactive(self, widget: Widget):
        widget.bg = self._disabled_bg
        widget.text_color = self._disabled_text

    # noinspection PyTypeChecker
    def set_button_active(self, widget: Widget):
        widget.bg = self._enabled_bg
        widget.text_color = self._enabled_text

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
