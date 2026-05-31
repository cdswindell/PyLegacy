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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

from PIL.ImageTk import PhotoImage

from .configured_accessory_adapter import ConfiguredAccessoryAdapter
from .engine_gui_conf import ENGINE_TYPE_TO_IMAGE
from ...db.accessory_state import AccessoryState
from ...db.engine_state import EngineState
from ...db.prod_info import ENGINE_IMAGES_CACHE_DIR, ProdInfo
from ...protocol.constants import CommandScope, EngineType
from ...utils.image_utils import center_text_on_image
from ...utils.path_utils import find_file

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui

log = logging.getLogger(__name__)


class ImagePresenter:
    def __init__(self, host: "EngineGui") -> None:
        self._last_box_size = None
        self._host = host
        self.avail_image_height: int | None = None
        self.avail_image_width: int | None = None
        self.asc2_image = find_file("LCS-ASC2-6-81639.jpg")
        self.amc2_image = find_file("LCS-AMC2-6-81641.jpg")
        self.bpc2_image = find_file("LCS-BPC2-6-81640.jpg")
        self.sensor_track_image = find_file("LCS-Sensor-Track-6-81294.jpg")
        self.loading_image = find_file("loading_image.png")
        self._checked_for_custom_images: set[int] = set()
        self._pending_custom_images: set[int] = set()
        self._executor = ThreadPoolExecutor(max_workers=1)

        # make sure custom image directory exists
        p = Path(ENGINE_IMAGES_CACHE_DIR)
        if not p.is_dir():
            p.mkdir(parents=True, exist_ok=True)

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
        elif host.controller_box and host.controller_box.visible:
            if host.controller_box not in host.size_cache:
                _, controller_height = host.size_cache[host.controller_box] = (
                    host.controller_box.tk.winfo_reqwidth(),
                    host.controller_box.tk.winfo_reqheight(),
                )
            else:
                _, controller_height = host.size_cache[host.controller_box]
            variable_content = controller_height
        elif host.sensor_track_box and host.sensor_track_box.visible:
            if host.sensor_track_box not in host.size_cache:
                _, sensor_height = host.size_cache[host.sensor_track_box] = (
                    host.sensor_track_box.tk.winfo_reqwidth(),
                    host.sensor_track_box.tk.winfo_reqheight(),
                )
            else:
                _, sensor_height = host.size_cache[host.sensor_track_box]
            variable_content = sensor_height
        elif host.acc_overlay and host.acc_overlay.visible:
            overlay_height = host.acc_overlay.tk.winfo_height()
            if overlay_height <= 1:
                overlay_height = host.acc_overlay.tk.winfo_reqheight()
            variable_content = overlay_height
        else:
            variable_content = 0
            if host.avail_image_height is None:
                log.warning("No variable content available while calculating image box size")

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
        self._last_box_size = (avail_image_height, avail_image_width)
        return avail_image_height, avail_image_width

    def _is_relevant_update(self, scope: CommandScope, tmcc_id: int | None, train_id: int | None = None) -> bool:
        host = self._host
        if tmcc_id is None:
            return False
        if scope == CommandScope.ENGINE:
            if host.scope == CommandScope.ENGINE:
                return tmcc_id == host.scope_tmcc_id(CommandScope.ENGINE)
            if host.scope == CommandScope.TRAIN and train_id is not None:
                return train_id == host.scope_tmcc_id(CommandScope.TRAIN)
            return False
        if scope == CommandScope.TRAIN:
            return host.scope == CommandScope.TRAIN and tmcc_id == host.scope_tmcc_id(CommandScope.TRAIN)
        return host.scope == scope and tmcc_id == host.scope_tmcc_id(scope)

    def _make_prod_info_callback(self, tmcc_id: int, train_id: int | None):
        if train_id is None:
            key: tuple[CommandScope, int] = (CommandScope.ENGINE, tmcc_id)
        else:
            key: tuple[CommandScope, int, int] = (CommandScope.ENGINE, tmcc_id, train_id)
        return lambda _resolved_tmcc_id: self.update(key=key)

    # noinspection PyProtectedMember
    def update(
        self,
        tmcc_id: int | None = None,
        key: tuple[CommandScope, int]
        | tuple[CommandScope, int, int]
        | tuple[CommandScope, int, int | None]
        | None = None,
    ) -> None:
        host = self._host

        if key is None and host.scope in {CommandScope.SWITCH, CommandScope.ROUTE}:
            # routes and switches don't use images
            return
        if key:
            scope: CommandScope = key[0]
            tmcc_id: int = int(key[1])
            train_id = key[2] if len(key) > 2 else None
            if not self._is_relevant_update(scope, tmcc_id, train_id):
                return
        else:
            scope = host.scope
            if tmcc_id is None:
                tmcc_id = host.scope_tmcc_id(host.scope)
            train_id = None
        img = None
        box_size: tuple[int, int] | None = None

        # for Trains, use the image of the lead engine
        if scope == CommandScope.TRAIN and host.active_state and not host.active_state.is_power_district and tmcc_id:
            with host.locked():
                img = host._image_cache.get((CommandScope.TRAIN, tmcc_id), None)
            if img is None:
                train_state = host.active_state
                train_id = tmcc_id
                head_id = train_state.head_tmcc_id
                with host.locked():
                    img = host._image_cache.get((CommandScope.ENGINE, head_id), None)
                if img is None:
                    if log.isEnabledFor(logging.DEBUG):
                        log.debug(f"No image for train {tmcc_id} head {head_id}; requesting...")
                    self.update(key=(CommandScope.ENGINE, head_id, train_id))
                    return
                else:
                    with host.locked():
                        host._image_cache[(CommandScope.TRAIN, train_id)] = img
        elif scope in {CommandScope.ENGINE} and tmcc_id != 0:
            # is an image cached?
            with host.locked():
                img = host._image_cache.get((CommandScope.ENGINE, tmcc_id), None)

            # is there a custom image?
            if img is None and tmcc_id not in self._checked_for_custom_images:
                if self._lookup_custom_image(tmcc_id, train_id):
                    return

            if img is not None:
                if train_id is not None:
                    with host.locked():
                        host._image_cache[(CommandScope.TRAIN, train_id)] = img
                    tmcc_id = int(train_id)
                    scope = CommandScope.TRAIN
            else:
                box_size = self.refresh_box_size() or self.calc_box_size()
                available_height, available_width = box_size

                state = host._state_store.get_state(scope, tmcc_id, False)
                if log.isEnabledFor(logging.DEBUG):
                    bt_id = state.bt_id if state else "NA"
                    log.debug(f"Requested product info for {scope.title} TMCC ID: {tmcc_id}  bt: {bt_id}...")
                prod_info = host.get_prod_info(
                    state.bt_id if state else None,
                    self._make_prod_info_callback(tmcc_id, train_id),
                    tmcc_id,
                    available_width=available_width,
                    available_height=available_height,
                )

                if prod_info is None:
                    img = host.get_image(self.loading_image, inverse=False, scale=False, force_lionel=True)
                    self._update_image(img, scope, tmcc_id, box_size)
                    return

                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"Prod_info: {prod_info.road_name if isinstance(prod_info, ProdInfo) else 'NA'}")

                if isinstance(prod_info, ProdInfo):
                    # Image should have been cached by fetch_prod_indo
                    with host.locked():
                        img = host._image_cache.get((CommandScope.ENGINE, tmcc_id), None)
                    if img is not None and train_id is not None:
                        with host.locked():
                            host._image_cache[(CommandScope.TRAIN, train_id)] = img
                        tmcc_id = train_id
                        scope = CommandScope.TRAIN
                else:
                    if isinstance(state, EngineState):
                        with host.locked():
                            img = host._image_cache.get((CommandScope.ENGINE, tmcc_id), None)
                        # Retrieves or generates cached engine image; caches by type
                        if img is None:
                            et_enum = (
                                state.engine_type_enum if state.engine_type_enum is not None else EngineType.DIESEL
                            )
                            source = ENGINE_TYPE_TO_IMAGE.get(et_enum, ENGINE_TYPE_TO_IMAGE[EngineType.DIESEL])
                            with host.locked():
                                img = host._image_cache.get(source, None)
                            if img is None:
                                img = host.get_scaled_image(source, force_lionel=True)
                                img = center_text_on_image(img, et_enum.label(), styled=True)
                                with host.locked():
                                    host._image_cache[source] = img
                            with host.locked():
                                # host._image_cache[(CommandScope.ENGINE, tmcc_id)] = img
                                if train_id:
                                    # host._image_cache[(CommandScope.TRAIN, train_id)] = img
                                    tmcc_id = train_id
                                    scope = CommandScope.TRAIN
                    else:
                        host._image_presenter.clear()
        elif host.scope in {CommandScope.ACC, CommandScope.TRAIN} and tmcc_id != 0:
            state = host.state_store.get_state(host.scope, tmcc_id, False)
            if state:
                key = (host.scope, tmcc_id)
                box_size = host.calc_image_box_size()
                if isinstance(state, AccessoryState):
                    if host.is_accessory_view(tmcc_id):
                        view = host.get_accessory_view(tmcc_id)
                        if view and hasattr(view, "acc"):
                            key = (host.scope, tmcc_id, getattr(view, "acc"))
                    elif host.get_configured_accessory(tmcc_id):
                        key = (host.scope, tmcc_id, host.get_configured_accessory(tmcc_id))
                with host.locked():
                    img = host._image_cache.get((*key, box_size), None)
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
                            acc: ConfiguredAccessoryAdapter = host.get_configured_accessory(tmcc_id)
                            key = (host.scope, tmcc_id, acc)
                            img_path = find_file(acc.image_path)
                    if img_path:
                        img = host.get_scaled_image(img_path, preserve_height=True)
                    if img:
                        with host.locked():
                            host._image_cache[(*key, box_size)] = img
                    else:
                        self.clear()
        if img is None:
            self.clear()

        # noinspection PyTypeChecker
        self._update_image(img, scope, tmcc_id, box_size)

    def _update_image(
        self, img: PhotoImage | None, scope: CommandScope, tmcc_id: int | None, box_size: tuple[int, int] | None
    ):
        # Updates image if scope and ID match current
        host = self._host
        if img and scope == host.scope and tmcc_id == host.scope_tmcc_id(host.scope):
            self.clear()
            if box_size is None:
                if host.avail_image_height is None or host.avail_image_width is None:
                    box_size = self.calc_box_size()
                else:
                    box_size = (host.avail_image_height, host.avail_image_width)
            available_height, available_width = box_size
            host.image_box.tk.config(width=available_width, height=available_height)
            host.image.tk.config(image=img)
            host.image_box.show()

    def refresh_box_size(self) -> tuple[int, int] | None:
        w = self._host.avail_image_width or self._host.image_box.tk.winfo_width()
        h = self._host.avail_image_height or self._host.image_box.tk.winfo_height()
        if h > 1 and w > 1:
            self._last_box_size = (h, w)
            return self._last_box_size
        return None

    # noinspection PyProtectedMember
    def _lookup_custom_image(self, tmcc_id: int, train_id: int | None = None) -> bool:
        """
        Schedule custom-image lookup off the Tk thread.

        Returns True when an existing or newly-created background lookup should
        be allowed to finish before falling back to product/default images.
        """
        host = self._host
        with host.locked():
            if tmcc_id in self._checked_for_custom_images:
                return False
            if tmcc_id in self._pending_custom_images:
                return True
            self._pending_custom_images.add(tmcc_id)

        try:
            self._executor.submit(self._load_custom_image, tmcc_id, train_id)
        except Exception as e:
            log.exception("Unable to schedule custom image lookup for TMCC ID %s", tmcc_id, exc_info=e)
            self._finish_custom_image_lookup(tmcc_id, train_id, None)
            return False
        return True

    def _load_custom_image(
        self,
        tmcc_id: int,
        train_id: int | None,
    ) -> None:
        host = self._host
        img = None
        try:
            image_path = find_file(f"{tmcc_id}.jpg", places=(Path.cwd(), ENGINE_IMAGES_CACHE_DIR))
            if image_path is not None:
                img = host.get_scaled_image(image_path, force_lionel=True)
        except Exception as e:
            log.exception("Unable to load custom image for TMCC ID %s", tmcc_id, exc_info=e)
        self._host.queue_message(self._finish_custom_image_lookup, tmcc_id, train_id, img)

    # noinspection PyProtectedMember
    def _finish_custom_image_lookup(
        self,
        tmcc_id: int,
        train_id: int | None,
        image: PhotoImage | None,
    ) -> None:
        # must run on TK thread
        host = self._host
        with host.locked():
            if image is not None:
                host._image_cache[(CommandScope.ENGINE, tmcc_id)] = image
            self._pending_custom_images.discard(tmcc_id)
            self._checked_for_custom_images.add(tmcc_id)
        if train_id is None:
            self.update(key=(CommandScope.ENGINE, tmcc_id))
        else:
            self.update(key=(CommandScope.ENGINE, tmcc_id, train_id))
