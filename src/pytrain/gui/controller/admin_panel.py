#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from guizero import Box, CheckBox, PushButton, Text, TitleBox

from ...cli.pytrain import PyTrain
from ...db.state_watcher import StateWatcher
from ...protocol.constants import PROGRAM_NAME
from ...protocol.tmcc1.tmcc1_constants import TMCC1SyncCommandEnum
from ..checkbox_group import CheckBoxGroup
from ..guizero_base import GuiZeroBase
from ..hold_button import HoldButton

SCOPE_OPTS = [
    ["Local", 0],
    ["All", 1],
]


# noinspection PyUnresolvedReferences
class AdminPanel:
    def __init__(self, gui: GuiZeroBase, width: int, height: int, hold_threshold: int = 3):
        self._gui = gui
        self._width = width
        self._height = height
        self._sync_watcher = None
        self._sync_state = None
        self._reload_btn = None
        self._scope_btns = None
        self._echo_btn = None
        self._debug_btn = None
        self.hold_threshold = hold_threshold
        self._pytrain = PyTrain.current()

    # noinspection PyTypeChecker,PyUnresolvedReferences
    def build(self, body: Box):
        """Builds the 2-column grid layout for the admin popup."""
        admin_box = Box(body, border=1, align="top", layout="grid")
        admin_box.tk.config(width=self._width)

        row = 0
        # noinspection PyTypeChecker
        tb = self._titlebox(
            admin_box,
            text="Base 3 Database",
            grid=[0, row, 2, 1],
        )

        self._sync_state = pb = PushButton(
            tb,
            text="Loaded",
            grid=[0, 0],
            width=12,
            padx=self._gui.text_pad_x,
            pady=self._gui.text_pad_y,
            align="left",
        )
        pb.bg = "green" if self._gui.sync_state.is_synchronized else "white"
        pb.text_bold = True
        pb.text_size = self._gui.s_18

        self._reload_btn = pb = HoldButton(
            tb,
            text="Reload",
            grid=[1, 0],
            on_hold=(self._gui.do_tmcc_request, [TMCC1SyncCommandEnum.RESYNC]),
            width=12,
            text_bold=True,
            text_size=self._gui.s_18,
            enabled=self._gui.sync_state.is_synchronized,
            padx=self._gui.text_pad_x,
            pady=self._gui.text_pad_y,
            align="right",
            show_hold_progress=True,
            progress_fill_color="darkgrey",
            progress_empty_color="white",
        )
        self._gui.add_hover_action(pb)

        # set up sync watcher to manage button state
        self._sync_watcher = StateWatcher(self._gui.sync_state, self._on_sync_state)

        row += 1
        sp = Text(admin_box, text=" ", grid=[0, row, 2, 1], height=1, bold=True, align="top")
        sp.text_size = self._gui.s_4

        # logging & debugging
        row += 1
        tb = self._titlebox(
            admin_box,
            text="Logging & Debugging",
            grid=[0, row, 2, 1],
            width="fill",
        )

        self._echo_btn = cb = CheckBox(
            tb,
            text="Logging",
            grid=[0, 0],
            command=self._on_echo,
        )
        cb.value = 1 if self._pytrain.echo else 0
        CheckBoxGroup.decorate_checkbox(cb, self._gui.s_20, width=int(self._width / 2.3))

        self._debug_btn = cb = CheckBox(
            tb,
            text="Debugging",
            grid=[1, 0],
            command=self._on_debug,
        )
        cb.value = 1 if self._pytrain.debug else 0
        CheckBoxGroup.decorate_checkbox(cb, self._gui.s_20, width=int(self._width / 2.3))

        row += 1
        sp = Text(admin_box, text=" ", grid=[0, row, 2, 1], height=1, bold=True, align="top")
        sp.text_size = self._gui.s_4

        # scope
        row += 1
        tb = self._titlebox(
            admin_box,
            text="Scope",
            grid=[0, row, 2, 1],
        )

        sp = Text(tb, text=" ", grid=[0, 0, 2, 1], height=1, bold=True, align="top")
        sp.text_size = self._gui.s_1
        self._scope_btns = CheckBoxGroup(
            tb,
            size=self._gui.s_20,
            grid=[0, 1, 2, 1],
            options=SCOPE_OPTS,
            horizontal=True,
            align="top",
            width=int(self._width / 2.3),
            style="radio",
        )

        # admin operations
        row += 1
        tb = self._titlebox(
            admin_box,
            text=f"Hold for {self.hold_threshold} second{'s' if self.hold_threshold > 1 else ''}",
            grid=[0, row, 2, 1],
        )
        tb.text_color = "red"

        sp = Text(tb, text=" ", grid=[0, 0, 2, 1], height=1, bold=True, align="top")
        sp.text_size = self._gui.s_4

        _ = self._hold_button(
            tb,
            text="Restart",
            grid=[0, 1],
            on_hold=(self.do_admin_command, [TMCC1SyncCommandEnum.RESTART]),
        )

        _ = self._hold_button(
            tb,
            text="Reboot",
            grid=[1, 1],
            on_hold=(self.do_admin_command, [TMCC1SyncCommandEnum.REBOOT]),
        )

        sp = Text(tb, text=" ", grid=[0, 2, 2, 1], height=1, bold=True, align="top")
        sp.text_size = self._gui.s_4

        _ = self._hold_button(
            tb,
            text=f"Update {PROGRAM_NAME}",
            grid=[0, 3],
            on_hold=(self.do_admin_command, [TMCC1SyncCommandEnum.UPDATE]),
        )

        _ = self._hold_button(
            tb,
            text="Upgrade Pi OS",
            grid=[1, 3],
            on_hold=(self.do_admin_command, [TMCC1SyncCommandEnum.UPGRADE]),
        )

        sp = Text(tb, text=" ", grid=[0, 4, 2, 1], height=1, bold=True, align="top")
        sp.text_size = self._gui.s_4

        _ = self._hold_button(
            tb,
            text="Quit",
            grid=[0, 5],
            on_hold=(self.do_admin_command, [TMCC1SyncCommandEnum.QUIT]),
        )

        _ = self._hold_button(
            tb,
            text="Shutdown",
            grid=[1, 5],
            on_hold=(self.do_admin_command, [TMCC1SyncCommandEnum.SHUTDOWN]),
        )

    def _on_echo(self) -> None:
        self._pytrain.echo = bool(self._echo_btn.value)

    def _on_debug(self) -> None:
        self._pytrain.debug = bool(self._debug_btn.value)

    def do_admin_command(self, command: TMCC1SyncCommandEnum) -> None:
        if self._scope_btns.value == "0":
            self._pytrain.do_admin_cmd(command, ["me"])
        else:
            self._gui.do_tmcc_request(command)

    def _titlebox(self, parent: Box, text: str, grid: list[int] = None, **kwargs):
        is_height = "height" in kwargs
        height = kwargs.pop("height", self._gui.button_size)
        if is_height:
            tb = TitleBox(
                parent,
                text=text,
                layout="grid",  # use grid INSIDE the TitleBox
                align="top",
                grid=grid,
                width=self._width,
                height=height,
            )
            tb.tk.config(width=self._width)
        else:
            tb = TitleBox(
                parent,
                text=text,
                layout="grid",  # use grid INSIDE the TitleBox
                align="top",
                grid=grid,
            )
            tb.tk.config(width=self._width)
        tb.text_size = self._gui.s_10
        tb.tk.grid_configure(column=grid[0], row=grid[1], columnspan=grid[2], rowspan=grid[3], sticky="nsew")
        if is_height:
            tb.tk.pack_propagate(False)
        else:
            tb.tk.pack_propagate(True)
        tb.tk.grid_columnconfigure(grid[0], weight=1)
        return tb

    def _hold_button(self, parent: Box, text: str, grid: list[int], **kwargs) -> HoldButton:
        text_size = kwargs.pop("text_size", self._gui.s_18)
        width = kwargs.pop("width", 12)
        text_bold = kwargs.pop("text_bold", True)
        hold_threshold = kwargs.pop("hold_threshold", self.hold_threshold)
        hb = HoldButton(
            parent,
            text=text,
            grid=grid,
            align="left" if grid[0] % 2 == 0 else "right",
            text_size=text_size,
            width=width,
            text_bold=text_bold,
            hold_threshold=hold_threshold,
            show_hold_progress=True,
            progress_fill_color="darkgrey",
            progress_empty_color="white",
            **kwargs,
        )
        self._gui.add_hover_action(hb)
        self._gui.cache(hb)
        return hb

    def _on_sync_state(self) -> None:
        if self._gui.sync_state.is_synchronized:
            self._sync_state.text = "Loaded"
            self._sync_state.bg = "green"
            self._reload_btn.enable()
        elif self._gui.sync_state.is_synchronizing:
            self._sync_state.text = "Reloading..."
            self._sync_state.bg = "white"
            self._reload_btn.disable()

    def _decorate_checkbox(self, cb: CheckBox, size: int) -> None:
        indicator_size = int(size * 0.95)
        widget = cb.tk
        widget.config(
            font=("TkDefaultFont", size),
            padx=18,  # Horizontal padding inside each radio button
            pady=6,  # Vertical padding inside each radio button
            anchor="w",
            width=int(self._width / 2.3),
        )
        # Increase the size of the radio button indicator
        widget.tk.eval(f"""
            image create photo radio_unsel_{id(widget)} -width {indicator_size} -height {indicator_size}
            image create photo radio_sel_{id(widget)} -width {indicator_size} -height {indicator_size}
            radio_unsel_{id(widget)} put lightgray -to 0 0 {indicator_size} {indicator_size}
            radio_sel_{id(widget)} put green -to 0 0 {indicator_size} {indicator_size}
        """)
        widget.config(
            image=f"radio_unsel_{id(widget)}",
            selectimage=f"radio_sel_{id(widget)}",
            compound="left",
            indicatoron=False,
        )
