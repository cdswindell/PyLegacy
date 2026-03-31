#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

from __future__ import annotations

from guizero import Text
from guizero.base import Widget

from ..db.sync_state import SyncState
from ..gui.component_state_gui import ComponentStateGui
from ..gui.state_based_gui import StateBasedGui
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope, PROGRAM_NAME
from ..protocol.tmcc1.tmcc1_constants import TMCC1SyncCommandEnum


class SystemsGui(StateBasedGui):
    def __init__(
        self,
        label: str = None,
        width: int = None,
        height: int = None,
        aggregator: ComponentStateGui = None,
        scale_by: float = 1.0,
        press_for: int = 3,
        exclude_unnamed: bool = True,
        screens: int | None = None,
        stand_alone: bool = True,
        parent=None,
        full_screen: bool = True,
        x_offset: int = 0,
        y_offset: int = 0,
    ) -> None:
        StateBasedGui.__init__(
            self,
            f"{PROGRAM_NAME} Administration",
            label,
            width,
            height,
            aggregator,
            enabled_bg="red",
            scale_by=scale_by,
            exclude_unnamed=exclude_unnamed,
            screens=screens,
            stand_alone=stand_alone,
            parent=parent,
            full_screen=full_screen,
            x_offset=x_offset,
            y_offset=y_offset,
        )
        self._press_for = press_for

    # noinspection PyTypeChecker
    def on_sync(self) -> None:
        if self._sync_state.is_synchronized:
            if self._sync_watcher:
                self._sync_watcher.shutdown()
                self._sync_watcher = None
            self._synchronized = True

            # get all target states; watch for state changes
            accs = self.get_target_states()  # should be just 1
            for acc in accs:
                self._states[acc.tmcc_id] = acc
            self._max_name_len = 12

            # start GUI
            self.start()

    def get_target_states(self) -> list[SyncState]:
        pds: list[SyncState] = []
        accs = self._state_store.get_all(CommandScope.SYNC)
        for acc in accs:
            pds.append(acc)
        return pds

    def is_active(self, state: SyncState) -> bool:
        return False

    def switch_state(self, pd: SyncState) -> None:
        pass

    def _make_state_button(self, pd: SyncState, row: int, col: int, **kwargs) -> tuple[list[Widget], int, int]:
        hold_threshold = kwargs.pop("hold_threshold", self._press_for)
        for w in {self.left_scroll_btn, self.right_scroll_btn, self.by_name, self.by_number}:
            w.hide()
        widgets: list[Widget] = []

        # make title label
        ts = int(round(23 * self._scale_by))
        title = Text(
            self.btn_box,
            text=f"Hold for {self._press_for} seconds",
            grid=[col, row, 2, 1],
            size=ts,
            bold=True,
            color="red",
        )
        widgets.append(title)

        # make reload button
        row += 1
        btn, btn_h, btn_y = super()._make_state_button(
            pd, row, col, hold_threshold=hold_threshold, show_hold_progress=True
        )
        btn.text = "Reload Base 3 State"
        btn.on_hold = CommandReq(TMCC1SyncCommandEnum.RESYNC).send
        self.set_button_inactive(btn)
        widgets.append(btn)

        # make restart button
        row += 1
        btn, btn_h, btn_y = super()._make_state_button(
            pd, row, col, hold_threshold=hold_threshold, show_hold_progress=True
        )
        btn.text = "Restart All Nodes"
        btn.on_hold = CommandReq(TMCC1SyncCommandEnum.RESTART).send
        self.set_button_inactive(btn)
        widgets.append(btn)

        # make update button
        row += 1
        btn, btn_h, btn_y = super()._make_state_button(
            pd, row, col, hold_threshold=hold_threshold, show_hold_progress=True
        )
        btn.text = f"Update {PROGRAM_NAME} Software"
        btn.on_hold = CommandReq(TMCC1SyncCommandEnum.UPDATE).send
        self.set_button_inactive(btn)
        widgets.append(btn)

        # make upgrade button
        row += 1
        btn, btn_h, btn_y = super()._make_state_button(
            pd, row, col, hold_threshold=hold_threshold, show_hold_progress=True
        )
        btn.text = "Upgrade Raspberry Pi Software"
        btn.on_hold = CommandReq(TMCC1SyncCommandEnum.UPGRADE).send
        self.set_button_inactive(btn)
        widgets.append(btn)

        # spacer
        row += 1
        spacer = Text(self.btn_box, text=" ", grid=[col, row], size=ts)
        widgets.append(spacer)

        # make reboot button
        row += 1
        btn, btn_h, btn_y = super()._make_state_button(
            pd, row, col, hold_threshold=hold_threshold, show_hold_progress=True
        )
        btn.text = "Reboot All Nodes"
        btn.on_hold = CommandReq(TMCC1SyncCommandEnum.REBOOT).send
        self.set_button_inactive(btn)
        widgets.append(btn)

        # make shutdown button
        row += 1
        btn, btn_h, btn_y = super()._make_state_button(
            pd, row, col, hold_threshold=hold_threshold, show_hold_progress=True
        )
        btn.text = "Shutdown All Nodes"
        btn.on_hold = CommandReq(TMCC1SyncCommandEnum.SHUTDOWN).send
        self.set_button_inactive(btn)
        widgets.append(btn)

        # noinspection PyTypeChecker
        self._state_buttons[pd.tmcc_id] = widgets
        return widgets, btn_h, btn_y
