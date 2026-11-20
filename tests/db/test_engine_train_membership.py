"""Resolve train membership from 2D assignments and 4D train record references."""

import pytest

from pytrain.comm.comm_buffer import CommBuffer
from pytrain.db.comp_data import EngineData
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.components import ConsistComponent
from pytrain.db.engine_state import EngineState, TrainState
from pytrain.pdi.constants import D4Action, PdiCommand
from pytrain.pdi.d4_req import D4Req
from pytrain.protocol.constants import CommandScope

from .test_pseudo_train_index import train_record


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch):
    monkeypatch.setattr(ComponentStateStore, "_instance", None)
    monkeypatch.setattr(CommBuffer, "is_server", staticmethod(lambda: False))
    monkeypatch.setattr(ComponentStateStore, "is_state_synchronized", classmethod(lambda cls: False))


# Initialize a 2D record without dispatching commands or starting network threads.
# noinspection PyProtectedMember
def engine_record(raw_train_id: int | None = 255) -> EngineState:
    engine = EngineState()
    engine.initialize(CommandScope.ENGINE, 37)
    engine._address = 37
    engine.comp_data.train_tmcc_id = raw_train_id
    return engine


def load_train(address: int = 550, pseudo_id: int = 100, record_no: int = 0) -> TrainState:
    store = ComponentStateStore.get() if ComponentStateStore.is_built() else ComponentStateStore.build()
    store(train_record(address=address, pseudo_id=pseudo_id, record_no=record_no))
    train = ComponentStateStore.get_state(CommandScope.TRAIN, address, create=False)
    assert isinstance(train, TrainState)
    return train


@pytest.mark.parametrize("train_id", range(100))
def test_two_digit_train_id_returns_directly_without_lookup(monkeypatch, train_id: int):
    def unexpected_lookup(_cls, _pseudo_id):
        pytest.fail("Ordinary 2D train IDs must not consult the pseudo train index")

    monkeypatch.setattr(ComponentStateStore, "by_pseudo_train_id", classmethod(unexpected_lookup))
    engine = engine_record(train_id)
    assert engine.train_tmcc_id == train_id
    assert engine.raw_train_tmcc_id == train_id
    data = engine.comp_data
    assert isinstance(data, EngineData)
    assert data.train_tmcc_id == train_id
    assert not ComponentStateStore.is_built()


@pytest.mark.parametrize("raw_id", (None, 128, 254, 255))
def test_unset_or_invalid_assignment_is_unresolved_without_changing_raw_value(raw_id):
    engine = engine_record(raw_id)
    assert engine.train_tmcc_id is None
    assert engine.raw_train_tmcc_id == raw_id
    assert not ComponentStateStore.is_built()


@pytest.mark.parametrize("pseudo_id", range(100, 128))
def test_unknown_pseudo_id_is_unresolved_not_an_actual_train_address(pseudo_id: int):
    engine = engine_record(pseudo_id)
    assert engine.train_tmcc_id is None
    assert engine.raw_train_tmcc_id == pseudo_id
    assert not ComponentStateStore.is_built()


def test_missing_component_data_has_no_membership():
    engine = EngineState()
    assert engine.train_tmcc_id is None
    assert engine.raw_train_tmcc_id is None


@pytest.mark.parametrize("pseudo_id", range(100, 128))
def test_hybrid_two_digit_engine_resolves_pseudo_id_to_actual_train(pseudo_id: int):
    engine = engine_record(pseudo_id)
    load_train(pseudo_id=pseudo_id)
    assert engine.train_tmcc_id == 550
    assert engine.raw_train_tmcc_id == pseudo_id
    data = engine.comp_data
    assert isinstance(data, EngineData)
    assert data.train_tmcc_id == pseudo_id


@pytest.mark.parametrize("raw_id", (7, 100, 255))
def test_loaded_roster_does_not_override_two_digit_record_assignment(raw_id: int):
    engine = engine_record(raw_id)
    train = load_train(pseudo_id=127)
    train.comp_data.consist_comps = [ConsistComponent(37, 1)]
    assert engine.train_tmcc_id == (7 if raw_id == 7 else None)
    assert engine.raw_train_tmcc_id == raw_id


@pytest.mark.parametrize("address", (100, 127, 3233))
@pytest.mark.parametrize("raw_id", (7, 100, 255))
def test_four_digit_engine_without_record_reference_does_not_infer_membership_from_byte_or_roster(
    address: int, raw_id: int
):
    train = load_train()
    train.comp_data.consist_comps = [ConsistComponent(address, 1)]
    record_data = train_record(address=address).data_bytes
    assert record_data is not None
    data = bytearray(record_data)
    data[2] = 12
    data[0x1C] = raw_id
    packet = D4Req(
        1, PdiCommand.D4_ENGINE, D4Action.QUERY, start=0, data_length=len(data), data_bytes=bytes(data), timestamp=0
    )
    engine = EngineState()
    engine.update(D4Req(packet.as_bytes))
    assert engine.is_d4
    assert engine.train_tmcc_id is None
    assert engine.raw_train_tmcc_id == raw_id


