#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import inspect
import logging
from pathlib import Path
from threading import Event, Thread
from typing import Any

from .accessory_gui_catalog import AccessoryGuiCatalog
from .accessory_registry import AccessoryRegistry
from .configured_accessory_set import ConfiguredAccessorySet, DEFAULT_CONFIG_FILE
from ...gpio.gpio_handler import GpioHandler

log = logging.getLogger(__name__)


def instantiate(
    cls: type,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    *,
    allow_partial: bool = False,
    apply_defaults: bool = True,
):
    kwargs = kwargs or {}

    sig = inspect.signature(cls.__init__)
    try:
        # noinspection PyArgumentList
        binder = (sig.bind_partial if allow_partial else sig.bind)(None, *args, **kwargs)
    except TypeError as e:
        raise TypeError(f"{cls.__name__}{sig}: {e}") from None

    if apply_defaults:
        binder.apply_defaults()

    bound_args = list(binder.args)[1:]  # drop fake self
    bound_kwargs = dict(binder.kwargs)
    return cls(*bound_args, **bound_kwargs)


def _norm(s: str) -> str:
    return " ".join(str(s).strip().lower().split())


def _filter_kwargs_for_ctor(cls: type, kwargs: dict[str, Any]) -> dict[str, Any]:
    """
    Filter kwargs down to only those accepted by cls.__init__ (excluding self).
    This lets config JSON include optional fields without breaking older GUIs.
    """
    sig = inspect.signature(cls.__init__)
    params = sig.parameters
    accepts_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    if accepts_kwargs:
        return dict(kwargs)

    allowed = {name for name in params.keys() if name != "self"}
    return {k: v for k, v in kwargs.items() if k in allowed}


class AccessoryGui(Thread):
    @classmethod
    def name(cls) -> str:
        return cls.__name__

    def __init__(
        self,
        *,
        width: int | None = None,
        height: int | None = None,
        scale_by: float = 1.0,
        initial: str | None = None,
        config_file: str | Path = DEFAULT_CONFIG_FILE,
        validate_config: bool = True,
        verify_config: bool = False,
    ) -> None:
        """
        Aggregator that builds its GUI list from accessory_config.json via ConfiguredAccessorySet.
        """
        super().__init__(daemon=True)
        self._ev = Event()
        self._catalog = AccessoryGuiCatalog()

        self._registry = AccessoryRegistry.get()
        self._registry.bootstrap()

        # Load + index configured accessories
        self._configured = ConfiguredAccessorySet.from_file(
            config_file,
            validate=validate_config,
            verify=verify_config,
        )

        self._guis: dict[str, tuple[type, tuple[Any, ...], dict[str, Any]]] = {}
        self._load_from_configured_set()

        if not self._guis:
            raise ValueError("AccessoryGui: no GUIs configured")

        self._sorted_guis = sorted(self._guis.keys(), key=lambda s: s.lower())

        # resolve initial selection
        if initial:
            for key in self._guis.keys():
                if initial.lower() in key.lower():
                    initial = key
                    break
            if initial not in self._guis:
                raise ValueError(f"Invalid initial GUI: {initial}")
        else:
            initial = self._sorted_guis[0]

        if width is None or height is None:
            try:
                from tkinter import Tk

                root = Tk()
                self.width = root.winfo_screenwidth()
                self.height = root.winfo_screenheight()
                root.destroy()
            except Exception as e:
                log.exception("Error determining window size", exc_info=e)
                self.width = width or 1024
                self.height = height or 600
        else:
            self.width = width
            self.height = height

        self._scale_by = scale_by
        self._gui = None
        self.requested_gui = initial

        self.start()

    # -------------------------------------------------------------------------
    # ConfiguredAccessorySet integration
    # -------------------------------------------------------------------------

    def _load_from_configured_set(self) -> None:
        """
        Build self._guis from ConfiguredAccessorySet entries.

        Expected keys:
          - gui (catalog key)
          - variant (variant key)
          - tmcc_ids (dict op_key -> int)
          - tmcc_id (int, optional)
          - instance_id (string, optional)
          - display_name (optional)
        """
        items = self._configured.all()
        if not items:
            return

        for item in items:
            if not isinstance(item, dict):
                continue

            gui_key = item.get("gui")
            if not isinstance(gui_key, str) or not gui_key.strip():
                raise ValueError(f"Accessory config entry missing/invalid 'gui': {item!r}")

            entry = self._catalog.resolve(gui_key)
            gui_class = entry.load_class()
            gui_type = entry.accessory_type
            if gui_type is None:
                raise TypeError(f"{gui_key}: missing AccessoryType in catalog entry; legacy mode is removed")

            variant = item.get("variant") if isinstance(item.get("variant"), str) else None
            instance_id = item.get("instance_id") if isinstance(item.get("instance_id"), str) else None
            display_name = item.get("display_name") if isinstance(item.get("display_name"), str) else None

            # Registry supplies stable title/image for menu identity
            definition = self._registry.get_definition(gui_type, variant)
            title = definition.variant.title

            # Prefer display_name for menu label; disambiguate duplicates
            label = display_name or title
            if label in self._guis:
                if instance_id:
                    label = f"{label} ({instance_id})"
                else:
                    base = label
                    n = 2
                    while label in self._guis:
                        label = f"{base} ({n})"
                        n += 1

            ctor_kwargs: dict[str, Any] = {}
            if variant is not None:
                ctor_kwargs["variant"] = variant

            tmcc_ids = item.get("tmcc_ids")
            if tmcc_ids is not None:
                if not isinstance(tmcc_ids, dict):
                    raise ValueError(f"{gui_key}: tmcc_ids must be a dict if present")
                for k, v in tmcc_ids.items():
                    if not isinstance(k, str):
                        raise ValueError(f"{gui_key}: tmcc_ids key must be str, got {k!r}")
                    if not isinstance(v, int):
                        raise ValueError(f"{gui_key}: tmcc_ids[{k!r}] must be int, got {v!r}")
                    ctor_kwargs[k] = int(v)

            tmcc_id_overall = item.get("tmcc_id")
            if tmcc_id_overall is not None:
                if not isinstance(tmcc_id_overall, int):
                    raise ValueError(f"{gui_key}: tmcc_id must be int if present, got {tmcc_id_overall!r}")
                ctor_kwargs["tmcc_id"] = int(tmcc_id_overall)

            # Optional metadata (only used if ctors accept them)
            if instance_id:
                ctor_kwargs["instance_id"] = instance_id
            if display_name:
                ctor_kwargs["display_name"] = display_name

            ctor_kwargs = _filter_kwargs_for_ctor(gui_class, ctor_kwargs)
            self._guis[label] = (gui_class, (), ctor_kwargs)

    # -------------------------------------------------------------------------
    # Thread loop
    # -------------------------------------------------------------------------

    def run(self) -> None:
        print(f"Creating GUI: {self.requested_gui}")
        gui = self._guis[self.requested_gui]
        gui[2]["aggregator"] = self
        self._gui = instantiate(gui[0], gui[1], gui[2])

        while True:
            self._ev.wait()
            self._ev.clear()

            GpioHandler.release_handler(self._gui)

            self._gui.destroy_complete.wait(10)
            self._gui.join()
            self._gui = None

            gui = self._guis[self.requested_gui]
            gui[2]["aggregator"] = self
            self._gui = instantiate(gui[0], gui[1], gui[2])

    def cycle_gui(self, gui: str) -> None:
        if gui in self._guis:
            self.requested_gui = gui
            self._ev.set()

    @property
    def guis(self) -> list[str]:
        return self._sorted_guis
