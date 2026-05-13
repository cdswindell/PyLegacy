#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

import logging
from typing import TYPE_CHECKING, cast

from guizero import Box, ListBox, Text, TitleBox

from .configured_accessory_adapter import ConfiguredAccessoryAdapter
from ..components.editable_text import EditableText, EditorType
from ...db.accessory_state import AccessoryState
from ...db.component_state import LcsProxyState
from ...db.engine_state import EngineState, TrainState
from ...db.prod_info import ProdInfo
from ...protocol.constants import CommandScope

log = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui


class StateInfoOverlay:
    def __init__(self, gui):
        self._gui = gui
        self.details = {}
        self._overlay = None

    @property
    def overlay(self) -> Box:
        if self._overlay is None:
            # noinspection PyProtectedMember, PyUnresolvedReferences
            self._overlay = self._gui._popup.create_popup(
                self._gui.version,
                self.build,
                on_popup_close=self._on_popup_closed,
            )
        return self._overlay

    @property
    def visible(self) -> bool:
        return self._overlay is not None and self._overlay.visible

    @staticmethod
    def make_field(
        host: "EngineGui",
        parent: Box,
        title: str,
        grid: list[int],
        max_cols: int = 4,
        scope: CommandScope = None,
        is_list: bool = False,
        center: bool = False,
        text_size: int = None,
        editable: bool = False,
        on_edit=None,
    ) -> tuple[TitleBox, Text]:
        text_size = text_size or host.s_18
        # grid can be [col, row] or [col, row, colspan, rowspan]
        aw = host.width
        if len(grid) >= 4:
            col, row, colspan, rowspan = grid
            aw = colspan * int(aw / max_cols)
        else:
            col, row = grid
            colspan, rowspan = 1, 1
            aw = int(aw / max_cols)

        # TitleBox participates in the parent's grid
        # noinspection PyTypeChecker
        tb = TitleBox(
            parent,
            text=title,
            layout="grid",  # use grid INSIDE the TitleBox
            grid=grid,
            width="fill",
            align="left",
        )
        tb.text_size = host.s_10
        tb.display_scope = scope

        # Now tell Tk this one actually spans columns/rows
        tb.tk.grid_configure(column=col, row=row, columnspan=colspan, rowspan=rowspan, sticky="ew")
        tb.tk.config(width=aw)
        tb.tk.pack_propagate(False)

        # Let the internal grid column stretch so the TextBox can fill
        tb.tk.grid_columnconfigure(0, weight=1)

        # Value field inside the TitleBox
        if is_list:
            # noinspection PyTypeChecker
            tf = ListBox(
                tb,
                items=None,
                grid=[0, 0],
                width="fill",
            )
            tf.text_size = text_size
            tk_listbox = tf.children[0].tk
            tk_listbox.config(
                bd=0,
                height=6,
                highlightthickness=0,
                selectbackground=tf.bg,
                width=36,
            )
        else:
            if editable:
                tf = EditableText(
                    tb,
                    grid=[0, 0],
                    width="fill",
                    height=1,
                    max_length=31,
                    on_commit=on_edit,
                )
                tf.add_hold_target(tb)
            else:
                tf = Text(tb, grid=[0, 0], width="fill", height=1)
            tf.text_size = text_size
            tf.tk.config(bd=0, highlightthickness=0, justify="left", anchor="w", width=aw)
            if center:
                tf.tk.grid_configure(sticky="")  # centered in cell
                tf.tk.config(justify="center", anchor="center")
        return tb, tf

    def build(self, body: Box):
        """Builds the 4-column grid layout for the info popup."""
        host = self._gui
        info_box = Box(body, layout="grid", border=1)
        for i in range(4):
            info_box.tk.grid_columnconfigure(i, weight=1, uniform="stateinfo")

        aw, _ = host.calc_image_box_size()
        info_box.tk.config(width=aw)

        # Config: [Key, Title, Grid, Scope]
        layouts = [
            ("number", "Road Number", [0, 0], None),
            ("type", "Type", [1, 0, 3, 1], None),
            ("name", "Road Name", [0, 1, 4, 1], None, EditorType.KEYBOARD, self._on_road_name_edited),
            ("control", "Control", [0, 2, 2, 1], CommandScope.ENGINE),
            ("sound", "Sound", [2, 2, 2, 1], CommandScope.ENGINE),
            ("speed", "Speed", [0, 3], CommandScope.ENGINE),
            ("target", "Target Speed", [1, 3], CommandScope.ENGINE),
            ("limit", "Speed Limit", [2, 3], CommandScope.ENGINE),
            ("max", "Max Speed", [3, 3], CommandScope.ENGINE),
            ("dir", "Direction", [0, 4], CommandScope.ENGINE),
            ("smoke", "Smoke Level", [1, 4], CommandScope.ENGINE),
            ("mom", "Momentum", [2, 4], CommandScope.ENGINE),
            ("brake", "Train Brake", [3, 4], CommandScope.ENGINE),
            ("labor", "Labor", [0, 5], CommandScope.ENGINE),
            ("rpm", "RPM", [1, 5], CommandScope.ENGINE),
            ("fuel", "Fuel Level", [2, 5], CommandScope.ENGINE),
            ("water", "Water Level", [3, 5], CommandScope.ENGINE),
            ("train id", "Train TMCC ID", [0, 6], CommandScope.ENGINE),
            ("train pos", "Position", [1, 6], CommandScope.ENGINE),
            ("train dir", "Direction", [2, 6], CommandScope.ENGINE),
            ("lead", "Lead Engine ID", [0, 6], CommandScope.TRAIN),
            ("engines", "Engines", [1, 6], CommandScope.TRAIN),
            ("cars", "Cars", [2, 6], CommandScope.TRAIN),
            ("accessories", "Accessories", [3, 6], CommandScope.TRAIN),
            ("mode", "Mode", [0, 2], CommandScope.ACC),
            ("parent", "Parent", [1, 2], CommandScope.ACC),
            ("port", "Port", [2, 2], CommandScope.ACC),
            ("firmware", "Firmware", [3, 2], CommandScope.ACC),
            ("operations", "Operations/TMCC IDs", [0, 2, 4, 1], CommandScope.CONFIGURED),
        ]

        for key, title, grid, scope, *rest in layouts:
            editor_type = rest[0] if len(rest) > 0 else None
            editable = editor_type is not None
            callback = rest[1] if len(rest) > 1 else None

            # Reusing the existing make_info_field logic from the main GUI
            is_list = key in {"operations"}
            self.details[key] = self.make_field(
                host,
                info_box,
                title,
                grid,
                scope=scope,
                is_list=is_list,
                editable=editable,
                on_edit=callback,
            )

    def update(self, state):
        """Populates the fields with data from the current state."""
        if not state or not self.details:
            return
        host = self._gui

        self._set_val("number", state.road_number)
        self._set_val("name", state.road_name)

        if isinstance(state, (EngineState, TrainState)):
            tmcc_id = state.tmcc_id if isinstance(state, EngineState) else state.head_tmcc_id
            # noinspection PyProtectedMember
            p_info = self._gui._prod_info_cache.get(tmcc_id)

            etype = state.engine_type_label
            if isinstance(p_info, ProdInfo) and p_info.engine_type:
                etype = f"{p_info.engine_type} {etype}"

            self._set_val("type", etype)
            self._set_val("control", f"{state.control_type_text} {state.record_no_label}")
            self._set_val("sound", state.sound_type_label)
            self._set_val("dir", "Fwd" if state.is_forward else "Rev" if state.is_reverse else "")
            self._set_val("smoke", state.smoke_text)
            self._set_val("mom", state.momentum_text)
            self._set_val("brake", state.train_brake_label)
            self._set_val("labor", state.labor_label)
            self._set_val("rpm", state.rpm_label)
            self._set_val("fuel", f"{state.fuel_level_pct:>3d} %")
            self._set_val("water", f"{state.water_level_pct:>3d} %")

            s, ts, sl, ms = state.speeds
            self._set_val("speed", f"{s:>3d}")
            self._set_val("target", f"{ts:>3d}")
            self._set_val("limit", f"{sl:>3d}" if sl is not None else "")
            self._set_val("max", f"{ms:>3d}")

            if isinstance(state, TrainState):
                self._set_val("engines", f"{state.num_engines}")
                self._set_val("lead", f"{state.head_tmcc_id:04d}")
                self._set_val("cars", f"{state.num_train_linked}")
                self._set_val("accessories", f"{state.num_accessories}")
            else:
                self._set_val("train id", f"{state.train_tmcc_id if state.train_tmcc_id else 'NA'}")
                self._set_val("train pos", f"{state.train_unit.position if state.train_unit else 'NA'}")
                self._set_val("train dir", f"{state.train_unit.direction if state.train_unit else 'NA'}")
        elif isinstance(state, LcsProxyState):
            self._set_val("type", state.accessory_type)
            self._set_val("mode", state.mode)
            self._set_val("parent", state.parent_id)
            self._set_val("port", state.port)
            self._set_val("firmware", state.firmware)

        # handle case where accessory has a configuration
        if isinstance(state, AccessoryState) and host.active_accessory:
            acc = host.active_accessory
            self._set_val("name", acc.name)
            self._set_val("type", acc.accessory_type.clean_title)
            self._set_val("operations", acc.configured_operations_legend)

    def _set_val(self, key, value):
        if key in self.details:
            if isinstance(value, list):
                field = cast(ListBox, self.details[key][1])
                field.clear()
                for item in value:
                    field.append(item)
            else:
                self.details[key][1].value = value

    def _on_road_name_edited(self, _field: EditableText, new_value: str, old_value: str) -> None:
        new_value = new_value.strip()
        old_value = old_value.strip()
        if new_value != _field.value:
            _field.value = new_value
        if new_value == old_value:
            return

        print(f"Road name changed from '{old_value}' to '{new_value}'")

        state = self._gui.active_state
        if isinstance(state, (EngineState, TrainState, AccessoryState, LcsProxyState)):
            # Keep recurring overlay refreshes from immediately overwriting the committed value.
            state._road_name = new_value

    def _on_popup_closed(self, overlay: Box | None = None) -> None:
        self.end_inline_edits(commit=True)
        self._gui.on_state_info_closed(overlay)

    def end_inline_edits(self, *, commit: bool = True) -> None:
        for _tb, field in self.details.values():
            if isinstance(field, EditableText) and field.is_editing:
                if commit:
                    field.commit_edit()
                else:
                    field.cancel_edit()

    def reset_visibility(self, scope, is_lcs_proxy=False, accessory: ConfiguredAccessoryAdapter = None):
        """Hides or shows fields based on the context."""
        current_scope = CommandScope.ACC if is_lcs_proxy else scope
        current_scope = (
            CommandScope.CONFIGURED if current_scope == CommandScope.ACC and accessory is not None else current_scope
        )
        for tb, _ in self.details.values():
            field_scope = getattr(tb, "display_scope", None)
            if field_scope is None or field_scope == current_scope:
                if hasattr(tb, "show"):
                    tb.show()
                else:
                    log.debug(f"No 'show' method for {tb}")
            elif current_scope == CommandScope.TRAIN and field_scope == CommandScope.ENGINE:
                if hasattr(tb, "show"):
                    tb.show()
                else:
                    log.debug(f"No 'show' method for {tb}")
            else:
                if hasattr(tb, "hide"):
                    tb.hide()
                else:
                    log.debug(f"No 'hide' method for {tb}")
