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

Two sources are merged, because neither alone tells the whole truth.

The first is the **PDI device store** (PdiStateStore), which holds one entry per
module *type* per TMCC ID -- keyed by (PdiDevice, tmcc_id) -- each built from that
module's own CONFIG packet and carrying its own mode. It is authoritative and is taken
first, because a component state is keyed by scope and address alone: an AMC2 and a BPC2
both answering to ACC 1 share a single AccessoryState, whose num_ids and mode
belong to whichever of them reported last. Sizing a module from that shared record is how
a BPC2 claiming eight IDs came to be reported as claiming one, and how an AMC2 sitting on
an address came to be reported as nothing at all.

The second is the **component state store**, walked for states whose LcsProxyState
flags identify one of the modules in lcs_device_registry.py. It covers what the PDI
store cannot: a module known only from control traffic, a store that has no PDI side at
all, and two modules of the *same* type at the same address on different remote keys,
which the PDI store's key cannot represent. Its block size is the module's own
LcsState.num_ids from its INFO packet, falling back to the registry's mode.ports.

Each module contributes a block of TMCC IDs starting at its own address.

A TMCC ID only means something together with the remote key that addresses it: ACC 1,
SW 1 and TR 1 are three different addresses on three different modules. Every lookup
here therefore takes an optional scope, and a caller that knows which key it is
programming should pass it -- an STM2 is a switch, and an accessory holding ACC 1 is
simply not in its way. The scope compared against is the occupant's
LcsOccupant.effective_scope, the registry's scope for the mode the module reports, not
the store scope the state happened to be filed under.

No Tk or guizero symbols are imported; the map is pure logic over the state store and
is unit-testable with any object exposing get_all(scope).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, List

