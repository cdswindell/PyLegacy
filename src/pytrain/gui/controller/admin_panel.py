#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
import ipaddress
import logging
import socket
from threading import Thread
from typing import TYPE_CHECKING

import psutil
from guizero import Box, CheckBox, PushButton, Text, TitleBox

from ...cli.pytrain import PyTrain
from ...db.state_watcher import StateWatcher
from ...protocol.constants import PROGRAM_NAME
from ...protocol.tmcc1.tmcc1_constants import TMCC1SyncCommandEnum
from ...utils import WiFiInfo
from ...utils.host_info import is_steam_deck
from ..components.checkbox_group import CheckBoxGroup
from ..components.hold_button import HoldButton
from .overlay_panel import OverlayPanel

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui

log = logging.getLogger(__name__)

TEST_NET_IP = ("192.0.2.1", 80)

ADMIN_TITLE = f"Manage {PROGRAM_NAME}"

SCOPE_OPTS = [
    ["Local", 0],
    ["All", 1],
]


# noinspection PyUnresolvedReferences
class AdminPanel(OverlayPanel):
    """The manage-PyTrain popup.

    An OverlayPanel rather than a plain callable body because ``create_popup`` only
    builds a footer (and so only puts anything to the left of Close) for panels of that
    type -- see PopupManager.create_popup.
    """

    def __init__(self, gui: "EngineGui", width: int, height: int, hold_threshold: int = 3):
        self._scope_radio_buttons = None
        self._scope_var = None
        # Set before super().__init__ because the title it is handed (popup_title) reads
        # self._gui.version. The base class assigns it again, to the same object.
        self._gui = gui
        self._width = width
        self._height = height
        self._compact = bool(getattr(gui, "compact", False))
        self._sync_watcher = None
        self._sync_state = None
        self._reload_btn = None
        self._scope_btns = None
        self._echo_btn = None
        self._debug_btn = None
        self._accs_btn = None
        self._imgs_btn = None
        self._wifi_box = None
        self._wifi_info = WiFiInfo()
        self._wifi_ssid = None
        self._wifi_ip = None
        self._wifi_signal = None
        self._wifi_refresh_after_id = None
        self._needs_scope_fix = True
        # Admin action buttons by TMCC1SyncCommandEnum name, so synthetic input can
        # drive the real widget (see ``begin_hold``).
        self._admin_buttons: dict[str, HoldButton] = {}
        self.hold_threshold = hold_threshold
        self._pytrain = PyTrain.current()
        # Sets _gui, _overlay and the post-close hook the base class owns. Deferred to
        # the end so the title, which reads self._compact, is computed after it is set.
        super().__init__(gui, self.popup_title, post_close=self._on_popup_close)

    @property
    def compact_control_height(self) -> int:
        return max(52, int(self._gui.button_size * 0.55))

    @property
    def compact_control_width(self) -> int:
        return int(self._width / 2.1)

    @property
    def compact_title_allowance(self) -> int:
        return 20

    @property
    def compact_section_height(self) -> int:
        return self.compact_control_height + self.compact_title_allowance

    @property
    def compact_network_height(self) -> int:
        return int(self.compact_section_height / 1.6)

    @property
    def scope_grid(self) -> list[int]:
        return [0, 0, 3, 1] if self._compact else [0, 0]

    @property
    def compact_admin_actions_height(self) -> int:
        return 3 * self.compact_control_height + self.compact_title_allowance

    @property
    def compact_database_height(self) -> int:
        return self.compact_section_height if self._compact else self._gui.button_size

    @property
    def admin_action_rows(self) -> tuple[int, int, int]:
        return (0, 1, 2) if self._compact else (0, 2, 4)

    @property
    def admin_action_columns(self) -> tuple[int, int]:
        return (0, 2) if self._compact else (0, 1)

    @property
    def popup_title(self) -> str:
        if not self._compact:
            return ADMIN_TITLE + "\n" + self._gui.version
        return self._gui.version

    @property
    def visible(self) -> bool:
        """True when this panel's overlay is built and on screen."""
        return bool(self._overlay is not None and self._overlay.visible)

    @property
    def os_upgrade_supported(self) -> bool:
        """False on the Steam Deck, where SteamOS updates itself.

        The upgrade action drives apt and rpi-eeprom-update, which are a Raspberry Pi
        story; ``PyTrain.upgrade()`` gates only on ``sys.platform == "linux"``, which
        the Deck satisfies. Disabling the button keeps that path unreachable from the
        Deck's admin panel.
        """
        return not is_steam_deck()

    def _admin_hold_button(self, parent, enabled: bool = True, **kwargs) -> HoldButton:
        # Create an admin action button and remember it by command name, so synthetic
        # input (a controller chord) can drive the very same widget rather than
        # duplicating its hold timing and progress feedback.
        button = self._hold_button(parent, **kwargs)
        command = kwargs["on_hold"][1][0]
        if not enabled:
            # HoldButton checks `enabled` before starting a hold, so greying it out is
            # enough to stop a finger. Leaving it out of the registry is what stops a
            # controller chord: begin_hold() then reports no hold started rather than
            # claiming one on a widget that will never fire.
            button.disable()
            return button
        self._admin_buttons[command.name] = button
        return button

    def begin_hold(self, command: str) -> bool:
        """Start the hold on an admin button as if a finger had pressed it.

        The button animates its hold progress and fires its own ``on_hold`` after
        ``hold_threshold`` seconds, so a controller chord gets identical timing and
        identical on-screen feedback. Returns whether a hold was started.
        """
        button = self._admin_buttons.get(command)
        if button is None or not self.visible:
            return False
        button.begin_hold()
        return True

    def cancel_hold(self, command: str) -> bool:
        """Abandon a hold started by :meth:`begin_hold` before it completes."""
        button = self._admin_buttons.get(command)
        if button is None:
            return False
        button.cancel_hold()
        return True

    @property
    def overlay(self) -> Box:
        # OverlayPanel builds it on first access, passing self -- which is what selects
        # create_popup's footer path. Everything below is this panel's own per-show
        # refresh, which the base class knows nothing about.
        overlay = super().overlay
        self._refresh_wifi_display()
        self._ensure_wifi_refresh()
        if self._needs_scope_fix:
            self._needs_scope_fix = False
            self._scope_btns.hide()
            self._scope_btns.show()
        return overlay

    # noinspection PyTypeChecker,PyUnresolvedReferences
    def build(self, body: Box):
        """Builds the 2-column grid layout for the admin popup."""
        width = int(self._width * 0.98)
        self._wifi_box = wifi_box = TitleBox(
            body,
            text="Network",
            layout="grid",
            align="top",
            width=width,
            height=self.compact_network_height if self._compact else int(7 * self._gui.button_size / 12),
        )
        wifi_box.tk.config(width=self._width)
        wifi_box.tk.pack_configure(fill="x", expand=False, padx=0, pady=0)
        wifi_box.tk.pack_propagate(False)
        wifi_box.text_size = self._gui.s_10
        wifi_box.tk.grid_rowconfigure(0, weight=1)
        wifi_box.tk.grid_columnconfigure(0, weight=1)
        wifi_box.tk.grid_columnconfigure(1, weight=0)
        wifi_box.tk.grid_columnconfigure(2, weight=1)

        self._wifi_ssid = self._wifi_text(wifi_box, grid=[0, 0], text="", anchor="w", sticky="w")
        self._wifi_ip = self._wifi_text(wifi_box, grid=[1, 0], text="", anchor="center")
        self._wifi_signal = self._wifi_signal_badge(wifi_box, grid=[2, 0], text="N/A", badge_color="dim gray")
        self._refresh_wifi_display()
        if not self._compact:
            sp = Text(wifi_box, text=" ", grid=[0, 1, 3, 1], height=1, align="bottom")
            sp.text_size = self._gui.s_1
            sp.tk.config(padx=0, pady=0)
            sp.tk.grid_configure(sticky="nse", padx=0, pady=0)

        if not self._compact:
            sp = Text(body, text=" ", height=1, bold=True, align="top")
            sp.text_size = self._gui.s_1

        admin_box = Box(body, border=1, align="top", layout="grid")
        admin_box.tk.config(width=self._width)

        # make admin_box column expand
        admin_box.tk.grid_columnconfigure(0, weight=1)
        admin_box.tk.grid_columnconfigure(1, weight=1)
        admin_box.tk.pack_configure(fill="x", expand=False, padx=2, pady=0)

        row = 0
        # noinspection PyTypeChecker
        tb = self._titlebox(
            admin_box,
            text="Base 3 Database",
            grid=[0, row, 2, 1],
            width=width,
            height=self.compact_database_height,
        )

        self._sync_state = pb = PushButton(
            tb,
            text="Loaded",
            grid=[0, 0],
            width=self._gui.rescale_by(12),
            align="left",
        )
        pb.bg = "green" if self._gui.sync_state.is_synchronized() else "white"
        pb.text_bold = True
        pb.text_size = self._gui.s_18
        self._fit_compact_control(pb)

        self.spacer(tb, grid=[1, 0])
        self._reload_btn = pb = HoldButton(
            tb,
            text="Reload",
            grid=[2, 0],
            on_hold=(self._gui.do_tmcc_request, [TMCC1SyncCommandEnum.RESYNC]),
            width=self._gui.rescale_by(12),
            text_bold=True,
            text_size=self._gui.s_18,
            enabled=self._gui.sync_state.is_synchronized(),
            align="right",
            show_hold_progress=True,
            progress_fill_color="darkgrey",
            progress_empty_color="white",
        )
        self._fit_compact_control(pb)
        self._gui.add_hover_action(pb)

        # set up sync watcher to manage button state
        self._sync_watcher = StateWatcher(self._gui.sync_state, self._on_sync_state)

        # Reload/Reset
        row += 1
        tb = self._titlebox(
            admin_box,
            text="Reload/Refresh",
            grid=[0, row, 2, 1],
            width="fill",
        )

        self._accs_btn = pb = HoldButton(
            tb,
            text="Accessories",
            grid=[0, 0],
            width=self._gui.rescale_by(12),
            text_bold=True,
            text_size=self._gui.s_18,
            align="left",
            command=self._gui.reload_configured_accessories,
        )
        self._fit_compact_control(pb)
        self._gui.add_hover_action(pb)

        self.spacer(tb, grid=[1, 0])
        self._imgs_btn = pb = HoldButton(
            tb,
            text="Images",
            grid=[2, 0],
            width=self._gui.rescale_by(12),
            text_bold=True,
            text_size=self._gui.s_18,
            align="right",
            command=self._gui.image_presenter.clear_caches,
        )
        self._fit_compact_control(pb)
        self._gui.add_hover_action(pb)

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
        CheckBoxGroup.decorate_checkbox(cb, self._gui.s_20, width=int(self._width / 2.48))
        self._fit_compact_control(cb, image_backed=True)

        self.spacer(tb, grid=[1, 0])
        self._debug_btn = cb = CheckBox(
            tb,
            text="Debugging",
            grid=[2, 0],
            command=self._on_debug,
        )
        cb.value = 1 if self._pytrain.debug else 0
        CheckBoxGroup.decorate_checkbox(cb, self._gui.s_20, width=int(self._width / 2.48))
        self._fit_compact_control(cb, image_backed=True)
        if self._pytrain.echo:
            cb.enable()
        else:
            cb.disable()

        # scope
        row += 1
        tb = self._titlebox(
            admin_box,
            text="Scope",
            grid=[0, row, 2, 1],
            width=width,
        )

        self._scope_btns = CheckBoxGroup(
            tb,
            size=self._gui.s_20,
            grid=self.scope_grid,
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
            **({"height": self.compact_admin_actions_height} if self._compact else {}),
        )
        tb.text_color = "red"

        restart_row, update_row, quit_row = self.admin_action_rows
        left_col, right_col = self.admin_action_columns
        if self._compact:
            self.spacer(tb, grid=[1, 0, 1, 3])
            for action_row in self.admin_action_rows:
                tb.tk.grid_rowconfigure(
                    action_row,
                    weight=0,
                    minsize=self.compact_control_height,
                    uniform="admin_actions",
                )
        self._admin_hold_button(
            tb,
            text="Restart",
            grid=[left_col, restart_row],
            on_hold=(self.do_admin_command, [TMCC1SyncCommandEnum.RESTART]),
        )

        self._admin_hold_button(
            tb,
            text="Reboot",
            grid=[right_col, restart_row],
            on_hold=(self.do_admin_command, [TMCC1SyncCommandEnum.REBOOT]),
        )

        if not self._compact:
            sp = Text(tb, text=" ", grid=[0, 1, 2, 1], height=1, bold=True, align="top")
            sp.text_size = self._gui.s_2

        self._admin_hold_button(
            tb,
            text=f"Update {PROGRAM_NAME}",
            grid=[left_col, update_row],
            on_hold=(self.do_admin_command, [TMCC1SyncCommandEnum.UPDATE]),
        )

        self._admin_hold_button(
            tb,
            text="Upgrade Pi OS",
            grid=[right_col, update_row],
            on_hold=(self.do_admin_command, [TMCC1SyncCommandEnum.UPGRADE]),
            enabled=self.os_upgrade_supported,
        )

        if not self._compact:
            sp = Text(tb, text=" ", grid=[0, 3, 2, 1], height=1, bold=True, align="top")
            sp.text_size = self._gui.s_2

        self._admin_hold_button(
            tb,
            text="Quit",
            grid=[left_col, quit_row],
            on_hold=(self.do_admin_command, [TMCC1SyncCommandEnum.QUIT]),
        )

        self._admin_hold_button(
            tb,
            text="Shutdown",
            grid=[right_col, quit_row],
            on_hold=(self.do_admin_command, [TMCC1SyncCommandEnum.SHUTDOWN]),
        )

    @property
    def controls_available(self) -> bool:
        """Whether there are controller bindings worth showing a help screen for.

        A portrait EngineGui runs stand-alone with no hosting SteamDeckGui, so it has no
        profile and the screen would have nothing to describe. Keyed off the profile
        rather than the platform so the button appears exactly when it leads somewhere.
        """
        return self._gui.controller_profile is not None

    @property
    def has_footer(self) -> bool:
        # False rather than an empty footer: create_popup then falls back to the plain
        # centred Close button, leaving the portrait panel exactly as it was before this
        # panel grew a footer at all.
        return self.controls_available

    def build_footer(self, footer: Box) -> None:
        """Put "Controls..." in the footer, to the left of Close.

        create_popup appends Close with align="right" after this runs, so anything packed
        left here lands to its left. The chord ("..." on the Deck) is unguessable, so the
        panel you already visit to look things up is where the discoverable copy belongs.
        """
        btn = PushButton(
            footer,
            text="Controls...",
            align="left",
            width=13,
            command=self.show_controls,
        )
        btn.text_size = self._gui.s_18 if self._compact else self._gui.s_20
        btn.tk.config(
            borderwidth=3,
            relief="raised",
            highlightthickness=1,
            highlightbackground="black",
            padx=6,
            pady=1 if self._compact else 4,
            activebackground="#e0e0e0",
            background="#f7f7f7",
        )
        padding = 4 if self._compact else 20
        btn.tk.pack_configure(padx=padding, pady=padding)
        self._gui.cache(btn)

    def show_controls(self) -> None:
        """Swap this panel for the controls screen.

        Closes the admin panel first: they are both popups, and leaving this one open
        behind the other makes the Close button ambiguous.
        """
        self._gui.close_popup()
        self._gui.on_controls_panel()

    def spacer(self, tb: TitleBox, grid: tuple[int, int], width: int = 2) -> Text:
        sp = Text(
            tb,
            grid=grid,
            width=width,
            align="top",
        )
        sp.text_size = self._gui.s_18
        self._gui.cache(sp)
        return sp

    def _wifi_status(self) -> tuple[str, str | None, str, str | None, str]:
        snapshot = self._wifi_info.query()
        ip_address = self._current_ip_address()
        quality = snapshot.quality
        is_wifi_active = bool(
            snapshot.connected
            and snapshot.ssid
            and snapshot.interface
            and self._ip_belongs_to_interface(ip_address, snapshot.interface)
        )
        title = "WiFi" if is_wifi_active else "Ethernet"
        ssid = self._truncate(snapshot.ssid, 14) if is_wifi_active and snapshot.ssid else None
        if quality is None and snapshot.signal_dbm is not None:
            quality = WiFiInfo.dbm_to_quality(snapshot.signal_dbm)
        strength = f"{quality}%" if is_wifi_active and quality is not None else None
        return title, ssid, ip_address, strength, self._signal_color(quality)

    def _wifi_text(self, parent: Box, grid: list[int], text: str, anchor: str, sticky: str = "nsew") -> Text:
        field = Text(
            parent,
            text=text,
            grid=grid,
            align="left",
            bold=True,
            size=self._gui.s_12,
        )
        field.tk.configure(anchor=anchor)
        field.tk.grid_configure(sticky=sticky, padx=2, pady=0 if self._compact else (2, 2))
        return field

    def _wifi_signal_badge(self, parent: Box, grid: list[int], text: str, badge_color: str) -> Text:
        badge = Text(
            parent,
            text=text,
            grid=grid,
            align="right",
            bold=True,
            size=self._gui.s_12,
            width=max(6, len(text) + 1),
        )
        badge.bg = badge_color
        badge.text_color = self._signal_text_color(badge_color)
        badge.tk.configure(
            padx=8,
            pady=0 if self._compact else 3,
            borderwidth=1,
            relief="flat",
            anchor="center",
        )
        badge.tk.grid_configure(sticky="nse", padx=2, pady=0 if self._compact else 2)
        return badge

    def _refresh_wifi_display(self) -> None:
        if self._wifi_box is None or self._wifi_ssid is None or self._wifi_ip is None or self._wifi_signal is None:
            return
        title, ssid, ip_address, strength, signal_color = self._wifi_status()
        show_wifi_details = bool(ssid and strength)
        self._wifi_box.text = title
        self._wifi_ssid.value = ssid if ssid else ""
        self._wifi_ip.value = ip_address
        self._wifi_signal.value = strength or ""

        if show_wifi_details:
            self._wifi_ssid.show()
            self._wifi_signal.show()
            self._wifi_signal.bg = signal_color
            self._wifi_signal.text_color = self._signal_text_color(signal_color)
        else:
            self._wifi_ssid.hide()
            self._wifi_signal.hide()

    def _ensure_wifi_refresh(self) -> None:
        if self._overlay is None or self._wifi_refresh_after_id is not None:
            return
        self._wifi_refresh_after_id = self._overlay.tk.after(5_000, self._refresh_wifi_if_visible)

    def _refresh_wifi_if_visible(self) -> None:
        self._wifi_refresh_after_id = None
        if self._overlay is None or not self._overlay.visible:
            return
        self._refresh_wifi_display()
        self._ensure_wifi_refresh()

    def _on_popup_close(self, _overlay: Box | None = None) -> None:
        if self._overlay is None or self._wifi_refresh_after_id is None:
            self._wifi_refresh_after_id = None
            return
        try:
            self._overlay.tk.after_cancel(self._wifi_refresh_after_id)
        except (AttributeError, RuntimeError, ValueError):
            pass
        self._wifi_refresh_after_id = None

    @staticmethod
    def _ip_belongs_to_interface(ip_address: str, interface: str) -> bool:
        if ip_address == "Unavailable" or not interface:
            return False
        try:
            addrs = psutil.net_if_addrs().get(interface, [])
        except OSError:
            return False
        return any(addr.family == socket.AF_INET and addr.address == ip_address for addr in addrs)

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
        if self._echo_btn.value:
            self._debug_btn.enable()
        else:
            self._pytrain.debug = False
            self._debug_btn.disable()

    def _on_debug(self) -> None:
        self._pytrain.debug = bool(self._debug_btn.value)

    def do_admin_command(self, command: TMCC1SyncCommandEnum) -> None:
        if self._scope_btns.value == "0":
            Thread(
                target=self._pytrain.do_admin_cmd,
                args=(command, ["me"]),
                daemon=True,
            ).start()
        else:
            self._gui.do_tmcc_request(command)

    def _titlebox(self, parent: Box, text: str, grid: list[int] | None = None, **kwargs):
        if self._compact and "height" not in kwargs:
            kwargs["height"] = self.compact_section_height
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
        if self._compact:
            tb.tk.grid_propagate(False)
        elif is_height:
            tb.tk.pack_propagate(False)
        else:
            tb.tk.pack_propagate(True)
        if self._compact:
            tb.tk.grid_columnconfigure(
                0,
                weight=1,
                minsize=self.compact_control_width,
                uniform="admin_controls",
            )
            tb.tk.grid_columnconfigure(1, weight=0)
            tb.tk.grid_columnconfigure(
                2,
                weight=1,
                minsize=self.compact_control_width,
                uniform="admin_controls",
            )
            tb.tk.grid_rowconfigure(0, weight=0, minsize=self.compact_control_height)
        else:
            tb.tk.grid_columnconfigure(grid[0], weight=1)
        return tb

    def _hold_button(self, parent: Box, text: str, grid: list[int], **kwargs) -> HoldButton:
        text_size = kwargs.pop("text_size", self._gui.s_18)
        width = self._gui.rescale_by(kwargs.pop("width", 12))
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
            # These are destructive, so sliding a finger off has to abandon the hold.
            # Safe to ask for now that HoldButton checks the pointer really left the
            # button rather than trusting a bare <Leave>.
            cancel_on_leave=True,
            progress_fill_color="darkgrey",
            critical_fill_color="red",
            progress_empty_color="lightgrey",
            **kwargs,
        )
        self._gui.add_hover_action(hb)
        self._gui.cache(hb)
        self._fit_compact_control(hb)
        return hb

    def _fit_compact_control(self, control, image_backed: bool = False) -> None:
        if self._compact:
            height = self.compact_control_height - 4 if image_backed else 1
            control.tk.config(height=height, pady=0)
            control.tk.grid_configure(sticky="nsew", padx=2, pady=2)

    def _on_sync_state(self) -> None:
        if self._gui.sync_state.is_synchronized():
            self._sync_state.text = "Loaded"
            self._sync_state.bg = "green"
            self._reload_btn.enable()
        elif self._gui.sync_state.is_synchronizing():
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
