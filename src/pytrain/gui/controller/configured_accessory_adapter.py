#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, TYPE_CHECKING, runtime_checkable

from ..accessories.configured_accessory import ConfiguredAccessory
from ...db.accessory_state import AccessoryState
from ...db.component_state import ComponentState
from ...protocol.constants import CommandScope

if TYPE_CHECKING:  # pragma: no cover
    from .engine_gui import EngineGui


@runtime_checkable
class _StateStoreLike(Protocol):
    def get_state(self, scope: CommandScope, tmcc_id: int) -> ComponentState: ...


@dataclass(slots=True)
class ConfiguredAccessoryAdapter:
    """
    EngineGui-facing wrapper for a ConfiguredAccessory.

    Goals:
      - feels "State-like" for EngineGui (tmcc_id-centric)
      - owns:
          * the ConfiguredAccessory (config identity + resolved label)
          * the constructed GUI instance (lazy or already created)
          * the overlay/popup object (PopupManager-managed)
      - tracks which TMCC id is currently "active" in EngineGui for this accessory
        (overall tmcc_id if present, else one of the operation tmcc_ids)

    This intentionally does NOT inherit AccessoryState/ComponentState; it adapts the
    few attributes EngineGui consumes (.tmcc_id, .name, .scope, .road_name, .road_number).
    """

    cfg: ConfiguredAccessory
    host: "EngineGui"

    # UI objects EngineGui/PopupManager will manage
    gui: Any | None = None
    overlay: Any | None = None

    # Which tmcc id should represent this adapter in TMCC_ID-centric contexts (recents, etc.)
    _active_tmcc_id: int | None = None
    _active_scope: CommandScope = CommandScope.ACC

    def __post_init__(self) -> None:
        # Prefer the accessory-wide tmcc_id when present, otherwise use the first operation id
        base = self.cfg.tmcc_id
        if base is None:
            tids = self.cfg.tmcc_ids
            base = tids[0] if tids else None
        self._active_tmcc_id = base

    # ---------------------------------------------------------------------
    # State-like surface area for EngineGui
    # ---------------------------------------------------------------------

    @property
    def tmcc_id(self) -> int:
        if self._active_tmcc_id is None:
            raise ValueError(f"{self}: no active tmcc_id (cfg has no tmcc ids)")
        return self._active_tmcc_id

    @property
    def tmcc_ids(self) -> tuple[int, ...]:
        return self.cfg.tmcc_ids

    @property
    def scope(self) -> CommandScope:
        return self._active_scope

    @property
    def name(self) -> str:
        """
        EngineGui uses .name for display. We want the fully resolved, user-facing label.
        """
        return self.cfg.label

    @property
    def road_name(self) -> str | None:
        return self.name

    @property
    def road_number(self) -> str | None:
        return ""

    # Convenience alias some code may expect
    @property
    def title(self) -> str:
        return self.name

    @property
    def image_path(self) -> str:
        return self.cfg.image_path

    # ---------------------------------------------------------------------
    # Access to the underlying current state (when you need it)
    # ---------------------------------------------------------------------

    @property
    def state(self) -> AccessoryState:
        """
        Fetch the live state for the adapter's active TMCC id.
        """
        return self.host.state_store.get_state(self.scope, self.tmcc_id)

    # ---------------------------------------------------------------------
    # Active TMCC selection
    # ---------------------------------------------------------------------

    def activate_tmcc_id(self, tmcc_id: int) -> None:
        """
        Set which tmcc_id represents this adapter in EngineGui.

        Use this when the user presses a specific operation button, and you want
        the adapter to "become" that tmcc_id for Recents / active selection.
        """
        if tmcc_id not in self.cfg.tmcc_ids and tmcc_id != self.cfg.tmcc_id:
            raise ValueError(f"{self}: tmcc_id {tmcc_id} not associated with cfg {self.cfg.tmcc_ids!r}")

        self._active_tmcc_id = int(tmcc_id)

    def activate_operation(self, op_key: str) -> int:
        """
        Convenience: activate using a configured operation key like 'power', 'eject', etc.
        Returns the activated tmcc_id.
        """
        tid = self.cfg.tmcc_id_for(op_key)
        self.activate_tmcc_id(tid)
        return tid

    def reset_active(self) -> None:
        """
        Reset active tmcc id back to cfg.tmcc_id (if present) else first operation id.
        """
        base = self.cfg.tmcc_id
        if base is None:
            tids = self.cfg.tmcc_ids
            base = tids[0] if tids else None
        self._active_tmcc_id = base

    # ---------------------------------------------------------------------
    # GUI/overlay lifecycle helpers (EngineGui decides how/when)
    # ---------------------------------------------------------------------

    def ensure_gui(self, *, aggregator: Any, extra_kwargs: dict[str, Any] | None = None) -> Any:
        """
        Lazily instantiate the accessory GUI (configured_accessory owns ctor filtering).
        """
        if self.gui is None:
            self.gui = self.cfg.create_gui(aggregator=aggregator, extra_kwargs=extra_kwargs or {})
            self.gui.menu_label = self.cfg.label
        return self.gui

    def attach_overlay(self, overlay: Any) -> None:
        """
        Store the overlay handle created by PopupManager.get_or_create(...).
        """
        self.overlay = overlay

    # ---------------------------------------------------------------------
    # Identity / debugging
    # ---------------------------------------------------------------------

    @property
    def key(self) -> str:
        return self.instance_id

    @property
    def instance_id(self) -> str:
        iid = self.cfg.instance_id
        if not self.cfg.instance_id:
            raise ValueError("ConfiguredAccessoryAdapter requires cfg.instance_id")
        return iid

    def __hash__(self) -> int:
        # Stable identity for hashing / de-duping in UniqueDeque
        return hash(self.instance_id)

    def __eq__(self, other: object) -> bool:
        if other is self:
            return True
        if not isinstance(other, ConfiguredAccessoryAdapter):
            return NotImplemented
        return self.instance_id == other.instance_id

    def __repr__(self) -> str:
        # Keep it readable in logs/recents debugging
        return (
            f"ConfiguredAccessoryAdapter("
            f"label={self.cfg.label!r}, "
            f"active_tmcc_id={self._active_tmcc_id}, "
            f"scope={self._active_scope.name}, "
            f"tmcc_ids={self.cfg.tmcc_ids!r})"
        )
