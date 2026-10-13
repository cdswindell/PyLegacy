# Process-aware, explicit initialization of PyTrain's application logging.
#
# SPDX-License-Identifier: LGPL-3.0-only

import logging
import os
from threading import RLock

from .dual_logging import set_up_logging


class LoggingManager:
    """Own application logging in the process that explicitly starts PyTrain.

    A forked worker must not rotate the parent's log. Spawn/forkserver workers
    that import PyTrain never initialize logging just by importing modules.
    """

    _lock = RLock()
    _pid: int | None = None
    _handlers: tuple[logging.Handler, ...] = ()

    @classmethod
    def initialize(cls, **kwargs) -> bool:
        with cls._lock:
            pid = os.getpid()
            root = logging.getLogger()
            if cls._pid == pid and cls._handlers and all(
                handler in root.handlers for handler in cls._handlers
            ):
                return True

            # After fork, the child inherits file descriptors and handler
            # objects. Detach inherited application handlers without rotating.
            if cls._pid is not None and cls._pid != pid:
                for handler in cls._handlers:
                    root.removeHandler(handler)
                cls._handlers = ()
                cls._pid = None

            before = tuple(root.handlers)
            if not set_up_logging(**kwargs):
                return False
            cls._handlers = tuple(handler for handler in root.handlers if handler not in before)
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
