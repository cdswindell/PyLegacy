#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import ipaddress
import socket

from guizero import Box, CheckBox, PushButton, Text, TitleBox

from ..components.checkbox_group import CheckBoxGroup
from ..components.hold_button import HoldButton
from ..guizero_base import GuiZeroBase
from ...cli.pytrain import PyTrain
from ...db.state_watcher import StateWatcher
from ...protocol.constants import PROGRAM_NAME
from ...protocol.tmcc1.tmcc1_constants import TMCC1SyncCommandEnum
from ...utils import WiFiInfo

TEST_NET_IP = ("192.0.2.1", 80)

ADMIN_TITLE = f"Manage {PROGRAM_NAME}"

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
        self._wifi_info = WiFiInfo()
        self.hold_threshold = hold_threshold
        self._pytrain = PyTrain.current()
        self._overlay = None

    @property
    def overlay(self) -> Box:
        if self._overlay is None:
            # noinspection PyProtectedMember
            self._overlay = self._gui._popup.create_popup(ADMIN_TITLE + "\n" + self._gui.version, self.build)
        return self._overlay

    # noinspection PyTypeChecker,PyUnresolvedReferences
    def build(self, body: Box):
        """Builds the 2-column grid layout for the admin popup."""
        ssid, ip_address, strength, signal_color = self._wifi_status()
        wifi_box = TitleBox(
            body,
            text="WiFi",
            layout="grid",
            align="top",
            width=self._width,
            height=self._gui.button_size // 2,
        )
        wifi_box.tk.config(width=self._width)
        wifi_box.tk.pack_configure(fill="x", expand=False, padx=0, pady=0)
        wifi_box.tk.pack_propagate(False)
        wifi_box.text_size = self._gui.s_10
        wifi_box.tk.grid_rowconfigure(0, weight=1)
        wifi_box.tk.grid_columnconfigure(0, weight=5, uniform="wifi")
        wifi_box.tk.grid_columnconfigure(1, weight=3, uniform="wifi")
        wifi_box.tk.grid_columnconfigure(2, weight=2, uniform="wifi")

        self._wifi_text(wifi_box, grid=[0, 0], text=f"SSID: {ssid}")
        self._wifi_text(wifi_box, grid=[1, 0], text=ip_address)
        self._wifi_signal_badge(wifi_box, grid=[2, 0], text=strength, badge_color=signal_color)

        admin_box = Box(body, border=1, align="top", layout="grid")
        admin_box.tk.config(width=self._width)
        admin_box.tk.pack_configure(fill="x", expand=False, padx=0, pady=0)

        row = 0
        # noinspection PyTypeChecker
        tb = self._titlebox(
            admin_box,
            text="Base 3 Database",
            grid=[0, row, 2, 1],
            height=self._gui.button_size,
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

    def _wifi_status(self) -> tuple[str, str, str, str]:
        snapshot = self._wifi_info.query()
        quality = snapshot.quality
        ssid = self._truncate(snapshot.ssid or "Unavailable", 14)
        if quality is None and snapshot.signal_dbm is not None:
            quality = WiFiInfo.dbm_to_quality(snapshot.signal_dbm)
        strength = f"{quality}%" if quality is not None else "N/A"
        ip_address = self._current_ip_address()
        return ssid, ip_address, strength, self._signal_color(quality)

    def _wifi_text(self, parent: Box, grid: list[int], text: str) -> Text:
        field = Text(
            parent,
            text=text,
            grid=grid,
            align="left",
            bold=True,
            size=self._gui.s_12,
        )
        field.tk.configure(anchor="w")
        field.tk.grid_configure(sticky="ew", padx=0, pady=(2, 4))
        return field

    def _wifi_signal_badge(self, parent: Box, grid: list[int], text: str, badge_color: str) -> Text:
        badge = Text(
            parent,
            text=text,
            grid=grid,
            align="left",
            bold=True,
            size=self._gui.s_12,
            width=max(6, len(text) + 1),
        )
        badge.bg = badge_color
        badge.text_color = self._signal_text_color(badge_color)
        badge.tk.configure(anchor="center", padx=8, pady=3, borderwidth=1, relief="flat")
        badge.tk.grid_configure(sticky="e", padx=0, pady=(1, 5))
        return badge

    @staticmethod
    def _current_ip_address() -> str:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.connect(TEST_NET_IP)
                ip = sock.getsockname()[0]
            finally:
                sock.close()

            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_loopback or ip_obj.is_link_local or ip == "0.0.0.0":
                return "Unavailable"
            return ip
        except OSError:
            return "Unavailable"

    @staticmethod
    def _signal_color(quality: int | None) -> str:
        if quality is None:
            return "dim gray"
        quality = max(0, min(100, quality))
        red = int(round(255 * (100 - quality) / 100))
        green = int(round(255 * quality / 100))
        return f"#{red:02x}{green:02x}00"

    @staticmethod
    def _signal_text_color(color: str) -> str:
        if not color.startswith("#") or len(color) != 7:
            return "white"
        red = int(color[1:3], 16)
        green = int(color[3:5], 16)
        blue = int(color[5:7], 16)
        luminance = (0.299 * red) + (0.587 * green) + (0.114 * blue)
        return "black" if luminance >= 140 else "white"

    @staticmethod
    def _truncate(value: str, max_len: int) -> str:
        if len(value) <= max_len:
            return value
        if max_len <= 3:
            return value[:max_len]
        return value[: max_len - 3] + "..."

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
