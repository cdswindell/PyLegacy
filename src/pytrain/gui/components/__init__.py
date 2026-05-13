#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

__all__ = ["EditableText"]


def __getattr__(name: str):
    if name == "EditableText":
        from .editable_text import EditableText

        return EditableText
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
