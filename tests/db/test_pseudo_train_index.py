"""Known pseudo train IDs select Legacy addressing without changing four-digit engines."""

from unittest.mock import Mock, patch

import pytest

from pytrain.comm.comm_buffer import CommBuffer, CommBufferSingleton
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.engine_state import TrainState
from pytrain.pdi.constants import D4Action, PdiCommand
from pytrain.pdi.d4_req import D4Req
from pytrain.pdi.pdi_req import PdiReq, TmccReq
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.multibyte.multibyte_constants import TMCC2MaskingControl
from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setattr(ComponentStateStore, "_instance", None)
    monkeypatch.setattr(CommBuffer, "is_server", staticmethod(lambda: False))
    monkeypatch.setattr(ComponentStateStore, "is_state_synchronized", classmethod(lambda cls: False))
    return ComponentStateStore.build()


def train_record(address: int = 550, pseudo_id: int = 100, record_no: int = 0) -> D4Req:
    data = bytearray(b"\xff" * 192)
    data[2] = 13
    data[7:10] = bytes(3)
    data[0x1E] = data[0x3E] = 0
    data[0x43:0x46] = bytes((0, 2, 3))
    data[0xB6] = pseudo_id
    data[0xB8:0xBC] = f"{address:04d}".encode()
    packet = D4Req(
        record_no,
        PdiCommand.D4_TRAIN,
        D4Action.QUERY,
        start=0,
        data_length=192,
        data_bytes=bytes(data),
        timestamp=0,
    )
    return D4Req(packet.as_bytes)


def horn(address: int, scope: CommandScope = CommandScope.TRAIN) -> CommandReq:
    return CommandReq.build(TMCC2EngineCommandEnum.BLOW_HORN_ONE, address, scope=scope)


def test_pseudo_lookup_does_not_initialize_store(monkeypatch):
    monkeypatch.setattr(ComponentStateStore, "_instance", None)
    assert ComponentStateStore.by_pseudo_train_id(100) is None
    assert not ComponentStateStore.is_pseudo_train_id(100)
    assert ComponentStateStore.pseudo_train_ids() == set()
    assert not ComponentStateStore.is_built()


@pytest.mark.parametrize("pseudo_id", range(100, 128))
def test_d4_record_indexes_owner_and_selects_legacy_horn(store, pseudo_id: int):
    store(train_record(pseudo_id=pseudo_id))
    owner = ComponentStateStore.by_pseudo_train_id(pseudo_id)
    assert isinstance(owner, TrainState)
    assert owner.address == 550
    assert owner.pseudo_train_id == pseudo_id
    assert ComponentStateStore.is_pseudo_train_id(pseudo_id)
    assert ComponentStateStore.pseudo_train_ids() == {pseudo_id}
    req = horn(pseudo_id)
    assert req.is_pseudo_train
    assert not req.uses_d4_address
    assert req.as_bytes == bytes((0xF9, pseudo_id << 1 | 1, 0x1C))


@pytest.mark.parametrize("pseudo_id", (0, 99, 128, 255))
def test_invalid_pseudo_field_is_not_indexed(store, pseudo_id):
    store(train_record(pseudo_id=pseudo_id))
    assert ComponentStateStore.pseudo_train_ids() == set()
    assert not ComponentStateStore.is_pseudo_train_id(pseudo_id)


def test_index_updates_after_reassignment_and_removal(store):
    store(train_record(pseudo_id=100))
    store(train_record(pseudo_id=127))
    assert ComponentStateStore.by_pseudo_train_id(100) is None
    assert ComponentStateStore.pseudo_train_ids() == {127}
    store(train_record(pseudo_id=255))
    assert ComponentStateStore.pseudo_train_ids() == set()


def test_index_is_removed_on_delete_and_reset(store):
    store(train_record())
    owner = ComponentStateStore.by_pseudo_train_id(100)
    assert isinstance(owner, TrainState)
    ComponentStateStore.delete_state(owner)
    assert ComponentStateStore.pseudo_train_ids() == set()
    store(train_record())
    assert ComponentStateStore.is_pseudo_train_id(100)
    ComponentStateStore.reset()
    assert ComponentStateStore.pseudo_train_ids() == set()


