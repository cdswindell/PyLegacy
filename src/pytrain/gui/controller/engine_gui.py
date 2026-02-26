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
from contextlib import contextmanager
from typing import Any, Callable, Generic, Iterator, TypeVar, cast

from guizero import App, Box, Combo, Picture, Text, TitleBox

from .admin_panel import ADMIN_TITLE, AdminPanel
from .bell_horn_panel import BellHornPanel
from .catalog_panel import CatalogPanel
from .configured_accessory_adapter import ConfiguredAccessoryAdapter
from .configured_accessory_adapter_provider import ConfiguredAccessoryAdapterProvider
from .controller_view import ControllerView
from .engine_gui_conf import (
    COMMAND_FALLBACKS,
    CONDUCTOR_ACTIONS,
    CREW_DIALOGS,
    EXTRA_FUNCTIONS,
    HALT_KEY,
    KEY_TO_COMMAND,
    REPEAT_EXCEPTIONS,
    SCOPE_TO_SET_ENUM,
    SMOKE_OFF,
    SMOKE_ON,
    STATION_DIALOGS,
    STEWARD_DIALOGS,
    TOWER_DIALOGS,
    send_lcs_off_command,
    send_lcs_on_command,
)
from .image_presenter import ImagePresenter
from .keypad_view import KeypadView
from .lighting_panel import LightingPanel
from .popup_manager import PopupManager
from .rr_speed_panel import RrSpeedPanel
from .state_info_overlay import StateInfoOverlay
from ..accessories.configured_accessory import ConfiguredAccessorySet, DEFAULT_CONFIG_FILE
from ..components.hold_button import HoldButton
from ..components.scrolling_text import ScrollingText
from ..components.swipe_detector import SwipeDetector
from ..guizero_base import GuiZeroBase
from ...db.accessory_state import AccessoryState
from ...db.component_state import ComponentState, LcsProxyState, RouteState, SwitchState
from ...db.engine_state import EngineState, TrainState
from ...db.irda_state import IrdaState
from ...db.state_watcher import StateWatcher
from ...protocol.command_def import CommandDefEnum
from ...protocol.command_req import CommandReq
from ...protocol.constants import CommandScope
from ...protocol.multibyte.multibyte_constants import TMCC2EffectsControl
from ...protocol.sequence.ramped_speed_req import RampedSpeedDialogReq, RampedSpeedReq
from ...protocol.sequence.sequence_constants import SequenceCommandEnum
from ...protocol.tmcc1.tmcc1_constants import (
    TMCC1AuxCommandEnum,
    TMCC1EngineCommandEnum,
    TMCC1RRSpeedsEnum,
)
from ...protocol.tmcc2.tmcc2_constants import (
    TMCC2EngineCommandEnum,
    TMCC2EngineOpsEnum,
    TMCC2RRSpeedsEnum,
)
from ...utils.path_utils import find_file
from ...utils.unique_deque import UniqueDeque

log = logging.getLogger(__name__)
S = TypeVar("S", bound=ComponentState)


