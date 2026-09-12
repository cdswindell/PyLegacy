#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

import tkinter as tk
from tkinter import ttk

from .scroll_box import BAR_ACTIVE_COLOR, BAR_COLOR, BAR_EDGE_COLOR, BAR_EDGE_PX, BAR_TROUGH_COLOR


class TouchScrollbar(ttk.Scrollbar):
    """A vertical scrollbar with a minimum thumb length and native scrolling behavior."""

    def __init__(self, master, *, command, width: int, min_thumb_length: int):
        super().__init__(master, orient="vertical", command=command, takefocus=0)
        style = ttk.Style(self)
        name = f"Touch{self}.Vertical.TScrollbar"
        self._thumb_images = []
        for color in (BAR_COLOR, BAR_ACTIVE_COLOR):
            image = tk.PhotoImage(master=self, width=width, height=min_thumb_length)
            image.put(BAR_EDGE_COLOR, to=(0, 0, width, min_thumb_length))
            image.put(color, to=(BAR_EDGE_PX, BAR_EDGE_PX, width - BAR_EDGE_PX, min_thumb_length - BAR_EDGE_PX))
            self._thumb_images.append(image)

        # The image sets the minimum size; ttk still handles drag distances and view fractions.
        style.element_create(
            f"{name}.thumb",
            "image",
            self._thumb_images[0],
            ("pressed", self._thumb_images[1]),
            ("active", self._thumb_images[1]),
            border=BAR_EDGE_PX,
            sticky="nsew",
        )
        for part in ("trough", "uparrow", "downarrow"):
            style.element_create(f"{name}.{part}", "from", "clam", f"Scrollbar.{part}")
        style.layout(
            name,
            [
                (
                    f"{name}.trough",
                    {
                        "sticky": "nswe",
                        "children": [
                            (f"{name}.uparrow", {"side": "top", "sticky": "ew"}),
                            (f"{name}.downarrow", {"side": "bottom", "sticky": "ew"}),
                            (f"{name}.thumb", {"sticky": "nswe"}),
                        ],
                    },
                )
            ],
        )
        style.configure(
            name,
            arrowsize=width - 2 * BAR_EDGE_PX,
            background=BAR_COLOR,
            troughcolor=BAR_TROUGH_COLOR,
            bordercolor=BAR_EDGE_COLOR,
            lightcolor=BAR_COLOR,
            darkcolor=BAR_COLOR,
            arrowcolor="black",
        )
        style.map(name, background=[("pressed", BAR_ACTIVE_COLOR), ("active", BAR_ACTIVE_COLOR)])
        self.configure(style=name)
