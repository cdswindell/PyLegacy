#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING

from ...db.comp_data import RouteData
from ...db.component_state import RouteState
from ...db.components import RouteComponent

if TYPE_CHECKING:
    from ...pdi.base_req import BaseReq

RouteLookup = Callable[[int], RouteState | None]


class RouteDraft:
    """Editable route metadata and ordered components isolated from live state."""

    def __init__(
        self,
        tmcc_id: int,
        components: Iterable[RouteComponent] = (),
        road_name: str = "",
        road_number: str = "",
    ) -> None:
        if not isinstance(tmcc_id, int) or isinstance(tmcc_id, bool) or not 1 <= tmcc_id <= 99:
            raise ValueError("Route ID must be an integer from 1 to 99.")
        self._validate_metadata(road_name, road_number)
        self._tmcc_id = tmcc_id
        self._components = self._copy_components(components)
        self._road_name = road_name
        self._road_number = road_number
        self._saved = (self._component_values(), self.road_name, self.road_number)

    @property
    def tmcc_id(self) -> int:
        return self._tmcc_id

    @property
    def components(self) -> tuple[RouteComponent, ...]:
        return tuple(RouteComponent(c.tmcc_id, c.flags) for c in self._components)

    @property
    def road_name(self) -> str:
        return self._road_name

    @property
    def road_number(self) -> str:
        return self._road_number

    @property
    def dirty(self) -> bool:
        return (self._component_values(), self.road_name, self.road_number) != self._saved

    def set_metadata(self, road_name: str, road_number: str) -> None:
        """Validate both fields before updating either draft value."""
        self._validate_metadata(road_name, road_number)
        self._road_name = road_name
        self._road_number = road_number

    def set_component(self, index: int | None, tmcc_id: int, flags: int, lookup: RouteLookup) -> None:
        candidate = list(self._components)
        component = RouteComponent(tmcc_id, flags)
        component.validate()
        if index is None:
            candidate.append(component)
        else:
            self._validate_index(index)
            current = candidate[index]
            if current.tmcc_id == tmcc_id and current.is_switch and flags in {0, 1}:
                # Reselecting OUT must not replace an existing OUT encoding.
                component.flags = current.flags if flags == 1 and current.is_out else (current.flags & ~0x03) | flags
            candidate[index] = component
        components = self._copy_components(candidate)
        self._validate_graph(components, lookup)
        self._components = components

    def remove(self, index: int) -> None:
        self._validate_index(index)
        self._components = self._components[:index] + self._components[index + 1 :]

    def move(self, index: int, delta: int) -> int:
        """Move an existing component, clamp at either end, and return its new index."""
        self._validate_index(index)
        if not isinstance(delta, int) or isinstance(delta, bool):
            raise ValueError("Move distance must be an integer.")
        selected = min(max(index + delta, 0), len(self._components) - 1)
        if selected != index:
            components = list(self._components)
            components.insert(selected, components.pop(index))
            self._components = tuple(components)
        return selected

    def clear(self) -> None:
        """Remove all components without changing draft metadata."""
        self._components = ()

    def validate(self, lookup: RouteLookup) -> None:
        self._validate_metadata(self.road_name, self.road_number)
        self._validate_graph(self._components, lookup)

    def build_request(self, state: RouteState, lookup: RouteLookup) -> BaseReq:
        """Build one component-only write; do not send it or mutate the live state."""
        if not isinstance(state, RouteState) or state.tmcc_id != self.tmcc_id or state.is_deleted:
            raise ValueError(f"Select route {self.tmcc_id} before saving its components.")
        self.validate(lookup)
        with state.synchronizer:
            data = state.comp_data if state.comp_data is not None else RouteData(None, self.tmcc_id)
            return data.set_components_req(self._components)

    def build_requests(self, state: RouteState, lookup: RouteLookup) -> list[BaseReq]:
        """Build unsent name, number, and component writes without changing live state.

        Metadata builders operate on a detached record. Their existing encoding
        pads nonzero road numbers to four digits and treats zero as empty.
        """
        components_req = self.build_request(state, lookup)
        data = RouteData(None, self.tmcc_id)
        return [
            data.set_road_name_req(self.road_name),
            data.set_road_number_req(int(self.road_number) if self.road_number else None),
            components_req,
        ]

    def mark_saved(self) -> None:
        self._saved = (self._component_values(), self.road_name, self.road_number)

    def _component_values(self) -> tuple[tuple[int, int], ...]:
        return tuple((c.tmcc_id, c.flags) for c in self._components)

    @staticmethod
    def _validate_metadata(road_name: str, road_number: str) -> None:
        if not isinstance(road_name, str) or len(road_name) > 31:
            raise ValueError("Road name must be a string of at most 31 characters.")
        if not road_name.isascii():
            raise ValueError("Road name must contain only ASCII characters.")
        if not isinstance(road_number, str) or len(road_number) > 4 or any(c < "0" or c > "9" for c in road_number):
            raise ValueError("Road number must be empty or contain at most 4 decimal digits.")

    def _validate_index(self, index: int) -> None:
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(self._components):
            raise ValueError("Select an existing route component.")

    @staticmethod
    def _copy_components(components: Iterable[RouteComponent]) -> tuple[RouteComponent, ...]:
        copied = []
        for component in components:
            if not isinstance(component, RouteComponent):
                raise ValueError("Each route component must be a switch or a nested route.")
            copied.append(RouteComponent(component.tmcc_id, component.flags))
        RouteComponent.to_bytes(copied)
        return tuple(copied)

    def _validate_graph(self, components: tuple[RouteComponent, ...], lookup: RouteLookup) -> None:
        visiting = {self.tmcc_id}
        visited = set()

        def visit(items: Iterable[RouteComponent]) -> None:
            items = self._copy_components(items)
            for component in items:
                if not component.is_route:
                    continue
                route_id = component.tmcc_id
                if route_id == self.tmcc_id:
                    raise ValueError(f"Route {self.tmcc_id} cannot include itself, directly or through another route.")
                if route_id in visiting:
                    raise ValueError(f"Route recursion detected involving route {route_id}.")
                if route_id in visited:
                    continue
                route = lookup(route_id)
                if (
                    route is None
                    or route.is_deleted
                    or not route.is_comp_data_record
                    or route.comp_data.components is None
                ):
                    raise ValueError(
                        f"Route {route_id} is unavailable or has not been loaded. Refresh route data first."
                    )
                with route.synchronizer:
                    nested = self._copy_components(route.comp_data.components)
                visiting.add(route_id)
                visit(nested)
                visiting.remove(route_id)
                visited.add(route_id)

        visit(components)
