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
import time
import tkinter as tk
from collections import deque
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Generic, TypeVar, cast

from guizero import App, Box, Combo, Picture, PushButton, Text, TitleBox

from .accessory_bindings import PANEL_CONTEXT_CHAINS, PANEL_GENERIC, ROUTE_CONTEXT, SWITCH_CONTEXT
from .admin_panel import ADMIN_TITLE, AdminPanel
from .amc2_ops_panel import Amc2OpsPanel
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
    FIRE_ROUTE_KEY,
    HALT_KEY,
    KEY_TO_COMMAND,
    REPEAT_EXCEPTIONS,
    SCOPE_TO_SET_ENUM,
    SMOKE_OFF,
    SMOKE_ON,
    STATION_DIALOGS,
    STEWARD_DIALOGS,
    SWITCH_OUT_KEY,
    SWITCH_THRU_KEY,
    TOWER_DIALOGS,
    send_lcs_off_command,
    send_lcs_on_command,
)
from .image_presenter import ImagePresenter
from .keypad_view import ACCESSORY_THROTTLE_MAX, ACCESSORY_THROTTLE_MIN, KeypadView
from .lighting_panel import LightingPanel
from .popup_manager import PopupManager
from .rr_speed_panel import RrSpeedPanel
from .state_info_overlay import StateInfoOverlay
from ..accessories.accessory_base import preload_accessory_button_image_paths
from ..accessories.configured_accessory import ConfiguredAccessorySet, DEFAULT_CONFIG_FILE
from ..components.hold_button import HoldButton
from ..components.scrolling_text import ScrollingText
from ..components.swipe_detector import SwipeDetector, event_screen_y, event_targets
from ..guizero_base import GuiZeroBase, resolve_font_family
from ...db.accessory_state import AccessoryState
from ...db.component_state import ComponentState, LcsProxyState, RouteState, SwitchState
from ...db.component_state_store import ComponentStateStore
from ...db.engine_state import EngineState, TrainState
from ...db.irda_state import IrdaState
from ...db.state_watcher import StateWatcher
from ...pdi.pdi_listener import PdiDispatcher
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
    TMCC1SyncCommandEnum,
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
AccessoryConfigSignature = tuple[str, bool, int | None, int | None]


TURN_ON_IMAGE = "on_button.jpg"
TURN_OFF_IMAGE = "off_button.jpg"
BULB_OFF_IMAGE = "bulb-power-off.png"
BULB_ON_IMAGE = "bulb-power-on.png"
OP_ACC_IMAGE = "op-acc.jpg"
# The generic-panel return control's purpose-drawn icons (see engine_gui_conf); preloaded here
# with every other button image so the first toggle does not stall on disk.
BPC2_OP_IMAGE = "op-bpc2.jpg"
ASC2_OP_IMAGE = "op-asc2.jpg"
OP_SCREEN_IMAGE = "op-screen.jpg"


@lru_cache(maxsize=1)
def _common_button_image_paths() -> dict[str, str | None]:
    return {
        TURN_ON_IMAGE: find_file(TURN_ON_IMAGE),
        TURN_OFF_IMAGE: find_file(TURN_OFF_IMAGE),
        BULB_ON_IMAGE: find_file(BULB_ON_IMAGE),
        BULB_OFF_IMAGE: find_file(BULB_OFF_IMAGE),
        OP_ACC_IMAGE: find_file(OP_ACC_IMAGE),
        BPC2_OP_IMAGE: find_file(BPC2_OP_IMAGE),
        ASC2_OP_IMAGE: find_file(ASC2_OP_IMAGE),
        OP_SCREEN_IMAGE: find_file(OP_SCREEN_IMAGE),
    }


def _common_button_image_path(filename: str) -> str | None:
    return _common_button_image_paths().get(filename)


