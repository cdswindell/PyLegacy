#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
import threading


def singleton(cls):
    _instances = {}
    _lock: threading.Lock = threading.Lock()

    def wrapper(*args, **kwargs):
        with _lock:
            if cls not in _instances:
                instance = cls(*args, **kwargs)
                instance._initialized = False
                _instances[cls] = instance
            return _instances[cls]

    return wrapper
