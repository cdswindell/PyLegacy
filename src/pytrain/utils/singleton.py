#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

import threading


def singleton(cls):
    _instances = {}
    _lock: threading.Lock = threading.Lock()

    def wrapper(*args, **kwargs):
        with _lock:
            if cls not in _instances:
                instance = cls(*args, **kwargs)
                if not hasattr(instance, "_initialized"):
                    instance._initialized = False
                _instances[cls] = instance
            print(_instances)
            return _instances[cls]

    return wrapper
