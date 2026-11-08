#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

"""Uncommitted engine metadata, separate from authoritative Base 3 state."""

from ...db.comp_data import CompData, EngineData
from ...db.engine_state import EngineState
from ...pdi.base_req import BaseReq
from ...protocol.constants import CONTROL_TYPE, LOCO_TYPE, SOUND_TYPE


class EngineAddSession:
    """Keep defaults and user edits local until the operator requests creation."""

    def __init__(self, state: EngineState, *, awaiting_discovery: bool | None = None):
        self.state = state
        self.tmcc_id = state.tmcc_id
        self.values = {
            "name": f"Engine {self.tmcc_id}",
            "number": str(self.tmcc_id),
            "control": 1,
            "type": 0,
            "sound": 0,
        }
        self.edited: set[str] = set()
        self.baseline: dict = {}
        self.refresh(state)
        self.awaiting_discovery = not self.has_complete_metadata if awaiting_discovery is None else awaiting_discovery

    @property
    def has_complete_metadata(self) -> bool:
        data = self.baseline
        return bool(
            data.get("name")
            and str(data["name"]).strip()
            and data.get("number")
            and data.get("control") in CONTROL_TYPE
            and data.get("type") in LOCO_TYPE
            and data.get("sound") in SOUND_TYPE
        )

    @property
    def discovery_complete(self) -> bool:
        return self.awaiting_discovery and self.has_complete_metadata and self.can_create and not self.edited

    def refresh(self, state: EngineState) -> bool:
        if state.scope != self.state.scope or state.tmcc_id != self.tmcc_id or state.is_deleted:
            return False
        self.state = state
        with state.synchronizer:
            data = state.comp_data
            self.baseline = (
                {
                    "name": data.road_name,
                    "number": data.road_number,
                    "control": data.control_type,
                    "type": data.engine_type,
                    "sound": data.sound_type,
                }
                if data is not None and data.is_user_defined()
                else {}
            )
        for key, value in self.baseline.items():
            if key not in self.edited:
                self.values[key] = value
        return True

    def awaiting_empty_record(self, state: EngineState) -> bool:
        """An empty 2D query confirms absence while a new-engine draft is open."""
        return (
            self.tmcc_id < 100
            and state.scope == self.state.scope
            and state.tmcc_id == self.tmcc_id
            and not self.baseline
            and not state.is_user_defined
        )

    @property
    def can_create(self) -> bool:
        return not self.state.is_deleted and (
            self.tmcc_id < 100 or self.state.record_no is not None and 0 <= self.state.record_no < 0xFFFF
        )

    def edit(self, key: str, value) -> None:
        self.values[key] = value
        self.edited.add(key)

    def requests(self) -> list:
        """Build all writes before dispatch, without modifying the live component data."""
        self.refresh(self.state)
        if not self.can_create:
            raise ValueError(
                "Waiting for the Base 3 engine record. Cancel and retry SET if discovery does not complete."
            )
        name = str(self.values["name"] or "").strip()
        number = str(self.values["number"] or "").strip()
        if not name or len(name) > 31:
            raise ValueError("Road Name must contain 1 to 31 characters.")
        if not number.isascii() or not number.isdigit() or not 0 <= int(number) <= 9999:
            raise ValueError("Road Number must be a number from 0 to 9999.")
        for key, choices in (("control", CONTROL_TYPE), ("type", LOCO_TYPE), ("sound", SOUND_TYPE)):
            if self.values[key] not in choices:
                raise ValueError(f"Choose a valid {key} before creating the engine.")
        values = dict(self.values, name=name, number=str(int(number)).zfill(4))
        baseline = self.baseline.copy()
        if baseline.get("number") and str(baseline["number"]).isdigit():
            baseline["number"] = str(int(baseline["number"])).zfill(4)
        changes = {key: value for key, value in values.items() if not baseline or value != baseline.get(key)}
        # Name/number builders update their CompData receiver: use a detached copy.
        data = EngineData(None, self.tmcc_id)
        requests = []
        if "name" in changes:
            requests.append(data.set_road_name_req(changes["name"]))
        if "number" in changes:
            requests.append(data.set_road_number_req(int(changes["number"])))
        for key, field in (("control", "CONTROL_TYPE"), ("type", "ENGINE_TYPE"), ("sound", "SOUND_TYPE")):
            if key in changes:
                for package in CompData.field_to_updates(field, self.tmcc_id, self.state.scope, changes[key]):
                    requests.append(package.as_request(self.tmcc_id, self.state.scope, self.state.record_no))
        return requests

    def create(self) -> None:
        requests = self.requests()
        if requests:
            # Enqueue writes in order, followed by one authoritative refresh.
            BaseReq.process_sync_reqs([*requests, self.state], deduplicate_writes=True)
