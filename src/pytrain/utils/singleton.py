#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#


from functools import wraps
from threading import Lock


def singleton(cls):
    instances = {}
    lock = Lock()

    @wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            with lock:
                if cls not in instances:
                    instance = cls(*args, **kwargs)
                    if not hasattr(instance, "_initialized"):
                        instance._initialized = False
                    instances[cls] = instance
        return instances[cls]

    return get_instance
