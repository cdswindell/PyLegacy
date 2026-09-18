"""Qt controllers for operating switches and routes."""

from __future__ import annotations

from threading import Thread

from PySide6.QtCore import Property, QObject, Signal, Slot

from pytrain.comm.command_listener import CommandDispatcher
from pytrain.db.component_state import RouteState, SwitchState
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.gui.controller.lcs_id_map import occupants_of
from pytrain.gui.controller.route_draft import RouteDraft
from pytrain.pdi.base_req import BaseReq
from pytrain.pdi.constants import PdiCommand
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1HaltCommandEnum, TMCC1SwitchCommandEnum
from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2RouteCommandEnum


class OpsController(QObject):
    """Expose a roster and direct operating commands for one scope."""

    changed = Signal()
    commandReceived = Signal(int, str)

    def __init__(self, scope: CommandScope, parent: QObject | None = None) -> None:
        if scope not in {CommandScope.SWITCH, CommandScope.ROUTE}:
            raise ValueError(f"Unsupported operations scope: {scope}")
        super().__init__(parent)
        self._scope = scope
        self._rows: list[dict] = []
        self._selected_id = 0
        self._route_draft: RouteDraft | None = None
        self._route_component_index = -1
        self._dispatcher = CommandDispatcher.get()
        self.commandReceived.connect(self._refresh_after_command)
        self._dispatcher.subscribe(self._command_received, self._scope)
        if self._scope == CommandScope.ROUTE:
            self._dispatcher.subscribe(self._command_received, CommandScope.SWITCH)
        self.reload()

    def close(self) -> None:
        self._dispatcher.unsubscribe(self._command_received, self._scope)
        if self._scope == CommandScope.ROUTE:
            self._dispatcher.unsubscribe(self._command_received, CommandScope.SWITCH)

    def _state(self):
        if not self._selected_id:
            return None
        return ComponentStateStore.get_state(self._scope, self._selected_id, create=False)

    @staticmethod
    def _identity(state) -> tuple[str, str]:
        road_name = str(getattr(state, "road_name", "") or getattr(state, "name", "") or "").strip()
        road_number = str(getattr(state, "road_number", "") or "").strip()
        return road_name, road_number

    @staticmethod
    def _state_text(state) -> str:
        if isinstance(state, SwitchState):
            return "THRU" if state.is_thru else "OUT" if state.is_out else "UNKNOWN"
        if isinstance(state, RouteState):
            return "ALIGNED" if state.is_aligned else "UNKNOWN" if state.is_unknown else "NOT ALIGNED"
        return "UNKNOWN"

    @staticmethod
    def _switch_lcs_associations(tmcc_id: int) -> str:
        """Describe each STM2/ASC2 module and port that owns this switch address."""
        associations = []
        for occupant in occupants_of(tmcc_id, scope=CommandScope.SWITCH):
            if occupant.device.key not in {"stm2", "asc2"}:
                continue
            port = occupant.port_index
            label = f"{occupant.device.label} {occupant.base_id}"
            if port is not None:
                label += f" Port {port}"
            associations.append(label)
        return " · ".join(associations)

    def _row(self, state) -> dict:
        road_name, road_number = self._identity(state)
        inactive = isinstance(state, SwitchState) and not state.is_user_defined
        lcs_associations = self._switch_lcs_associations(int(state.tmcc_id)) if isinstance(state, SwitchState) else ""
        return {
            "tmccId": int(state.tmcc_id),
            "roadName": road_name,
            "roadNumber": road_number,
            "stateText": self._state_text(state),
            "inactive": inactive,
            "lcsAssociations": lcs_associations,
        }

    def _refresh_row(self, tmcc_id: int) -> None:
        state = ComponentStateStore.get_state(self._scope, tmcc_id, create=False)
        if state is None:
            self.reload()
            return
        row = self._row(state)
        for index, existing in enumerate(self._rows):
            if existing["tmccId"] == tmcc_id:
                self._rows[index] = row
                self._rows = list(self._rows)
                self.changed.emit()
                return
        self.reload()

    def _command_received(self, command: CommandReq) -> None:
        """Queue UI refresh until dispatcher subscribers have processed the command."""
        tmcc_id = int(getattr(command, "address", 0) or 0)
        scope = getattr(command, "scope", None)
        if tmcc_id and scope in {CommandScope.SWITCH, CommandScope.ROUTE}:
            self.commandReceived.emit(tmcc_id, scope.name)

    @Slot(int, str)
    def _refresh_after_command(self, tmcc_id: int, scope_name: str) -> None:
        """Read state on the Qt thread after ComponentStateStore has handled the command."""
        if self._scope == CommandScope.ROUTE and scope_name == CommandScope.SWITCH.name:
            self.reload()
        elif scope_name == self._scope.name:
            self._refresh_row(tmcc_id)

    @Slot()
    def reload(self) -> None:
        states = sorted(ComponentStateStore.get().get_all(self._scope), key=lambda item: item.tmcc_id)
        self._rows = [self._row(state) for state in states]
        state_ids = {int(state.tmcc_id) for state in states}
        if self._selected_id and self._selected_id not in state_ids:
            self._selected_id = 0
        self.changed.emit()

    @Slot(int)
    def select(self, tmcc_id: int) -> None:
        if any(row["tmccId"] == tmcc_id for row in self._rows):
            self._selected_id = tmcc_id
            self.changed.emit()

    @Slot(str)
    def operate(self, action: str) -> None:
        if not self._selected_id:
            return
        if self._scope == CommandScope.SWITCH:
            command = TMCC1SwitchCommandEnum.THRU if action == "THRU" else TMCC1SwitchCommandEnum.OUT
        else:
            command = TMCC2RouteCommandEnum.FIRE
        CommandReq.build(command, self._selected_id).send()

    @Slot(int, str)
    def operateSwitch(self, tmcc_id: int, action: str) -> None:
        if self._scope != CommandScope.SWITCH or action not in {"THRU", "OUT"}:
            return
        if not any(row["tmccId"] == tmcc_id for row in self._rows):
            return
        command = TMCC1SwitchCommandEnum.THRU if action == "THRU" else TMCC1SwitchCommandEnum.OUT
        CommandReq.build(command, tmcc_id).send()

    @Slot(int)
    def toggleSwitch(self, tmcc_id: int) -> None:
        if self._scope != CommandScope.SWITCH:
            return
        state = ComponentStateStore.get_state(CommandScope.SWITCH, tmcc_id, create=False)
        if not isinstance(state, SwitchState):
            return
        command = TMCC1SwitchCommandEnum.OUT if state.is_thru else TMCC1SwitchCommandEnum.THRU
        CommandReq.build(command, tmcc_id).send()

    @Slot(int, result=str)
    def switchRoadName(self, tmcc_id: int) -> str:
        state = ComponentStateStore.get_state(CommandScope.SWITCH, tmcc_id, create=False)
        return self._identity(state)[0] if isinstance(state, SwitchState) else ""

    @Slot(int, result=str)
    def switchRoadNumber(self, tmcc_id: int) -> str:
        state = ComponentStateStore.get_state(CommandScope.SWITCH, tmcc_id, create=False)
        return self._identity(state)[1] if isinstance(state, SwitchState) else ""

    @Slot(int, str, str)
    def saveSwitchIdentity(self, tmcc_id: int, road_name: str, road_number: str) -> None:
        if self._scope != CommandScope.SWITCH:
            return
        state = ComponentStateStore.get_state(CommandScope.SWITCH, tmcc_id, create=False)
        if not isinstance(state, SwitchState) or state.comp_data is None:
            return
        road_name = road_name.strip()
        road_number = road_number.strip().zfill(4) if road_number.strip() else ""
        requests = []
        if road_name != str(state.road_name or "").strip():
            requests.append(state.comp_data.set_road_name_req(road_name))
        if road_number != str(state.road_number or "").strip():
            requests.append(state.comp_data.set_road_number_req(road_number))
        if requests:
            BaseReq.process_sync_reqs([*requests, state], do_async=True)
        self._refresh_row(tmcc_id)

    def _provision_switch(self, tmcc_id: int, road_name: str, road_number: str, command_control: bool) -> None:
        """Program the switch, persist its Base record, then request authoritative config."""
        if command_control:
            CommandReq.build(TMCC1SwitchCommandEnum.SET_ADDRESS, tmcc_id).send()

        state = ComponentStateStore.get_state(CommandScope.SWITCH, tmcc_id, create=True)
        if state is None:
            return
        if state.comp_data is None:
            state.initialize(CommandScope.SWITCH, tmcc_id)

        requests = [state.comp_data.set_road_name_req(road_name)]
        if road_number:
            requests.append(state.comp_data.set_road_number_req(road_number))
        for request in requests:
            request.send()

        # BASE_SWITCH is deliberately last. Its reply is the authoritative switch config
        # and follows the normal PDI distribution path to the server and connected clients.
        BaseReq(tmcc_id, PdiCommand.BASE_SWITCH).send()

    @Slot(int, result="QVariantMap")
    def switchIdentity(self, tmcc_id: int) -> dict:
        """Return an existing switch's identity for Add Switch field completion."""
        if not 1 <= tmcc_id <= 98:
            return {"exists": False, "roadName": "", "roadNumber": ""}
        state = ComponentStateStore.get_state(CommandScope.SWITCH, tmcc_id, create=False)
        if not isinstance(state, SwitchState):
            return {"exists": False, "roadName": "", "roadNumber": ""}
        road_name, road_number = self._identity(state)
        return {"exists": True, "roadName": road_name, "roadNumber": road_number}

    @Slot(int, str, str, bool, bool, result=str)
    def addSwitch(
        self,
        tmcc_id: int,
        road_name: str,
        road_number: str,
        command_control: bool,
        overwrite: bool = False,
    ) -> str:
        """Validate and start provisioning a physical switch; return an error or empty string."""
        if self._scope != CommandScope.SWITCH:
            return "Switch provisioning is only available from the Switch screen."
        if not 1 <= tmcc_id <= 98:
            return "TMCC ID must be between 1 and 98; 99 is the broadcast address."
        exists = ComponentStateStore.get_state(CommandScope.SWITCH, tmcc_id, create=False) is not None
        if exists and not overwrite:
            return f"Switch {tmcc_id} already exists."

        road_name = road_name.strip()
        if not road_name:
            return "Road Name is required."
        road_number = road_number.strip()
        if road_number and (not road_number.isdigit() or len(road_number) > 4):
            return "Road Number must contain no more than four digits."
        road_number = road_number.zfill(4) if road_number else ""

        Thread(
            target=self._provision_switch,
            args=(tmcc_id, road_name, road_number, command_control),
            daemon=True,
        ).start()
        return ""

    @staticmethod
    def _existing_route(state) -> bool:
        return (
            isinstance(state, RouteState)
            and not state.is_deleted
            and state.tmcc_id is not None
            and 1 <= state.tmcc_id <= 99
            and bool(not state.is_comp_data_empty or state.is_user_defined or state.components)
        )

    def _lookup_route(self, tmcc_id: int) -> RouteState | None:
        state = ComponentStateStore.get_state(CommandScope.ROUTE, tmcc_id, create=False)
        return state if isinstance(state, RouteState) else None

    @Slot()
    def openNewRouteBuilder(self) -> None:
        """Open an unnumbered route draft so components can be selected before assigning its TMCC ID."""
        if self._scope != CommandScope.ROUTE:
            return
        self._route_draft = RouteDraft(0, ())
        self._route_component_index = -1
        self.changed.emit()

    @Slot(int, result=str)
    def openRouteBuilder(self, tmcc_id: int) -> str:
        if self._scope != CommandScope.ROUTE or not 1 <= tmcc_id <= 98:
            return "Route ID must be an integer from 1 to 98."
        state = self._lookup_route(tmcc_id)
        self._route_draft = RouteDraft(
            tmcc_id,
            (state.components or ()) if self._existing_route(state) else (),
            road_name=state.road_name if self._existing_route(state) and state.is_road_name else "",
            road_number=state.road_number if self._existing_route(state) and state.is_road_number else "",
        )
        self._route_component_index = 0 if self._route_draft.components else -1
        self.changed.emit()
        return ""

    @Slot(int, result=str)
    def assignRouteBuilderId(self, tmcc_id: int) -> str:
        if self._route_draft is None:
            return "Open a route before assigning its TMCC ID."
        try:
            self._route_draft.assign_tmcc_id(tmcc_id)
        except ValueError as exc:
            return str(exc)
        self.changed.emit()
        return ""

    @Slot(int, result=bool)
    def routeExists(self, tmcc_id: int) -> bool:
        return self._existing_route(self._lookup_route(tmcc_id))

    @Slot()
    def closeRouteBuilder(self) -> None:
        self._route_draft = None
        self._route_component_index = -1
        self.changed.emit()

    @Slot(int)
    def selectRouteComponent(self, index: int) -> None:
        if self._route_draft is not None and 0 <= index < len(self._route_draft.components):
            self._route_component_index = index
            self.changed.emit()

    @Slot(int)
    def moveRouteComponent(self, delta: int) -> None:
        if self._route_draft is None or self._route_component_index < 0:
            return
        self._route_component_index = self._route_draft.move(self._route_component_index, delta)
        self.changed.emit()

    @Slot()
    def removeRouteComponent(self) -> None:
        if self._route_draft is None or self._route_component_index < 0:
            return
        self._route_draft.remove(self._route_component_index)
        count = len(self._route_draft.components)
        self._route_component_index = min(self._route_component_index, count - 1) if count else -1
        self.changed.emit()

    @Slot()
    def clearRouteComponents(self) -> None:
        if self._route_draft is not None:
            self._route_draft.clear()
            self._route_component_index = -1
            self.changed.emit()

    @Slot(str)
    def setRouteComponentPosition(self, position: str) -> None:
        if self._route_draft is None or self._route_component_index < 0:
            return
        component = self._route_draft.components[self._route_component_index]
        if component.is_route or position not in {"THRU", "OUT"}:
            return
        self._route_draft.set_component(
            self._route_component_index,
            component.tmcc_id,
            0 if position == "THRU" else 1,
            self._lookup_route,
        )
        self.changed.emit()

    @Slot(str, int, result=str)
    def addRouteComponent(self, scope_name: str, tmcc_id: int) -> str:
        if self._route_draft is None:
            return "Open a route before adding components."
        if len(self._route_draft.components) >= 16:
            return "A route can contain at most 16 components."
        try:
            scope = CommandScope[scope_name]
        except KeyError:
            return "Choose a switch or route."
        if scope not in {CommandScope.SWITCH, CommandScope.ROUTE}:
            return "Choose a switch or route."
        try:
            self._route_draft.set_component(
                None,
                tmcc_id,
                3 if scope == CommandScope.ROUTE else 0,
                self._lookup_route,
            )
        except ValueError as exc:
            return str(exc)
        self._route_component_index = len(self._route_draft.components) - 1
        self.changed.emit()
        return ""

    @Slot(str, str, result=str)
    def saveRouteBuilder(self, road_name: str, road_number: str) -> str:
        if self._route_draft is None:
            return "Open a route before saving."
        road_name = road_name.strip()
        road_number = road_number.strip()
        try:
            self._route_draft.set_metadata(road_name, road_number)
            self._route_draft.validate(self._lookup_route)
            state = self._lookup_route(self._route_draft.tmcc_id)
            if state is None:
                state = ComponentStateStore.get_state(CommandScope.ROUTE, self._route_draft.tmcc_id, create=True)
                if state is None:
                    return "Unable to create the route state."
                state.initialize(CommandScope.ROUTE, self._route_draft.tmcc_id)
            requests = self._route_draft.build_requests(state, self._lookup_route)
            BaseReq.process_sync_reqs([*requests, state], do_async=True)
        except Exception as exc:
            return str(exc)
        self._route_draft.mark_saved()
        self._route_draft = None
        self._route_component_index = -1
        self.reload()
        return ""

    @Property(bool, notify=changed)
    def routeBuilderOpen(self) -> bool:
        return self._route_draft is not None

    @Property(int, notify=changed)
    def routeBuilderId(self) -> int:
        return self._route_draft.tmcc_id if self._route_draft is not None else 0

    @Property(str, notify=changed)
    def routeBuilderName(self) -> str:
        return self._route_draft.road_name if self._route_draft is not None else ""

    @Property(str, notify=changed)
    def routeBuilderNumber(self) -> str:
        return self._route_draft.road_number if self._route_draft is not None else ""

    @Property(int, notify=changed)
    def routeComponentIndex(self) -> int:
        return self._route_component_index

    @Property(list, notify=changed)
    def routeComponents(self) -> list[dict]:
        if self._route_draft is None:
            return []
        rows = []
        for index, component in enumerate(self._route_draft.components):
            scope = CommandScope.ROUTE if component.is_route else CommandScope.SWITCH
            state = ComponentStateStore.get_state(scope, component.tmcc_id, create=False)
            name = self._identity(state)[0] if state is not None else ""
            rows.append(
                {
                    "index": index,
                    "tmccId": component.tmcc_id,
                    "scope": scope.name,
                    "name": name or f"{scope.title} {component.tmcc_id:02d}",
                    "position": ("ROUTE" if component.is_route else "THRU" if component.is_thru else "OUT"),
                }
            )
        return rows

    @Property(list, notify=changed)
    def routeCandidates(self) -> list[dict]:
        if self._route_draft is None:
            return []
        rows = []
        for scope in (CommandScope.SWITCH, CommandScope.ROUTE):
            for state in ComponentStateStore.get().get_all(scope):
                if state.is_deleted or not 1 <= state.tmcc_id <= 99:
                    continue
                if scope == CommandScope.ROUTE and state.tmcc_id == self._route_draft.tmcc_id:
                    continue
                name, road_number = self._identity(state)
                rows.append(
                    {
                        "tmccId": int(state.tmcc_id),
                        "scope": scope.name,
                        "name": name or f"{scope.title} {state.tmcc_id:02d}",
                        "roadNumber": road_number,
                        "userDefined": bool(state.is_user_defined),
                    }
                )
        return rows

    @Slot(int)
    def fireRoute(self, tmcc_id: int) -> None:
        if self._scope != CommandScope.ROUTE:
            return
        if any(row["tmccId"] == tmcc_id for row in self._rows):
            CommandReq.build(TMCC2RouteCommandEnum.FIRE, tmcc_id).send()

    @Slot()
    def halt(self) -> None:
        CommandReq.build(TMCC1HaltCommandEnum.HALT).send()

    @Property(str, constant=True)
    def scope(self) -> str:
        return self._scope.name

    @Property(list, notify=changed)
    def rows(self) -> list[dict]:
        return self._rows

    @Property(int, notify=changed)
    def selectedId(self) -> int:
        return self._selected_id

    @Property(str, notify=changed)
    def roadName(self) -> str:
        state = self._state()
        return self._identity(state)[0] if state is not None else ""

    @Property(str, notify=changed)
    def roadNumber(self) -> str:
        state = self._state()
        return self._identity(state)[1] if state is not None else ""

    @Property(str, notify=changed)
    def stateText(self) -> str:
        state = self._state()
        return self._state_text(state) if state is not None else ""

    @Property(bool, notify=changed)
    def isThru(self) -> bool:
        state = self._state()
        return isinstance(state, SwitchState) and state.is_thru

    @Property(bool, notify=changed)
    def isOut(self) -> bool:
        state = self._state()
        return isinstance(state, SwitchState) and state.is_out
