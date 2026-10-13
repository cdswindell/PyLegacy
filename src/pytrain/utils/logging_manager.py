# Process-aware, explicit initialization of PyTrain's application logging.
#
# SPDX-License-Identifier: LGPL-3.0-only

import logging
import os
from threading import RLock

from .dual_logging import set_up_logging


class _OwnerProcessFilter(logging.Filter):
    """Never let a forked worker write through an inherited file descriptor."""

    def __init__(self, pid: int) -> None:
        super().__init__()
        self.pid = pid

    def filter(self, record: logging.LogRecord) -> bool:
        return os.getpid() == self.pid


class LoggingManager:
    """Own the application's console and rotating-file handlers per process."""

    _lock = RLock()
    _pid: int | None = None
    _handlers: tuple[logging.Handler, ...] = ()

    @classmethod
    def initialize(cls, **kwargs) -> bool:
        with cls._lock:
            pid = os.getpid()
            root = logging.getLogger()
            if cls._pid == pid and cls._handlers and all(handler in root.handlers for handler in cls._handlers):
                return True

            if cls._pid is not None and cls._pid != pid:
                # A forked child inherited the parent's handlers. Close only
                # the child's copies; the parent retains its own descriptors.
                for handler in cls._handlers:
                    root.removeHandler(handler)
                    handler.close()
                cls._handlers = ()
                cls._pid = None

            before = tuple(root.handlers)
            if not set_up_logging(**kwargs):
                # set_up_logging may have installed a console handler before a
                # file setup error. Do not leave partially configured handlers.
                for handler in tuple(root.handlers):
                    if handler not in before:
                        root.removeHandler(handler)
                        handler.close()
                return False

            cls._handlers = tuple(handler for handler in root.handlers if handler not in before)
            owner_filter = _OwnerProcessFilter(pid)
            for handler in cls._handlers:
                handler.addFilter(owner_filter)
            cls._pid = pid
            return True

    @classmethod
    def is_initialized(cls) -> bool:
        with cls._lock:
            return (
                cls._pid == os.getpid()
                and bool(cls._handlers)
                and all(handler in logging.getLogger().handlers for handler in cls._handlers)
            )
