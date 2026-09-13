"""Qt bridge exposing a PyTrain cab through QObject properties and slots."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.prod_info import ENGINE_IMAGES_CACHE_DIR, ENGINE_INFO_CACHE_DIR
from pytrain.protocol.constants import CommandScope
from pytrain.utils.path_utils import find_file

from pytrain_ui.actions import cab_action, cab_actions
from pytrain_ui.adapters import PyTrainCabCommandAdapter, PyTrainCabStateAdapter
from pytrain_ui.contracts import EngineViewState
from pytrain_ui.panels import panel_actions, panel_title

_ENGINE_ARTWORK = {
    "ACELA": "acela.jpg",
    "CRANE": "generic_crane_car.jpg",
    "DIESEL": "generic_diesel.jpg",
    "DIESEL_PULLMOR": "generic_diesel.jpg",
    "DIESEL_SWITCHER": "generic_diesel_switcher.jpg",
    "ELECTRIC": "generic_electric.jpg",
    "STEAM": "generic_steam.jpg",
}


class CabController(QObject):
    stateChanged = Signal()
    rosterChanged = Signal()

    def __init__(self, scope: CommandScope, tmcc_id: int, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state_port = None
        self._command_port = None
        self._unsubscribe = None
        self._snapshot = EngineViewState(scope=scope.name, tmcc_id=tmcc_id)
        self._targets: list[tuple[CommandScope, int, str]] = []
        self._target_labels: list[str] = []
        self._target_index = -1
        self._reload_roster()
        self._switch_target(scope, tmcc_id)

    def close(self) -> None:
        self._release_target()

    def _release_target(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._state_port is not None:
            self._state_port.shutdown()
            self._state_port = None
        self._command_port = None

    def _reload_roster(self) -> None:
        store = ComponentStateStore.get()
        targets: list[tuple[CommandScope, int, str]] = []
        for scope in (CommandScope.ENGINE, CommandScope.TRAIN):
            for state in store.get_all(scope):
                road_name = str(getattr(state, "road_name", "") or getattr(state, "name", "") or "").strip()
                road_number = str(getattr(state, "road_number", "") or "").strip()
                detail = " ".join(part for part in (road_name, road_number) if part)
                label = f"{scope.label.title()} {state.tmcc_id}"
                if detail:
                    label += f" — {detail}"
                targets.append((scope, state.tmcc_id, label))
        targets.sort(key=lambda item: (0 if item[0] == CommandScope.ENGINE else 1, item[1]))
        self._targets = targets
        self._target_labels = [item[2] for item in targets]
        self.rosterChanged.emit()

    def _switch_target(self, scope: CommandScope, tmcc_id: int) -> None:
        self._release_target()
        self._state_port = PyTrainCabStateAdapter(scope, tmcc_id)
        self._command_port = PyTrainCabCommandAdapter(self._state_port)
        self._snapshot = self._state_port.current()
        self._unsubscribe = self._state_port.subscribe(self._on_state)
        self._target_index = next(
            (i for i, item in enumerate(self._targets) if item[0] == scope and item[1] == tmcc_id),
            -1,
        )
        self.stateChanged.emit()
        self.rosterChanged.emit()

    def _on_state(self, snapshot: EngineViewState) -> None:
        self._snapshot = snapshot
        self.stateChanged.emit()

    def _artwork_state(self):
        state = self._state_port.state if self._state_port is not None else None
        if state is not None and state.scope == CommandScope.TRAIN:
            head_id = int(getattr(state, "head_tmcc_id", 0) or 0)
            if head_id:
                head = ComponentStateStore.get_state(CommandScope.ENGINE, head_id, create=False)
                if head is not None:
                    state = head
        return state

    def _custom_artwork(self, state) -> str | None:
        if state is None:
            return None
        tmcc_id = int(getattr(state, "tmcc_id", 0) or 0)
        if not tmcc_id:
            return None
        return find_file(f"{tmcc_id}.jpg", places=(Path.cwd(), ENGINE_IMAGES_CACHE_DIR))

    def _product_artwork(self, state) -> str | None:
        if state is None:
            return None
        bt_id = str(getattr(state, "bt_id", "") or "").strip()
        if not bt_id:
            return None
        info_file = find_file(f"{bt_id}.json", places=(Path.cwd(), ENGINE_INFO_CACHE_DIR))
        if not info_file or not Path(info_file).is_file():
            return None
        try:
            with open(info_file, "r", encoding="utf-8") as handle:
                product = json.load(handle)
            image_url = str(product.get("imageUrl", "") or "")
            filename = PurePosixPath(urlparse(image_url).path).name if image_url else ""
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
        if not filename:
            return None
        return find_file(filename, places=(Path.cwd(), ENGINE_IMAGES_CACHE_DIR))

    def _resolved_artwork(self, state) -> tuple[str | None, str]:
        path = self._custom_artwork(state)
        if path:
            return path, "custom"
        path = self._product_artwork(state)
        if path:
            return path, "product"
        engine_type = getattr(state, "engine_type_enum", None)
        name = str(getattr(engine_type, "name", "DIESEL") or "DIESEL")
        return find_file(_ENGINE_ARTWORK.get(name, "generic_diesel.jpg")), "generic"

    def _action_model(self, group: str) -> list[dict]:
        if self._command_port is None:
            return []
        profile = self._command_port.control_profile
        model: list[dict] = []
        for action in cab_actions(group):
            if not self._command_port.supports_action(action):
                continue
            icon_path = find_file(action.icon) if action.icon else None
            hold_enabled = action.hold and not (action.hold_legacy_only and not profile.is_legacy)
            if hold_enabled and action.hold_kind == "analog":
                hold_enabled = action.hold_target in profile.analog_modes
            model.append(
                {
                    "key": action.key,
                    "label": action.label,
                    "iconSource": QUrl.fromLocalFile(str(icon_path)).toString() if icon_path else "",
                    "hold": hold_enabled,
                    "holdThreshold": action.hold_threshold_ms,
                    "holdKind": action.hold_kind if hold_enabled else "",
                    "holdTarget": action.hold_target if hold_enabled else "",
                    "repeat": action.repeat,
                    "repeatInterval": action.repeat_interval_ms,
                    "group": action.group,
                }
            )
        return model

    @Property(list, notify=rosterChanged)
    def targetLabels(self) -> list[str]:
        return self._target_labels

    @Property(int, notify=rosterChanged)
    def targetIndex(self) -> int:
        return self._target_index

    @Slot(int)
    def selectTarget(self, index: int) -> None:
        if 0 <= index < len(self._targets) and index != self._target_index:
            scope, tmcc_id, _ = self._targets[index]
            self._switch_target(scope, tmcc_id)

    @Slot()
    def refreshRoster(self) -> None:
        current_scope = CommandScope[self.scope]
        current_id = self.tmccId
        self._reload_roster()
        self._target_index = next(
            (i for i, item in enumerate(self._targets) if item[0] == current_scope and item[1] == current_id),
            -1,
        )
        self.rosterChanged.emit()

    @Property(str, notify=stateChanged)
    def scope(self) -> str:
        return self._snapshot.scope

    @Property(int, notify=stateChanged)
    def tmccId(self) -> int:
        return self._snapshot.tmcc_id

    @Property(str, notify=stateChanged)
    def roadName(self) -> str:
        return self._snapshot.road_name

    @Property(str, notify=stateChanged)
    def roadNumber(self) -> str:
        return self._snapshot.road_number

    @Property(list, notify=stateChanged)
    def primaryActionModel(self) -> list[dict]:
        return self._action_model("primary")

    @Property(list, notify=stateChanged)
    def actionModel(self) -> list[dict]:
        return self._action_model("operations")

    @Property(list, notify=stateChanged)
    def secondaryActionModel(self) -> list[dict]:
        return self._action_model("secondary")

    @Property(list, notify=stateChanged)
    def tuningActionModel(self) -> list[dict]:
        return self._action_model("tuning")

    @Property(str, notify=stateChanged)
    def artworkSource(self) -> str:
        path, _ = self._resolved_artwork(self._artwork_state())
        return QUrl.fromLocalFile(str(path)).toString() if path else ""

    @Property(str, notify=stateChanged)
    def artworkKind(self) -> str:
        return self._resolved_artwork(self._artwork_state())[1]

    @Property(bool, notify=stateChanged)
    def hasCustomArtwork(self) -> bool:
        return self.artworkKind == "custom"

    @Property(str, notify=stateChanged)
    def engineType(self) -> str:
        if self._command_port is None:
            return "UNKNOWN"
        return self._command_port.control_profile.engine_type

    @Property(str, notify=stateChanged)
    def controlType(self) -> str:
        if self._command_port is None:
            return "NA"
        return self._command_port.control_profile.control_type

    @Property(list, notify=stateChanged)
    def analogModes(self) -> list[str]:
        if self._command_port is None:
            return []
        return list(self._command_port.control_profile.analog_modes)

    @Property(list, notify=stateChanged)
    def infoModel(self) -> list[dict]:
        """Mirror ControllerView's six-field state summary without GuiZero dependencies."""
        state = self._state_port.state if self._state_port is not None else None
        if state is None:
            return []

        speeds = getattr(state, "speeds", (None, None, None, None))
        speed_limit = speeds[2] if len(speeds) > 2 else None
        momentum = str(getattr(state, "momentum_text", "") or self._snapshot.momentum)
        labor = getattr(state, "labor", None)

        if bool(getattr(state, "is_legacy", False)):
            train_brake = getattr(state, "train_brake", None)
            brake = str(train_brake) if train_brake else "Off"
            smoke = str(getattr(state, "smoke_text", "") or "")
        else:
            brake = "NA"
            smoke = "NA"

        rpm = getattr(state, "rpm", None) if bool(getattr(state, "is_rpm", False)) else None
        return [
            {"label": "Mom", "value": momentum},
            {"label": "Brake", "value": brake},
            {"label": "Smoke", "value": smoke},
            {"label": "Speed Lim", "value": "" if speed_limit is None else str(speed_limit)},
            {"label": "Effort", "value": "" if labor is None else str(labor)},
            {"label": "RPM", "value": "NA" if rpm is None else str(rpm)},
        ]

    @Property(bool, notify=stateChanged)
    def supportsMomentum(self) -> bool:
        return bool(self._command_port is not None and self._command_port.control_profile.supports_momentum)

    @Property(bool, notify=stateChanged)
    def supportsTrainBrake(self) -> bool:
        return bool(self._command_port is not None and self._command_port.control_profile.supports_train_brake)

    @Property(bool, notify=stateChanged)
    def supportsQuillingHorn(self) -> bool:
        return bool(self._command_port is not None and self._command_port.control_profile.supports_quilling_horn)

    @Property(bool, notify=stateChanged)
    def supportsSpeedLimit(self) -> bool:
        return bool(self._command_port is not None and self._command_port.control_profile.supports_speed_limit)

    @Property(bool, notify=stateChanged)
    def isLegacy(self) -> bool:
        return bool(self._command_port is not None and self._command_port.control_profile.is_legacy)

    @Property(bool, notify=stateChanged)
    def hasThrottle(self) -> bool:
        return bool(self._command_port is not None and self._command_port.control_profile.has_throttle)

    @Property(int, notify=stateChanged)
    def speed(self) -> int:
        return self._snapshot.speed

    @Property(int, notify=stateChanged)
    def targetSpeed(self) -> int:
        return self._snapshot.target_speed

    @Property(int, notify=stateChanged)
    def speedMax(self) -> int:
        return self._snapshot.speed_max

    @Property(int, notify=stateChanged)
    def commandSpeedMax(self) -> int:
        state = self._state_port.state if self._state_port is not None else None
        return 199 if state is not None and bool(getattr(state, "is_legacy", False)) else 31

    @Property(int, notify=stateChanged)
    def speedLimit(self) -> int:
        state = self._state_port.state if self._state_port is not None else None
        value = getattr(state, "speed_limit", None) if state is not None else None
        return int(value or 0)

    @Property(str, notify=stateChanged)
    def direction(self) -> str:
        return self._snapshot.direction

    @Property(int, notify=stateChanged)
    def momentum(self) -> int:
        return self._snapshot.momentum

    @Property(int, notify=stateChanged)
    def trainBrake(self) -> int:
        return self._snapshot.train_brake

    @Property(int, notify=stateChanged)
    def smoke(self) -> int:
        return self._snapshot.smoke

    @Property(int, notify=stateChanged)
    def labor(self) -> int:
        return self._snapshot.labor

    @Property(int, notify=stateChanged)
    def rpm(self) -> int:
        return self._snapshot.rpm

    @Slot(str, result=str)
    def panelTitle(self, key: str) -> str:
        return panel_title(key)

    @Slot(str, result=list)
    def panelModel(self, key: str) -> list[dict]:
        if self._command_port is None:
            return []
        type_key = self._command_port.controller_type_key
        return [
            {"section": item.section, "label": item.label, "command": item.command}
            for item in panel_actions(key)
            if (not item.type_keys or type_key in item.type_keys)
            and self._command_port.supports_panel_command(item.command)
        ]

    @Slot(str)
    def triggerPanelCommand(self, command: str) -> None:
        if self._command_port is not None:
            self._command_port.send_panel_command(command)

    @Slot(int)
    def setSpeed(self, speed: int) -> None:
        self._command_port.set_speed(speed)

    @Slot(int)
    def changeSpeed(self, delta: int) -> None:
        self._command_port.change_speed(delta)

    @Slot(int)
    def setMomentum(self, value: int) -> None:
        self._command_port.set_momentum(value)

    @Slot(int)
    def setTrainBrake(self, value: int) -> None:
        self._command_port.set_train_brake(value)

    @Slot(int)
    def setQuillingHorn(self, value: int) -> None:
        self._command_port.set_quilling_horn(value)

    @Slot(int)
    def setSpeedLimit(self, value: int) -> None:
        self._command_port.set_speed_limit(value)

    @Slot()
    def clearSpeedLimit(self) -> None:
        self._command_port.set_speed_limit(None)

    @Slot(str)
    def setDirection(self, direction: str) -> None:
        self._command_port.set_direction(direction)

    @Slot(str)
    def triggerAction(self, key: str) -> None:
        self._command_port.perform(key)

    @Slot(str)
    def triggerHoldAction(self, key: str) -> None:
        action = cab_action(key)
        if action is not None and action.hold_kind == "command":
            self._command_port.perform_hold(action)

    @Slot()
    def bell(self) -> None:
        self._command_port.bell()

    @Slot(bool)
    def horn(self, active: bool) -> None:
        self._command_port.horn(active)

    @Slot(bool)
    def boost(self, active: bool) -> None:
        self._command_port.boost(active)

    @Slot(bool)
    def brake(self, active: bool) -> None:
        self._command_port.brake(active)

    @Slot()
    def stop(self) -> None:
        self._command_port.stop()

    @Slot()
    def reset(self) -> None:
        self._command_port.reset()

    @Slot()
    def startup(self) -> None:
        self._command_port.startup()

    @Slot()
    def shutdown(self) -> None:
        self._command_port.shutdown()

    @Slot()
    def frontCoupler(self) -> None:
        self._command_port.front_coupler()

    @Slot()
    def rearCoupler(self) -> None:
        self._command_port.rear_coupler()

    @Slot()
    def smokeUp(self) -> None:
        self._command_port.smoke_up()

    @Slot()
    def smokeDown(self) -> None:
        self._command_port.smoke_down()

    @Slot()
    def volumeUp(self) -> None:
        self._command_port.volume_up()

    @Slot()
    def volumeDown(self) -> None:
        self._command_port.volume_down()

    @Slot()
    def rpmUp(self) -> None:
        self._command_port.rpm_up()

    @Slot()
    def rpmDown(self) -> None:
        self._command_port.rpm_down()

    @Slot()
    def engineerChatter(self) -> None:
        self._command_port.engineer_chatter()

    @Slot()
    def towerChatter(self) -> None:
        self._command_port.tower_chatter()
