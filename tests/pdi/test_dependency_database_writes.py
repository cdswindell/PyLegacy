"""Fast, hardware-free contracts for dependency effects and Base 3 database writes.

The expected offsets and values below are protocol fixtures, not copied from the
production update map. Keep these fixtures deliberate when changing policy.
"""

from unittest.mock import Mock

import pytest

from src.pytrain.db.comp_data import CompData
from src.pytrain.db.component_state import ComponentStateDict
from src.pytrain.db.component_state_store import ComponentStateStore, DependencyCache
from src.pytrain.db.engine_state import EngineState
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import D4Action, PdiCommand
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import LEGACY_CONTROL_TYPE, CommandScope
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum as Engine2


# Every explicitly registered Legacy engine cause, with its intended effects.
# This is independent of DependencyCache.initialize(), so changes require review.
ENGINE_CAUSES = {
    "SYSTEM_HALT": {"SPEED_STOP_HOLD"},
    "RESET": {
        "STOP_IMMEDIATE",
        "ABSOLUTE_SPEED",
        "FORWARD_DIRECTION",
        "DIESEL_RPM",
        "ENGINE_LABOR_DEFAULT",
        "BELL_OFF",
        "NUMERIC",
    },
    "STOP_IMMEDIATE": {"ABSOLUTE_SPEED", "DIESEL_RPM", "ENGINE_LABOR_DEFAULT"},
    "FORWARD_DIRECTION": {"STOP_IMMEDIATE", "ABSOLUTE_SPEED", "DIESEL_RPM", "ENGINE_LABOR_DEFAULT"},
    "REVERSE_DIRECTION": {"STOP_IMMEDIATE", "ABSOLUTE_SPEED", "DIESEL_RPM", "ENGINE_LABOR_DEFAULT"},
    "TOGGLE_DIRECTION": {"STOP_IMMEDIATE", "ABSOLUTE_SPEED", "DIESEL_RPM", "ENGINE_LABOR_DEFAULT"},
    "SHUTDOWN_IMMEDIATE": {"SPEED_STOP_HOLD", "STOP_IMMEDIATE", "DIESEL_RPM", "ENGINE_LABOR_DEFAULT"},
}


def test_all_legacy_engine_dependency_causes_match_reviewed_contract():
    cache = DependencyCache.build()
    actual = {
        command.name: {effect[0].name if isinstance(effect, tuple) else effect.name for effect in effects}
        for command, effects in cache._causes.items()
        if isinstance(command, Engine2)
    }
    assert actual == ENGINE_CAUSES


@pytest.fixture
def engine_state(monkeypatch):
    state = ComponentStateDict(CommandScope.ENGINE)[60]
    assert isinstance(state, EngineState)
    state.initialize(CommandScope.ENGINE, 60)
    state.comp_data.control_type = LEGACY_CONTROL_TYPE
    state.comp_data.speed = 30
    state.comp_data.target_speed = 30
    state.comp_data.rpm_labor = 2
    state.comp_data.soft_status = 0
    lookup = Mock(return_value=state)
    monkeypatch.setattr(ComponentStateStore, "get_state", lookup)
    monkeypatch.setattr(CompData, "state_store", lambda: ComponentStateStore)
    return state


@pytest.mark.parametrize(
    "command,data,expected",
    [
        ("ABSOLUTE_SPEED", 30, [(0x07, b"\x1e"), (0x08, b"\x1e")]),
        ("STOP_IMMEDIATE", 0, [(0x07, b"\x00"), (0x08, b"\x00"), (0x0C, b"\x00")]),
        ("FORWARD_DIRECTION", 0, [(0x0B, b"\x00")]),
        ("REVERSE_DIRECTION", 0, [(0x0B, b"\x01")]),
        ("DIESEL_RPM", 2, [(0x0C, b"\x02")]),
        ("ENGINE_LABOR", 12, [(0x0C, b"\x02")]),
        ("SHUTDOWN_IMMEDIATE", 0, [(0x0C, b"\x00")]),
        (
            "RESET",
            0,
            [
                (0x07, b"\x00"),
                (0x08, b"\x00"),
                (0x0C, b"\x00"),
                (0x0B, b"\x00"),
            ],
        ),
    ],
)
def test_command_generates_expected_database_writes(engine_state, command, data, expected):
    request = CommandReq(getattr(Engine2, command), 60, data=data, scope=CommandScope.ENGINE)
    packages = CompData.request_to_updates(request)
    assert [(p.offset, p.data_bytes) for p in packages] == expected

    outbound = BaseReq.updates_to_reqs(engine_state, packages, refresh=False)
    writes = [req for req in outbound if req.pdi_command == PdiCommand.BASE_MEMORY]
    assert [(req.start, req.data_bytes) for req in writes] == expected
    assert all(req.flags == 0xC2 and req.tmcc_id == 60 for req in writes)
    assert all(
        req._update_dedup_key == (CommandScope.ENGINE, 60, req.start, len(req.data_bytes), req.data_bytes)
        for req in writes
    )


@pytest.mark.parametrize(
    "command,expected",
    [
        ("STOP_IMMEDIATE", [(0x07, b"\x00"), (0x08, b"\x00"), (0x0C, b"\x00")]),
        ("REVERSE_DIRECTION", [(0x0B, b"\x01")]),
    ],
)
def test_same_command_packages_use_d4_writes(engine_state, command, expected):
    engine_state = ComponentStateDict(CommandScope.ENGINE)[1234]
    engine_state.initialize(CommandScope.ENGINE, 1234)
    engine_state.comp_data.control_type = LEGACY_CONTROL_TYPE
    engine_state.comp_data.rpm_labor = 2
    engine_state.comp_data.soft_status = 0
    engine_state._d4_rec_no = 0x1234
    request = CommandReq(getattr(Engine2, command), 1234, scope=CommandScope.ENGINE)
    packages = CompData.request_to_updates(request)
    assert [(p.offset, p.data_bytes) for p in packages] == expected
    outbound = BaseReq.updates_to_reqs(engine_state, packages, refresh=False)
    assert len(outbound) == len(expected)
    assert all(
        isinstance(req, D4Req) and req.pdi_command == PdiCommand.D4_ENGINE and req.action == D4Action.UPDATE
        for req in outbound
    )
    assert [(req.start, req.data_bytes) for req in outbound] == expected
