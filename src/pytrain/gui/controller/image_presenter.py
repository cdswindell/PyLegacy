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
from io import BytesIO
from typing import TYPE_CHECKING

from .configured_accessory_adapter import ConfiguredAccessoryAdapter
from .engine_gui_conf import ENGINE_TYPE_TO_IMAGE
from ...db.accessory_state import AccessoryState
from ...db.engine_state import EngineState
from ...db.prod_info import ProdInfo
from ...protocol.constants import CommandScope, EngineType
from ...utils.image_utils import center_text_on_image
from ...utils.path_utils import find_file

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui

log = logging.getLogger(__name__)


class ImagePresenter:
    def __init__(self, host: "EngineGui") -> None:
        self._host = host
        self.avail_image_height: int | None = None
        self.avail_image_width: int | None = None
        self.asc2_image = find_file("LCS-ASC2-6-81639.jpg")
        self.amc2_image = find_file("LCS-AMC2-6-81641.jpg")
        self.bpc2_image = find_file("LCS-BPC2-6-81640.jpg")
        self.sensor_track_image = find_file("LCS-Sensor-Track-6-81294.jpg")

    def clear(self) -> None:
        self._host.image.image = None
        self._host.image_box.hide()

    def calc_box_size(self) -> tuple[int, int]:
        """
        Calculates available image box size based on layout
        Can only call from the main gui thread!
        """
        host = self._host

        # force geometry layout
        host.app.tk.update_idletasks()

        # Get the heights of fixed elements
        if host.header not in host.size_cache:
            _, header_height = host.size_cache[host.header] = (
                host.header.tk.winfo_reqwidth(),
                host.header.tk.winfo_reqheight(),
            )
        else:
            _, header_height = host.size_cache[host.header]

        if host.emergency_box not in host.size_cache:
            emergency_width, emergency_height = host.size_cache[host.emergency_box] = (
                host.emergency_box.tk.winfo_reqwidth(),
                host.emergency_box_height or host.emergency_box.tk.winfo_reqheight(),
            )
        else:
            emergency_width, emergency_height = host.size_cache[host.emergency_box]

        if host.info_box not in host.size_cache:
            _, info_height = host.size_cache[host.info_box] = (
                host.info_box.tk.winfo_reqwidth(),
                host.info_box.tk.winfo_reqheight(),
            )
        else:
            _, info_height = host.size_cache[host.info_box]

        if host.scope_box not in host.size_cache:
            _, scope_height = host.size_cache[host.scope_box] = (
                host.scope_box.tk.winfo_reqwidth(),
                host.scope_box.tk.winfo_reqheight(),
            )
        else:
            _, scope_height = host.size_cache[host.scope_box]

        if host.keypad_box.visible:
            if host.keypad_box not in host.size_cache:
                _, keypad_height = host.size_cache[host.keypad_box] = (
                    host.keypad_box.tk.winfo_reqwidth(),
                    host.keypad_box.tk.winfo_reqheight(),
                )
            else:
                _, keypad_height = host.size_cache[host.keypad_box]
            variable_content = keypad_height
        elif host.controller_box.visible:
            if host.controller_box not in host.size_cache:
                _, controller_height = host.size_cache[host.controller_box] = (
                    host.controller_box.tk.winfo_reqwidth(),
                    host.controller_box.tk.winfo_reqheight(),
                )
            else:
                _, controller_height = host.size_cache[host.controller_box]
            variable_content = controller_height
        elif host.sensor_track_box.visible:
            if host.sensor_track_box not in host.size_cache:
                _, sensor_height = host.size_cache[host.sensor_track_box] = (
                    host.sensor_track_box.tk.winfo_reqwidth(),
                    host.sensor_track_box.tk.winfo_reqheight(),
                )
            else:
                _, sensor_height = host.size_cache[host.sensor_track_box]
            variable_content = sensor_height
        else:
            variable_content = 0
            if host.avail_image_height is None:
                print("*********** No Variable Content *******")

        # Calculate remaining vertical space
        if host.avail_image_height is None:
            avail_image_height = (
                host.height - header_height - emergency_height - info_height - variable_content - scope_height - 20
            )
            host.avail_image_height = avail_image_height
        else:
            avail_image_height = host.avail_image_height

        if host.avail_image_width is None:
            # use width of emergency height box as standard
            host.avail_image_width = avail_image_width = emergency_width
        else:
            avail_image_width = host.avail_image_width
        return avail_image_height, avail_image_width

    # noinspection PyProtectedMember
    def update(
        self,
        tmcc_id: int | None = None,
        key: tuple[CommandScope, int] | tuple[CommandScope, int, int] | None = None,
    ) -> None:
        host = self._host

        if key is None and host.scope in {CommandScope.SWITCH, CommandScope.ROUTE}:
            # routes and switches don't use images
            return
        if key:
            scope = key[0]
            tmcc_id = key[1]
            train_id = key[2] if len(key) > 2 else None
        else:
            scope = host.scope
            if tmcc_id is None:
                tmcc_id = host._scope_tmcc_ids[host.scope]
            train_id = None
        img = None

        # for Trains, use the image of the lead engine
        if scope == CommandScope.TRAIN and host.active_state and not host.active_state.is_power_district and tmcc_id:
            img = host._image_cache.get((CommandScope.TRAIN, tmcc_id), None)
            if img is None:
                train_state = host.active_state
                train_id = tmcc_id
                head_id = train_state.head_tmcc_id
                img = host._image_cache.get((CommandScope.ENGINE, head_id), None)
                if img is None:
                    self.update(key=(CommandScope.ENGINE, head_id, train_id))
                    return
                else:
                    host._image_cache[(CommandScope.TRAIN, train_id)] = img
        elif scope in {CommandScope.ENGINE} and tmcc_id != 0:
            with host.locked():
                state = host._state_store.get_state(scope, tmcc_id, False)
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"Requested product info for TMCC ID: {tmcc_id}  bt: {state.bt_id}...")
                prod_info = host.get_prod_info(state.bt_id if state else None, self.update, tmcc_id)

                if prod_info is None:
                    return

                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"Prod_info: {prod_info.road_name if isinstance(prod_info, ProdInfo) else 'NA'}")

                if isinstance(prod_info, ProdInfo):
                    # Image should have been cached by fetch_prod_indo
                    with host.locked():
                        img = host._image_cache.get((CommandScope.ENGINE, tmcc_id), None)
                    if img is None and prod_info.image_content:
                        img = host.get_scaled_image(BytesIO(prod_info.image_content))
                        host._image_cache[(CommandScope.ENGINE, tmcc_id)] = img
                    if img and train_id:
                        host._image_cache[(CommandScope.TRAIN, train_id)] = img
                        tmcc_id = train_id
                        scope = CommandScope.TRAIN
                else:
                    print(f"***** Prod_info: {prod_info}")
                    if isinstance(state, EngineState):
                        img = host._image_cache.get((CommandScope.ENGINE, tmcc_id), None)
                        # Retrieves or generates cached engine image; caches by type
                        if img is None:
                            et_enum = (
                                state.engine_type_enum if state.engine_type_enum is not None else EngineType.DIESEL
                            )
                            source = ENGINE_TYPE_TO_IMAGE.get(et_enum, ENGINE_TYPE_TO_IMAGE[EngineType.DIESEL])
                            img = host._image_cache.get(source, None)
                            if img is None:
                                img = host.get_scaled_image(source, force_lionel=True)
                                img = center_text_on_image(img, et_enum.label(), styled=True)
                                host._image_cache[source] = img
                                host._image_cache[(CommandScope.ENGINE, tmcc_id)] = img
                                host._image_cache[source] = img
                            host._image_cache[(CommandScope.ENGINE, tmcc_id)] = img
                            if train_id:
                                host._image_cache[(CommandScope.ENGINE, train_id)] = img
                                tmcc_id = train_id
                                scope = CommandScope.TRAIN
                    else:
                        host._image_presenter.clear()
        elif host.scope in {CommandScope.ACC, CommandScope.TRAIN} and tmcc_id != 0:
            state = host.state_store.get_state(host.scope, tmcc_id, False)
            if state:
                key = (host.scope, tmcc_id)
                if isinstance(state, AccessoryState):
                    if host.is_accessory_view(tmcc_id):
                        view = host.get_accessory_view(tmcc_id)
                        if view and hasattr(view, "acc"):
                            key = (host.scope, tmcc_id, getattr(view, "acc"))
                    elif host.get_configured_accessory(tmcc_id):
                        key = (host.scope, tmcc_id, host.get_configured_accessory(tmcc_id))
                img = host._image_cache.get(key, None)
                # Attempts to load and cache image from state
                if img is None:
                    img_path = None
                    if len(key) > 2 and isinstance(key[2], ConfiguredAccessoryAdapter):
                        acc = key[2]
                        img_path = find_file(acc.image_path)
                    elif isinstance(state, AccessoryState):
                        # Selects image based on accessory state properties
                        if state.is_asc2:
                            img_path = self.asc2_image
                        elif state.is_bpc2:
                            img_path = self.bpc2_image
                        elif state.is_amc2:
                            img_path = self.amc2_image
                        elif state.is_sensor_track:
                            img_path = self.sensor_track_image
                        if img_path is None and host.get_configured_accessory(tmcc_id):
                            acc = host.get_configured_accessory(tmcc_id)
                            key = (host.scope, tmcc_id, acc)
                            img_path = find_file(acc.image_path)
                    if img_path:
                        img = host.get_image(img_path, inverse=False, scale=True, preserve_height=True)
                    if img:
                        host._image_cache[key] = img
                    else:
                        self.clear()
        if img is None:
            self.clear()
        # Updates image if scope and ID match current
        if img and scope == host.scope and tmcc_id == host._scope_tmcc_ids[host.scope]:
            available_height, available_width = self.calc_box_size()
            host.image_box.tk.config(width=available_width, height=available_height)
            host.image.tk.config(image=img)
            host.image_box.show()