def preload_engine_button_image_paths() -> None:
    _common_button_image_paths()


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
        enable_editing: bool = True,
        config_file: str = DEFAULT_CONFIG_FILE,
        full_screen: bool = True,
        x_offset: int = 0,
        y_offset: int = 0,
        stand_alone: bool = True,
        parent: Box | None = None,
        parent_gui: GuiZeroBase | None = None,
        compact: bool = False,
        show_halt: bool = True,
        linked_car_transfer: Callable[[EngineState], bool] | None = None,
        button_divisor: float | None = None,
    ) -> None:
        if stand_alone and (parent is not None or parent_gui is not None):
            raise ValueError("A standalone EngineGui cannot have a parent")
        if not stand_alone and (parent is None or parent_gui is None):
            raise ValueError("An embedded EngineGui requires both parent and parent_gui")

        # have to call parent init after all variables are set up
        base_kwargs = {
            "title": "Engine GUI",
            "width": width,
            "height": height,
            "enabled_bg": enabled_bg,
            "disabled_bg": disabled_bg,
            "enabled_text": enabled_text,
            "disabled_text": disabled_text,
            "active_bg": active_bg,
            "inactive_bg": inactive_bg,
            "scale_by": scale_by,
            "full_screen": full_screen,
            "x_offset": x_offset,
            "y_offset": y_offset,
        }
        if not stand_alone:
            base_kwargs["stand_alone"] = False
        if button_divisor is not None:
            base_kwargs["button_divisor"] = button_divisor
        GuiZeroBase.__init__(self, **base_kwargs)
        self._parent = parent
        self._parent_gui = parent_gui
        self._compact = compact
        self._show_halt = show_halt
        self._linked_car_transfer = linked_car_transfer
        if parent_gui is not None:
            self._app = parent_gui.app
            self._sync_state = parent_gui.sync_state
            self.attach_to_parent_queue(parent_gui)

        # preload common images
        self._engine_buttons_future = self._executor.submit(preload_engine_button_image_paths)
        self._acc_buttons_future = self._executor.submit(preload_accessory_button_image_paths)

        self.digital_font = None
        self._last_header_options = None
        self.auto_scroll = auto_scroll
        self.image_file = None
        self._engine_tmcc_id = None
        self._engine_state = None
        self._image = None
        self.repeat = repeat
        self.num_recents = num_recents
        self._sensor_track_id = sensor_track_id
        self.slider_height = self.button_size * 4
        self.enable_editing = enable_editing
        self._scale_factor: float = 1.0

        self.scope_size = int(round(self.width / 5))
        self.grid_pad_by = 2
        self.avail_image_height = self.avail_image_width = None
        self.options = [self.title]

        self.box = self.acc_box = self.y_offset = None
        self.turn_on_image = _common_button_image_path(TURN_ON_IMAGE)
        self.turn_off_image = _common_button_image_path(TURN_OFF_IMAGE)
        self.power_off_path = _common_button_image_path(BULB_OFF_IMAGE)
        self.power_on_path = _common_button_image_path(BULB_ON_IMAGE)
        self.op_acc_image = _common_button_image_path(OP_ACC_IMAGE)

        self._btn_images = []
        self._dim_cache = {}
        self._scope_buttons = {}
        self._scope_tmcc_ids = {}
        self._scope_watchers = {}
        self._recents_queue: dict[CommandScope, UniqueDeque[S]] = {}
        self._train_linked_queue: UniqueDeque[EngineState] = UniqueDeque()
        self._options_to_state = {}
        # components we created ourselves from the keypad, and that the Base 3 has not yet
        # confirmed; they stay out of the recents queue and the scope catalog until named
        self._provisional: set[tuple[CommandScope, int]] = set()

        self.entry_cells = set()
        self.ops_cells = set()
        self.aux_cells = set()
        self.numeric_btns = {}
        self.scope = scope if scope else CommandScope.ENGINE
        self.initial = tmcc_id
        self._active_engine_state = self._active_train_state = None
        self._is_train_linked_cars = False
        self._actual_current_engine_id = 0

        self._sensor_track_watcher = None
        self._sensor_track_state = None

        # various boxes
        self.emergency_box = self.info_box = self.keypad_box = self.scope_box = self.name_box = self.image_box = None
        self.amc2_ops_box = None
        self.controller_box = self.controller_keypad_box = None
        self.controller_throttle_box = self.controller_info_box = None

        self.emergency_box_width = self.emergency_box_height = None

        # various buttons
        self.halt_btn = self.reset_btn = self.linked_cars_btn = self.off_btn = self.on_btn = self.set_btn = None
        self.fire_route_btn = self.switch_thru_btn = self.switch_out_btn = self.keypad_keys = None
        self.sw_set_btn = self.info_btn = self.acc_generic_btn = None

        # various fields
        self.tmcc_id_box = self.tmcc_id_text = self._nbi = self.header = None
        self.name_text = self.titlebar_height = self.popup_position = None
        self.on_key_cell = self.off_key_cell = None
        self.image = None
        self._acc_overlay = None
        self.clear_key_cell = self.enter_key_cell = self.set_key_cell = self.fire_route_cell = None
        self.switch_thru_cell = self.switch_out_cell = self.sw_set_cell = self.info_cell = None
        self.acc_generic_cell = None
        self.avail_image_height_engine = None

        # Sensor Track
        self.sensor_track_box = self.sensor_track_buttons = self.sensor_track_generic_btn = None
        # The (tmcc_id, sequence) this Sensor Track is believed to hold: what an incoming
        # IrdaState last reported, or what the pad last wrote. Read as "where a revert with
        # nothing to undo goes back to".
        self._sensor_track_selected: tuple[int, int] | None = None
        # The pair the most recent select displaced, and so what a revert puts back. One-shot:
        # cleared by the revert that spends it. Carries the id as well as the value so a pane
        # re-scoped to another Sensor Track cannot be reverted to this one's option.
        self._sensor_track_undo: tuple[int, int] | None = None

        # BPC2/ASC2
        self.ac_on_cell = self.ac_off_cell = self.ac_status_cell = None
        self.ac_off_btn = self.ac_on_btn = self.ac_status_btn = None
        self.ac_aux1_cell = self.ac_aux1_btn = None
        self.ac_op_cell = self.ac_op_btn = None
        self.acc_throttle_box = self.acc_throttle_title_box = None
        self.acc_throttle_level = self.acc_throttle = None

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

        # don't ask
        self._isd = None  # swipe detector for engine image field
        self._isd_area = None  # swipe detector for the margin beside the image
        self._image_parent = None  # container that owns that margin
        self._admin_panel = None
        self._catalog_panel = None
        self._lighting_panel = None
        self._rr_speed_panel = None
        self._state_info = None
        self._bell_horn_panel = None
        self._amc2_ops_panel: Amc2OpsPanel | None = None
        self._accessory_view: dict[int, Box | None] = {}
        self.engine_ops_cells = {}
        self._transition_depth = 0
        self._options_rebuild_pending = False
        self._last_displayed_scope: CommandScope | None = None
        self._last_displayed_tmcc_id: int | None = None

        # callbacks
        self._scoped_callbacks = {
            CommandScope.ROUTE: self.on_new_route,
            CommandScope.SWITCH: self.on_new_switch,
            CommandScope.ACC: self.on_new_accessory,
            CommandScope.ENGINE: self.on_new_engine,
            CommandScope.TRAIN: self.on_new_train,
            CommandScope.IRDA: self.on_sensor_track_update,
        }

        # helpers to reduce code
        self._popup: PopupManager = PopupManager(self)
        self._image_presenter: ImagePresenter = ImagePresenter(self)
        self._controller_view: ControllerView = ControllerView(self)
        self._keypad_view: KeypadView = KeypadView(self)

        # get configured accessories
        self._accessory_config_file = config_file
        self._caa = ConfiguredAccessorySet.from_file(config_file, verify=True)
        self._caap = ConfiguredAccessoryAdapterProvider(self._caa, self)
        self._acc_tmcc_to_adapter: dict[int, ConfiguredAccessoryAdapter] = {}
        self._accessory_overlay_prewarm_queue = deque()
        self._accessory_overlay_prewarm_active = False
        self._accessory_overlay_prewarm_generation = 0
        self._accessory_config_poll_interval = 1.0
        self._accessory_config_debounce = 0.5
        self._accessory_config_watcher_future = None
        self._accessory_config_last_signature = self._accessory_config_signature(self.accessories.path)
        self._accessory_config_pending_signature: AccessoryConfigSignature | None = None
        self._accessory_config_pending_since: float | None = None

        # tell parent we've set up variables and are ready to proceed
        self.init_complete()

    def __call__(self, state: S):
        if isinstance(state, ComponentState) and not self._shutdown_flag.is_set():
            self._message_queue.put((self._rebuild_state_caches, [state]))

    @property
    def image_presenter(self) -> ImagePresenter:
        return self._image_presenter

    @property
    def root(self) -> App | Box:
        return self._parent or self.app

    @property
    def compact(self) -> bool:
        return self._compact

    @property
    def info_box_height(self) -> int | None:
        return max(44, int(self.button_size * 0.55)) if self._compact else None

    def fit_info_box_height(self, required_height: int) -> int:
        compact_height = self.info_box_height
        return compact_height if compact_height is not None else required_height

    def fit_info_id_width(self, actual_width: int, required_width: int) -> int:
        return max(actual_width, required_width) if self._compact else actual_width

    def fit_emergency_box_width(self, measured_width: int) -> int:
        return self.width if getattr(self, "_compact", False) else measured_width

    @property
    def info_id_text_size(self) -> int:
        return self.s_18 if self._compact else self.s_20

    @property
    def info_name_text_size(self) -> int:
        return self.s_18

    @property
    def sensor_track_row_pady(self) -> int:
        # The image box above the keypad is sized once, from the keypad's height, and
        # ImagePresenter.calc_box_size caches that in avail_image_height. When the taller
        # Sequence box replaces the keypad, the image keeps its keypad-sized allocation,
        # so the extra height the 10 radio rows need has nowhere to come from and the last
        # row spills off the bottom of the compact (Steam Deck) pane. Trimming the per-row
        # padding reclaims ~60px there, which clears the shortfall with room to spare.
        # The taller portrait pane has no such problem, so it keeps the standard padding.
        return 5 if self._compact else 6

    def fit_image_box_size(self, available_height: int, available_width: int) -> tuple[int, int]:
        if not self._compact:
            return available_height, available_width
        fitted_height = min(available_height, int(self.height * 0.15), available_width // 3)
        fitted_height = max(0, fitted_height)
        return fitted_height, fitted_height * 3

    @property
    def show_halt(self) -> bool:
        return self._show_halt

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

    @property
    def popup_manager(self) -> PopupManager:
        return self._popup

    def scope_tmcc_id(self, scope: CommandScope | None = None) -> int:
        scoped = scope or self.scope
        return self._scope_tmcc_ids.get(scoped, 0)

    def is_accessory_view(self, tmcc_id: int) -> bool:
        if tmcc_id in self._accessory_view:
            return True
        return self.accessory_provider is not None and self.accessory_provider.adapters_for_tmcc_id(tmcc_id)

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
    def amc2_ops_panel(self) -> Amc2OpsPanel | None:
        return self._amc2_ops_panel

    @amc2_ops_panel.setter
    def amc2_ops_panel(self, panel: Amc2OpsPanel | None) -> None:
        assert self._amc2_ops_panel is None
        self._amc2_ops_panel = panel

    @property
    def scale_factor(self) -> float:
        return self._scale_factor

    def rescale_by(self, size: int, maximum: int = None) -> int:
        if self._scale_factor > 1.0:
            if maximum:
                return min(int(size * self._scale_factor), maximum)
            return int(size * self._scale_factor)
        return size

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

    def clear_record(self, state: S = None):
        state = state or self.active_state
        if state and state.is_deletable:
            # clear this state on the Base 3; this will take some time to percolate
            state.clear(notify=False, clear_db=True)
            self._message_queue.put((self._rebuild_state_caches, [state]))

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
        root = self.root
        self.digital_font = resolve_font_family(app.tk, "DigitalDream", fallback="DigitalDream")

        # customize label
        self.header = cb = Combo(
            root,
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

        # Reserve the bottom edge before any top-aligned content is packed.
        #
        # Both modes, deliberately. pack allots parcels in creation order, so a later child that
        # expands -- which is what makes a popup panel reach down to these buttons -- takes its
        # space out of whatever has not been claimed yet. With the scope box created last, as
        # portrait used to do, that includes the scope box itself and the controller keypad. The
        # box renders at the bottom either way, so there is no visible difference today; the
        # difference is that an expanding sibling can no longer push these buttons off the
        # bottom edge. make_scope_box is idempotent and make_scope goes through it, so this is
        # purely a matter of when the widget joins the pack order.
        self.make_scope_box(root)

        # Make the emergency buttons, including Halt and Reset
        self.make_emergency_buttons(root)

        # Make info box for TMCC ID and Road Name
        self.make_info_box(root)

        # make selection box and keypad
        self._engine_buttons_future.result()  # wait for common engine buttons to load
        self._keypad_view.build(root)

        # precreate extra functions popup
        self._popup.get_or_create("extra_functions", "Additional Options", self.build_extra_functions_body)

        # make engine/train controller UI
        self._controller_view.build(root)

        # make scope buttons
        self.make_scope(root)

        # Simulate the ops-mode display to compute and cache the engine-image
        # baseline height even when no engine image is selected. This ensures
        # accessory and other modes use the engine ops-mode available height.
        # ONE geometry pass at the end
        self._compute_engine_image_baseline()

        # Finally, resize image box
        available_height, available_width = (
            (self.avail_image_height, self.avail_image_width)
            if self.avail_image_height and self.avail_image_width
            else self._image_presenter.calc_box_size()
        )
        self.image_box.tk.config(height=available_height, width=available_width)

        # calculate offset for popups
        x = self.info_box.tk.winfo_rootx()
        y = self.info_box.tk.winfo_rooty() + self.info_box.tk.winfo_reqheight()
        if root is not app:
            x -= root.tk.winfo_rootx()
            y -= root.tk.winfo_rooty()
        self.popup_position = (x, y)

        # create watcher for sensor track, if needed
        if self._sensor_track_id:
            state = self._state_store.get_state(CommandScope.IRDA, self._sensor_track_id)
            action = self.on_state_changed_action(state)
            if state:
                self._sensor_track_watcher = StateWatcher(state, action)

        if self.initial:
            app.after(100, self.update_component_info, [self.initial])

        # prewarm some images after initial display settles to avoid flashing
        # Delayed scheduling on GUI thread prevents redraws during startup
        self.app.tk.after_idle(self._popup.preload_images)
        for image in (self.power_on_path, self.power_off_path, self.turn_off_image, self.op_acc_image):
            self.app.tk.after_idle(lambda img=image: self.get_titled_image(img))
        self.app.tk.after(750, self._start_accessory_overlay_prewarm)
        self._start_accessory_config_watcher()

        # register this class to receive delete events
        PdiDispatcher.get().subscribe_delete(self)

    def destroy_gui(self) -> None:
        self._stop_accessory_config_watcher()
        if PdiDispatcher.is_built():
            PdiDispatcher.get().unsubscribe_delete(self)
        self.clear_cache()
        self.engine_ops_cells.clear()
        self.box = None
        self.acc_box = None
        self._image = None

    def destroy_embedded(self) -> None:
        if self._stand_alone:
            raise RuntimeError("destroy_embedded is only valid for an embedded EngineGui")
        self.close()
        self.destroy_gui()
        self._finalize_gui_resources()

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

    def _bind_image_long_press(self) -> None:
        if self._isd:
            self._isd.on_long_press = self.on_info

    def _unbind_image_long_press(self) -> None:
        if self._isd:
            self._isd.on_long_press = None

    def on_state_info_closed(self, _overlay: Box | None = None) -> None:
        self._bind_image_long_press()

    def on_info(self, state: S = None) -> None:
        """Shows state information in popup overlay"""
        is_new = state is not None and state.is_comp_data_empty
        state = state or self.active_state
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
        self._state_info.update(state, new=is_new)
        self._unbind_image_long_press()
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
        self._acc_buttons_future.result()  # make sure accessory buttons are loaded
        tmcc_id = self._scope_tmcc_ids[self.scope]
        acc.activate_tmcc_id(tmcc_id)
        self.name_text.value = acc.name
        overlay = self._popup.get_or_create(acc.instance_id, "", acc, self.restore_accessory_info)
        setattr(overlay, "caa", acc)
        self.set_accessory_view(tmcc_id, acc)
        self.app.tk.after_idle(self._refresh_accessory_image, tmcc_id)
        return overlay

    def _refresh_accessory_image(self, tmcc_id: int) -> None:
        self._image_presenter.refresh_box_size()
        self._image_presenter.update(tmcc_id=tmcc_id)

    def _start_accessory_overlay_prewarm(self, generation: int | None = None) -> None:
        generation = self._accessory_overlay_prewarm_generation if generation is None else generation
        if generation != self._accessory_overlay_prewarm_generation:
            return
        if self._shutdown_flag.is_set() or self._accessory_overlay_prewarm_active:
            return
        if not self._acc_buttons_future.done():
            self.app.tk.after(50, lambda: self._start_accessory_overlay_prewarm(generation))
            return
        try:
            self._acc_buttons_future.result()
        except Exception as e:
            log.exception("Unable to prewarm accessory overlays because button image preload failed", exc_info=e)
            return
        self._accessory_overlay_prewarm_active = True
        self._accessory_overlay_prewarm_queue = deque(self.accessories.configured_all())
        self.app.tk.after(25, lambda: self._prewarm_next_accessory_overlay(generation))

    def _prewarm_next_accessory_overlay(self, generation: int | None = None) -> None:
        generation = self._accessory_overlay_prewarm_generation if generation is None else generation
        if generation != self._accessory_overlay_prewarm_generation:
            return
        if self._shutdown_flag.is_set():
            self._accessory_overlay_prewarm_active = False
            return
        while self._accessory_overlay_prewarm_queue:
            cfg = self._accessory_overlay_prewarm_queue.popleft()
            acc = self.accessory_provider.get(cfg)
            if acc.overlay is None:
                tmcc_ids = cfg.tmcc_ids
                if tmcc_ids:
                    acc.activate_tmcc_id(tmcc_ids[0])
                overlay = self._popup.get_or_create(acc.instance_id, "", acc, self.restore_accessory_info)
                setattr(overlay, "caa", acc)
            self.app.tk.after(25, lambda: self._prewarm_next_accessory_overlay(generation))
            return
        self._accessory_overlay_prewarm_active = False

    def reload_configured_accessories(self) -> bool:
        """
        Reread accessory_config.json and rebuild all configured accessory GUI state.
        """
        configured = self._load_configured_accessories()
        if configured is None:
            return False

        self._apply_configured_accessories(configured)
        return True

    def _load_configured_accessories(self) -> ConfiguredAccessorySet | None:
        try:
            return ConfiguredAccessorySet.from_file(self._accessory_config_file, verify=True)
        except Exception as e:
            log.exception("Unable to reload configured accessories", exc_info=e)
            return None

    @staticmethod
    def _accessory_config_signature(path: str | Path | None) -> AccessoryConfigSignature:
        if path is None:
            return "", False, None, None

        path = Path(path)
        resolved_path = str(path.expanduser().resolve(strict=False))
        try:
            stat = path.stat()
        except OSError:
            return resolved_path, False, None, None
        return resolved_path, True, stat.st_mtime_ns, stat.st_size

    def _watch_accessory_config_changes(self) -> None:
        while not self._shutdown_flag.is_set():
            try:
                self._check_accessory_config_change()
            except Exception as e:
                log.exception("Accessory config watcher failed while checking for changes", exc_info=e)
            self._shutdown_flag.wait(self._accessory_config_poll_interval)

    def _start_accessory_config_watcher(self) -> None:
        if self._shutdown_flag.is_set():
            return
        if self._accessory_config_watcher_future is not None:
            return
        self._accessory_config_last_signature = self._accessory_config_signature(self.accessories.path)
        self._accessory_config_watcher_future = self._executor.submit(self._watch_accessory_config_changes)

    def _stop_accessory_config_watcher(self) -> None:
        future = self._accessory_config_watcher_future
        self._accessory_config_watcher_future = None
        if future is not None:
            future.cancel()

    def _check_accessory_config_change(self) -> None:
        watched_path = ConfiguredAccessorySet.resolve_config_path(self._accessory_config_file)
        signature = self._accessory_config_signature(watched_path)
        if signature == self._accessory_config_last_signature:
            self._accessory_config_pending_signature = None
            self._accessory_config_pending_since = None
            return

        now = time.monotonic()
        if signature != self._accessory_config_pending_signature:
            self._accessory_config_pending_signature = signature
            self._accessory_config_pending_since = now
            return

        pending_since = self._accessory_config_pending_since
        if pending_since is None or now - pending_since < self._accessory_config_debounce:
            return

        configured = self._load_configured_accessories()
        if configured is None:
            self._accessory_config_pending_signature = None
            self._accessory_config_pending_since = None
            return

        self._schedule_configured_accessory_apply(configured)
        self._accessory_config_pending_signature = None
        self._accessory_config_pending_since = None

    def _schedule_configured_accessory_apply(self, configured: ConfiguredAccessorySet) -> None:
        if self._shutdown_flag.is_set():
            return
        self.app.tk.after(0, lambda: self._apply_changed_configured_accessories(configured))

    def _apply_changed_configured_accessories(self, configured: ConfiguredAccessorySet) -> None:
        if self._shutdown_flag.is_set():
            return
        self._apply_configured_accessories(configured)
        self._accessory_config_last_signature = self._accessory_config_signature(configured.path)

    def _apply_configured_accessories(self, configured: ConfiguredAccessorySet) -> None:
        old_overlay_keys = self._configured_accessory_overlay_keys()
        old_configured_tmcc_ids = self._configured_accessory_tmcc_ids(self.accessories)
        had_active_accessory_overlay = self._acc_overlay is not None

        with self._cv:
            self._caa = configured
            self._caap.set_configured_set(configured, drop_adapters=True)
            self._acc_tmcc_to_adapter.clear()
            self._accessory_view.clear()
            self._remove_removed_configured_accessory_options(
                old_configured_tmcc_ids - self._configured_accessory_tmcc_ids(configured)
            )
            self._discard_configured_accessory_overlays(old_overlay_keys)

            if had_active_accessory_overlay:
                self._show_accessory_entry_keypad()

            self._reset_catalog_configured_accessories()
            self._request_options_rebuild()
            self._restart_accessory_overlay_prewarm()

        log.info("Reloaded %d configured accessories from %s", len(configured.configured_all()), configured.path)
        self._accessory_config_last_signature = self._accessory_config_signature(configured.path)

    def _configured_accessory_overlay_keys(self) -> set[str]:
        keys: set[str] = set()
        try:
            for acc in self.accessories.configured_all():
                if acc.instance_id:
                    keys.add(acc.instance_id)
        except (AttributeError, ValueError):
            pass

        key = getattr(self._acc_overlay, "overlay_key", None)
        if isinstance(key, str) and key:
            keys.add(key)
        return keys

    @staticmethod
    def _configured_accessory_tmcc_ids(accessories) -> set[int]:
        tmcc_ids: set[int] = set()
        try:
            configured = accessories.configured_all()
        except (AttributeError, ValueError):
            return tmcc_ids

        for acc in configured:
            try:
                ids = acc.tmcc_ids
            except (AttributeError, ValueError):
                ids = ()
            for tmcc_id in ids:
                if isinstance(tmcc_id, int):
                    tmcc_ids.add(tmcc_id)

            try:
                tmcc_id = acc.tmcc_id
            except (AttributeError, ValueError):
                tmcc_id = None
            if isinstance(tmcc_id, int):
                tmcc_ids.add(tmcc_id)

        return tmcc_ids

    def _remove_removed_configured_accessory_options(self, removed_tmcc_ids: set[int]) -> None:
        if not removed_tmcc_ids:
            return
        queue = self._recents_queue.get(CommandScope.ACC)
        if not isinstance(queue, UniqueDeque):
            return

        retained = [state for state in queue if getattr(state, "tmcc_id", None) not in removed_tmcc_ids]
        if len(retained) == len(queue):
            return

        queue.clear()
        queue.extend(retained)

    def _discard_configured_accessory_overlays(self, keys: set[str]) -> None:
        self._popup.discard_acc_overlay_restore()
        if self._acc_overlay and getattr(self._acc_overlay, "visible", False):
            self._acc_overlay.hide()
        self._acc_overlay = None
        if keys:
            self._popup.forget(keys)

    def _show_accessory_entry_keypad(self) -> None:
        self.scope = CommandScope.ACC
        self._scope_tmcc_ids[CommandScope.ACC] = 0
        if self.tmcc_id_box:
            self.tmcc_id_box.text = f"{CommandScope.ACC.title} ID"
        for scope, button in getattr(self, "_scope_buttons", {}).items():
            if scope == CommandScope.ACC:
                button.bg = self._enabled_bg
                button.text_color = self._enabled_text
            else:
                button.bg = "white"
                button.text_color = "black"
        self._popup.close()
        self._keypad_view.scope_keypad(force_entry_mode=True, clear_info=True)
        if self.scope_box and not getattr(self.scope_box, "visible", True):
            self.scope_box.show()

    def _reset_catalog_configured_accessories(self) -> None:
        if self._catalog_panel is not None:
            self._catalog_panel.reset_configured_accessory_cache(scope=self.scope)

    def _restart_accessory_overlay_prewarm(self) -> None:
        self._accessory_overlay_prewarm_generation += 1
        generation = self._accessory_overlay_prewarm_generation
        self._accessory_overlay_prewarm_queue.clear()
        self._accessory_overlay_prewarm_active = False
        if not self._shutdown_flag.is_set():
            self.app.tk.after(25, lambda: self._start_accessory_overlay_prewarm(generation))

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

    @property
    def controller_profile(self):
        """The controller profile in force, read from the pane's host.

        Kept as a lookup rather than a copy: the profile belongs to the SteamDeckGui and
        a stale duplicate here would describe bindings that are no longer live. A
        stand-alone EngineGui has no host and so no profile.
        """
        return getattr(self._parent_gui, "controller_profile", None)

    def on_controls_panel(self) -> None:
        """Ask the host to show the controls help screen.

        The screen spans both panes, so the hosting SteamDeckGui owns it -- a pane-hosted
        popup could never be wider than its pane. A stand-alone GUI has no host and no
        controller, so there is nothing to show.
        """
        host = self._parent_gui
        if host is None or not hasattr(host, "on_show_controls"):
            log.debug("No controls screen available: %s has no controller host", type(self).__name__)
            return
        host.on_show_controls()

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

    @property
    def linked_car_states(self) -> tuple[EngineState, ...]:
        return tuple(self._train_linked_queue)

    @property
    def has_active_selection(self) -> bool:
        return bool(self._scope_tmcc_ids.get(self.scope, 0))

    def select_component(self, scope: CommandScope, tmcc_id: int) -> None:
        if not isinstance(scope, CommandScope):
            raise ValueError(f"Invalid command scope: {scope}")
        if not isinstance(tmcc_id, int) or tmcc_id <= 0:
            raise ValueError(f"Invalid TMCC ID: {tmcc_id}")
        self.on_scope(scope)
        self.update_component_info(tmcc_id)

    def get_options(self) -> list[str]:
        if self._separator is None:
            self._separator = "-" * int(3 * len(self.title) / 2)
        options = [self.title]
        add_sep = False
        with self._cv:
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
                    acc = None
                    if self.scope == CommandScope.ACC:
                        acc = self._acc_tmcc_to_adapter.get(state.tmcc_id)
                        if state.tmcc_id not in self._acc_tmcc_to_adapter:
                            acc = self.get_configured_accessory(state.tmcc_id)
                    if acc:
                        road_name = acc.name
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

    def _rebuild_state_caches(self, state: S):
        if state:
            with self._cv:
                self._provisional.discard((state.scope, state.tmcc_id))
                reselect_current = False
                if self._scope_tmcc_ids.get(state.scope, 0) == state.tmcc_id:
                    self._scope_tmcc_ids[state.scope] = 0
                    if self.scope == state.scope:
                        reselect_current = True
                watcher = self._scope_watchers.get(state.scope, None)
                if (
                    isinstance(watcher, StateWatcher)
                    and watcher.scope == state.scope
                    and watcher.tmcc_id == state.tmcc_id
                ):
                    watcher.shutdown()
                    self._scope_watchers[state.scope] = None
                if self.active_engine_state == state:
                    self._active_engine_state = None
                if self._active_train_state == state:
                    self._active_train_state = None
                    self._train_linked_queue.clear()
                if isinstance(self._catalog_panel, CatalogPanel) and self.scope == state.scope:
                    self._catalog_panel.configure(state.scope, force=True)
                recents = self._recents_queue.get(state.scope, None)
                if isinstance(recents, UniqueDeque) and state in recents:
                    recents.remove(state)
                    self._request_options_rebuild()
                if reselect_current:
                    if self._scope_tmcc_ids[state.scope] == 0:
                        self.display_most_recent(state.scope)
                        self.update_component_info()
                        # force entry mode if scoped tmcc_id is 0
                        force_entry_mode = False
                        if self._scope_tmcc_ids[state.scope] == 0 or self.active_state is None:
                            force_entry_mode = True
                        self._request_options_rebuild()
                        num_chars = 4 if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN} else 2
                        self.tmcc_id_text.value = f"{self._scope_tmcc_ids[self.scope]:0{num_chars}d}"
                        self._keypad_view.scope_keypad(force_entry_mode, True)

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
        if state and state.is_deleted:
            return
        self._active_engine_state = state
        if isinstance(state, EngineState):
            if self.name_text.value != state.name:
                self.name_text.value = state.name
            if self._active_train_state and state in self._active_train_state:
                # if we are operating on a train-linked car with the associated train
                # active in the Train scope tab, indicate that on the gui
                self._scope_buttons[CommandScope.TRAIN].bg = "lightgreen"
                self._is_train_linked_cars = True
            elif is_engine:
                # otherwise, indicate we are in "Engine": mode and tear down the
                # train-linked gui components
                if self._is_train_linked_cars:
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
            self._controller_view.update(state=state, throttle_state=throttle_state)

        # update info detail popup, if its visible
        if ops_mode_setup:
            pass
        elif self._state_info and self._state_info.visible:
            self._state_info.update(state)

    def on_new_train(self, state: TrainState = None, ops_mode_setup: bool = False) -> None:
        if state and state.is_deleted:
            return
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
                if self._train_linked_queue:
                    self._setup_train_link_gui(self._train_linked_queue[0])
                    if getattr(self, "linked_cars_btn", None):
                        self.linked_cars_btn.enabled = True
                else:
                    self._tear_down_link_gui()
            else:
                self._tear_down_link_gui()
            self._active_train_state = state
            self._request_options_rebuild()
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
        if getattr(self, "linked_cars_btn", None):
            self.linked_cars_btn.enabled = False
        self._active_train_state = None
        self._is_train_linked_cars = False
        self._request_options_rebuild()

    def clear_speed_limit(self) -> None:
        from ...pdi.base_req import BaseReq

        if self.throttle_state:
            state = self.throttle_state
            BaseReq.do_update_field("SPEED_LIMIT", 255, state, True)

    def set_speed_limit(self, speed_limit: int) -> None:
        from ...pdi.base_req import BaseReq

        if self.throttle_state:
            state = self.throttle_state
            BaseReq.do_update_field("SPEED_LIMIT", speed_limit, state, True)

    def on_new_route(self, state: RouteState = None):
        if state and state.is_deleted:
            return
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
        if state and state.is_deleted:
            return
        # must be called from app thread!!
        if state is None:
            tmcc_id = self._scope_tmcc_ids[CommandScope.SWITCH]
            state = self._state_store.get_state(CommandScope.SWITCH, tmcc_id, False) if 1 <= tmcc_id < 99 else None
        self._promote_if_populated(state)
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
        if state and state.is_deleted:
            return
        state = state if state else self.active_state
        tmcc_id = self._scope_tmcc_ids[CommandScope.ACC]
        self._promote_if_populated(state)
        if isinstance(state, AccessoryState):
            # keypad_view = getattr(self, "_keypad_view", None)
            if state.is_sensor_track:
                st_state = self._state_store.get_state(CommandScope.IRDA, tmcc_id, False)
                previously = self._sensor_track_selected
                if isinstance(st_state, IrdaState):
                    # Assigned to the widget rather than through the keypad's setter, and that
                    # is the difference that matters: this moves the dot alone and leaves the
                    # cursor where the operator put it, so a track reporting itself cannot
                    # cancel a step in progress.
                    self.sensor_track_buttons.value = st_state.sequence.value
                    # The one place the panel learns what the track actually holds, so it is
                    # where the pad's notion of "the option currently selected" is seeded. Any
                    # undo point goes with it: it belonged to a select made against whatever
                    # was showing before, which this report supersedes.
                    #
                    # Read defensively rather than trusted: the widget takes whatever it is
                    # given, but a value the pad cannot compare is one it cannot revert to, so
                    # it is better forgotten than half-remembered.
                    try:
                        self._sensor_track_selected = (tmcc_id, int(st_state.sequence.value))
                    except (TypeError, ValueError):
                        self._sensor_track_selected = None
                else:
                    self.sensor_track_buttons.value = None
                    self._sensor_track_selected = None
                self._sensor_track_undo = None
                self._seed_sensor_track_cursor(tmcc_id, previously)
            elif state.is_bpc2 or state.is_asc2:
                self.update_ac_status(state)
            elif state.is_amc2:
                if self._amc2_ops_panel:
                    self._amc2_ops_panel.update_from_state(state)
            # elif keypad_view and hasattr(keypad_view, "update_accessory_throttle_from_state"):
            #     keypad_view.update_accessory_throttle_from_state(state)
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

    def make_scope_box(self, app: App) -> Box:
        if self.scope_box is None:
            self.scope_box = Box(app, layout="grid", border=2, align="bottom")
        return self.scope_box

    def make_scope(self, app: App):
        button_height = int(round(40 * self._scale_by))
        scope_box = self.make_scope_box(app)
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

    def show_scope_catalog(self) -> None:
        # Toggle the scope catalog: if it is already showing in this panel,
        # close it; otherwise open it for the current scope.
        if self.catalog_visible:
            self.hide_scope_catalog()
            return
        pb = self._scope_buttons.get(self.scope)
        if pb is not None:
            self.on_scope_hold(pb)

    def hide_scope_catalog(self) -> None:
        panel = self._catalog_panel
        if panel is not None and panel.visible:
            self._popup.close(panel.overlay)

    @property
    def catalog_visible(self) -> bool:
        panel = self._catalog_panel
        return bool(panel is not None and panel.visible)

    @property
    def _open_chooser(self):
        """The StateInfo field whose choice list is up, if any."""
        info = self._state_info
        return info.active_chooser if info is not None else None

    @property
    def chooser_visible(self) -> bool:
        """Whether a choice list is open, so the D-pad drives it instead of the train."""
        return self._open_chooser is not None

    def move_chooser(self, forward: bool = True) -> bool:
        """Move the highlighted option. Returns whether there was a chooser to move."""
        chooser = self._open_chooser
        if chooser is None:
            return False
        chooser.move_choice(1 if forward else -1)
        return True

    def select_chooser(self) -> bool:
        """Commit the highlighted option -- D-pad right, or the A button."""
        chooser = self._open_chooser
        if chooser is None:
            return False
        chooser.commit_edit()
        return True

    def cancel_chooser(self) -> bool:
        """Abandon the choice and put the field back -- D-pad left."""
        chooser = self._open_chooser
        if chooser is None:
            return False
        chooser.cancel_edit()
        return True

    @property
    def admin_visible(self) -> bool:
        panel = self._admin_panel
        return bool(panel is not None and panel.visible)

    @property
    def controls_visible(self) -> bool:
        """Whether the host's controls screen is on display.

        Delegated and read through this pane because the input router resolves actions
        against the focused pane rather than the host.
        """
        return bool(getattr(self._parent_gui, "controls_visible", False))

    def page_controls(self, forward: bool = True) -> bool:
        """Page the host's controls screen, for the D-pad while it is displayed."""
        host = self._parent_gui
        if host is None or not hasattr(host, "page_controls"):
            return False
        return host.page_controls(forward)

    def close_controls(self) -> bool:
        """Close the host's controls screen for the X button while it is displayed."""
        host = self._parent_gui
        if host is None or not hasattr(host, "close_controls"):
            return False
        return host.close_controls()

    def on_admin_command(self, command: str, pressed: bool = True) -> bool:
        """Hold an admin panel button by name (QUIT, UPDATE, REBOOT, SHUTDOWN, ...).

        Rather than running the command outright, this drives the panel's own
        ``HoldButton``: ``pressed`` starts its hold, so the on-screen progress bar
        animates and the command fires only after ``hold_threshold`` seconds, exactly
        as for a finger. Releasing before then cancels it. A controller chord
        therefore gets the same dwell and the same feedback as the button it stands in
        for, with no second copy of the timing logic.

        A press is only honored while the panel is on screen, so a chord cannot
        reboot or shut down the machine from an ordinary operating screen. A release
        is always forwarded, so an in-flight hold can always be canceled.
        """
        panel = self._admin_panel
        if panel is None:
            return False
        if TMCC1SyncCommandEnum.by_name(command) is None:
            log.warning("Unknown admin command: %s", command)
            return False
        if not pressed:
            return panel.cancel_hold(command)
        if not self.admin_visible:
            return False
        return panel.begin_hold(command)

    @property
    def popup_visible(self) -> bool:
        popup = self._popup.current_popup
        return bool(popup is not None and getattr(popup, "visible", False))

    def close_popup(self) -> bool:
        if not self.popup_visible:
            return False
        self._popup.close()
        return True

    def select_catalog_entry(self) -> bool:
        panel = self._catalog_panel
        if panel is None or not panel.visible:
            return False
        return panel.select_highlighted()

    def scroll_catalog(self, delta: int) -> bool:
        panel = self._catalog_panel
        if panel is None or not panel.visible:
            return False
        return panel.move_highlight(delta)

    def scroll_catalog_to_end(self, to_top: bool) -> bool:
        # Jump the catalog highlight to the first (``to_top``) or last entry,
        # mirroring the controller's shoulder buttons while the catalog is open
        # (L1 = first entry, R1 = last). This only moves the highlight; it does not
        # select/activate the entry (the user confirms it separately), so the
        # catalog stays open.
        panel = self._catalog_panel
        if panel is None or not panel.visible:
            return False
        return panel.move_highlight_to_end(to_top)

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
        self._begin_transition()
        try:
            # a forced accessory panel does not survive a scope press
            self._keypad_view.set_panel_kind_override(None)
            self.scope_box.hide()
            force_entry_mode = False
            clear_info = True
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
            if not held:
                self.update_component_info()
            # force entry mode if scoped tmcc_id is 0
            if self._scope_tmcc_ids[scope] == 0 or self.active_state is None:
                force_entry_mode = True
            self._request_options_rebuild()
            num_chars = 4 if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN} else 2
            self.tmcc_id_text.value = f"{self._scope_tmcc_ids[scope]:0{num_chars}d}"
            self.scope_box.show()
            self._keypad_view.scope_keypad(force_entry_mode, clear_info)
        finally:
            self._end_transition()

    def display_most_recent(self, scope: CommandScope) -> None:
        """
        Display the most recent scoped component in the recents queue.
        """
        with self._cv:
            recents = self._recents_queue.get(scope, None)
            if isinstance(recents, UniqueDeque) and len(recents) > 0:
                state = recents[0]
                self._scope_tmcc_ids[scope] = state.tmcc_id

    def create_provisional_component(self, scope: CommandScope, tmcc_id: int) -> S:
        """
        Materialize a provisional component record for the given scope and TMCC ID, using the
        same primitive the Set key does. The record is a real store entry with empty comp data,
        but is kept out of recents and the catalog until it is named.
        """
        state = self.state_store.get_state(scope, tmcc_id, False)
        if state is None:
            state = ComponentStateStore.get_state(scope, tmcc_id, create=True)
            state.initialize(scope=scope, tmcc_id=tmcc_id)
        with self._cv:
            self._provisional.add((scope, tmcc_id))
            self._scope_tmcc_ids[scope] = tmcc_id
        return state

    def is_provisional(self, scope: CommandScope, tmcc_id: int) -> bool:
        return (scope, tmcc_id) in self._provisional

    def promote_component(self, state: S = None) -> bool:
        """
        Promote a provisional component into a fully-fledged one: it now belongs in the recents
        queue, the header options, and the scope catalog. Called once the component has been
        named, or once the Base 3 reports real data for it. A no-op for anything that isn't
        provisional.
        """
        state = state if state is not None else self.active_state
        if state is None:
            return False
        key = (state.scope, state.tmcc_id)
        with self._cv:
            if key not in self._provisional:
                return False
            self._provisional.discard(key)
        self.make_recent(state.scope, state.tmcc_id, state)
        self._request_options_rebuild()
        self._reset_catalog_configured_accessories()
        return True

    def on_show_generic_acc_panel(self) -> None:
        """Switch the display from an LCS-specific accessory panel to the generic one.

        The generic panel is the only one that carries Set Address, so it is the way to program
        a new device to this address. Routed through the keypad's panel override, the single
        decision point both the drawn keys and the gamepad context chain read, so the pad
        follows the screen without being told separately.
        """
        self._popup.close()
        self._keypad_view.set_panel_kind_override(PANEL_GENERIC)
        self.ops_mode(update_info=False)

    def on_show_native_acc_panel(self) -> None:
        """Return the display to whatever panel this component's own flags call for."""
        self._popup.close()
        self._keypad_view.set_panel_kind_override(None)
        self.ops_mode(update_info=False)

    def _promote_if_populated(self, state: S = None) -> None:
        """
        Promote a provisional component the moment the Base 3 answers for it; an empty comp
        data record is the marker that says we're still waiting.
        """
        if state is None or getattr(state, "is_comp_data_empty", True):
            return
        if self.is_provisional(state.scope, state.tmcc_id):
            self.promote_component(state)

    def make_recent(self, scope: CommandScope, tmcc_id: int, state: S = None) -> bool:
        self._popup.close()
        log.debug(f"Pushing current: {scope} {tmcc_id} {self.scope} {self.tmcc_id_text.value}")
        with self._cv:
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
                    self._request_options_rebuild()
                    return True
        return False

    def show_next_component(self) -> None:
        self._popup.close()
        with self._cv:
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
        with self._cv:
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
        with self._cv:
            new_options = tuple(self.get_options())

            if new_options == getattr(self, "_last_header_options", None):
                return

            self._last_header_options = new_options

            self.header.clear()
            for option in new_options:
                self.header.append(option)

            if new_options:
                self.header.select_default()

    def _begin_transition(self) -> None:
        self._transition_depth += 1

    def _end_transition(self) -> None:
        self._transition_depth = max(0, self._transition_depth - 1)
        if self._transition_depth == 0 and self._options_rebuild_pending:
            self._options_rebuild_pending = False
            self.rebuild_options()

    def _request_options_rebuild(self) -> None:
        if self._transition_depth > 0:
            self._options_rebuild_pending = True
        else:
            self.rebuild_options()

    def make_info_box(self, app: App):
        self.info_box = info_box = Box(app, layout="left", border=2, align="top")
        info_height = self.info_box_height

        # ───────────────────────────────
        # Left: ID box
        # ───────────────────────────────
        self.tmcc_id_box = tmcc_id_box = TitleBox(info_box, f"{self.scope.title} ID", align="left")
        tmcc_id_box.text_size = self.s_10 if self._compact else self.s_12
        self.tmcc_id_text = Text(tmcc_id_box, text="0000", align="left", bold=True, width=5)
        self.tmcc_id_text.text_color = "blue"
        self.tmcc_id_text.text_size = self.info_id_text_size

        # ───────────────────────────────
        # Right: Road Name box
        # ───────────────────────────────
        self.name_box = name_box = TitleBox(info_box, "Road Name", align="right")
        name_box.text_size = self.s_10 if self._compact else self.s_12
        self.name_text = ScrollingText(
            name_box,
            text="",
            align="top",
            bold=True,
            width="fill",
            auto_scroll=self.auto_scroll,
        )
        self.name_text.text_color = "blue"
        self.name_text.text_size = self.info_name_text_size
        self.name_text.tk.config(justify="left", anchor="w")
        if self._compact:
            self.tmcc_id_text.tk.pack_configure(fill="both", expand=True)
            self.name_text.tk.pack_configure(fill="both", expand=True)
        else:
            name_box.tk.pack_propagate(False)  # preserve portrait behavior

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
                if info_height is not None:
                    required_height = max(tmcc_id_box.tk.winfo_reqheight(), name_box.tk.winfo_reqheight())
                    id_h = self.fit_info_box_height(required_height)
                    id_w = self.fit_info_id_width(
                        actual_width=tmcc_id_box.tk.winfo_width(),
                        required_width=tmcc_id_box.tk.winfo_reqwidth(),
                    )
                    tmcc_id_box.tk.config(width=id_w, height=id_h)
                    tmcc_id_box.tk.pack_propagate(False)
                    name_box.tk.pack_propagate(False)
                else:
                    id_h = tmcc_id_box.tk.winfo_height()
                    id_w = tmcc_id_box.tk.winfo_width()
                info_box.tk.config(width=total_w, height=id_h + 2)
                info_box.tk.pack_propagate(False)  # <- prevent any child resizing

                # Compute sub-box dimensions but don’t change the overall width later
                name_box.tk.config(height=id_h, width=max(0, total_w - id_w))
            except tk.TclError as e:
                log.exception(f"[adjust_road_name_box] failed: {e}", exc_info=e)

        # Schedule width/height fix after geometry update
        app.tk.after(10, adjust_road_name_box)

        # add a picture placeholder here, we may not use it
        self.image_box = image_box = Box(app, border=0, align="top")
        self.image = Picture(image_box, align="top")
        self._isd = SwipeDetector(self.image)
        self._bind_image_long_press()
        self._isd.on_swipe_right = self.show_previous_component
        self._isd.on_swipe_left = self.show_next_component
        # Also catch swipes that begin *beside* the image, which previously did
        # nothing at all. Two Tk facts decide where this has to be bound:
        #
        #   * ``image_box.tk.config(width=..., height=...)`` has no effect on its
        #     actual size: pack geometry propagation is on, so the box shrinks to hug
        #     the Picture (itself a Label sized to the image). The empty area beside
        #     the image therefore belongs to the box's *parent*, not to the box.
        #   * Tk delivers a press to the innermost widget only, and an intermediate
        #     frame never sees presses on its children. So binding the parent catches
        #     exactly the margin presses, and does not double-fire with the Picture's
        #     own detector.
        #
        # The parent spans the whole pane, so restrict the gesture to the image's
        # vertical band -- otherwise a swipe across background elsewhere in the pane
        # would change components too. No geometry is altered, only bindings, so
        # portrait layout is unaffected.
        # ``bind_directly`` matters here: the parent may already carry raw Tk
        # bindings (the Steam Deck panes bind <Button-1> for tap-to-focus), and
        # guizero's when_* hooks bind without add="+", which would silently replace
        # them -- <Button-1> and <ButtonPress-1> are the same Tk sequence.
        self._image_parent = app
        self._isd_area = SwipeDetector(app, should_start=self._press_starts_in_image_band, bind_directly=True)
        self._isd_area.on_swipe_right = self.show_previous_component
        self._isd_area.on_swipe_left = self.show_next_component
        self.image_box.hide()

    def _press_starts_in_image_band(self, event) -> bool:
        # True when a press on the image's parent container belongs to the image
        # region rather than the controls below it. The region is everything at or
        # above the bottom edge of the image box: the box hugs the image (pack
        # propagation ignores its configured size), so keying off its *top* edge too
        # would reject a press in the margin only slightly above or below the image.
        box = self.image_box
        if box is None:
            return False
        try:
            tkw = box.tk
            # winfo_ismapped() is the truth about being on screen; guizero's own
            # ``visible`` flag is a separate bookkeeping attribute.
            mapped = bool(tkw.winfo_ismapped())
            bottom = tkw.winfo_rooty() + tkw.winfo_height()
            # The event is a raw Tk event or a guizero EventData depending on how the
            # detector was bound, and the two spell screen coordinates and the target
            # widget differently.
            screen_y = event_screen_y(event)
            # When the parent is the toplevel (portrait), Tk *does* report presses on
            # descendants here, so ignore ones the Picture's own detector handles.
            #
            # Matched on the *Tk* widget, which identifies the Picture under either binding:
            # event_targets pairs a guizero widget with its .tk, and a raw Tk event names that
            # same Tk widget directly. It cannot go the other way -- Tk widget to guizero
            # widget -- so comparing against the guizero Picture matched nothing here, because
            # this detector is bound with bind_directly and sees raw Tk events. The guard never
            # fired, both detectors handled every swipe, and each advanced one component: two
            # advances per gesture, which with two engines lands you back where you started.
            # That is why portrait looked dead while the Deck, whose area detector hangs off a
            # pane and so never sees its children's presses, was fine.
            targets = event_targets(event)
            on_image = self.image is not None and self.image.tk in targets
            accepted = mapped and not on_image and screen_y is not None and screen_y <= bottom
            log.debug(
                "swipe region check: screen_y=%s image box bottom=%s mapped=%s on_image=%s -> %s",
                screen_y,
                bottom,
                mapped,
                on_image,
                "in" if accepted else "out",
            )
            return accepted
        except (AttributeError, tk.TclError) as exc:
            log.debug("swipe region check failed (%s); treating as outside the region", exc)
            return False

    def make_keypad_button(
        self,
        keypad_box: Box | TitleBox,
        label: str | None,
        row: int,
        col: int,
        size: int | None = None,
        image: str = None,
        generator: type = None,
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
            generator=generator,
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
        self._keypad_view.on_keypress(key)

    def on_set_key(self, scope: CommandScope, tmcc_id: int) -> None:
        # Fire the set address command; only valid for switches, accessories, and engines
        if scope != CommandScope.TRAIN and tmcc_id:
            cmd_enum = SCOPE_TO_SET_ENUM.get(scope, None)
            if isinstance(cmd_enum, CommandDefEnum):
                if scope == CommandScope.ENGINE and tmcc_id > 99:
                    cmd = CommandReq.build(TMCC2EngineCommandEnum.SET_ADDRESS, address=tmcc_id, scope=scope)
                else:
                    cmd = CommandReq.build(cmd_enum, address=tmcc_id, scope=scope)
                self.submit_request(cmd, repeat=self.repeat)
        else:
            self._keypad_view.entry_mode(clear_info=False)

    def do_command(self, key: str) -> None:
        cmd = KEY_TO_COMMAND.get(key, None)
        tmcc_id = self._scope_tmcc_ids[self.scope]
        if cmd:
            # special case HALT cmd
            if key == HALT_KEY:
                # do this command on GUI thread; we want it sent immediately
                cmd.send()
            elif tmcc_id > 0:
                if isinstance(cmd, CommandReq):
                    cmd.scope = self.scope
                    cmd.address = self._scope_tmcc_ids[self.scope]
                    self.submit_request(cmd, repeat=self.repeat)
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

    @property
    def switch_active(self) -> bool:
        """Whether this panel is controlling a track switch.

        Read by the Steam Deck input layer: a panel showing a switch has no engine to
        drive, so the triggers and sticks that would drive one throw the switch instead.
        True, while the panel's scope is Switch and one has been selected -- including while
        a replacement id is being keyed in, so a throw still reaches the switch. The panel
        is displaying rather than being swallowed until the entry is committed.
        """
        return self.scope == CommandScope.SWITCH and self.scope_tmcc_id(CommandScope.SWITCH) > 0

    def on_switch_command(self, thru: bool) -> None:
        """Throw the selected switch through (``thru``) or out.

        The controller's entry point for the switch keys. It goes through ``do_command`` so
        a switch thrown from the gamepad is indistinguishable from a press of the on-screen
        key -- same command, same address, same repeats. The guard keeps a stray
        action from addressing a switch command to whatever else the panel is showing.
        """
        if not self.switch_active:
            return
        self.do_command(SWITCH_THRU_KEY if thru else SWITCH_OUT_KEY)

    @property
    def input_contexts(self) -> tuple[str, ...]:
        """The gamepad contexts this panel is in, most specific first.

        Read by the Steam Deck input layer, which looks each control up in the context table
        and takes the first entry the chain defines. An empty tuple means an engine panel:
        nothing is remapped and nothing is claimed, so every control keeps the meaning it has
        everywhere else.

        Stated here rather than re-derived in the input layer so that the pad and the screen
        cannot disagree about what this panel is showing.
        """
        if self.switch_active:
            return (SWITCH_CONTEXT,)
        if self.route_active:
            return (ROUTE_CONTEXT,)
        return self._accessory_contexts

    @property
    def _accessory_contexts(self) -> tuple[str, ...]:
        """The chain for whichever accessory panel the keypad is showing, if any.

        Built from ``KeypadView.accessory_panel_kind`` rather than from the state flags again,
        so the pad follows the panel: a port that shows the generic panel is bound like any
        other accessory, LCS device or not. AMC2 reports nothing yet, and neither does an
        accessory scope with nothing selected -- there is no panel to claim for.
        """
        if self.scope == CommandScope.ACC and self.scope_tmcc_id(CommandScope.ACC) <= 0:
            return ()
        kind = self._keypad_view.accessory_panel_kind
        return PANEL_CONTEXT_CHAINS.get(kind, ())

    @property
    def route_active(self) -> bool:
        """Whether this panel is controlling a route.

        The switch story one-panel type along, and read by the Steam Deck input layer for
        the same reason: a panel showing a route has no engine to drive, so the triggers
        and sticks that would drive one fire the route instead. True on the same terms as
        ``switch_active`` -- scope is Route, and one has been selected, including while a
        replacement id is being keyed in.
        """
        return self.scope == CommandScope.ROUTE and self.scope_tmcc_id(CommandScope.ROUTE) > 0

    def on_route_command(self) -> None:
        """Fire the selected route.

        The controller's entry point for the fire key, and ``on_switch_command``'s twin: it
        goes through ``do_command`` so a route fired from the gamepad is indistinguishable
        from a press of the on-screen key. No argument, because a route has nothing to be
        fired the other way.
        """
        if not self.route_active:
            return
        self.do_command(FIRE_ROUTE_KEY)

    def on_lcs_command(self, on: bool) -> None:
        """Switch the selected power district or ASC2 output on or off.

        The controller's entry point for the On and Off keys, and ``on_switch_command``'s
        counterpart for an accessory: it resolves the state the same way ``do_command`` does
        for those keys and calls the same sender, so a district switched from the gamepad is
        indistinguishable from a press of the key on screen.
        """
        tmcc_id = self.scope_tmcc_id(self.scope)
        if tmcc_id <= 0:
            return
        state = self._state_store.get_state(self.scope, tmcc_id, False)
        if state is None:
            return
        if on:
            send_lcs_on_command(state)
        else:
            send_lcs_off_command(state)

    def on_asc2_momentary(self, pressed: bool) -> None:
        """Hold an ASC2 output on while a control is held and drop it on the release.

        Delegates to the keypad, which is where the on-screen momentary key sends from, so
        the two cannot send different requests. The release is delivered even if the panel's
        scope has changed since the press, so nothing is left energized.
        """
        self._keypad_view.asc2_control(pressed)

    def on_sensor_track_step(self, delta: int) -> bool:
        """Move the Sensor Track's Sequence cursor ``delta`` options. True, where it moved.

        Nothing is written and the radio dot does not move: the cursor moves and stops there, so
        crossing the ten options puts nothing on the wire and claims nothing on screen. The
        option settled on is the only one the track ever hears about, and
        ``on_sensor_track_select`` is what sends it.

        Returns whether anything moved, so a caller can tell a step from a press clamped at
        either end of the list.
        """
        return self._keypad_view.step_sensor_track_sequence(delta) is not None

    def _seed_sensor_track_cursor(self, tmcc_id: int, previously: tuple[int, int] | None) -> None:
        """Put the cursor on the option the track holds, where this pane is new to that track.

        The cursor is seeded rather than remembered: a position left somewhere by an earlier
        session must never be presented as this track's. But ``on_new_accessory`` runs on every
        accessory state update and not only on a change of id, so seeding unconditionally would
        yank the cursor out from under a step the moment the track reported itself. Hence the
        rule: seed on a change of id, or where there is no cursor at all; leave a refresh for
        the same id to move the dot and nothing else.
        """
        view = getattr(self, "_keypad_view", None)
        if view is None:
            return
        selected = self._sensor_track_selected
        if selected is None:
            # Nothing is known about this track, so there is nothing to point at either.
            view.set_sensor_track_cursor(None)
            return
        if previously is None or previously[0] != tmcc_id or view.sensor_track_cursor is None:
            view.set_sensor_track_cursor(selected[1])

    def on_sensor_track_select(self) -> None:
        """Write the Sequence option under the cursor, and remember what it replaced.

        The cursor is what the pad has stepped to, so it -- not the radio dot -- is what a
        select writes. The dot then moves onto it, and the two coincide, which is what "done"
        looks like on the panel.

        The id and the value are read together, here, so the write cannot go to a track other
        than the one the choice belongs to.

        An undo point is recorded only where the value actually changes: selecting the option
        already showing is a confirmation rather than a change, and taking it as one would
        throw away a real undo and leave the operator with nothing to go back to.
        """
        sequence = self._keypad_view.sensor_track_cursor
        if sequence is None:
            return
        tmcc_id = self.scope_tmcc_id(self.scope)
        if tmcc_id <= 0:
            return
        selected = self._sensor_track_selected
        if selected is not None and selected[0] == tmcc_id and selected[1] != sequence:
            self._sensor_track_undo = selected
        self._sensor_track_selected = (tmcc_id, sequence)
        self._keypad_view.set_sensor_track_sequence(sequence)
        self._keypad_view.send_sensor_track_sequence(tmcc_id, sequence)

    def on_sensor_track_revert(self) -> None:
        """Put back the option the last select replaced, or abandon a move not yet selected.

        Two cases, and the second is what makes revert useful before the first select has
        happened:

        * There is an undo point -- a select displaced something -- so the dot and the cursor go
          back to it and the write goes with it. One-shot: the undo point is spent, a revert
          being an undo rather than a way of flipping between two options.
        * There is none, so the stepping is simply abandoned: the cursor returns to the option
          the track is believed to hold, and **nothing is sent**, the track already being there.
          A write would be a command asked for by nobody.

        Either way it leaves nothing pending: the dot and the cursor end up on the same option,
        so no bar is left claiming a choice that has not been made.

        A pair belonging to another id is ignored rather than written, so a pane re-scoped to a
        second Sensor Track cannot be reverted to the first one's option.
        """
        tmcc_id = self.scope_tmcc_id(self.scope)
        undo = self._sensor_track_undo
        if undo is not None and undo[0] == tmcc_id:
            self._sensor_track_undo = None
            if not self._keypad_view.set_sensor_track_sequence(undo[1]):
                return
            self._sensor_track_selected = undo
            self._keypad_view.send_sensor_track_sequence(*undo)
            return
        selected = self._sensor_track_selected
        if selected is not None and selected[0] == tmcc_id:
            # The dot is already there, so this is the cursor coming back to it -- which is
            # exactly what abandoning an uncommitted move looks like.
            self._keypad_view.set_sensor_track_cursor(selected[1])

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

            self._controller_view.apply_engine_type(state)
            self._controller_view.show()

        # 3) Non-engine path (already moved)
        else:
            self._keypad_view.apply_ops_mode_ui_non_engine(state=state)
            if isinstance(self.active_state, AccessoryState):
                tmcc_id = self.active_state.tmcc_id
                if self.scope == CommandScope.ACC and self.is_accessory_view(tmcc_id):
                    view = self.get_accessory_view(tmcc_id)
                    acc = getattr(view, "caa", None)
                    if acc is None:
                        acc = self.get_configured_accessory(tmcc_id)
                    self.on_configured_accessory(acc)

        # 4) Preserve existing behavior
        if update_info:
            self.update_component_info(in_ops_mode=True)

    def _resolve_component_state(self, tmcc_id: int) -> tuple[int, S | None]:
        state = self.active_state
        if state and tmcc_id != state.tmcc_id:
            tmcc_id = state.tmcc_id
            self._scope_tmcc_ids[self.scope] = tmcc_id
        return tmcc_id, state

    def _is_same_display_selection(self, tmcc_id: int) -> bool:
        return self._last_displayed_scope == self.scope and self._last_displayed_tmcc_id == tmcc_id

    def _apply_component_labels(
        self,
        tmcc_id: int,
        state: S | None,
        not_found_value: str,
        num_chars: int,
    ) -> tuple[str, bool]:
        name = not_found_value
        update_button_state = True
        if state:
            if tmcc_id != int(self.tmcc_id_text.value):
                self.tmcc_id_text.value = f"{tmcc_id:0{num_chars}d}"
            if isinstance(state, AccessoryState):
                acc = None
                if self.is_accessory_view(tmcc_id):
                    view = self.get_accessory_view(tmcc_id)
                    acc = getattr(view, "caa", None)
                if acc is None:
                    acc = self.get_configured_accessory(tmcc_id)
                if acc:
                    name = acc.name
                    acc.activate_tmcc_id(tmcc_id)
                else:
                    name = state.name
                    name = name if name and name != "NA" else not_found_value
            else:
                name = state.name
                name = name if name and name != "NA" else not_found_value
            update_button_state = False
        self.name_text.value = name
        return name, update_button_state

    def _update_recent_selection(
        self,
        tmcc_id: int,
        state: S | None,
        in_ops_mode: bool,
        selection_changed: bool,
    ) -> None:
        if state and selection_changed:
            if self.is_provisional(self.scope, tmcc_id):
                # a provisional record stays out of recents (and so out of the header
                # combo) until it is named; still track it as the current selection
                self._scope_tmcc_ids[self.scope] = tmcc_id
            else:
                self.make_recent(self.scope, tmcc_id, state)
            if not in_ops_mode:
                self.ops_mode(update_info=False)

    def _clear_component_display(self, tmcc_id: int, num_chars: int) -> None:
        if self._keypad_view.reset_on_keystroke:
            self._scope_tmcc_ids[self.scope] = 0
            self._keypad_view.reset_on_keystroke = False
        self.tmcc_id_text.value = f"{tmcc_id:0{num_chars}d}"
        self.name_text.value = ""
        self._image_presenter.clear()

    def _refresh_component_view(
        self,
        state: S | None,
        update_button_state: bool,
        tmcc_id: int,
        selection_changed: bool,
    ) -> None:
        if selection_changed:
            self.monitor_state()
        if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN, CommandScope.ACC}:
            if update_button_state:
                # noinspection PyTypeChecker
                self._scoped_callbacks.get(self.scope, lambda s: print(f"from uci: {s}"))(state)
            refresh_image = selection_changed
            if (
                not refresh_image
                and tmcc_id != 0
                and state is not None
                and not self._keypad_view.is_entry_mode
                and not getattr(self.image_box, "visible", False)
            ):
                # Returning from entry mode to ops mode can hide the image without changing
                # TMCC selection; force a repaint in that case.
                refresh_image = True
            if refresh_image:
                self._image_presenter.update(tmcc_id)
        else:
            self.image_box.hide()
        self._last_displayed_scope = self.scope
        self._last_displayed_tmcc_id = tmcc_id

    # noinspection PyTypeChecker
    def update_component_info(
        self,
        tmcc_id: int = None,
        not_found_value: str = "Not Configured",
        in_ops_mode: bool = False,
    ) -> None:
        self._begin_transition()
        try:
            self._popup.close()
            if tmcc_id is None:
                tmcc_id = self._scope_tmcc_ids.get(self.scope, 0)
            # update the tmcc_id associated with current scope
            self._scope_tmcc_ids[self.scope] = tmcc_id
            update_button_state = True
            num_chars = 4 if self.scope in {CommandScope.ENGINE, CommandScope.TRAIN} else 2
            if tmcc_id:
                tmcc_id, state = self._resolve_component_state(tmcc_id)
                selection_changed = not self._is_same_display_selection(tmcc_id)
                _, update_button_state = self._apply_component_labels(tmcc_id, state, not_found_value, num_chars)
                self._update_recent_selection(tmcc_id, state, in_ops_mode, selection_changed)
            else:
                state = None
                selection_changed = not self._is_same_display_selection(tmcc_id)
                self._clear_component_display(tmcc_id, num_chars)
            if selection_changed:
                # a forced accessory panel belongs to the component it was forced on
                self._keypad_view.set_panel_kind_override(None)
            self._refresh_component_view(state, update_button_state, tmcc_id, selection_changed)
        finally:
            self._end_transition()

    def calc_image_box_size(self) -> tuple[int, int | Any]:
        # Prefer explicit cached values
        if self.avail_image_height is not None and self.avail_image_width is not None:
            return self.avail_image_height, self.avail_image_width
        # If engine baseline exists, use it
        if getattr(self, "avail_image_height_engine", None) is not None and self.avail_image_width is not None:
            return self.avail_image_height_engine, self.avail_image_width
        # Fallback to presenter calculation
        return self._image_presenter.calc_box_size()

    def _compute_engine_image_baseline(self) -> None:
        """Compute image height based on engine ops-mode layout and remember it.

        Baseline = device height - ops keypad/controller - scope buttons - info box
                   - engine id/road name box - Emergency/reset box - top header - padding
        This is computed eagerly when entering ops mode so other modes use it.
        """
        try:
            self.app.tk.update_idletasks()
            header_h = self.header.tk.winfo_reqheight() if self.header else 0
            emergency_h = self.emergency_box_height or (
                self.emergency_box.tk.winfo_reqheight() if self.emergency_box else 0
            )
            info_h = self.info_box.tk.winfo_reqheight() if self.info_box else 0
            scope_h = self.scope_box.tk.winfo_reqheight() if self.scope_box else 0
            # Use controller_box as the ops-mode keypad area; use reqheight even if hidden
            controller_h = self.controller_box.tk.winfo_reqheight() if self.controller_box else 0

            baseline = self.height - header_h - emergency_h - info_h - scope_h - controller_h - 20
            baseline = max(0, int(baseline))
            available_width = self.emergency_box_width or (
                self.emergency_box.tk.winfo_reqwidth() if self.emergency_box else 0
            )
            available_width = min(self.width, max(0, available_width))
            baseline, available_width = self.fit_image_box_size(baseline, available_width)
            self.avail_image_height_engine = baseline
            self.avail_image_width = available_width

            # Apply globally so image presenter and other modes use engine baseline
            self.avail_image_height = baseline
            if log.isEnabledFor(logging.DEBUG):
                log.debug(
                    f"Computed engine image baseline height={baseline} (hdr={header_h}, em={emergency_h}, "
                    f"info={info_h}, scope={scope_h}, ctrl={controller_h})"
                )
        except Exception as e:
            log.exception("Failed to compute engine image baseline", exc_info=e)

    def make_emergency_buttons(self, app: App | Box):
        self.emergency_box = emergency_box = Box(app, layout="grid", border=2, align="top")
        compact = getattr(self, "_compact", False)
        if not compact:
            _ = Text(emergency_box, text=" ", grid=[0, 0, 3, 1], align="top", size=2, height=1, bold=True)

        label_width = 8 if compact else 11
        padding_x = padding_y = 4 if compact else None
        if not compact:
            padding_x = self.text_pad_x
            padding_y = self.text_pad_y
        if getattr(self, "_show_halt", True):
            self.halt_btn = HoldButton(
                emergency_box,
                text=HALT_KEY,
                grid=[0, 1],
                align="top",
                width=label_width,
                padx=padding_x,
                pady=padding_y,
                bg="red",
                text_bold=True,
                text_size=self.s_20,
                command=self.on_keypress,
                args=[HALT_KEY],
            )
            if not compact:
                _ = Text(emergency_box, text=" ", grid=[1, 1], align="top", size=6, height=1, bold=True)
            reset_col = 2
        else:
            self.halt_btn = None
            reset_col = 0

        self.reset_btn = HoldButton(
            emergency_box,
            text="Reset",
            grid=[reset_col, 1],
            align="top",
            width=label_width,
            padx=padding_x,
            pady=padding_y,
            bg="gray",
            text_size=self.s_20,
            text_color="black",
            text_bold=True,
            enabled=False,
            on_press=(self.on_engine_command, ["RESET"]),
            on_repeat=(self.on_engine_command, ["RESET"]),
            repeat_interval=0.1,
        )

        if getattr(self, "_linked_car_transfer", None) is not None:
            self.linked_cars_btn = HoldButton(
                emergency_box,
                text="Cars..." if compact else "Linked Cars…",
                grid=[2, 1],
                align="top",
                width=label_width,
                padx=padding_x,
                pady=padding_y,
                bg="lightgrey",
                text_size=self.s_18,
                text_color="black",
                text_bold=True,
                enabled=False,
                command=self.on_linked_cars,
            )

        if not compact:
            _ = Text(emergency_box, text=" ", grid=[0, 2, 3, 1], align="top", size=2, height=1, bold=True)
        self.app.tk.update_idletasks()
        self.emergency_box_width = emergency_box.tk.winfo_width()
        self.emergency_box_height = emergency_box.tk.winfo_height()

        # compute/apply scaling for larger displays, like the GPD 4
        scale = self.width / self.emergency_box_width
        if scale > 1.0:
            self._scale_factor = scale
            child_width = self.rescale_by(label_width)
            if self.halt_btn:
                self.halt_btn.width = child_width
            self.reset_btn.width = child_width
            if self.linked_cars_btn:
                self.linked_cars_btn.width = child_width
            self.app.tk.update_idletasks()
            self.emergency_box_width = emergency_box.tk.winfo_width()
            self.emergency_box_height = emergency_box.tk.winfo_height()

        fitted_width = self.fit_emergency_box_width(self.emergency_box_width)
        if compact:
            emergency_box.tk.config(width=fitted_width, height=self.emergency_box_height)
            emergency_box.tk.pack_configure(fill="x", expand=False)
            emergency_box.tk.pack_propagate(False)
            # The emergency box lays its buttons out with ``grid`` (not ``pack``),
            # so ``pack_propagate(False)`` above does not keep the frame from
            # shrinking to the natural width of its buttons. Use
            # ``grid_propagate(False)`` so the box honors the fixed width above
            # and the column weights below stretch HALT/Reset across the whole
            # width, matching the Road Number/Name info row.
            emergency_box.tk.grid_propagate(False)
            emergency_box.tk.grid_columnconfigure(reset_col, weight=1)
            self.reset_btn.tk.grid_configure(sticky="ew")
            if self.halt_btn:
                emergency_box.tk.grid_columnconfigure(0, weight=1, uniform="emergency_actions")
                emergency_box.tk.grid_columnconfigure(reset_col, weight=1, uniform="emergency_actions")
                self.halt_btn.tk.grid_configure(sticky="ew")
            if self.linked_cars_btn:
                emergency_box.tk.grid_columnconfigure(2, weight=1, uniform="emergency_actions")
                self.linked_cars_btn.tk.grid_configure(sticky="ew")
        self.emergency_box_width = fitted_width

    def on_linked_cars(self) -> None:
        if self._linked_car_transfer is None or not self._train_linked_queue:
            return

        def build_linked_cars(body: Box) -> None:
            Text(body, text="Open linked car in other panel", align="top", bold=True, size=self.s_18)
            for state in self._train_linked_queue:
                label = f"{state.tmcc_id:04d}: {state.name or state.road_name}"
                button = PushButton(
                    body,
                    text=label,
                    align="top",
                    width=24,
                    command=self._transfer_linked_car,
                    args=[state],
                )
                button.text_size = self.s_18
                self.cache(button)

        key = "linked_car_transfer"
        self._popup.forget([key])
        overlay = self._popup.get_or_create(key, "Linked Cars", build_linked_cars)
        self.show_popup(overlay, hide_image_box=True)

    def _transfer_linked_car(self, state: EngineState) -> None:
        if self._linked_car_transfer is not None and self._linked_car_transfer(state):
            self._popup.close()

    @property
    def throttle_state(self) -> EngineState | None:
        state = self.active_engine_state
        if self._active_train_state and state in self._train_linked_queue:
            state = self._active_train_state
        return state if isinstance(state, EngineState) else None

    # noinspection argument-list,none-function-assignment
    def on_speed_command(self, speed_req: str | int) -> None:
        state = self.throttle_state
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
            if state.is_cab1:
                req = CommandReq.build(
                    TMCC1EngineCommandEnum.RELATIVE_SPEED, state.tmcc_id, data=rr_speed, scope=state.scope
                )
            else:
                if do_dialog:
                    req = RampedSpeedDialogReq(state.tmcc_id, rr_speed, state.scope)
                else:
                    req = RampedSpeedReq(state.tmcc_id, rr_speed, state.scope)
        else:
            tmcc_id = self._scope_tmcc_ids[self.scope]
            req = CommandReq(TMCC1EngineCommandEnum.ABSOLUTE_SPEED, tmcc_id, scope=self.scope, data=rr_speed)

        # dispatch command
        self.submit_request(req)

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
                self.submit_request(cmd, repeat=repeat, delay=delay)
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
            else:
                return TMCC2EffectsControl.SMOKE_LOW
        elif cmd == SMOKE_OFF:  # decrease smoke
            if cur_smoke == TMCC2EffectsControl.SMOKE_LOW:
                return TMCC2EffectsControl.SMOKE_OFF
            elif cur_smoke == TMCC2EffectsControl.SMOKE_MEDIUM:
                return TMCC2EffectsControl.SMOKE_LOW
            elif cur_smoke == TMCC2EffectsControl.SMOKE_HIGH:
                return TMCC2EffectsControl.SMOKE_MEDIUM
            else:
                return TMCC2EffectsControl.SMOKE_OFF
        return None

    def on_acc_speed_command(self, value: int) -> None:
        """Ask the selected accessory for a relative speed step.

        The controller's entry point for the accessory speed slider, and the reason a gamepad
        stick and the slider cannot ask for different things: both end in the same
        ``RELATIVE_SPEED`` command, clamped to the range the slider offers. A step of zero is
        no request at all and is dropped rather than sent.
        """
        try:
            speed = int(value)
        except (TypeError, ValueError):
            return
        speed = max(ACCESSORY_THROTTLE_MIN, min(ACCESSORY_THROTTLE_MAX, speed))
        if speed == 0:
            return
        self.on_acc_command("RELATIVE_SPEED", speed)

    def on_acc_command(self, target: str, data: int | None = None) -> None:
        state = self.active_state
        if isinstance(state, AccessoryState):
            acc_enum = TMCC1AuxCommandEnum.by_name(target)
            if acc_enum:
                tmcc_id = state.tmcc_id
                self.submit_request(CommandReq.build(acc_enum, tmcc_id, data))
