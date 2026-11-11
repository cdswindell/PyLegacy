"""Qt presentation and record actions for the inline StateInfo panel."""

from __future__ import annotations

from time import monotonic

from PySide6.QtCore import Property, QObject, Signal, Slot

from pytrain.db.component_state import ComponentStateDict
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.engine_state import EngineState
from pytrain.gui.controller.engine_add_session import EngineAddSession
from pytrain.pdi.base_req import BaseReq
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CONTROL_TYPE, LOCO_TYPE, SOUND_TYPE, CommandScope
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum

_FIELDS = (
    ("name", "Road Name", "road_name", None, None),
    ("number", "Road Number", "road_number", None, None),
    ("type", "Engine Type", "engine_type", LOCO_TYPE, "ENGINE_TYPE"),
    ("control", "Control Type", "control_type", CONTROL_TYPE, "CONTROL_TYPE"),
    ("sound", "Sound Type", "sound_type", SOUND_TYPE, "SOUND_TYPE"),
)
_READBACK_TIMEOUT = 10


class StateInfoController(QObject):
    changed = Signal()
    recordReady = Signal(str, int)
    recordCleared = Signal(str, int)

    def __init__(self) -> None:
        super().__init__()
        self._scope = CommandScope.ENGINE
        self._id = 0
        self._draft: EngineAddSession | None = None
        self._waiting_until = 0.0
        self._pending: dict | None = None
        self._error = ""
        self._model: dict = {}

    def _lookup(self):
        return ComponentStateStore.get_state(self._scope, self._id, create=False)

    @Property("QVariantMap", notify=changed)
    def model(self) -> dict:
        return self._model

    @Slot(int, result=bool)
    def needsEngineRecord(self, tmcc_id: int) -> bool:
        state = ComponentStateStore.get_state(CommandScope.ENGINE, tmcc_id, create=False)
        return state is None or not state.is_user_defined

    @Slot(str, int, bool)
    def openFor(self, scope: str, tmcc_id: int, create: bool) -> None:
        self._scope = CommandScope[scope]
        self._id = tmcc_id
        self._draft = None
        self._pending = None
        self._waiting_until = 0
        self._error = ""
        state = self._lookup()
        if create and self._scope == CommandScope.ENGINE and 1 <= tmcc_id <= 9999 and tmcc_id != 99:
            self._draft = EngineAddSession(state or ComponentStateDict(self._scope)[tmcc_id])
        self.refresh(False)

    @Slot()
    def close(self) -> None:
        self._draft = None
        self._pending = None
        self._waiting_until = 0
        self._id = 0
        self._model = {}
        self.changed.emit()

    @staticmethod
    def _rows(values) -> list[dict]:
        return [{"label": label, "value": str(value) if value not in (None, "") else "—"} for label, value in values]

    def _details(self, state: EngineState) -> tuple[list[dict], list[dict]]:
        speed, target, limit, maximum = state.speeds
        live = self._rows(
            (
                ("Speed", speed),
                ("Target speed", target),
                ("Speed limit", limit),
                ("Max speed", maximum),
                ("Direction", "Fwd" if state.is_forward else "Rev" if state.is_reverse else None),
                ("Smoke level", state.smoke_text),
                ("Momentum", state.momentum_text),
                ("Train brake", state.train_brake_label),
                ("Labor", state.labor_label),
                ("RPM", state.rpm_label),
                ("Fuel level", f"{state.fuel_level_pct}%"),
                ("Water level", f"{state.water_level_pct}%"),
            )
        )
        if self._scope == CommandScope.TRAIN:
            membership = self._rows(
                (
                    ("Lead engine ID", state.head_tmcc_id or None),
                    ("Engines", state.num_engines),
                    ("Linked cars", state.num_train_linked),
                    ("Accessories", state.num_accessories),
                )
            )
        else:
            train = (
                ComponentStateStore.get_state(CommandScope.TRAIN, state.train_tmcc_id, create=False)
                if state.train_tmcc_id
                else None
            )
            component = train.get_consist_component(state.tmcc_id) if train else None
            membership = self._rows(
                (
                    ("Train TMCC ID", state.train_tmcc_id or None),
                    ("Consist position", component.position if component else None),
                    ("Consist direction", component.direction if component else None),
                )
            )
        return live, membership

    def _identity(self, state) -> list[dict]:
        rows = []
        for key, label, attribute, options, _ in _FIELDS:
            if self._scope == CommandScope.TRAIN and key in {"control", "sound"}:
                continue
            value = self._draft.values[key] if self._draft else getattr(state, attribute, None)
            display = (options.get(value, "—") if options else value) or "—"
            if key == "sound" and value == 0:
                display = "No Sound"
            rows.append(
                {
                    "key": key,
                    "label": label,
                    "value": value,
                    "display": str(display),
                    "options": [
                        {"value": code, "label": "No Sound" if key == "sound" and code == 0 else name}
                        for code, name in options.items()
                    ]
                    if options
                    else [],
                }
            )
        return rows

    @Slot(bool)
    def refresh(self, editor_open: bool) -> None:
        if not self._id:
            return
        state = self._lookup()
        draft = self._draft
        status = ""
        if draft:
            if state is not None:
                draft.refresh(state)
            if self._pending is not None:
                if draft.baseline and all(
                    str(draft.baseline.get(key) or "0").zfill(4) == str(value).zfill(4)
                    if key == "number"
                    else draft.baseline.get(key) == value
                    for key, value in self._pending.items()
                ):
                    self._pending = None
                    self.recordReady.emit(self._scope.name, self._id)
                    return
                if monotonic() >= self._waiting_until:
                    self._pending = None
                    self._error = "Base 3 has not confirmed the record. Check the connection or retry Create."
            elif draft.discovery_complete and not editor_open:
                self.recordReady.emit(self._scope.name, self._id)
                return
            if self._pending is not None:
                status = "Waiting for Base 3 to confirm the engine record…"
            elif not draft.can_create:
                status = "Waiting for a Base 3 record for this four-digit address. Use Set Address to start discovery."
            else:
                status = "Edit the engine details, then select Create."
        elif state is None:
            status = "This address is not in the roster."

        live, membership = (
            self._details(state) if isinstance(state, EngineState) and state.comp_data is not None else ([], [])
        )
        model = {
            "scopeTitle": self._scope.title,
            "creating": draft is not None,
            "canCreate": bool(draft and draft.can_create and self._pending is None),
            "canClear": bool(not draft and state and state.is_deletable),
            "editable": bool(self._pending is None and (draft or (state and state.comp_data))),
            "busy": self._pending is not None,
            "status": self._error or status,
            "identity": self._identity(state) if state or draft else [],
            "live": live,
            "membership": membership,
            "bluetoothId": state.bt_id if isinstance(state, EngineState) and self._scope == CommandScope.ENGINE else "",
            "record": " ".join(part for part in ("4D" if state.is_d4 else "", state.record_no_label) if part)
            if isinstance(state, EngineState)
            else "",
        }
        if model != self._model:
            self._model = model
            self.changed.emit()

    @Slot(str, str, result=bool)
    def edit(self, key: str, text: str) -> bool:
        state = self._lookup()
        if not self._model.get("editable"):
            return False
        field = next((field for field in _FIELDS if field[0] == key), None)
        if field is None or (self._scope == CommandScope.TRAIN and key in {"control", "sound"}):
            return False
        _, _, attribute, options, command = field
        try:
            value = text.strip()
            if options:
                value = int(value)
                if value not in options:
                    raise ValueError("Choose a value from the list.")
            elif key == "name" and (len(value) > 31 or (self._draft and not value)):
                raise ValueError("Road Name must contain 1 to 31 characters.")
            elif key == "number":
                if not value and not self._draft:
                    value = "0"
                if not value.isascii() or not value.isdigit() or len(value) > 4:
                    raise ValueError("Road Number must be a number from 0 to 9999.")
                value = value.zfill(4)

            if self._draft:
                self._draft.edit(key, value)
            elif state is not None and state.comp_data is not None and value != getattr(state, attribute):
                if command:
                    BaseReq.do_update_field(command, value, state, do_async=False)
                else:
                    request = (
                        state.comp_data.set_road_name_req(value)
                        if key == "name"
                        else state.comp_data.set_road_number_req(int(value))
                    )
                    BaseReq.process_sync_reqs([request, state], deduplicate_writes=True)
            self._error = ""
        except (AssertionError, OSError, RuntimeError, ValueError) as exc:
            self._error = str(exc)
            self.refresh(True)
            return False
        self.refresh(True)
        return True

    @Slot(int, result=str)
    def programEngineAddress(self, tmcc_id: int) -> str:
        if not 1 <= tmcc_id <= 9999 or tmcc_id == 99:
            return "Enter an engine address from 1 to 9999, excluding 99."
        scope = CommandScope.ENGINE
        state = ComponentStateStore.get_state(scope, tmcc_id, create=False)
        try:
            command = TMCC2EngineCommandEnum.SET_ADDRESS if tmcc_id > 99 else TMCC1EngineCommandEnum.SET_ADDRESS
            CommandReq.build(command, address=tmcc_id, scope=scope).send()
            if tmcc_id < 99 or (state is not None and state.record_no is not None and 0 <= state.record_no < 0xFFFF):
                BaseReq.create_base_query_request(state or ComponentStateDict(scope)[tmcc_id]).send()
        except (AssertionError, OSError, RuntimeError, ValueError) as exc:
            return str(exc) or "Unable to set the engine address."
        return ""

    @Slot()
    def setAddress(self) -> None:
        if self._draft is None or self._pending is not None:
            return
        self._error = self.programEngineAddress(self._id)
        self.refresh(True)

    @Slot()
    def create(self) -> None:
        draft = self._draft
        if draft is None or self._pending is not None:
            return
        try:
            draft.create()
            self._pending = draft.values.copy()
            self._waiting_until = monotonic() + _READBACK_TIMEOUT
            self._error = ""
        except (AssertionError, OSError, RuntimeError, ValueError) as exc:
            self._error = str(exc)
        self.refresh(False)

    @Slot()
    def clear(self) -> None:
        state = self._lookup()
        if self._draft or state is None or not state.is_deletable:
            return
        try:
            if state.clear(notify=True, clear_db=True):
                self.recordCleared.emit(self._scope.name, self._id)
        except (AssertionError, OSError, RuntimeError, ValueError) as exc:
            self._error = str(exc)
            self.refresh(False)
