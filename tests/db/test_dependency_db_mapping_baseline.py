#
# PyTrain: baseline characterization tests for command dependencies and Base 3 DB mappings.
# SPDX-License-Identifier: LGPL-3.0-only
#
# These tests deliberately capture CURRENT behavior before DB write coalescing.
# They do not claim that unconditional direction dependencies are desirable.
#
import pytest

from src.pytrain.db.comp_data import REQUEST_TO_UPDATES_MAP, CompData
from src.pytrain.db.component_state_store import DependencyCache
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum as Engine1
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum as Engine2


@pytest.fixture
def cache():
    # DependencyCache is a singleton; reset its relationships to the declared baseline.
    instance = DependencyCache.build()
    instance.initialize()
    return instance


@pytest.mark.parametrize(
    "cause, effects",
    [
        (Engine2.SYSTEM_HALT, {Engine2.SPEED_STOP_HOLD}),
        (Engine2.RESET, {
            Engine2.STOP_IMMEDIATE, Engine2.ABSOLUTE_SPEED,
            Engine2.FORWARD_DIRECTION, Engine2.DIESEL_RPM,
            Engine2.ENGINE_LABOR_DEFAULT, Engine2.BELL_OFF, Engine2.NUMERIC,
        }),
        (Engine2.STOP_IMMEDIATE, {
            Engine2.ABSOLUTE_SPEED, Engine2.DIESEL_RPM, Engine2.ENGINE_LABOR_DEFAULT,
        }),
        (Engine2.FORWARD_DIRECTION, {
            Engine2.STOP_IMMEDIATE, Engine2.ABSOLUTE_SPEED,
            Engine2.DIESEL_RPM, Engine2.ENGINE_LABOR_DEFAULT,
        }),
        (Engine2.REVERSE_DIRECTION, {
            Engine2.STOP_IMMEDIATE, Engine2.ABSOLUTE_SPEED,
            Engine2.DIESEL_RPM, Engine2.ENGINE_LABOR_DEFAULT,
        }),
        (Engine2.TOGGLE_DIRECTION, {
            Engine2.STOP_IMMEDIATE, Engine2.ABSOLUTE_SPEED,
            Engine2.DIESEL_RPM, Engine2.ENGINE_LABOR_DEFAULT,
        }),
        (Engine2.SHUTDOWN_IMMEDIATE, {
            Engine2.SPEED_STOP_HOLD, Engine2.STOP_IMMEDIATE,
            Engine2.DIESEL_RPM, Engine2.ENGINE_LABOR_DEFAULT,
        }),
        (Engine1.RESET, {
            Engine1.SPEED_STOP_HOLD, Engine1.FORWARD_DIRECTION,
            Engine1.START_UP_IMMEDIATE, Engine1.RPM_DOWN, Engine1.NUMERIC,
        }),
        (Engine1.FORWARD_DIRECTION, {Engine1.SPEED_STOP_HOLD}),
        (Engine1.REVERSE_DIRECTION, {Engine1.SPEED_STOP_HOLD}),
        (Engine1.TOGGLE_DIRECTION, {Engine1.SPEED_STOP_HOLD}),
    ],
)
def test_direct_dependency_graph_baseline(cache, cause, effects):
    # Compare raw edges, rather than results_in(), which also includes the cause.
    assert cache._causes[cause] == effects
    assert cache.results_in(cause) == effects | {cause}
    for effect in effects:
        assert cause in cache._caused_bys[effect]


def test_unknown_command_returns_itself(cache):
    assert cache.results_in(Engine2.BELL_OFF) == {Engine2.BELL_OFF}