class EngineGui(GuiZeroBase, Generic[S]):
    @classmethod
    def name(cls) -> str:
        return cls.__name__

    def __init__(
        self,
        width: int = None,
        height: int = None,
        enabled_bg: str = "green",
        disabled_bg: str = "white",
        enabled_text: str = "black",
        disabled_text: str = "lightgrey",
        active_bg: str = "green",
        inactive_bg: str = "#f7f7f7",
        scale_by: float = 1.5,
        repeat: int = 2,
        num_recents: int = 5,
        sensor_track_id: int = None,
        tmcc_id: int = None,
        scope: CommandScope = CommandScope.ENGINE,
        auto_scroll: bool = True,
        config_file: str = DEFAULT_CONFIG_FILE,
    ) -> None:
        # have to call parent init after all variables are set up
        GuiZeroBase.__init__(
            self,
            title="Engine GUI",
            width=width,
            height=height,
            enabled_bg=enabled_bg,
            disabled_bg=disabled_bg,
            enabled_text=enabled_text,
            disabled_text=disabled_text,
            active_bg=active_bg,
            inactive_bg=inactive_bg,
            scale_by=scale_by,
        )

        self.auto_scroll = auto_scroll
        self.image_file = None
        self._engine_tmcc_id = None
        self._engine_state = None
        self._image = None
        self.repeat = repeat
        self.num_recents = num_recents
        self._sensor_track_id = sensor_track_id
        self.slider_height = self.button_size * 4

        self.scope_size = int(round(self.width / 5))
        self.grid_pad_by = 2
        self.avail_image_height = self.avail_image_width = None
        self.options = [self.title]

        self.box = self.acc_box = self.y_offset = None
        self.turn_on_image = find_file("on_button.jpg")
        self.turn_off_image = find_file("off_button.jpg")
        self.power_off_path = find_file("bulb-power-off.png")
        self.power_on_path = find_file("bulb-power-on.png")
        self.op_acc_image = find_file("op-acc.jpg")

        self._btn_images = []
        self._dim_cache = {}
        self._scope_buttons = {}
        self._scope_tmcc_ids = {}
        self._scope_watchers = {}
        self._recents_queue: dict[CommandScope, UniqueDeque[S]] = {}
        self._train_linked_queue: UniqueDeque[EngineState] = UniqueDeque()
        self._options_to_state = {}

        self.entry_cells = set()
        self.ops_cells = set()
        self.aux_cells = set()
        self.numeric_btns = {}
        self.scope = scope if scope else CommandScope.ENGINE
        self.initial = tmcc_id
        self._active_engine_state = self._active_train_state = None
        self._actual_current_engine_id = 0

        self._sensor_track_watcher = None
        self._sensor_track_state = None

        # various boxes
        self.emergency_box = self.info_box = self.keypad_box = self.scope_box = self.name_box = self.image_box = None
        self.controller_box = self.controller_keypad_box = self.controller_throttle_box = None
        self.emergency_box_width = self.emergency_box_height = None

        # various buttons
        self.halt_btn = self.reset_btn = self.off_btn = self.on_btn = self.set_btn = None
        self.fire_route_btn = self.switch_thru_btn = self.switch_out_btn = self.keypad_keys = None

        # various fields
        self.tmcc_id_box = self.tmcc_id_text = self._nbi = self.header = None
        self.name_text = self.titlebar_height = self.popup_position = None
        self.on_key_cell = self.off_key_cell = None
        self.image = None
        self._acc_overlay = None
        self.clear_key_cell = self.enter_key_cell = self.set_key_cell = self.fire_route_cell = None
        self.switch_thru_cell = self.switch_out_cell = None

        # Sensor Track
        self.sensor_track_box = self.sensor_track_buttons = None

        # BPC2/ASC2
        self.ac_on_cell = self.ac_off_cell = self.ac_status_cell = None
        self.ac_off_btn = self.ac_on_btn = self.ac_status_btn = None
        self.ac_aux1_cell = self.ac_aux1_btn = None
        self.ac_op_cell = self.ac_op_btn = None

        # controller
        self._separator = None
        self.controller_box = self.controller_keypad_box = None
        self.brake_box = self.brake_level = self.brake = self.focus_widget = None
        self.throttle_box = self.throttle = self.speed = self._rr_speed_btn = self._rr_speed_box = None
        self._bell_btn = self._horn_btn = None
        self._freight_sounds_bell_horn_box = None
        self.momentum_box = self.momentum_level = self.momentum = None
        self.horn_box = self.horn_title_box = self.horn_level = self.horn = None
        self.horn_overlay = None

        self._last_engine_type = None

        # don't ask
        self._isd = None  # swipe detector for engine image field
        self._admin_panel = None
        self._catalog_panel = None
        self._lighting_panel = None
        self._rr_speed_panel = None
        self._state_info = None
        self._bell_horn_panel = None
        self._accessory_view: dict[int, Box | None] = {}
        self.engine_ops_cells = {}

        # callbacks
        self._scoped_callbacks = {
            CommandScope.ROUTE: self.on_new_route,
            CommandScope.SWITCH: self.on_new_switch,
            CommandScope.ACC: self.on_new_accessory,
            CommandScope.ENGINE: self.on_new_engine,
            CommandScope.TRAIN: self.on_new_train,
            CommandScope.IRDA: self.on_sensor_track_update,
        }

        # delete after refactor

        # helpers to reduce code
        self._popup: PopupManager = PopupManager(self)
        self._image_presenter: ImagePresenter = ImagePresenter(self)
        self._controller_view: ControllerView = ControllerView(self)
        self._keypad_view: KeypadView = KeypadView(self)

        # get configured accessories
        self._caa = ConfiguredAccessorySet.from_file(config_file, verify=True)
        self._caap = ConfiguredAccessoryAdapterProvider(self._caa, self)
        self._acc_tmcc_to_adapter: dict[int, ConfiguredAccessoryAdapter] = {}

        # tell parent we've set up variables and are ready to proceed
        self.init_complete()

    @contextmanager
    def locked(self) -> Iterator[None]:
        with self._cv:
            yield

    @property
    def accessories(self) -> ConfiguredAccessorySet:
        return self._caa

    @property
    def accessory_provider(self) -> ConfiguredAccessoryAdapterProvider:
        return self._caap

    @property
    def accessory_labels(self) -> list[str]:
        return self._caa.configured_labels()

    @property
    def acc_overlay(self) -> Box | None:
        return self._acc_overlay

    def reset_acc_overlay(self) -> None:
        if self._acc_overlay and self._acc_overlay.visible:
            self._acc_overlay.hide()
        self._acc_overlay = None

    @property
    def active_accessory(self) -> ConfiguredAccessoryAdapter | None:
        if self._acc_overlay:
            return getattr(self._acc_overlay, "caa", None)
        return None

    def is_accessory_view(self, tmcc_id: int) -> bool:
        return tmcc_id in self._accessory_view

    def get_accessory_view(self, tmcc_id: int) -> Box | None:
        """
        By default, we prefer to display the configured accessory view, if available.
        If the tmcc id isn't in the dict, we create a view, if possible
        """
        with self._cv:
            if tmcc_id not in self._accessory_view:
                acc = self.get_configured_accessory(tmcc_id)
                self.set_accessory_view(tmcc_id, acc)
        return self._accessory_view.get(tmcc_id, None)

    def set_accessory_view(self, tmcc_id: int, acc: ConfiguredAccessoryAdapter | None):
        if acc is None:
            self._accessory_view[tmcc_id] = None
        else:
            with self._cv:
                acc.activate_tmcc_id(tmcc_id)
                if acc.overlay is None:
                    self._create_accessory_view(acc)
                assert acc.overlay
                self._accessory_view[tmcc_id] = acc.overlay

    def get_configured_accessory(self, tmcc_id: int) -> ConfiguredAccessoryAdapter | None:
        """
        By default, we prefer to display the configured accessory view, if available.
        If the tmcc id isn't in the dict, we create a view, if possible
        """
        with self._cv:
            if tmcc_id not in self._acc_tmcc_to_adapter:
                acc = None
                accs = self.accessory_provider.adapters_for_tmcc_id(tmcc_id)
                if accs and len(accs) >= 1 and accs[0]:
                    acc = accs[0]
                    acc.activate_tmcc_id(tmcc_id)
                    # TODO: what if there is more than one?
                self._acc_tmcc_to_adapter[tmcc_id] = acc
            return self._acc_tmcc_to_adapter[tmcc_id]

    @property
    def controller_view(self) -> ControllerView:
        return self._controller_view

    @property
    def active_engine_state(self) -> EngineState | None:
        if self.scope in (CommandScope.ENGINE, CommandScope.TRAIN):
            if (
                self._active_engine_state
                and self._active_engine_state.scope == self.scope
                and self._active_engine_state.tmcc_id == self._scope_tmcc_ids[self.scope]
            ):
                return self._active_engine_state
            else:
                self._active_engine_state = self.active_state
                return self._active_engine_state
        else:
            return None

    def on_sensor_track_update(self, state: IrdaState) -> None:
        if state.last_train_id:
            scope = CommandScope.TRAIN
            tmcc_id = state.last_train_id
        elif state.last_engine_id:
            scope = CommandScope.ENGINE
            tmcc_id = state.last_engine_id
        else:
            scope = tmcc_id = None
        if scope and tmcc_id:
            if scope != self.scope:
                self.on_scope(scope)
            if tmcc_id != self._scope_tmcc_ids[scope]:
                self.update_component_info(tmcc_id)
            elif self._keypad_view.is_entry_mode:
                self.ops_mode()

    # noinspection PyTypeChecker
    def build_gui(self) -> None:
        app = self.app

        # customize label
        self.header = cb = Combo(
            app,
            options=self.get_options(),
            selected=self.title,
            align="top",
            command=self.on_recents,
        )
        cb.text_size = self.s_24
        cb.text_bold = True

        if "menu" in cb.tk.children:
            menu = cb.tk.children["menu"]
            menu.config(activebackground="lightgrey")

        # determine if we can set the "selected" value directly;
        # will be used for other combo boxes
        self._popup.is_combo_hackable = hasattr(cb, "_selected")

        # Make the emergency buttons, including Halt and Reset
        self.make_emergency_buttons(app)

        # Make info box for TMCC ID and Road Name
        self.make_info_box(app)

        # make selection box and keypad
        self._keypad_view.build(app)

        # make engine/train make_controller
        self._controller_view.build(app)
        self._popup.get_or_create("extra_functions", "Additional Options", self.build_extra_functions_body)

        # make scope buttons
        self.make_scope(app)

        # Finally, resize image box
        available_height, available_width = self._image_presenter.calc_box_size()
        self.image_box.tk.config(height=available_height, width=available_width)

        # ONE geometry pass at the end
        app.tk.after_idle(app.tk.update_idletasks)

        # calculate offset for popups
        x = self.info_box.tk.winfo_rootx()
        y = self.info_box.tk.winfo_rooty() + self.info_box.tk.winfo_reqheight()
        self.popup_position = (x, y)

        # create watcher for sensor track, if needed
        if self._sensor_track_id:
            state = self._state_store.get_state(CommandScope.IRDA, self._sensor_track_id)
            action = self.on_state_changed_action(state)
            if state:
                self._sensor_track_watcher = StateWatcher(state, action)

        if self.initial:
            app.after(100, self.update_component_info, [self.initial])

    def destroy_gui(self) -> None:
        self.clear_cache()
        self.engine_ops_cells.clear()
        self.box = None
        self.acc_box = None
        self._image = None

    def build_tower_dialogs_body(self, body: Box):
        self._popup.make_combo_panel(body, TOWER_DIALOGS)

    def build_crew_dialogs_body(self, body: Box):
        self._popup.make_combo_panel(body, CREW_DIALOGS)

    def build_conductor_actions_body(self, body: Box):
        self._popup.make_combo_panel(body, CONDUCTOR_ACTIONS)

    def build_station_dialogs_body(self, body: Box):
        self._popup.build_button_panel(body, STATION_DIALOGS)

    def build_steward_dialogs_body(self, body: Box):
        self._popup.build_button_panel(body, STEWARD_DIALOGS)

    def build_extra_functions_body(self, body: Box):
        if body.layout != "grid":
            body = Box(body, align="top", layout="grid")
        self.controller_view.populate_keypad(EXTRA_FUNCTIONS, body)
        self.controller_view.regen_engine_keys_map()

    def on_info(self) -> None:
        """Shows state information in popup overlay"""
        state = self.active_state
        if state is None:
            return  # this should never be the case...

        with self._cv:
            if self._state_info is None:
                self._state_info = StateInfoOverlay(self)
        overlay = self._state_info.overlay

        scope = CommandScope.ACC if isinstance(state, LcsProxyState) and state.is_lcs else state.scope
        is_lcs = isinstance(state, LcsProxyState) and state.is_lcs

        # show/hide fields in the overlay
        self._state_info.reset_visibility(scope, is_lcs_proxy=is_lcs, accessory=self.active_accessory)
        self._state_info.update(state)
        self.show_popup(overlay)

    def on_rr_speed(self) -> None:
        with self._cv:
            if self._rr_speed_panel is None:
                self._rr_speed_panel = RrSpeedPanel(self)
        overlay = self._rr_speed_panel.overlay
        self._rr_speed_panel.configure(self.active_engine_state)
        self.show_popup(overlay)

    # noinspection PyUnresolvedReferences
    def on_lights(self) -> None:
        with self._cv:
            if self._lighting_panel is None:
                self._lighting_panel = LightingPanel(self)
        overlay = self._lighting_panel.overlay
        self._lighting_panel.configure(self.active_engine_state)
        self.show_popup(overlay, "AUX2_OPTION_ONE", "e")

    def on_tower_dialog(self) -> None:
        overlay = self._popup.get_or_create("tower_dialog", "Tower Dialogs", self.build_tower_dialogs_body)
        self.show_popup(overlay, "TOWER_CHATTER", "e")

    def on_crew_dialog(self) -> None:
        overlay = self._popup.get_or_create("crew_dialog", "Engineer & Crew Dialogs", self.build_crew_dialogs_body)
        self.show_popup(overlay, "ENGINEER_CHATTER", "e")

    def on_conductor_actions(self) -> None:
        overlay = self._popup.get_or_create("conductor_action", "Conductor Actions", self.build_conductor_actions_body)
        self.show_popup(overlay, "ENGINEER_CHATTER", "p")

    def on_station_dialogs(self) -> None:
        overlay = self._popup.get_or_create("station_dialog", "Station Dialogs", self.build_station_dialogs_body)
        self.show_popup(overlay, "TOWER_CHATTER", "p")

    def on_steward_dialogs(self) -> None:
        overlay = self._popup.get_or_create("steward_dialog", "Steward Dialogs", self.build_steward_dialogs_body)
        self.show_popup(overlay, "STEWARD_CHATTER", "p")

    def on_bell_horn_options(self) -> None:
        with self._cv:
            if self._bell_horn_panel is None:
                self._bell_horn_panel = BellHornPanel(self)
        overlay = self._bell_horn_panel.overlay
        self.show_popup(overlay, "RING_BELL", "e")

    def on_bell_horn_options_fs(self) -> None:
        with self._cv:
            if self._bell_horn_panel is None:
                self._bell_horn_panel = BellHornPanel(self)
        overlay = self._bell_horn_panel.overlay
        self.show_popup(overlay, button=self._bell_btn)

    def on_extra(self) -> None:
        overlay = self._popup.get_or_create("extra_functions", "Additional Options", self.build_extra_functions_body)
        self.show_popup(overlay, "AUX3_OPT_ONE", "l")

    def on_configured_accessory(self, acc: ConfiguredAccessoryAdapter) -> None:
        self._acc_overlay = overlay = self._create_accessory_view(acc)
        if self.keypad_box.visible:
            self.keypad_box.hide()
        if not overlay.visible:
            overlay.show()

    def _create_accessory_view(self, acc: ConfiguredAccessoryAdapter) -> Box:
        assert acc
        tmcc_id = self._scope_tmcc_ids[self.scope]
        acc.activate_tmcc_id(tmcc_id)
        self.name_text.value = acc.name
        overlay = self._popup.get_or_create(acc.instance_id, "", acc, self.restore_accessory_info)
        setattr(overlay, "caa", acc)
        self.set_accessory_view(tmcc_id, acc)
        self._image_presenter.update(tmcc_id=tmcc_id)
        return overlay

    def show_popup(
        self,
        overlay,
        op: str = None,
        modifier: str = None,
        button: HoldButton = None,
        position: tuple = None,
        hide_image_box: bool = False,
    ):
        self._popup.show(
            overlay=overlay,
            op=op,
            modifier=modifier,
            button=button,
            position=position,
            hide_image_box=hide_image_box,
        )

    def restore_accessory_info(self, overlay: Box = None):
        acc = getattr(overlay, "caa", None) if overlay else None
        if isinstance(acc, ConfiguredAccessoryAdapter):
            self.set_accessory_view(acc.state.tmcc_id, None)
            self._image_presenter.update(tmcc_id=acc.tmcc_id)
            self.name_text.value = self.active_state.name
        overlay.hide()
        self._acc_overlay = None
        if not self.keypad_box.visible:
            self.keypad_box.show()

    def on_admin_panel(self) -> None:
        with self._cv:
            if self._admin_panel is None:
                self._admin_panel = AdminPanel(self, width=self.emergency_box_width, height=int(self.height / 2))
        overlay = self._admin_panel.overlay
        self.show_popup(overlay, hide_image_box=True)

    def on_recents(self, value: str):
        # Updates component info if selected state is valid
        if value not in {self.title, self._separator}:
            if value == ADMIN_TITLE:
                self.on_admin_panel()
            else:
                state = self._options_to_state[value]
                if state and state not in {self._active_engine_state, self._active_train_state}:
                    self.update_component_info(tmcc_id=state.tmcc_id)
        self.header.select_default()

    @property
    def active_state(self) -> S | None:
        if self.scope and self._scope_tmcc_ids.get(self.scope, None):
            return self._state_store.get_state(self.scope, self._scope_tmcc_ids[self.scope], False)
        else:
            return None

    def get_options(self) -> list[str]:
        if self._separator is None:
            self._separator = "-" * int(3 * len(self.title) / 2)
        options = [self.title]
        add_sep = False
        self._options_to_state.clear()
        queue = self._recents_queue.get(self.scope, UniqueDeque())
        if self.scope == CommandScope.ENGINE and self._train_linked_queue:
            if queue:
                # we want to preserve the order of the original queue
                queue = queue.copy()
                add_sep = True
            for i, state in enumerate(self._train_linked_queue):
                queue.insert(i, state)
        # Adds formatted options from recent states queue
        if isinstance(queue, UniqueDeque):
            num_chars = 4 if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN} else 2
            for state in queue:
                if add_sep and self._train_linked_queue and state not in self._train_linked_queue:
                    options.append(self._separator)
                    add_sep = False
                if (
                    self.scope == CommandScope.ACC
                    and state.tmcc_id in self._acc_tmcc_to_adapter
                    and self._acc_tmcc_to_adapter[state.tmcc_id]
                ):
                    road_name = self._acc_tmcc_to_adapter[state.tmcc_id].name
                else:
                    road_name = state.road_name
                name = f"{state.tmcc_id:0{num_chars}d}: {road_name}"
                road_number = state.road_number
                if road_number and road_number.isnumeric() and int(road_number) != state.tmcc_id:
                    name += f" #{int(road_number)}"
                if name:
                    options.append(name)
                    self._options_to_state[name] = state
        options.append(self._separator)
        options.append(ADMIN_TITLE)
        return options

    def monitor_state(self):
        with self._cv:
            tmcc_id = self._scope_tmcc_ids.get(self.scope, 0)
            watcher = self._scope_watchers.get(self.scope, None)
            if isinstance(watcher, StateWatcher) and watcher.tmcc_id == tmcc_id:
                # we're good, return
                return
            if isinstance(watcher, StateWatcher):
                # close existing watcher
                watcher.shutdown()
                self._scope_watchers[self.scope] = None
            if tmcc_id:
                # create a new state watcher to monitor state of scoped entity
                state = self.active_state
                # state shouldn't be None, but good to check
                if state:
                    action = self.on_state_changed_action(state)
                    self._scope_watchers[self.scope] = StateWatcher(state, action)

    def on_state_changed_action(self, state: S) -> Callable:
        action = self._scoped_callbacks.get(state.scope, lambda s: log.info(f"** No action callback for {s}"))

        def upd():
            if not self._shutdown_flag.is_set():
                self._message_queue.put((action, [state]))

        return upd

    # noinspection PyUnusedLocal
    def on_new_engine(self, state: EngineState = None, ops_mode_setup: bool = False, is_engine: bool = True) -> None:
        self._active_engine_state = state
        if isinstance(state, EngineState):
            if self._active_train_state and state in self._active_train_state:
                # if we are operating on a train-linked car with the associated train
                # active in the Train scope tab, indicate that on the gui
                self._scope_buttons[CommandScope.TRAIN].bg = "lightgreen"
            elif is_engine:
                # otherwise, indicate we are in "Engine": mode and tear down the
                # train-linked gui components
                self._tear_down_link_gui()
                self._scope_buttons[CommandScope.TRAIN].bg = "white"

            # only set throttle/brake/momentum value if we are not in the middle of setting it
            # and if the engine is not a passenger or freight sounds car
            if self._active_train_state and state in self._train_linked_queue:
                throttle_state = self._active_train_state
            elif self.scope == CommandScope.ENGINE and self._active_train_state and state in self._active_train_state:
                # don't allow throttle of an engine in a consist to be modified directly
                throttle_state = None
            elif state.has_throttle:
                throttle_state = state
            else:
                throttle_state = None

            # UI painting lives in ControllerView now
            self._controller_view.update_from_state(state=state, throttle_state=throttle_state)

        # update info detail popup, if its visible
        if self._state_info and self._state_info.visible:
            self._state_info.update(state)

    def on_new_train(self, state: TrainState = None, ops_mode_setup: bool = False) -> None:
        if state and state != self._active_train_state:
            # set up for Train; if there are train-linked cars available, remember them
            # and set "Eng" scope key color accordingly. Also, add train-linked cars to
            # list of recent engines
            if state.num_train_linked > 0:
                self._train_linked_queue.clear()
                if self.scope == CommandScope.TRAIN:
                    self._scope_buttons[CommandScope.ENGINE].bg = "lightgreen"
                cars = state.link_tmcc_ids
                for tmcc_id in cars:
                    car_state = self._state_store.get_state(CommandScope.ENGINE, tmcc_id, False)
                    if car_state:
                        self._train_linked_queue.append(car_state)
                self._setup_train_link_gui(self._train_linked_queue[0])
            else:
                self._tear_down_link_gui()
            self._active_train_state = state
            self.rebuild_options()
        elif state is None:
            self._tear_down_link_gui()
        if self.scope == CommandScope.TRAIN and state == self._active_train_state and self._train_linked_queue:
            self._scope_buttons[CommandScope.ENGINE].bg = "lightgreen"
        self.on_new_engine(state, ops_mode_setup=ops_mode_setup, is_engine=False)

    def _setup_train_link_gui(self, state: TrainState) -> None:
        # self._actual_current_engine_id = self._scope_tmcc_ids.get(CommandScope.ENGINE, 0)
        self._active_train_state = state
        self._scope_tmcc_ids[CommandScope.ENGINE] = self._train_linked_queue[0].tmcc_id

    def _tear_down_link_gui(self) -> None:
        if self.scope != CommandScope.ENGINE:
            self._scope_buttons[CommandScope.ENGINE].bg = "white"
        current_engine_id = self._scope_tmcc_ids.get(CommandScope.ENGINE, 0)
        if current_engine_id and current_engine_id in {x.tmcc_id for x in self._train_linked_queue}:
            self._scope_tmcc_ids[CommandScope.ENGINE] = 0  # force current engine to be from queue
        self._train_linked_queue.clear()
        self._active_train_state = None
        self.rebuild_options()

    def on_new_route(self, state: RouteState = None):
        # must be called from app thread!!
        if state is None:
            tmcc_id = self._scope_tmcc_ids[CommandScope.ROUTE]
            state = self._state_store.get_state(CommandScope.ROUTE, tmcc_id, False) if 1 <= tmcc_id < 99 else None
        if state:
            bg = self._active_bg if state.is_active else self._inactive_bg
            hc = "lightgreen" if state.is_active else "#e0e0e0"
            self.add_hover_action(self.fire_route_btn, hover_color=hc, background=bg)
        else:
            self.add_hover_action(self.fire_route_btn, background=self._inactive_bg)

    def on_new_switch(self, state: SwitchState = None):
        # must be called from app thread!!
        if state is None:
            tmcc_id = self._scope_tmcc_ids[CommandScope.SWITCH]
            state = self._state_store.get_state(CommandScope.SWITCH, tmcc_id, False) if 1 <= tmcc_id < 99 else None
        if state:
            if state.is_thru:
                self.add_hover_action(self.switch_thru_btn, hover_color="lightgreen", background=self._active_bg)
                self.add_hover_action(self.switch_out_btn, background=self._inactive_bg)
            elif state.is_out:
                self.add_hover_action(self.switch_out_btn, hover_color="lightgreen", background=self._active_bg)
                self.add_hover_action(self.switch_thru_btn, background=self._inactive_bg)
            else:
                for btn in (self.switch_thru_btn, self.switch_out_btn):
                    self.add_hover_action(btn, background=self._inactive_bg)
            # self.switch_thru_btn.bg = self._active_bg if state.is_thru else self._inactive_bg
            # self.switch_out_btn.bg = self._active_bg if state.is_out else self._inactive_bg
        else:
            for btn in (self.switch_thru_btn, self.switch_out_btn):
                self.add_hover_action(btn, background=self._inactive_bg)

    def on_new_accessory(self, state: AccessoryState | TrainState = None):
        state = state if state else self.active_state
        tmcc_id = self._scope_tmcc_ids[CommandScope.ACC]
        if isinstance(state, AccessoryState):
            if state.is_sensor_track:
                st_state = self._state_store.get_state(CommandScope.IRDA, tmcc_id, False)
                if isinstance(st_state, IrdaState):
                    self.sensor_track_buttons.value = st_state.sequence.value
                else:
                    self.sensor_track_buttons.value = None
            elif state.is_bpc2 or state.is_asc2:
                self.update_ac_status(state)
            elif state.is_amc2:
                pass
        elif isinstance(state, TrainState) and state.is_power_district:
            self.update_ac_status(state)

    def update_ac_status(self, state: AccessoryState | TrainState):
        power_on_image, _ = self.get_titled_image(self.power_on_path)
        power_off_image, _ = self.get_titled_image(self.power_off_path)
        img = power_on_image if state.is_aux_on else power_off_image
        self.ac_status_btn.tk.config(
            image=img,
            height=self.titled_button_size,
            width=self.titled_button_size,
        )
        self.ac_status_btn.image = img

    def make_scope(self, app: App):
        button_height = int(round(40 * self._scale_by))
        self.scope_box = scope_box = Box(app, layout="grid", border=2, align="bottom")
        img = tk.PhotoImage(width=self.scope_size, height=button_height)
        self._btn_images.append(img)
        for i, scope_abbrev in enumerate(["ACC", "SW", "RTE", "TR", "ENG"]):
            scope = CommandScope.by_prefix(scope_abbrev)
            pb = HoldButton(
                scope_box,
                text=scope_abbrev,
                grid=[i, 1],
                align="top",
                height=1,
                text_size=self.s_18,
                text_bold=True,
                command=self.on_scope,
                args=[scope],
            )
            pb.scope = scope
            pb.on_hold = (self.on_scope_hold, [pb])
            # Configure the button with the image as background
            pb.tk.config(
                image=img,
                compound="center",
                width=self.scope_size,
                height=button_height,
                padx=0,
                pady=0,
            )
            # Make the grid column expand to fill space
            scope_box.tk.grid_columnconfigure(i, weight=1)
            # associate the button with its scope
            self._scope_buttons[scope] = pb
            # don't overwrite initial tmcc id if one specified
            if scope not in self._scope_tmcc_ids:
                self._scope_tmcc_ids[scope] = 0
        # highlight initial button
        self.on_scope(self.scope)

    # noinspection PyUnresolvedReferences
    def on_scope_hold(self, pb: HoldButton):
        self.on_scope(pb.scope, held=True)
        with self._cv:
            if self._catalog_panel is None:
                self._catalog_panel = CatalogPanel(
                    self, width=self.emergency_box_width, height=int(3 * self.height / 4)
                )
        overlay = self._catalog_panel.overlay
        self._catalog_panel.configure(pb.scope)  # only call *after* overlay is created
        overlay.title.value = self._catalog_panel.title
        self.show_popup(overlay, hide_image_box=True)

    # noinspection PyTypeChecker
    def on_scope(self, scope: CommandScope, held: bool = False) -> None:
        self.scope_box.hide()
        force_entry_mode = False
        clear_info = True
        # self._last_engine_type = None
        for k, v in self._scope_buttons.items():
            if k == scope:
                v.bg = self._enabled_bg
                v.text_color = self._enabled_text
            else:
                v.bg = "white"
                v.text_color = "black"
        # if new scope selected, display most recent scoped component, if one existed
        if scope != self.scope:
            self.tmcc_id_box.text = f"{scope.title} ID"
            self.scope = scope
            # if scoped TMCC_ID is 0, take the first item on the recents queue
            if self._scope_tmcc_ids[scope] == 0:
                self.display_most_recent(scope)
        else:
            # if the pressed scope button is the same as the current scope,
            # return to entry mode or pop an element from the recents queue,
            # based on whether the current scope TMCC_ID is 0 or not
            if self._scope_tmcc_ids[scope] == 0:
                self.display_most_recent(scope)
            else:
                if not held:
                    # pressing the same scope button again returns to entry mode with current
                    # component active
                    if self._keypad_view.is_entry_mode:
                        self.ops_mode(update_info=False)
                    else:
                        force_entry_mode = True
                        clear_info = False
                        if self.acc_overlay and self.acc_overlay.visible:
                            self.acc_overlay.hide()
        # update display
        self._popup.close()
        self.update_component_info()
        # force entry mode if scoped tmcc_id is 0
        if self._scope_tmcc_ids[scope] == 0:
            force_entry_mode = True
        self.rebuild_options()
        num_chars = 4 if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN} else 2
        self.tmcc_id_text.value = f"{self._scope_tmcc_ids[scope]:0{num_chars}d}"
        self.scope_box.show()
        self._keypad_view.scope_keypad(force_entry_mode, clear_info)

    def display_most_recent(self, scope: CommandScope) -> None:
        """
        Display the most recent scoped component in the recents queue.
        """
        recents = self._recents_queue.get(scope, None)
        if isinstance(recents, UniqueDeque) and len(recents) > 0:
            state = recents[0]
            self._scope_tmcc_ids[scope] = state.tmcc_id

    def make_recent(self, scope: CommandScope, tmcc_id: int, state: S = None) -> bool:
        self._popup.close()
        log.debug(f"Pushing current: {scope} {tmcc_id} {self.scope} {self.tmcc_id_text.value}")
        self._scope_tmcc_ids[self.scope] = tmcc_id
        if tmcc_id > 0:
            if state is None:
                state = self.state_store.get_state(self.scope, tmcc_id, False)
            if state:
                # add to scope queue
                if state in self._train_linked_queue:
                    queue = self._train_linked_queue
                else:
                    if (
                        scope == CommandScope.ENGINE
                        and self._active_train_state
                        and state not in self._active_train_state
                    ):
                        self._tear_down_link_gui()
                    queue = self._recents_queue.get(self.scope, None)
                    if queue is None:
                        queue = UniqueDeque[S](maxlen=self.num_recents)
                        self._recents_queue[self.scope] = queue
                queue.appendleft(state)
                self.rebuild_options()
                return True
        return False

    def show_next_component(self) -> None:
        self._popup.close()
        if self.scope == CommandScope.ENGINE and self._train_linked_queue:
            recents = self._train_linked_queue
        else:
            recents = self._recents_queue.get(self.scope, None)
        if isinstance(recents, UniqueDeque) and len(recents) > 0:
            current = recents[0]
            state = cast(ComponentState, cast(object, recents.next()))
            recents.append(current)
            self._scope_tmcc_ids[self.scope] = state.tmcc_id
            self.update_component_info(tmcc_id=state.tmcc_id)
            self.header.select_default()

    def show_previous_component(self) -> None:
        self._popup.close()
        if self.scope == CommandScope.ENGINE and self._train_linked_queue:
            recents = self._train_linked_queue
        else:
            recents = self._recents_queue.get(self.scope, None)
        if isinstance(recents, UniqueDeque) and len(recents) > 0:
            state = cast(ComponentState, cast(object, recents.previous()))
            self._scope_tmcc_ids[self.scope] = state.tmcc_id
            self.update_component_info(tmcc_id=state.tmcc_id)
            self.header.select_default()

    def rebuild_options(self):
        self.header.clear()
        for option in self.get_options():
            self.header.append(option)
        self.header.select_default()

    def make_info_box(self, app: App):
        self.info_box = info_box = Box(app, layout="left", border=2, align="top")

        # ───────────────────────────────
        # Left: ID box
        # ───────────────────────────────
        self.tmcc_id_box = tmcc_id_box = TitleBox(info_box, f"{self.scope.title} ID", align="left")
        tmcc_id_box.text_size = self.s_12
        self.tmcc_id_text = Text(tmcc_id_box, text="0000", align="left", bold=True, width=5)
        self.tmcc_id_text.text_color = "blue"
        self.tmcc_id_text.text_size = self.s_20

        # ───────────────────────────────
        # Right: Road Name box
        # ───────────────────────────────
        self.name_box = name_box = TitleBox(info_box, "Road Name", align="right")
        name_box.text_size = self.s_12
        self.name_text = ScrollingText(
            name_box,
            text="",
            align="top",
            bold=True,
            width="fill",
            auto_scroll=self.auto_scroll,
        )
        self.name_text.text_color = "blue"
        self.name_text.text_size = self.s_18
        self.name_text.tk.config(justify="left", anchor="w")
        name_box.tk.pack_propagate(False)  # prevent pack from shrinking

        # ───────────────────────────────
        # Wait until the ID box is actually realized
        # ───────────────────────────────
        def adjust_road_name_box():
            try:
                # Force the ID box to compute geometry first
                tmcc_id_box.tk.update_idletasks()

                # Determine target width from the emergency box
                total_w = self.emergency_box_width or self.emergency_box.tk.winfo_width()
                if total_w is None or total_w <= 1:
                    app.tk.after(50, adjust_road_name_box)
                    return

                # Fix the overall info_box width permanently
                id_h = tmcc_id_box.tk.winfo_height()
                info_box.tk.config(width=total_w, height=id_h + 2)
                info_box.tk.pack_propagate(False)  # <- prevent any child resizing

                # Compute sub-box dimensions but don’t change the overall width later
                id_w = self.tmcc_id_box.tk.winfo_width()
                id_h = self.tmcc_id_box.tk.winfo_height()
                name_box.tk.config(height=id_h, width=max(0, total_w - id_w))
            except tk.TclError as e:
                log.exception(f"[adjust_road_name_box] failed: {e}", exc_info=e)

        # Schedule width/height fix after geometry update
        app.tk.after(10, adjust_road_name_box)

        # add a picture placeholder here, we may not use it
        self.image_box = image_box = Box(app, border=0, align="top")
        self.image = Picture(image_box, align="top")
        self._isd = SwipeDetector(self.image)
        self._isd.on_long_press = self.on_info
        self._isd.on_swipe_right = self.show_previous_component
        self._isd.on_swipe_left = self.show_next_component
        self.image_box.hide()

    def make_keypad_button(
        self,
        keypad_box: Box | TitleBox,
        label: str | None,
        row: int,
        col: int,
        size: int | None = None,
        image: str = None,
        visible: bool = True,
        bolded: bool = True,
        is_ops: bool = False,
        is_entry: bool = False,
        titlebox_text: str = None,
        align: str = "bottom",
        hover: bool = False,
        command: Callable | bool | None = None,
        args: list = None,
    ):
        if args is None:
            args = [label]
        if isinstance(command, bool) and not command:
            command = args = None
        elif command is None or (isinstance(command, bool) and command):
            command = (self.on_keypress, args)
        else:  # custom command
            command = (command, args)

        cell, nb = self._build_keypad_button(
            keypad_box=keypad_box,
            label=label,
            row=row,
            col=col,
            size=size,
            image=image,
            visible=visible,
            bolded=bolded,
            titlebox_text=titlebox_text,
            align=align,
            hover=hover,
            command=command,
            args=args,
        )

        if is_ops:
            self.ops_cells.add(cell)
        if is_entry:
            self.entry_cells.add(cell)

        return cell, nb

    def on_keypress(self, key):
        """Convenience wrapper; heavy lifting done in KeypadView"""
        return self._keypad_view.on_keypress(key)

    def on_set_key(self, scope: CommandScope, tmcc_id: int) -> None:
        # Fire the set address command; only valid for switches, accessories, and engines
        if scope != CommandScope.TRAIN and tmcc_id:
            cmd_enum = SCOPE_TO_SET_ENUM.get(scope, None)
            if isinstance(cmd_enum, CommandDefEnum):
                if scope == CommandScope.ENGINE and tmcc_id > 99:
                    cmd = CommandReq.build(TMCC2EngineCommandEnum.SET_ADDRESS, address=tmcc_id, scope=scope)
                else:
                    cmd = CommandReq.build(cmd_enum, address=tmcc_id, scope=scope)
                cmd.send(repeat=self.repeat)
        else:
            self._keypad_view.entry_mode(clear_info=False)

    def do_command(self, key: str) -> None:
        cmd = KEY_TO_COMMAND.get(key, None)
        tmcc_id = self._scope_tmcc_ids[self.scope]
        if cmd:
            # special case HALT cmd
            if key == HALT_KEY:
                cmd.send()
            elif tmcc_id > 0:
                if isinstance(cmd, CommandReq):
                    cmd.scope = self.scope
                    cmd.address = self._scope_tmcc_ids[self.scope]
                    cmd.send(repeat=self.repeat)
                elif cmd == send_lcs_on_command:
                    state = self._state_store.get_state(self.scope, tmcc_id, False)
                    if state:
                        cmd(state)
                elif cmd == send_lcs_off_command:
                    state = self._state_store.get_state(self.scope, tmcc_id, False)
                    if state:
                        cmd(state)
        else:
            log.warning(f"Unknown key: {key}")

    # noinspection PyTypeChecker
    def ops_mode(self, update_info: bool = True, state: S | None = None) -> None:
        # 1) Common UI transition (moved)
        self._keypad_view.enter_ops_mode_base()

        # 2) Engine/train path
        if self._keypad_view.is_engine_or_train:
            # pure UI shell now lives in KeypadView
            self._keypad_view.apply_ops_mode_ui_engine_shell()

            # Resolve state (EngineGui responsibility)
            if not isinstance(state, EngineState):
                self._active_engine_state = state = self.state_store.get_state(
                    self.scope, self._scope_tmcc_ids[self.scope], False
                )

            # Apply model changes (EngineGui responsibility)
            if isinstance(state, TrainState):
                self.on_new_train(state, ops_mode_setup=True)
            else:
                self.on_new_engine(state, ops_mode_setup=True)

            self._last_engine_type = None
            self._controller_view.apply_engine_type(state)

        # 3) Non-engine path (already moved)
        else:
            self._keypad_view.apply_ops_mode_ui_non_engine(state=state)
            tmcc_id = self.active_state.tmcc_id
            if self.scope == CommandScope.ACC and self.get_accessory_view(tmcc_id):
                view = self.get_accessory_view(tmcc_id)
                acc = getattr(view, "caa", None)
                self.on_configured_accessory(acc)

        # 4) Preserve existing behavior
        if update_info:
            self.update_component_info(in_ops_mode=True)

    # noinspection PyTypeChecker
    def update_component_info(
        self,
        tmcc_id: int = None,
        not_found_value: str = "Not Configured",
        in_ops_mode: bool = False,
    ) -> None:
        self._popup.close()
        if tmcc_id is None:
            tmcc_id = self._scope_tmcc_ids.get(self.scope, 0)
        # update the tmcc_id associated with current scope
        self._scope_tmcc_ids[self.scope] = tmcc_id
        update_button_state = True
        num_chars = 4 if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN} else 2
        if tmcc_id:
            state = self.active_state
            name = not_found_value
            if state:
                # Make sure ID field shows TMCC ID, not just road number
                if tmcc_id != state.tmcc_id or tmcc_id != int(self.tmcc_id_text.value):
                    tmcc_id = state.tmcc_id
                    self._scope_tmcc_ids[self.scope] = tmcc_id
                    self.tmcc_id_text.value = f"{tmcc_id:0{num_chars}d}"
                if isinstance(state, AccessoryState) and self.get_accessory_view(tmcc_id):
                    view = self.get_accessory_view(tmcc_id)
                    acc = getattr(view, "caa", None)
                    if acc:
                        name = acc.name
                        acc.activate_tmcc_id(tmcc_id)
                elif state:
                    name = state.name
                    name = name if name and name != "NA" else not_found_value
                update_button_state = False
                self.make_recent(self.scope, tmcc_id, state)
                if not in_ops_mode:
                    self.ops_mode(update_info=False)
            self.name_text.value = name
        else:
            if self._keypad_view.reset_on_keystroke:
                self._scope_tmcc_ids[self.scope] = 0
                self._keypad_view.reset_on_keystroke = False
            self.tmcc_id_text.value = f"{tmcc_id:0{num_chars}d}"
            self.name_text.value = ""
            state = None
            self._image_presenter.clear()
        self.monitor_state()
        # use the callback to update ops button state
        if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.ACC}:
            if update_button_state:
                # noinspection PyTypeChecker
                self._scoped_callbacks.get(self.scope, lambda s: print(f"from uci: {s}"))(state)
            self._image_presenter.update(tmcc_id)
        else:
            self.image_box.hide()

    def calc_image_box_size(self) -> tuple[int, int | Any]:
        return self._image_presenter.calc_box_size()

    def make_emergency_buttons(self, app: App):
        self.emergency_box = emergency_box = Box(app, layout="grid", border=2, align="top")
        _ = Text(emergency_box, text=" ", grid=[0, 0, 3, 1], align="top", size=2, height=1, bold=True)

        self.halt_btn = HoldButton(
            emergency_box,
            text=HALT_KEY,
            grid=[0, 1],
            align="top",
            width=11,
            padx=self.text_pad_x,
            pady=self.text_pad_y,
            bg="red",
            text_bold=True,
            text_size=self.s_20,
            command=self.on_keypress,
            args=[HALT_KEY],
        )

        _ = Text(emergency_box, text=" ", grid=[1, 1], align="top", size=6, height=1, bold=True)

        self.reset_btn = HoldButton(
            emergency_box,
            text="Reset",
            grid=[2, 1],
            align="top",
            width=11,
            padx=self.text_pad_x,
            pady=self.text_pad_y,
            bg="gray",
            text_size=self.s_20,
            text_color="black",
            text_bold=True,
            enabled=False,
            on_press=(self.on_engine_command, ["RESET"]),
            on_repeat=(self.on_engine_command, ["RESET"]),
            repeat_interval=0.2,
        )

        _ = Text(emergency_box, text=" ", grid=[0, 2, 3, 1], align="top", size=2, height=1, bold=True)
        self.app.tk.update_idletasks()
        self.emergency_box_width = emergency_box.tk.winfo_width()
        self.emergency_box_height = emergency_box.tk.winfo_height()

    def on_speed_command(self, speed_req: str | int) -> None:
        state = self.active_engine_state
        if self._active_train_state and state in self._train_linked_queue:
            state = self._active_train_state
        if isinstance(speed_req, str):
            speed = speed_req.split(", ")
            do_dialog = isinstance(speed, list) and len(speed) > 1
            speed = (speed[-1] if isinstance(speed, list) else speed).replace("SPEED_", "")
            if state and state.is_legacy:
                rr_speed = TMCC2RRSpeedsEnum.by_name(speed)
            else:
                rr_speed = TMCC1RRSpeedsEnum.by_name(speed)
            if rr_speed is None and speed == "EMERGENCY_STOP":
                # dispatch directly to on_engine_command for processing
                if state:
                    state.is_ramping = False
                self.on_engine_command(speed_req, state=state, scope=state.scope)
                return
        else:
            do_dialog = False
            rr_speed = speed_req

        if state:
            if do_dialog:
                req = RampedSpeedDialogReq(state.tmcc_id, rr_speed, state.scope)
            else:
                req = RampedSpeedReq(state.tmcc_id, rr_speed, state.scope)
        else:
            tmcc_id = self._scope_tmcc_ids[self.scope]
            req = CommandReq(TMCC1EngineCommandEnum.ABSOLUTE_SPEED, tmcc_id, scope=self.scope, data=rr_speed)

        # dispatch command
        req.send()

    def on_engine_command(
        self,
        targets: str | list[str] | CommandReq,
        data: int = 0,
        repeat: int = None,
        delay: float = 0.0,
        do_ops: bool = False,
        do_entry: bool = False,
        state: EngineState | TrainState = None,
        scope: CommandScope = None,
    ) -> None:
        """
        Send commands to a TMCC or Legacy Engine or Train.

        To allow for command differences between TMCC and Legacy engines, commands can be sent in as
        lists, with each element being tried in order, until one is found that is appropriate for the
        engine generation.

        """
        repeat = repeat if repeat else self.repeat
        scope = scope or self.scope
        tmcc_id = state.tmcc_id if state else self._scope_tmcc_ids[scope]
        if tmcc_id == 0:
            tmcc_id = int(self.tmcc_id_text.value)
            self._scope_tmcc_ids[scope] = tmcc_id
        if scope in {CommandScope.ENGINE, CommandScope.TRAIN} and tmcc_id:
            state = state or self._state_store.get_state(scope, tmcc_id, False)
            if isinstance(targets, str):
                for ix, target in enumerate(targets.split(",")):
                    target = target.strip()
                    delay = 0.100 if ix else 0.0
                    self.do_engine_command(tmcc_id, target, data, scope, do_entry, do_ops, repeat, state, delay)
            else:
                self.do_engine_command(tmcc_id, targets, data, scope, do_entry, do_ops, repeat, state, delay)

    @staticmethod
    def get_repeats(cmd: CommandDefEnum, repeat: int) -> int:
        if cmd in REPEAT_EXCEPTIONS:
            return REPEAT_EXCEPTIONS.get(cmd)
        if cmd.is_alias and cmd.alias_enum in REPEAT_EXCEPTIONS:
            return REPEAT_EXCEPTIONS.get(cmd.alias_enum)
        return repeat

    def do_engine_command(
        self,
        tmcc_id: int | Any,
        targets: str | list[str] | tuple[str],
        data: int,
        scope: CommandScope,
        do_entry: bool,
        do_ops: bool,
        repeat: int,
        state: S,
        delay: float = 0.0,
    ) -> bool:
        sent_command = False
        if isinstance(targets, str):
            targets = [targets]
        for target in targets:
            if state and state.is_legacy:
                # there are a few special cases
                if target in {SMOKE_ON, SMOKE_OFF}:
                    cmd_enum = self.get_tmcc2_smoke_cmd(target, state)
                else:
                    cmd_enum = TMCC2EngineOpsEnum.look_up(target)
                    if cmd_enum is None:
                        cmd_enum = SequenceCommandEnum.by_name(target)
            else:
                cmd_enum = TMCC1EngineCommandEnum.by_name(target)
            if cmd_enum:
                cmd = CommandReq.build(cmd_enum, tmcc_id, data, scope)
                repeat = self.get_repeats(cmd_enum, repeat)
                cmd.send(repeat=repeat, delay=delay)
                if do_ops is True and self._keypad_view.is_entry_mode is True:
                    self.ops_mode(update_info=True)
                elif do_entry and self._keypad_view.is_entry_mode is False:
                    self._keypad_view.entry_mode(clear_info=False)
                sent_command = True
                break
            else:
                target = COMMAND_FALLBACKS.get(target, None)
                if target:
                    if self.do_engine_command(tmcc_id, target, data, scope, do_entry, do_ops, repeat, state, delay):
                        sent_command = True
                        break
        return sent_command

    @staticmethod
    def get_tmcc2_smoke_cmd(cmd: str, state: EngineState) -> TMCC2EngineOpsEnum | None:
        cur_smoke = state.smoke_level
        if cmd == SMOKE_ON:  # increase smoke
            if cur_smoke == TMCC2EffectsControl.SMOKE_OFF:
                return TMCC2EffectsControl.SMOKE_LOW
            elif cur_smoke == TMCC2EffectsControl.SMOKE_LOW:
                return TMCC2EffectsControl.SMOKE_MEDIUM
            elif cur_smoke == TMCC2EffectsControl.SMOKE_MEDIUM:
                return TMCC2EffectsControl.SMOKE_HIGH
        elif cmd == SMOKE_OFF:  # decrease smoke
            if cur_smoke == TMCC2EffectsControl.SMOKE_LOW:
                return TMCC2EffectsControl.SMOKE_OFF
            elif cur_smoke == TMCC2EffectsControl.SMOKE_MEDIUM:
                return TMCC2EffectsControl.SMOKE_LOW
            elif cur_smoke == TMCC2EffectsControl.SMOKE_HIGH:
                return TMCC2EffectsControl.SMOKE_MEDIUM
        return None

    def on_acc_command(self, target: str, data: int | None = None) -> None:
        state = self.active_state
        if isinstance(state, AccessoryState):
            acc_enum = TMCC1AuxCommandEnum.by_name(target)
            if acc_enum:
                tmcc_id = state.tmcc_id
                CommandReq.build(acc_enum, tmcc_id, data).send()