@pytest.mark.usefixtures("store")
def test_direct_state_replacement_updates_index():
    first = TrainState()
    first.update(train_record())
    ComponentStateStore.set_state(CommandScope.TRAIN, 550, first)
    assert ComponentStateStore.by_pseudo_train_id(100) is first
    replacement = TrainState()
    replacement.update(train_record(pseudo_id=101))
    ComponentStateStore.set_state(CommandScope.TRAIN, 550, replacement)
    assert ComponentStateStore.by_pseudo_train_id(100) is None
    assert ComponentStateStore.by_pseudo_train_id(101) is replacement


def test_pseudo_id_reuse_keeps_new_owner_when_old_train_is_deleted(store):
    store(train_record())
    old_owner = ComponentStateStore.by_pseudo_train_id(100)
    assert isinstance(old_owner, TrainState)
    store(train_record(address=551, record_no=1))
    owner = ComponentStateStore.by_pseudo_train_id(100)
    assert isinstance(owner, TrainState)
    assert owner.address == 551
    store(horn(550))
    assert ComponentStateStore.by_pseudo_train_id(100) is owner
    ComponentStateStore.delete_state(old_owner)
    assert ComponentStateStore.by_pseudo_train_id(100) is owner


@pytest.mark.parametrize("pseudo_id", (101, 255))
def test_partial_pseudo_field_write_refreshes_index(store, pseudo_id):
    store(train_record())
    update = D4Req(0, PdiCommand.D4_TRAIN, D4Action.UPDATE, start=0xB6, data_bytes=bytes((pseudo_id,)), timestamp=0)
    store(D4Req(update.as_bytes))
    assert ComponentStateStore.by_pseudo_train_id(100) is None
    if pseudo_id == 101:
        owner = ComponentStateStore.by_pseudo_train_id(101)
        assert isinstance(owner, TrainState)
        assert owner.pseudo_train_id == 101
    else:
        assert ComponentStateStore.pseudo_train_ids() == set()


def test_short_write_response_does_not_clear_index(store):
    store(train_record())
    response = D4Req(0, PdiCommand.D4_TRAIN, D4Action.UPDATE, start=0xB6, timestamp=0)
    store(D4Req(response.as_bytes))
    assert ComponentStateStore.pseudo_train_ids() == {100}


def test_existing_request_tracks_index_changes_without_rebuilding(store):
    req = horn(100)
    assert req.as_bytes == bytes.fromhex("f9 01 1c 30 31 30 30")
    store(train_record())
    assert req.as_bytes == bytes.fromhex("f9 c9 1c")
    assert "0xf9c91c" in repr(req)
    ComponentStateStore.reset()
    assert req.as_bytes == bytes.fromhex("f9 01 1c 30 31 30 30")


@pytest.mark.parametrize(
    "address,scope",
    (
        (99, CommandScope.TRAIN),
        (128, CommandScope.TRAIN),
        (550, CommandScope.TRAIN),
        (100, CommandScope.ENGINE),
        (127, CommandScope.ENGINE),
    ),
)
def test_other_addresses_and_engine_scope_bypass_pseudo_lookup(store, address, scope):
    store(train_record())
    with patch.object(
        ComponentStateStore, "is_pseudo_train_id", side_effect=AssertionError("Unexpected pseudo lookup")
    ):
        req = horn(address, scope)
        packet = req.as_bytes
    assert not req.is_pseudo_train
    assert len(packet) == (3 if address == 99 else 7)
    if address > 99:
        assert packet[3:] == f"{address:04d}".encode()