def test_pseudo_resolution_tracks_owner_changes_and_deletion():
    engine = engine_record(100)
    train = load_train()
    assert engine.train_tmcc_id == 550
    ComponentStateStore.delete_state(train)
    assert engine.train_tmcc_id is None
    load_train(address=551)
    assert engine.train_tmcc_id == 551
    ComponentStateStore.reset()
    assert engine.train_tmcc_id is None
    assert engine.raw_train_tmcc_id == 100


def test_train_state_does_not_resolve_its_record_as_an_engine_assignment():
    train = load_train()
    train.comp_data.train_tmcc_id = 100
    assert train.train_tmcc_id == 100
    assert train.raw_train_tmcc_id == 100


def four_digit_engine_record(train_record_no: int, raw_train_id: int = 255) -> EngineState:
    record_data = train_record(address=3233).data_bytes
    assert record_data is not None
    data = bytearray(record_data)
    data[2] = 0x0E
    data[0x1C] = raw_train_id
    data[0xB4:0xB6] = train_record_no.to_bytes(2, "little")
    packet = D4Req(
        train_record_no,
        PdiCommand(0x2E),
        D4Action.QUERY,
        start=0,
        data_length=len(data),
        data_bytes=bytes(data),
        timestamp=0,
    )
    engine = EngineState()
    engine.update(D4Req(packet.as_bytes))
    assert engine.is_d4
    return engine


@pytest.mark.parametrize("train_id", (100, 127, 500, 550, 9999))
@pytest.mark.parametrize("record_no", (0, 1, 0x1234))
def test_four_digit_engine_resolves_train_record_in_train_scope(train_id: int, record_no: int):
    load_train(train_id, pseudo_id=255, record_no=record_no)
    engine = four_digit_engine_record(record_no)
    # Engine and train record numbers are separate namespaces; deliberately collide.
    ComponentStateStore.set_state(CommandScope.ENGINE, 3233, engine)
    assert ComponentStateStore.by_record_no(record_no) is engine
    assert engine.train_tmcc_id == train_id
    assert engine.raw_train_tmcc_id == 255
    data = engine.comp_data
    assert isinstance(data, EngineData)
    assert data.train_record_no == record_no
    assert data.train_tmcc_id == 255


@pytest.mark.parametrize("raw_id", (7, 100, 255))
def test_four_digit_reference_takes_precedence_over_one_byte_field(raw_id: int):
    load_train(500, record_no=1)
    engine = four_digit_engine_record(1, raw_id)
    assert engine.train_tmcc_id == 500
    assert engine.raw_train_tmcc_id == raw_id


def test_four_digit_reference_without_store_is_unresolved_and_does_not_build_store():
    engine = four_digit_engine_record(0)
    assert not ComponentStateStore.is_built()
    assert engine.train_tmcc_id is None
    assert not ComponentStateStore.is_built()


@pytest.mark.parametrize("record_no", (None, 0xFFFF))
def test_unset_four_digit_reference_does_not_fall_back_to_pseudo_or_roster(record_no):
    train = load_train(record_no=0)
    train.comp_data.consist_comps = [ConsistComponent(3233, 1)]
    engine = four_digit_engine_record(0xFFFF, raw_train_id=100)
    data = engine.comp_data
    assert isinstance(data, EngineData)
    data.train_record_no = record_no
    assert engine.train_tmcc_id is None
    assert engine.raw_train_tmcc_id == 100


def test_missing_referenced_train_does_not_create_state_or_use_other_record():
    load_train(500, record_no=0)
    engine = four_digit_engine_record(17)
    store = ComponentStateStore.get()
    before = store.addresses(CommandScope.TRAIN)
    assert engine.train_tmcc_id is None
    assert store.addresses(CommandScope.TRAIN) == before


def test_four_digit_membership_tracks_late_train_load_deletion_and_record_reuse():
    engine = four_digit_engine_record(0)
    assert engine.train_tmcc_id is None
    train = load_train(500, record_no=0)
    assert engine.train_tmcc_id == 500
    ComponentStateStore.delete_state(train)
    assert engine.train_tmcc_id is None
    load_train(501, record_no=0)
    assert engine.train_tmcc_id == 501
    ComponentStateStore.reset()
    assert engine.train_tmcc_id is None