@pytest.mark.parametrize(
    "name, fields",
    [
        ("RESET", ("speed", "target_speed", "rpm_labor", "soft_status")),
        ("STOP_IMMEDIATE", ("speed", "target_speed", "rpm_labor")),
        ("SYSTEM_HALT", ("speed", "target_speed", "rpm_labor")),
        ("EMERGENCY_STOP", ("speed", "target_speed", "rpm_labor")),
        ("HALT", ("speed", "target_speed", "rpm_labor")),
        ("SHUTDOWN_IMMEDIATE", ("rpm_labor",)),
        ("SHUTDOWN_DELAYED", ("rpm_labor",)),
        ("ABSOLUTE_SPEED", ("speed", "target_speed")),
        ("RAMP_TARGET_SPEED", ("target_speed",)),
        ("SPEED", ("speed",)),
        ("DIESEL_RPM", ("rpm",)),
        ("ENGINE_LABOR", ("labor",)),
        ("FORWARD_DIRECTION", ("soft_status",)),
        ("REVERSE_DIRECTION", ("soft_status",)),
    ],
)
def test_command_to_database_field_baseline(name, fields):
    assert tuple(entry[0] for entry in REQUEST_TO_UPDATES_MAP[name]) == fields


def test_database_map_key_inventory_baseline():
    assert set(REQUEST_TO_UPDATES_MAP) == {
        "PREV_LINK",
        "NEXT_LINK",
        "ABSOLUTE_SPEED",
        "SPEED",
        "RAMP_TARGET_SPEED",
        "DIESEL_RPM",
        "ENGINE_LABOR",
        "ENGINEER_FUEL_REFILLED",
        "ENGINEER_WATER_REFILLED",
        "HALT",
        "FORWARD_DIRECTION",
        "REVERSE_DIRECTION",
        "CONTROL_TYPE",
        "ENGINE_TYPE",
        "SOUND_TYPE",
        "MOMENTUM",
        "MOMENTUM_HIGH",
        "MOMENTUM_LOW",
        "MOMENTUM_MEDIUM",
        "RESET",
        "ROAD_NAME",
        "ROAD_NAME_LEN",
        "ROAD_NUMBER",
        "ROAD_NUMBER_LEN",
        "SHUTDOWN_DELAYED",
        "SHUTDOWN_IMMEDIATE",
        "SMOKE_HIGH",
        "SMOKE_LOW",
        "SMOKE_MEDIUM",
        "SMOKE_OFF",
        "SMOKE_ON",
        "SPEED_LIMIT",
        "STOP_IMMEDIATE",
        "SYSTEM_HALT",
        "EMERGENCY_STOP",
        "TRAIN_ADDRESS",
        "TRAIN_BRAKE",
        "TRAIN_UNIT",
    }

@pytest.mark.parametrize("command", [Engine1.RESET, Engine2.RESET])
@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
def test_reset_encoded_database_bytes_baseline(monkeypatch, command, scope):
    # Characterize the mapping without requiring a running server or Base 3.
    from src.pytrain.db.component_state_store import ComponentStateStore

    monkeypatch.setattr(ComponentStateStore, "get_state", lambda *args, **kwargs: None)
    req = CommandReq.build(command, 7, scope=scope)
    packages = CompData.request_to_updates(req)
    assert [(p.field, p.offset, p.length, p.data_bytes) for p in packages] == [
        ("speed", 0x07, 1, bytes([0])),
        ("target_speed", 0x08, 1, bytes([0])),
        ("rpm_labor", 0x0C, 1, bytes([0])),
        ("soft_status", 0x0B, 1, bytes([0])),
    ]


@pytest.mark.parametrize("command", [Engine1.RESET, Engine2.RESET])
def test_reset_field_and_command_paths_agree(monkeypatch, command):
    from src.pytrain.db.component_state_store import ComponentStateStore

    monkeypatch.setattr(ComponentStateStore, "get_state", lambda *args, **kwargs: None)
    req = CommandReq.build(command, 7, scope=CommandScope.ENGINE)
    from_command = CompData.request_to_updates(req)
    from_field = CompData.field_to_updates(
        "reset", 7, CommandScope.ENGINE, legacy=command.is_legacy
    )
    assert [(p.field, p.offset, p.data_bytes) for p in from_command] == [
        (p.field, p.offset, p.data_bytes) for p in from_field
    ]
