#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from guizero import ButtonGroup


class CheckBoxGroup(ButtonGroup):
    def __init__(
        self,
        master,
        size: int = 22,
        scale_by: float = 1.5,
        **kwargs,
    ):
        # now initialize parent class
        padx = kwargs.pop("padx", 18)
        pady = kwargs.pop("pady", 6)
        super().__init__(master, **kwargs)

        indicator_size = int(size * scale_by)
        for widget in self.tk.winfo_children():
            widget.config(
                font=("TkDefaultFont", size),
                padx=padx,  # Horizontal padding inside each radio button
                pady=pady,  # Vertical padding inside each radio button
                anchor="w",
            )
            # Increase the size of the radio button indicator
            widget.tk.eval(f"""
                image create photo radio_unsel_{id(widget)} -width {indicator_size} -height {indicator_size}
                image create photo radio_sel_{id(widget)} -width {indicator_size} -height {indicator_size}
                radio_unsel_{id(widget)} put white -to 0 0 {indicator_size} {indicator_size}
                radio_sel_{id(widget)} put green -to 0 0 {indicator_size} {indicator_size}
            """)
            widget.config(
                image=f"radio_unsel_{id(widget)}",
                selectimage=f"radio_sel_{id(widget)}",
                compound="left",
                indicatoron=False,
            )