def test_pseudo_horn_uses_tmcc_pdi_wrapper(store):
    store(train_record())
    packets = TmccReq.as_packets(horn(100))
    assert packets == [bytes.fromhex("d1 27 f9 c9 1c fb df")]
    parsed = PdiReq.from_bytes(packets[0])
    assert isinstance(parsed, TmccReq)
    assert parsed.tmcc_command.address == 100
    assert not parsed.is_tmcc4


def test_four_digit_horn_keeps_tmcc4_wrapper(store):
    store(train_record())
    packets = TmccReq.as_packets(horn(550))
    parsed = PdiReq.from_bytes(packets[0])
    assert isinstance(parsed, TmccReq)
    assert parsed.pdi_command is PdiCommand.TMCC4_TX
    assert parsed.is_tmcc4
    assert parsed.tmcc_command.as_bytes == bytes.fromhex("f9 01 1c 30 35 35 30")


def test_multibyte_builder_uses_shared_pseudo_decision(store):
    store(train_record())
    req = CommandReq.build(TMCC2MaskingControl.NC_NC, 100, scope=CommandScope.TRAIN)
    assert req.is_pseudo_train
    assert req.as_bytes == bytes.fromhex("f9 c9 76 fb c9 00 fb c9 2e")
    packets = TmccReq.as_packets(req)
    assert len(packets) == 3
    assert all(packet[1] == PdiCommand.TMCC_TX for packet in packets)


@pytest.mark.parametrize("packet,pseudo", (("f9 c9 1c", True), ("f9 01 1c 30 31 30 30", False)))
def test_received_wire_format_takes_precedence_over_index(store, packet, pseudo):
    store(train_record())
    req = CommandReq.from_bytes(bytes.fromhex(packet))
    assert req.address == 100
    assert req.is_pseudo_train is pseudo
    assert req.as_bytes == bytes.fromhex(packet)


@pytest.mark.parametrize("address", range(100, 128))
def test_real_four_digit_train_in_pseudo_range_keeps_four_digit_encoding(store, address: int):
    pseudo_id = 127 if address == 100 else 100
    store(train_record(address=address, pseudo_id=pseudo_id))
    assert not ComponentStateStore.is_pseudo_train_id(address)
    assert ComponentStateStore.is_pseudo_train_id(pseudo_id)
    real = horn(address)
    pseudo = horn(pseudo_id)
    assert not real.is_pseudo_train
    assert real.uses_d4_address
    assert real.as_bytes == bytes.fromhex("f9 01 1c") + f"{address:04d}".encode()
    assert pseudo.is_pseudo_train
    assert pseudo.as_bytes == bytes((0xF9, pseudo_id << 1 | 1, 0x1C))


@pytest.mark.parametrize(
    "address,scope,pdi_command,expected",
    (
        (100, CommandScope.TRAIN, PdiCommand.TMCC_TX, "f9 c9 1c"),
        (550, CommandScope.TRAIN, PdiCommand.TMCC4_TX, "f9 01 1c 30 35 35 30"),
        (127, CommandScope.TRAIN, PdiCommand.TMCC4_TX, "f9 01 1c 30 31 32 37"),
        (100, CommandScope.ENGINE, PdiCommand.TMCC4_TX, "f8 01 1c 30 31 30 30"),
    ),
)
# Supply only the transport fields so this test exercises the real send method without queue threads.
# noinspection PyProtectedMember
def test_base3_send_uses_shared_address_format(store, address, scope, pdi_command, expected):
    store(train_record())
    transport = Mock()
    dispatcher = Mock()
    buffer = Mock(spec=CommBufferSingleton)
    buffer._base3 = transport
    buffer._tmcc_dispatcher = dispatcher
    buffer.is_ser2 = False
    request = horn(address, scope)
    CommBufferSingleton.base3_send(buffer, request.as_bytes)
    transport.send.assert_called_once()
    parsed = PdiReq.from_bytes(transport.send.call_args.args[0])
    assert isinstance(parsed, TmccReq)
    assert parsed.pdi_command is pdi_command
    assert parsed.tmcc_command.as_bytes == bytes.fromhex(expected)
    dispatcher.offer.assert_called_once()
