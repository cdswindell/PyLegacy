#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""
Answers the question "what owns this TMCC ID?" for the LCS configuration panel.

The component state store is walked for states whose ``LcsProxyState`` flags identify
one of the modules in :mod:`lcs_device_registry`. Each such module contributes a block
of TMCC IDs starting at its own address. The block size is the module's own
``LcsState.num_ids``, reported in its PDI INFO packet; when INFO has not arrived, the
registry's ``mode.ports`` is used instead.

No Tk or guizero symbols are imported; the map is pure logic over the state store and
is unit-testable with any object exposing ``get_all(scope)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List

from ...protocol.constants import CommandScope
from .lcs_device_registry import LcsDevice, LcsMode, device_for_state

LCS_SCOPES: tuple[CommandScope, ...] = (
    CommandScope.ACC,
    CommandScope.SWITCH,
    CommandScope.TRAIN,
)


@dataclass(frozen=True)
class LcsOccupant:
    """
    An LCS module that claims a block of TMCC IDs.
    """

    base_id: int
    device: LcsDevice
    mode: LcsMode | None
    ports: int
    port_index: int | None = None
    scope: CommandScope | None = None
    state: Any = None

    @property
    def last_id(self) -> int:
        return self.base_id + self.ports - 1

    @property
    def is_base(self) -> bool:
        return self.port_index == 1 or self.port_index is None

    def claims(self, tmcc_id: int) -> bool:
        return self.base_id <= tmcc_id <= self.last_id

    def at(self, tmcc_id: int) -> LcsOccupant:
        """
        Return a copy of this occupant reporting the 1-based port index of ``tmcc_id``.
        """
        index = tmcc_id - self.base_id + 1 if self.claims(tmcc_id) else None
        return LcsOccupant(
            base_id=self.base_id,
            device=self.device,
            mode=self.mode,
            ports=self.ports,
            port_index=index,
            scope=self.scope,
            state=self.state,
        )


def _store(store: Any = None) -> Any:
    if store is not None:
        return store
    from ...db.component_state_store import ComponentStateStore

    return ComponentStateStore.get() if ComponentStateStore.is_built() else None


def _pdi_mode(state: Any) -> int | None:
    mode = getattr(state, "mode", None)
    return mode if isinstance(mode, int) and not isinstance(mode, bool) else None


def _mode_of(device: LcsDevice, state: Any) -> LcsMode | None:
    mode = device.mode_for_pdi_mode(_pdi_mode(state))
    if mode is None and len(device.modes) == 1:
        mode = device.modes[0]
    return mode


def _ports_of(mode: LcsMode | None, state: Any) -> int:
    num_ids = getattr(state, "num_ids", None)
    if isinstance(num_ids, int) and num_ids > 0:
        return num_ids
    return mode.ports if mode else 1


def _occupant_of_state(state: Any, scope: CommandScope) -> LcsOccupant | None:
    device = device_for_state(state)
    if device is None:
        return None
    base_id = getattr(state, "address", None)
    if not isinstance(base_id, int) or base_id < 1:
        return None
    mode = _mode_of(device, state)
    return LcsOccupant(
        base_id=base_id,
        device=device,
        mode=mode,
        ports=_ports_of(mode, state),
        port_index=1,
        scope=scope,
        state=state,
    )


def occupants(store: Any = None) -> List[LcsOccupant]:
    """
    Return every LCS module currently known to the state store, one per module base.
    """
    store = _store(store)
    if store is None:
        return []
    found: List[LcsOccupant] = []
    seen: set[tuple[str, int]] = set()
    for scope in LCS_SCOPES:
        try:
            states = store.get_all(scope) or []
        except Exception:  # pragma: no cover - defensive; store shapes vary
            continue
        for state in states:
            # Interior ports have a parent and a port number greater than one. A
            # Sensor Track proxy also has a parent, but its IRDA sibling is at
            # the same address and the proxy is still the module's base state.
            if getattr(state, "parent", None) is not None and getattr(state, "port", 1) > 1:
                continue
            occupant = _occupant_of_state(state, scope)
            if occupant is None:
                continue
            key = (occupant.device.key, occupant.base_id)
            if key in seen:
                continue
            seen.add(key)
            found.append(occupant)
    found.sort(key=lambda o: o.base_id)
    return found


def occupant_of(tmcc_id: int, store: Any = None) -> LcsOccupant | None:
    """
    Return the LCS module claiming ``tmcc_id``, with its 1-based ``port_index``, or None.
    """
    for occupant in occupants(store):
        if occupant.claims(tmcc_id):
            return occupant.at(tmcc_id)
    return None


def overlaps(base_id: int, ports: int, store: Any = None, ignore_base: int | None = None) -> List[LcsOccupant]:
    """
    Return the known modules whose blocks intersect ``base_id .. base_id + ports - 1``.

    ``ignore_base`` omits the module being reconfigured, which necessarily overlaps itself.
    """
    last_id = base_id + max(ports, 1) - 1
    found: List[LcsOccupant] = []
    for occupant in occupants(store):
        if ignore_base is not None and occupant.base_id == ignore_base:
            continue
        if occupant.base_id <= last_id and base_id <= occupant.last_id:
            found.append(occupant)
    return found
