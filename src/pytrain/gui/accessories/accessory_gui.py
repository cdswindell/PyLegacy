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
import json
import logging
from pathlib import Path
from threading import Event, Thread
from typing import Any

from .accessory_gui_catalog import AccessoryGuiCatalog
from .accessory_registry import AccessoryRegistry
from .configured_accessory_set import DEFAULT_CONFIG_FILE
from ...gpio.gpio_handler import GpioHandler
from ...utils.path_utils import find_file

log = logging.getLogger(__name__)


def instantiate(
    cls: type,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    *,
    allow_partial: bool = False,
    apply_defaults: bool = True,
):
    """
    Validate (and optionally complete) constructor args, then instantiate `cls`.
    - If allow_partial=True, missing optional args are ok; missing required args will still error on actual call.
    - apply_defaults=True fills in defaulted parameters.
    """
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


def _load_accessory_config(path: str | Path) -> list[dict[str, Any]]:
    p = Path(find_file(path))
    obj = json.loads(p.read_text(encoding="utf-8"))

    if isinstance(obj, dict) and isinstance(obj.get("accessories"), list):
        return list(obj["accessories"])
    if isinstance(obj, list):
        return list(obj)

    raise ValueError(f"Unsupported accessory config JSON shape in {p!s}")


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
    ) -> None:
        """
        Aggregator that builds its GUI list from an EngineGui accessory JSON file.

        config_file is REQUIRED.
        """
        super().__init__(daemon=True)
        self._ev = Event()
        self._catalog = AccessoryGuiCatalog()

        self._registry = AccessoryRegistry.instance()
        self._registry.bootstrap()

        self._guis: dict[str, tuple[type, tuple[Any, ...], dict[str, Any]]] = {}
        self._load_from_config(config_file)

        if not self._guis:
            raise ValueError("AccessoryGui: no GUIs configured")

        self._sorted_guis = sorted(self._guis.keys(), key=lambda s: s.lower())

        # verify requested GUI exists:
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
                # sensible fallback if Tk isn't available
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
    # Config-file path
    # -------------------------------------------------------------------------

    def _load_from_config(self, config_file: str | Path) -> None:
        """
        Build self._guis from the EngineGui accessory JSON.

        Expected per-item keys (from your CLI tool):
          - gui (catalog key, e.g. "milk")
          - variant (variant key)
          - tmcc_ids (dict op_key -> int) [ASC2-style]
          - tmcc_id (int) [overall ID for command-style accessories, optional]
          - instance_id (string, optional but recommended)
          - display_name (optional)
        """
        items = _load_accessory_config(config_file)

        for item in items:
            if not isinstance(item, dict):
                continue

            gui_key = item.get("gui")
            if not gui_key:
                raise ValueError(f"Accessory config entry missing 'gui': {item!r}")

            entry = self._catalog.resolve(str(gui_key))
            gui_class = entry.load_class()
            gui_type = entry.accessory_type

            variant = item.get("variant")
            instance_id = item.get("instance_id") or None
            display_name = item.get("display_name") or None

            # Registry supplies stable title/image for menu identity
            title, _ = self._resolve_variant(gui_class, gui_type, variant)

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
            if isinstance(tmcc_ids, dict):
                # Pass operation keys as kwargs (power=..., alarm=..., etc.)
                for k, v in tmcc_ids.items():
                    try:
                        ctor_kwargs[str(k)] = int(v)
                    except Exception:
                        raise ValueError(f"Invalid tmcc_ids value for {k!r}: {v!r}")

            tmcc_id_overall = item.get("tmcc_id")
            if tmcc_id_overall is not None:
                ctor_kwargs["tmcc_id"] = int(tmcc_id_overall)

            # Optional metadata (only used if GUI ctors accept them)
            if instance_id:
                ctor_kwargs["instance_id"] = instance_id
            if display_name:
                ctor_kwargs["display_name"] = display_name

            ctor_kwargs = _filter_kwargs_for_ctor(gui_class, ctor_kwargs)
            self._guis[label] = (gui_class, (), ctor_kwargs)

    # -------------------------------------------------------------------------
    # Variant resolution (menu title / image)
    # -------------------------------------------------------------------------

    def _resolve_variant(self, gui_class: type, gui_type, variant: str | None) -> tuple[str, str]:
        if gui_type is not None:
            definition = self._registry.get_definition(gui_type, variant)
            title = definition.variant.title
            image = find_file(definition.variant.image)
            return title, image

        # At this point you said legacy is gone; keep a hard error so problems show early.
        raise TypeError(f"{gui_class.__name__}: missing AccessoryType; legacy tuple mode removed")

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
