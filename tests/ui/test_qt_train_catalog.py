"""Train rosters distinguish command aliases from real database records."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QCoreApplication

from pytrain.db.component_state_store import ComponentStateStore
from pytrain.protocol.constants import CommandScope, EngineType
from pytrain_ui.qt.cab_controller import CabController
from pytrain_ui.qt.catalog_controller import EngineCatalogController
from pytrain_ui.qt.presentation import is_pseudo_train


@pytest.fixture
def roster_states(monkeypatch):
    application = QCoreApplication.instance() or QCoreApplication([])
    assert application is not None

    def state(scope, address, record_no, engine_type):
        return SimpleNamespace(
            scope=scope,
            tmcc_id=address,
            record_no=record_no,
            road_name=f"{scope.name} {address}",
            road_number=str(address),
            engine_type_enum=engine_type,
            control_type_label="Legacy",
        )

    states = [
        state(CommandScope.ENGINE, 100, None, EngineType.DIESEL),
        state(CommandScope.TRAIN, 100, 0, EngineType.DIESEL),
        state(CommandScope.TRAIN, 550, 7, EngineType.ELECTRIC),
        state(CommandScope.TRAIN, 101, None, EngineType.STEAM),
    ]
    aliases = {100, 101}
    store = SimpleNamespace(get_all=lambda scope: [item for item in states if item.scope == scope])
    monkeypatch.setattr(ComponentStateStore, "get", lambda: store)
    monkeypatch.setattr(ComponentStateStore, "is_pseudo_train_id", lambda address: address in aliases)
    monkeypatch.setattr("pytrain_ui.qt.catalog_controller.CommandDispatcher.is_built", lambda: False)
    yield states, aliases


def test_train_roster_keeps_real_record_100_and_excludes_pseudo_rows_and_their_types(roster_states):
    catalog = EngineCatalogController()
    try:
        assert [row["tmccId"] for row in catalog.trains] == [100, 550]
        assert [row["tmccId"] for row in catalog.engines] == [100]
        assert {row["key"] for row in catalog.typeFilters} == {"DIESEL", "ELECTRIC"}
    finally:
        catalog.close()


def test_roster_reload_removes_late_pseudo_alias_without_hiding_real_train(roster_states):
    _, aliases = roster_states
    aliases.remove(101)
    catalog = EngineCatalogController()
    try:
        assert [row["tmccId"] for row in catalog.trains] == [100, 101, 550]
        aliases.add(101)
        catalog.reload()
        assert [row["tmccId"] for row in catalog.trains] == [100, 550]
    finally:
        catalog.close()


def test_cab_target_menu_uses_the_same_real_train_filter(roster_states, monkeypatch):
    monkeypatch.setattr("pytrain_ui.qt.cab_controller.ArtworkLoader", Mock())
    # Build the actual menu without starting state subscriptions or selecting hardware targets.
    # noinspection PyProtectedMember
    monkeypatch.setattr(CabController, "_switch_target", Mock())
    cab = CabController(CommandScope.ENGINE, 100)
    try:
        assert len(cab.targetLabels) == 3
        assert any(label.startswith("Train 100") for label in cab.targetLabels)
        assert any(label.startswith("Train 550") for label in cab.targetLabels)
        assert not any(label.startswith("Train 101") for label in cab.targetLabels)
    finally:
        cab.close()


@pytest.mark.parametrize("record_no", [0, 7])
def test_real_train_record_at_a_pseudo_address_is_not_an_alias(roster_states, record_no):
    states, _ = roster_states
    train = states[1]
    train.record_no = record_no
    assert not is_pseudo_train(train)
    train.record_no = None
    assert is_pseudo_train(train)
    assert not is_pseudo_train(states[0]), "An engine at the same address is not a train alias"