from ...protocol.constants import CommandScope
from .lcs_device_registry import LcsDevice, LcsMode, device_for_pdi_device, devices_for_state

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
    def effective_scope(self) -> CommandScope | None:
        """
        The remote key that actually addresses this module: ACC, SW, or TR.

        The registry's scope for the mode the module reports, in preference to the store
        scope the state was filed under, because the registry is the panel's source of
        truth for scope: asc2_req.py reads SWITCH if mode == 2 else ACC, so a mode-3
        (switch, latching) ASC2 is filed with the accessories. The store scope is the
        fallback for a module whose mode has not been parsed.
        """
        return self.mode.scope if self.mode is not None else self.scope

    @property
    def is_base(self) -> bool:
        return self.port_index == 1 or self.port_index is None

    def claims(self, tmcc_id: int) -> bool:
        return self.base_id <= tmcc_id <= self.last_id

    def at(self, tmcc_id: int) -> LcsOccupant:
        """
        Return a copy of this occupant reporting the 1-based port index of tmcc_id.
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


def _pdi_store(pdi_store: Any = None) -> Any:
    """
    The PDI device store, when this process has one; every caller tolerates None.

    A GUI can run against a component state store with no PDI side at all -- an embedded
    panel in a process that never built one, or a test -- so its absence is normal and
    simply leaves the component states as the only source.
    """
    if pdi_store is not None:
        return pdi_store
    from ...pdi.pdi_state_store import PdiStateStore

    return PdiStateStore.get() if PdiStateStore.is_built() else None


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


def _occupants_of_state(state: Any, scope: CommandScope) -> List[LcsOccupant]:
    """
    Every module the given component state identifies, sized from that record.

    A record shared by two modules names them both once each has reported, but it carries
    only one num_ids and one mode, so both come out the same size. That is why the PDI
    store is consulted first, where each module is sized from its own CONFIG packet.
    """
    base_id = getattr(state, "address", None)
    if not isinstance(base_id, int) or base_id < 1:
        return []
    found: List[LcsOccupant] = []
    for device in devices_for_state(state):
        mode = _mode_of(device, state)
        found.append(
            LcsOccupant(
                base_id=base_id,
                device=device,
                mode=mode,
                ports=_ports_of(mode, state),
                port_index=1,
                scope=scope,
                state=state,
            )
        )
    return found


def _state_occupants(store: Any) -> List[LcsOccupant]:
    """
    Walk the component state store for modules its states identify.
    """
    if store is None:
        return []
    found: List[LcsOccupant] = []
    for store_scope in LCS_SCOPES:
        # noinspection PyBroadException
        try:
            states = store.get_all(store_scope) or []
        except Exception:  # pragma: no cover - defensive; store shapes vary
            continue
        for state in states:
            # Interior ports have a parent and a port number greater than one. A
            # Sensor Track proxy also has a parent, but its IRDA sibling is at
            # the same address and the proxy is still the module's base state.
            if getattr(state, "parent", None) is not None and getattr(state, "port", 1) > 1:
                continue
            found.extend(_occupants_of_state(state, store_scope))
    return found


# A callable checked against None is still narrowed to a callable, but PyCharm loses that
# inside a loop; the guard below is what makes the call safe.
# noinspection PyCallingNonCallable
def _state_at(store: Any, occupant_scope: CommandScope | None, device: LcsDevice, base_id: int) -> Any:
    """
    The component state behind a PDI-derived module, when there is one.

    Carried on the occupant so that seeding a chosen module from it still works. The
    module's own remote key is tried first, then the scope its PDI requests are filed
    under, which differ for a mode-3 ASC2: the registry calls it a switch, while
    asc2_req.py files it with the accessories.
    """
    get_state: Callable[..., Any] | None = getattr(store, "get_state", None) if store is not None else None
    if get_state is None:
        return None
    for scope in (occupant_scope, device.pdi_device.scope):
        if scope is None:
            continue
        # noinspection PyBroadException
        try:
            state = get_state(scope, base_id, False)
        except Exception:  # pragma: no cover - defensive; store shapes vary
            continue
        if state is not None:
            return state
    return None


def _pdi_occupants(pdi_store: Any, store: Any) -> List[LcsOccupant]:
    """
    Every module the PDI device store knows, one entry per module type per TMCC ID.

    Sized from the module's own mode rather than from any component state: the record at
    the address may be shared with another module, and its num_ids then belongs to
    whichever of them reported last. A module the registry declares no modes for -- an
    AMC2 -- holds a single ID, which is what Amc2Req.num_addressable_ports reports.
    """
    if pdi_store is None:
        return []
    # noinspection PyBroadException
    try:
        pdi_devices = pdi_store.keys() or []
    except Exception:  # pragma: no cover - defensive; store shapes vary
        return []
    found: List[LcsOccupant] = []
    for pdi_device in pdi_devices:
        device = device_for_pdi_device(pdi_device)
        if device is None:
            continue
        # noinspection PyBroadException
        try:
            configs = pdi_store.get_all(pdi_device) or []
        except Exception:  # pragma: no cover - defensive; store shapes vary
            continue
        for config in configs:
            base_id = getattr(config, "tmcc_id", None)
            if not isinstance(base_id, int) or base_id < 1:
                continue
            mode = _mode_of(device, config)
            scope = getattr(config, "scope", None) or pdi_device.scope
            found.append(
                LcsOccupant(
                    base_id=base_id,
                    device=device,
                    mode=mode,
                    ports=mode.ports if mode is not None else 1,
                    port_index=1,
                    scope=scope,
                    state=_state_at(store, mode.scope if mode is not None else scope, device, base_id),
                )
            )
    return found


def occupants(store: Any = None, scope: CommandScope | None = None, pdi_store: Any = None) -> List[LcsOccupant]:
    """
    Return every LCS module currently known, one per module base.

    The PDI device store is read first and the component states second, so a module the
    PDI bus reported keeps the mode and block size from its own CONFIG packet even when it
    shares a component state with another module. Modules found only in the states are
    appended, which is what covers a store with no PDI side.

    scope keeps only the modules addressed by that remote key, compared against each
    occupant's LcsOccupant.effective_scope. Omit it while still working out what kind of
    module is being looked at, when every module is a candidate.
    """
    store = _store(store)
    candidates = _pdi_occupants(_pdi_store(pdi_store), store) + _state_occupants(store)
    found: List[LcsOccupant] = []
    seen: set[tuple[str, int, Any]] = set()
    for occupant in candidates:
        if scope is not None and occupant.effective_scope != scope:
            continue
        # One entry per module: the same base under two remote keys is two modules, so the
        # key that de-duplicates has to say which key addresses this one. The first entry
        # wins, which is the PDI-derived one whenever the PDI store knows the module.
        key = (occupant.device.key, occupant.base_id, occupant.effective_scope)
        if key in seen:
            continue
        seen.add(key)
        found.append(occupant)
    found.sort(key=lambda o: o.base_id)
    return found


def occupants_of(
    tmcc_id: int,
    store: Any = None,
    scope: CommandScope | None = None,
    pdi_store: Any = None,
) -> List[LcsOccupant]:
    """
    Return every LCS module claiming tmcc_id, each with its 1-based port_index.

    More than one module can hold the same address even on the same remote key: an AMC2
    and a BPC2 both answering to ACC 1 is a real layout, and reporting only the first of
    them would tell the operator half the truth about the address they are about to
    program. Ordered by base ID, so the module whose block starts earliest is named first.

    scope limits the answer to modules answering to that remote key; see occupants().
    """
    return [occupant.at(tmcc_id) for occupant in occupants(store, scope, pdi_store) if occupant.claims(tmcc_id)]


def occupant_of(
    tmcc_id: int,
    store: Any = None,
    scope: CommandScope | None = None,
    pdi_store: Any = None,
) -> LcsOccupant | None:
    """
    Return the LCS module claiming tmcc_id, with its 1-based port_index, or None.

    The first of them when several do; occupants_of() returns them all.
    scope limits the answer to modules answering to that remote key; see occupants().
    """
    found = occupants_of(tmcc_id, store, scope, pdi_store)
    return found[0] if found else None


def overlaps(
    base_id: int,
    ports: int,
    store: Any = None,
    ignore_base: int | None = None,
    scope: CommandScope | None = None,
    pdi_store: Any = None,
) -> List[LcsOccupant]:
    """
    Return the known modules whose blocks intersect base_id .. base_id + ports - 1.

    ignore_base omits the module being reconfigured, which necessarily overlaps itself.
    scope limits the answer to modules answering to that remote key; blocks in two
    different key namespaces cannot collide, however far they run into one another.
    """
    last_id = base_id + max(ports, 1) - 1
    found: List[LcsOccupant] = []
    for occupant in occupants(store, scope, pdi_store):
        if ignore_base is not None and occupant.base_id == ignore_base:
            continue
        if occupant.base_id <= last_id and base_id <= occupant.last_id:
            found.append(occupant)
    return found
