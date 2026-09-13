#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import logging
import tkinter as tk
from importlib.resources import as_file, files
from tkinter import simpledialog

from guizero import App

from . import images

log = logging.getLogger(__name__)


def load_pycab_icon(master, *, large: bool = False) -> tk.PhotoImage | None:
    name = f"en-US_pycab_{'large' if large else 'small'}.png"
    try:
        with as_file(files(images).joinpath(name)) as path:
            return tk.PhotoImage(master=master, file=str(path))
    except (OSError, tk.TclError) as exc:
        log.warning("Unable to load PyCab icon %s: %s", name, exc)
        return None


def add_pycab_logo(master) -> tk.Label | None:
    image = load_pycab_icon(master)
    if image is None:
        return None
    label = tk.Label(master, image=image)
    label.image = image  # Tk does not retain the Python photo object.
    label.pack(side="left", padx=16, pady=8)
    return label


class ConfirmationDialog(simpledialog.Dialog):
    """A modal confirmation with PyCab artwork, independent of native alert icons."""

    def __init__(self, parent, title: str, message: str) -> None:
        self._message = message
        self._yes_btn: tk.Button | None = None
        super().__init__(parent, title)

    def body(self, master):
        self.resizable(False, False)
        add_pycab_logo(master)
        tk.Label(master, text=self._message, wraplength=360, justify="left").pack(
            side="left", fill="both", expand=True, padx=12, pady=16
        )

    def buttonbox(self):
        row = tk.Frame(self)
        row.pack(fill="x", padx=12, pady=(0, 12))
        no_btn = tk.Button(row, text="No", command=self.cancel, width=10, height=2, default="active")
        self._yes_btn = tk.Button(row, text="Yes", command=self.ok, width=10, height=2)
        for button in (no_btn, self._yes_btn):
            button.pack(side="left", fill="x", expand=True, padx=6)
        self.initial_focus = no_btn
        self.bind("<Return>", self._on_return)
        self.bind("<Escape>", self.cancel)

    def _on_return(self, _event=None):
        if self.focus_get() is self._yes_btn:
            self.ok()
        else:
            self.cancel()

    def apply(self):
        self.result = True


class PyCabApp(App):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._pycab_icons = tuple(
            image for image in (load_pycab_icon(self.tk, large=True), load_pycab_icon(self.tk)) if image is not None
        )
        if self._pycab_icons:
            try:
                self.tk.iconphoto(True, *self._pycab_icons)
            except tk.TclError as exc:
                log.warning("Unable to set PyCab window icon: %s", exc)

    def yesno(self, title, text) -> bool:
        # Native message boxes only accept stock icons; window icons are not enough.
        return bool(ConfirmationDialog(self.tk, title, text).result)
