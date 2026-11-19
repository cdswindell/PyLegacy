"""Compare encoders against bytes frozen from the original Git revision."""

import json
from pathlib import Path

import pytest

from pytrain.comm.comm_buffer import CommBuffer
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.pdi.pdi_req import TmccReq
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.multibyte.dcds_command_req import VariableCommandReq
from pytrain.protocol.multibyte.multibyte_constants import (
    TMCC2DcdsCommandEnum,
    TMCC2EffectsControl,
    TMCC2LightingControl,
    TMCC2MaskingControl,
    TMCC2R4LCEnum,
    TMCC2VariableEnum,
)
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum

from ..db.test_pseudo_train_index import train_record

BASELINE = json.loads((Path(__file__).parent / "fixtures" / "original_command_bytes.json").read_text())
GROUPS = BASELINE["groups"]
FAMILIES = {
    family.__name__: family
    for family in (
        TMCC1EngineCommandEnum,
        TMCC2EngineCommandEnum,
        TMCC2MaskingControl,
        TMCC2EffectsControl,
        TMCC2LightingControl,
        TMCC2R4LCEnum,
        TMCC2DcdsCommandEnum,
    )
}


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch):
    monkeypatch.setattr(ComponentStateStore, "_instance", None)
    monkeypatch.setattr(CommBuffer, "is_server", staticmethod(lambda: False))
    monkeypatch.setattr(ComponentStateStore, "is_state_synchronized", classmethod(lambda cls: False))


def build_request(group, address: int) -> CommandReq:
    command = FAMILIES[group["family"]][group["command"]]
    scope = CommandScope[group["scope"]]
    if isinstance(command, TMCC2VariableEnum):
        return VariableCommandReq.build(command, address, group["data"], scope)
    return CommandReq.build(command, address, group["data"], scope)


def assert_original_bytes(request: CommandReq, vector):
    address, command_hex, packet_hex = vector
    assert request.address == address
    assert request.as_bytes.hex() == command_hex
    assert [packet.hex() for packet in TmccReq.as_packets(request)] == packet_hex


def group_id(group):
    return f"{group['family']}-{group['command']}-{group['data']}-{group['scope']}"


@pytest.mark.parametrize("group", GROUPS, ids=group_id)
def test_construction_matches_original_bytes(group):
    for vector in group["vectors"]:
        assert_original_bytes(build_request(group, vector[0]), vector)


@pytest.mark.parametrize("group", GROUPS, ids=group_id)
def test_address_setter_matches_original_bytes_in_both_directions(group):
    vectors = group["vectors"]
    request = build_request(group, vectors[0][0])
    for vector in vectors + list(reversed(vectors)):
        request.address = vector[0]
        assert_original_bytes(request, vector)


@pytest.mark.parametrize("group", [g for g in GROUPS if g["scope"] == "TRAIN"], ids=group_id)
def test_scope_setter_matches_original_bytes(group):
    engine_group = next(
        g
        for g in GROUPS
        if g["scope"] == "ENGINE" and all(g[key] == group[key] for key in ("family", "command", "data"))
    )
    engine_vectors = {vector[0]: vector for vector in engine_group["vectors"]}
    for vector in group["vectors"]:
        if vector[0] not in engine_vectors:
            continue
        request = build_request(engine_group, vector[0])
        request.scope = CommandScope.TRAIN
        assert_original_bytes(request, vector)
        request.scope = CommandScope.ENGINE
        assert_original_bytes(request, engine_vectors[vector[0]])


@pytest.mark.parametrize("address", range(100, 128))
@pytest.mark.parametrize("scope", (CommandScope.ENGINE, CommandScope.TRAIN))
def test_real_four_digit_addresses_with_populated_pseudo_index(address: int, scope: CommandScope):
    store = ComponentStateStore.build()
    pseudo_id = 127 if address == 100 else 100
    store(train_record(address=address, pseudo_id=pseudo_id))
    assert ComponentStateStore.pseudo_train_ids() == {pseudo_id}
    assert not ComponentStateStore.is_pseudo_train_id(address)
    for group in GROUPS:
        if group["family"] == "TMCC1EngineCommandEnum" or group["scope"] != scope.name:
            continue
        vector = next(v for v in group["vectors"] if v[0] == address)
        request = build_request(group, address)
        assert request.uses_d4_address
        assert_original_bytes(request, vector)


def test_fixture_provenance_and_coverage():
    assert BASELINE["schema"] == 1
    assert BASELINE["revision"] == "677f25b4438f1765e0040b2b441913f21a022420"
    assert sum(len(group["vectors"]) for group in GROUPS) == BASELINE["vector_count"] == 17942
    for group in GROUPS:
        if group["family"] != "TMCC1EngineCommandEnum":
            assert set(range(100, 128)) <= {vector[0] for vector in group["vectors"]}
