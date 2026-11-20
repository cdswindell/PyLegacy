"""Train Link tiles follow consist flags and completed state notifications."""

import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QObject, Signal

from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.components import ConsistComponent
from pytrain.db.state_changes import StateChange
from pytrain.protocol.constants import CommandScope, EngineType
from pytrain_ui.qt.train_link_controller import TrainLinkController
from pytrain_ui.qt.selection_controller import SelectedEngineController
from pytrain_ui.profiles import equipment_flag


class TrainCab(QObject):
    stateChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.scope = "TRAIN"
        self.tmccId = 41

    def select(self, scope: str, address: int) -> None:
        self.scope = scope
        self.tmccId = address
        self.stateChanged.emit()


@pytest.fixture
def linked_train(monkeypatch):
    cab = TrainCab()
    train = SimpleNamespace(
        is_deleted=False,
        consist_components=[ConsistComponent(1, 1), ConsistComponent(12, 10), ConsistComponent(3233, 11)],
    )
    car = SimpleNamespace(is_deleted=False, road_name="StationSounds Diner", name="Diner", road_number="12")
    other = SimpleNamespace(is_deleted=False, road_name="Operating Boxcar", name="Boxcar", road_number="0345")
    states = {
        (CommandScope.TRAIN, 41): train,
        (CommandScope.ENGINE, 12): car,
        (CommandScope.ENGINE, 3233): other,
    }

    def lookup(scope, address, *, create=False):
        assert not create, "Displaying consist members must not create engine records"
        return states.get((scope, address))

    monkeypatch.setattr(ComponentStateStore, "get_state", lookup)
    links = TrainLinkController(cab)
    yield cab, links, train, car, other, states
    links.close()


def test_only_train_link_flags_determine_car_membership_in_consist_order(linked_train):
    _, links, train, _, _, _ = linked_train
    train.consist_components = [
        ConsistComponent(1, 1),
        ConsistComponent(3233, 10),
        ConsistComponent(12, 10),
        ConsistComponent(3233, 11),
        ConsistComponent(55, 128),
    ]
    links.refresh()
    assert [row["tmccId"] for row in links.rows] == [3233, 12]
    assert links.rows[0]["roadName"] == "Operating Boxcar"
    assert links.rows[0]["roadNumber"] == "0345"
    assert links.rows[1]["roadNumber"] == "0012"


def test_switching_trains_and_scopes_does_not_retain_previous_cars(linked_train):
    cab, links, _, _, _, states = linked_train
    states[(CommandScope.TRAIN, 42)] = SimpleNamespace(is_deleted=False, consist_components=[ConsistComponent(12, 1)])
    cab.select("TRAIN", 42)
    assert links.rows == []
    cab.select("TRAIN", 41)
    assert len(links.rows) == 2
    cab.select("ENGINE", 41)
    assert links.rows == []


def test_car_identity_updates_only_for_relevant_completed_state_changes(linked_train):
    _, links, _, car, _, _ = linked_train
    changes = Mock()
    links.changed.connect(changes)
    car.road_name = "New Diner Name"
    car.engine_type_label = "Passenger"
    links.applyStateChanges(frozenset({StateChange(CommandScope.ENGINE, 99)}))
    assert links.rows[0]["roadName"] == "StationSounds Diner"
    changes.assert_not_called()
    links.applyStateChanges(frozenset({StateChange(CommandScope.ENGINE, 12)}))
    assert links.rows[0]["roadName"] == "New Diner Name"
    assert links.rows[0]["engineType"] == "Passenger"
    changes.assert_called_once()


def test_consist_edits_missing_created_and_deleted_records_refresh_without_watchers(linked_train):
    _, links, train, car, _, states = linked_train
    train.consist_components = [ConsistComponent(50, 10)]
    links.applyStateChanges(frozenset({StateChange(CommandScope.TRAIN, 41)}))
    assert links.rows == []
    states[(CommandScope.ENGINE, 50)] = car
    links.applyStateChanges(frozenset({StateChange(CommandScope.ENGINE, 50)}))
    assert [row["tmccId"] for row in links.rows] == [50]
    car.is_deleted = True
    links.applyStateChanges(frozenset({StateChange(CommandScope.ENGINE, 50)}))
    assert links.rows == []
    car.is_deleted = False
    links.refresh()
    del states[(CommandScope.ENGINE, 50)]
    links.applyStateChanges(frozenset({StateChange(CommandScope.ENGINE, 50)}))
    assert links.rows == []


def test_deleted_train_and_closed_model_ignore_late_notifications(linked_train):
    cab, links, train, _, _, _ = linked_train
    train.is_deleted = True
    links.applyStateChanges(frozenset({StateChange(CommandScope.TRAIN, 41)}))
    assert links.rows == []
    train.is_deleted = False
    links.close()
    cab.stateChanged.emit()
    links.applyStateChanges(frozenset({StateChange(CommandScope.TRAIN, 41)}))
    assert links.rows == []


def test_rows_cannot_be_mutated_by_a_consumer(linked_train):
    _, links, _, _, _, _ = linked_train
    rows = links.rows
    rows[0]["roadName"] = "Changed outside the model"
    rows.clear()
    assert links.rows[0]["roadName"] == "StationSounds Diner"


def test_selected_car_is_validated_and_released_on_consist_changes(linked_train, monkeypatch):
    cab, links, train, _, _, _ = linked_train

    class CarCab(QObject):
        def __init__(self, scope, address, parent, *, remember_initial):
            super().__init__(parent)
            assert scope == CommandScope.ENGINE
            assert not remember_initial
            self.tmccId = address
            self.close = Mock()

    monkeypatch.setattr("pytrain_ui.qt.cab_controller.CabController", CarCab)
    assert not links.select(99)
    assert links.select(12)
    selected = links.selectedCab
    assert links.select(12) and links.selectedCab is selected
    train.consist_components = []
    links.refresh()
    assert links.selectedId == 0 and links.selectedCab is None
    selected.close.assert_called_once()
    train.consist_components = [ConsistComponent(12, 10)]
    links.refresh()
    assert links.select(12)
    selected = links.selectedCab
    cab.select("TRAIN", 42)
    assert links.selectedCab is None
    selected.close.assert_called_once()
    cab.select("TRAIN", 41)
    assert links.select(12)
    selected = links.selectedCab
    selected.close.side_effect = [RuntimeError("Cleanup failed"), None]
    links.clearSelection()
    assert links.selectedCab is None
    links.close()
    assert selected.close.call_count == 2


@pytest.mark.parametrize("change", ["removed", "unlinked", "deleted"])
def test_invalidated_car_closes_controls_and_notifies_the_info_owner(linked_train, monkeypatch, change):
    _, links, train, car, _, _ = linked_train

    class CarCab(QObject):
        def __init__(self, _scope, address, parent, **_kwargs):
            super().__init__(parent)
            self.tmccId = address
            self.close = Mock()

    monkeypatch.setattr("pytrain_ui.qt.cab_controller.CabController", CarCab)
    invalidated = Mock()
    links.selectionInvalidated.connect(invalidated)
    assert links.select(12)
    selected = links.selectedCab
    if change == "removed":
        train.consist_components = []
    elif change == "unlinked":
        train.consist_components = [ConsistComponent(12, 1)]
    else:
        car.is_deleted = True
    links.applyStateChanges(frozenset({StateChange(CommandScope.TRAIN, 41), StateChange(CommandScope.ENGINE, 12)}))
    assert links.selectedCab is None
    selected.close.assert_called_once()
    invalidated.assert_called_once_with(12)
    links.refresh()
    invalidated.assert_called_once()


def test_missing_or_deleted_train_notifies_roster_once_and_recovers(linked_train):
    _, links, train, _, _, states = linked_train
    unavailable = Mock()
    links.trainUnavailable.connect(unavailable)
    train.is_deleted = True
    links.applyStateChanges(frozenset({StateChange(CommandScope.TRAIN, 41)}))
    assert links.rows == []
    unavailable.assert_called_once_with(41)
    links.refresh()
    unavailable.assert_called_once()
    train.is_deleted = False
    links.refresh()
    assert len(links.rows) == 2
    del states[(CommandScope.TRAIN, 41)]
    links.refresh()
    assert links.rows == []
    assert unavailable.call_count == 2


@pytest.fixture
def active_selection(monkeypatch):
    cab = TrainCab()
    cab.scope = "ENGINE"
    cab.tmccId = 1
    cab.selectAddress = Mock(return_value=True)
    # The selection controller uses the cab's internal target-switch hook.
    # noinspection PyProtectedMember
    cab._switch_target = Mock()
    train = SimpleNamespace(
        tmcc_id=502,
        is_deleted=False,
        speed=5,
        target_speed=5,
        consist_components=[ConsistComponent(737, 1), ConsistComponent(12, 10)],
    )
    states = {
        (CommandScope.TRAIN, 502): train,
        (CommandScope.ENGINE, 737): SimpleNamespace(tmcc_id=737, train_tmcc_id=502, bt_int=0),
        (CommandScope.ENGINE, 12): SimpleNamespace(tmcc_id=12, train_tmcc_id=None, bt_int=0),
        (CommandScope.ENGINE, 99): SimpleNamespace(tmcc_id=99, train_tmcc_id=None, bt_int=0),
    }
    store = SimpleNamespace(get_all=lambda scope: [train] if scope == CommandScope.TRAIN else [])
    monkeypatch.setattr(ComponentStateStore, "get", lambda: store)
    monkeypatch.setattr(ComponentStateStore, "get_state", lambda scope, address, **_: states.get((scope, address)))
    monkeypatch.setattr("pytrain_ui.qt.selection_controller.CommandDispatcher.is_built", lambda: False)
    monkeypatch.setattr("pytrain_ui.qt.selection_controller.StateWatcher", lambda *_: Mock())
    selection = SelectedEngineController(cab)
    yield cab, selection, train, states
    selection.close()


def test_active_train_hides_consist_members_but_dismissal_restores_engine_tiles(active_selection):
    _, selection, _, _ = active_selection
    selection.selectEngine(737)
    selection.selectEngine(12)
    selection.selectEngine(99)
    assert [(row["scope"], row["tmccId"]) for row in selection.selectedEngines] == [("ENGINE", 99), ("TRAIN", 502)]
    selection.dismissTrain(502)
    assert [row["tmccId"] for row in selection.selectedEngines] == [99, 737]


def test_train_link_car_requires_engine_scope_selection_then_operation(active_selection):
    cab, selection, _, _ = active_selection
    command = SimpleNamespace(scope=CommandScope.ENGINE, address=12)
    # Exercise the dispatcher callback to model traffic from Train Link controls or another cab.
    # noinspection PyProtectedMember
    selection._engine_command(command)
    assert not any(row["tmccId"] == 12 for row in selection.selectedEngines)
    selection.selectEngine(12)
    cab.select("ENGINE", 12)
    assert not any(row["tmccId"] == 12 for row in selection.selectedEngines)
    # A command after explicit Engine-scope selection qualifies the car, even in an active train.
    # noinspection PyProtectedMember
    selection._engine_command(command)
    assert any(row["tmccId"] == 12 for row in selection.selectedEngines)
    cab.select("ENGINE", 99)
    assert any(row["tmccId"] == 12 for row in selection.selectedEngines)
    selection.dismissEngine(12)
    # Train-scope car commands must not restore a dismissed tile.
    cab.select("TRAIN", 502)
    # noinspection PyProtectedMember
    selection._engine_command(command)
    assert not any(row["tmccId"] == 12 for row in selection.selectedEngines)


def test_train_link_selection_in_train_scope_does_not_qualify_active_tile(active_selection):
    cab, selection, _, _ = active_selection
    selection.selectEngine(12)
    cab.select("TRAIN", 502)
    # The same address receives commands while operating a car through Train Link.
    # noinspection PyProtectedMember
    selection._engine_command(SimpleNamespace(scope=CommandScope.ENGINE, address=12))
    selection.dismissTrain(502)
    assert not any(row["tmccId"] == 12 for row in selection.selectedEngines)


def test_engine_membership_hides_member_when_train_consist_is_not_resolved(active_selection):
    _, selection, train, _ = active_selection
    train.consist_components = []
    selection.selectEngine(737)
    assert [(row["scope"], row["tmccId"]) for row in selection.selectedEngines] == [("TRAIN", 502)]


def test_deleted_train_restores_members_and_train_selection_uses_train_scope(active_selection):
    cab, selection, train, _ = active_selection
    selection.selectEngine(737)
    assert selection.selectTrain(502)
    cab.selectAddress.assert_called_once_with("TRAIN", 502)
    train.is_deleted = True
    selection.applyTrainStateChanges(frozenset({StateChange(CommandScope.TRAIN, 502)}))
    assert [row["tmccId"] for row in selection.selectedEngines] == [737]
    assert not selection.selectTrain(502)


def test_selected_active_consist_engine_stays_visible_with_membership_context(active_selection):
    cab, selection, train, states = active_selection
    cab.select("ENGINE", 737)
    assert selection.currentTrainId == 502
    member = next(row for row in selection.selectedEngines if row["scope"] == "ENGINE")
    assert member["tmccId"] == 737 and member["trainId"] == 502 and member["current"]
    selection.dismissTrain(502)
    assert selection.currentTrainId == 0
    assert not any(row["tmccId"] == 737 for row in selection.selectedEngines)
    # A broadcast to the train restores membership context even without a speed change.
    selection.trainCommandReceived.emit(502)
    assert selection.currentTrainId == 502
    train.consist_components = []
    states[(CommandScope.ENGINE, 737)].train_tmcc_id = None
    selection.applyTrainStateChanges(frozenset({StateChange(CommandScope.TRAIN, 502)}))
    assert selection.currentTrainId == 0


@pytest.mark.parametrize(
    "engine_type,kind",
    [
        (EngineType.DIESEL, "ENG"),
        (EngineType.STEAM, "ENG"),
        (EngineType.ELECTRIC, "ENG"),
        (EngineType.SUBWAY, "ENG"),
        (EngineType.ACELA, "ENG"),
        (EngineType.DIESEL_SWITCHER, "ENG"),
        (EngineType.STEAM_SWITCHER, "ENG"),
        (EngineType.DIESEL_PULLMOR, "ENG"),
        (EngineType.STEAM_PULLMOR, "ENG"),
        (EngineType.ACCESSORY, "CAR"),
        (EngineType.PASSENGER_CAR, "CAR"),
        (EngineType.FREIGHT_SOUNDS, "CAR"),
        (EngineType.BREAKDOWN, "CAR"),
        (EngineType.RESERVED, "CAR"),
        (EngineType.CRANE, "CAR"),
        (EngineType.TRANSFORMER, "CAR"),
    ],
)
def test_active_tile_prefix_distinguishes_locomotives_cars_and_trains(active_selection, engine_type, kind):
    _, selection, _, states = active_selection
    states[(CommandScope.ENGINE, 99)].engine_type = engine_type
    selection.selectEngine(99)
    assert [(row["scope"], row["kind"]) for row in selection.selectedEngines] == [("ENGINE", kind), ("TRAIN", "TRN")]


def test_pseudo_train_commands_never_create_active_tiles(active_selection, monkeypatch):
    _, selection, _, states = active_selection
    states[(CommandScope.TRAIN, 101)] = SimpleNamespace(tmcc_id=101, is_deleted=False, speed=10, consist_components=[])
    monkeypatch.setattr(ComponentStateStore, "is_pseudo_train_id", lambda address: address == 101)
    selection.trainCommandReceived.emit(101)
    selection.applyTrainStateChanges(frozenset({StateChange(CommandScope.TRAIN, 101)}))
    assert [(row["scope"], row["tmccId"]) for row in selection.selectedEngines] == [("TRAIN", 502)]
    assert selection.count == 1


def test_real_train_100_remains_active_even_when_address_is_also_a_pseudo_id(active_selection, monkeypatch):
    _, selection, _, states = active_selection
    states[(CommandScope.TRAIN, 100)] = SimpleNamespace(
        tmcc_id=100, record_no=0, is_deleted=False, speed=10, consist_components=[]
    )
    monkeypatch.setattr(ComponentStateStore, "is_pseudo_train_id", lambda address: address == 100)
    selection.trainCommandReceived.emit(100)
    selection.applyTrainStateChanges(frozenset({StateChange(CommandScope.TRAIN, 100)}))
    assert [(row["scope"], row["tmccId"]) for row in selection.selectedEngines] == [("TRAIN", 100), ("TRAIN", 502)]


def test_late_pseudo_id_assignment_removes_previously_active_alias(active_selection, monkeypatch):
    _, selection, _, states = active_selection
    states[(CommandScope.TRAIN, 101)] = SimpleNamespace(tmcc_id=101, is_deleted=False, speed=10, consist_components=[])
    monkeypatch.setattr(ComponentStateStore, "is_pseudo_train_id", lambda _: False)
    selection.trainCommandReceived.emit(101)
    assert selection.count == 2
    monkeypatch.setattr(ComponentStateStore, "is_pseudo_train_id", lambda address: address == 101)
    selection.applyTrainStateChanges(frozenset({StateChange(CommandScope.TRAIN, 502)}))
    assert [row["tmccId"] for row in selection.selectedEngines] == [502]
    assert selection.count == 1


@pytest.mark.parametrize("scope", [CommandScope.ENGINE, CommandScope.TRAIN])
def test_only_train_metadata_provides_equipment_fallback_without_lead_engine(scope):
    state = SimpleNamespace(scope=scope, head=None, engine_type=0, is_rpm=False, has_throttle=False)
    assert equipment_flag(state, "is_rpm") == (scope == CommandScope.TRAIN)
    assert equipment_flag(state, "has_throttle") == (scope == CommandScope.TRAIN)


# The isolated GUI uses Qt API identifiers verbatim.
# noinspection SpellCheckingInspection
TRAIN_LINK_CHILD = r"""
import sys
import traceback
from time import monotonic
from types import SimpleNamespace
from unittest.mock import Mock, patch
from PySide6.QtCore import QObject, QPointF, QTimer, Qt, QMetaObject, Q_ARG
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlEngine
from PySide6.QtTest import QTest
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.components import ConsistComponent
from pytrain.db.state_changes import StateChange, state_changes
from pytrain.protocol.constants import CommandScope
from pytrain.protocol.command_req import CommandReq
from pytrain.protocol.sequence.ramp_speed_req import RampSpeedReq
from pytrain.protocol.sequence.labor_effect import LaborEffectUpReq, LaborEffectDownReq
from pytrain.protocol.tmcc1.tmcc1_constants import TMCC1EngineCommandEnum
from pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum
from pytrain_ui.qt.app import run_cab

store = ComponentStateStore.build()
for address, name, number in (
    (1, "Canadian National", "3233"),
    (12, "StationSounds Diner", "12"),
    (34, "Operating Boxcar", "34"),
    (56, "Milk Car", "56"),
    (77, "Switcher", "77"),
):
    state = store.get_state(CommandScope.ENGINE, address)
    state.initialize(CommandScope.ENGINE, address)
    # Seed the synchronized identity without starting Base readback services.
    # noinspection PyProtectedMember
    state._road_name = name
    # noinspection PyProtectedMember
    state._road_number = number
    state.comp_data.road_name = name
    state.comp_data.road_number = number
    state.comp_data.control_type = 2 if address == 34 else 1
    state.comp_data.engine_type = 5 if address == 12 else 12 if address == 34 else 0
train = store.get_state(CommandScope.TRAIN, 41)
train.initialize(CommandScope.TRAIN, 41)
# Seed the synchronized identity without a live Base connection.
# noinspection PyProtectedMember
train._road_name = "Empire Builder"
# noinspection PyProtectedMember
train._road_number = "0041"
train.comp_data.road_name = "Empire Builder"
train.comp_data.road_number = "41"
train.comp_data.control_type = 2
train.comp_data.engine_type = 0
train.comp_data.consist_comps = [
    ConsistComponent(1, 1), ConsistComponent(12, 10), ConsistComponent(34, 10), ConsistComponent(56, 11)
]
failures = []
requests = []

def factory(argv):
    app = QGuiApplication(argv)
    def checks():
        try:
            window = next(w for w in app.allWindows() if w.property("workspace") is not None)
            window.resize(720, 1280)
            workspace = window.property("workspace")
            context = QQmlEngine.contextForObject(window)
            cab = context.contextProperty("cabController")
            links = context.contextProperty("trainLinkController")
            assert cab.selectAddress("TRAIN", 41)
            workspace.setProperty("activeScope", "TRAIN")
            workspace.setProperty("engineCatalogVisible", False)
            app.processEvents()

            def descendants(item):
                yield item
                for child in item.childItems():
                    yield from descendants(child)

            def visible(name):
                return next(i for i in descendants(window.contentItem()) if i.isVisible() and i.objectName() == name)

            bar = visible("trainLinkedCarBar")
            assert [row["tmccId"] for row in links.rows] == [12, 34, 56]
            assert visible("trainLinkedCarType-12").property("text") == "Passenger"
            assert visible("trainLinkedCarType-34").property("text") == "Freight Sounds"
            third = visible("trainLinkedCar-56")
            assert third.x() + third.width() <= bar.width() - 8
            tile = visible("trainLinkedCar-12")
            point = tile.mapToScene(QPointF(tile.width()/2, tile.height()/2)).toPoint()
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            QTest.qWait(30)
            assert cab.scope == "TRAIN" and cab.tmccId == 41
            assert workspace.property("activeScope") == "TRAIN"
            assert links.selectedId == 12
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            QTest.qWait(20)
            assert links.selectedId == 0
            assert cab.scope == "TRAIN" and cab.tmccId == 41
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            QTest.qWait(20)
            assert links.selectedId == 12
            controls = visible("operatingCabView")
            assert controls.property("keyCab") is links.selectedCab
            assert links.selectedCab.isStandalonePassenger
            assert visible("targetSpeedThrottle").isEnabled()
            requests.clear()
            key = visible("actionControl_car_lights_on")
            point = key.mapToScene(QPointF(key.width()/2, key.height()/2)).toPoint()
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            QTest.qWait(20)
            assert requests[-1].address == 12 and requests[-1].scope == CommandScope.ENGINE
            assert requests[-1].command == TMCC1EngineCommandEnum.NUMBER_9
            assert {row["key"] for row in links.selectedCab.volumeActionModel} == {
                "master_volume_up", "master_volume_down", "blend_up", "blend_down", "labor_up", "labor_down"
            }
            for volume_action in links.selectedCab.volumeActionModel:
                previous_requests = len(requests)
                links.selectedCab.triggerVolumeAction(volume_action["key"])
                if volume_action["disabled"]:
                    assert len(requests) == previous_requests
                else:
                    assert len(requests) == previous_requests + 1
                    assert requests[-1].address == 12 and requests[-1].scope == CommandScope.ENGINE
            QMetaObject.invokeMethod(visible("targetSpeedThrottle"), "valueCommitted", Q_ARG(int, 10))
            assert requests[-1].address == 41 and requests[-1].scope == CommandScope.TRAIN
            assert isinstance(requests[-1], RampSpeedReq)
            assert requests[-1].target_speed == 10
            controls.setProperty("selectedAnalogMode", "Brake")
            assert QMetaObject.invokeMethod(controls, "syncAnalogMode")
            assert visible("variableCabControl").isEnabled()
            QMetaObject.invokeMethod(visible("variableCabControl"), "valueMoved", Q_ARG(int, 3))
            assert requests[-1].address == 41 and requests[-1].scope == CommandScope.TRAIN
            assert requests[-1].command == TMCC2EngineCommandEnum.TRAIN_BRAKE
            tab = visible("cabInfoTab")
            point = tab.mapToScene(QPointF(tab.width()/2, tab.height()/2)).toPoint()
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            QTest.qWait(20)
            info = context.contextProperty("stateInfoController")
            assert info.model["tmccId"] == 12 and info.model["scopeTitle"] == "Engine"
            assert QMetaObject.invokeMethod(
                workspace, "changeScope", Q_ARG("QVariant", "TRAIN"), Q_ARG("QVariant", False)
            )
            app.processEvents()
            assert links.selectedId == 0
            assert not workspace.property("stateInfoVisible")
            assert not workspace.property("engineCatalogVisible")
            assert controls.property("keyCab") is cab
            assert links.select(34)
            app.processEvents()
            assert links.selectedCab.isStandaloneFreight
            assert visible("stateTile_Brake").property("editable")
            assert QMetaObject.invokeMethod(controls, "editState", Q_ARG("QVariant", "Brake"))
            app.processEvents()
            state_dialog = window.findChild(QObject, "stateValueDialog")
            assert state_dialog.property("targetText") == "TRAIN 41"
            assert QMetaObject.invokeMethod(
                state_dialog, "valueSubmitted", Q_ARG(str, "Brake"), Q_ARG(int, 4)
            )
            assert requests[-1].address == 41 and requests[-1].scope == CommandScope.TRAIN
            assert requests[-1].command == TMCC2EngineCommandEnum.TRAIN_BRAKE
            assert QMetaObject.invokeMethod(state_dialog, "close")
            app.processEvents()
            key = visible("actionControl_freight_load")
            point = key.mapToScene(QPointF(key.width()/2, key.height()/2)).toPoint()
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            QTest.qWait(20)
            assert requests[-1].address == 34 and requests[-1].scope == CommandScope.ENGINE
            assert requests[-1].command == TMCC2EngineCommandEnum.NUMBER_3
            tab = visible("speedTab")
            point = tab.mapToScene(QPointF(tab.width()/2, tab.height()/2)).toPoint()
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            QTest.qWait(20)
            assert controls.property("keyCab") is cab
            assert links.selectedId == 34
            assert not any(i.isVisible() and i.objectName() == "actionControl_set_address"
                           for i in descendants(window.contentItem()))
            volume_geometry = []
            volume_keys = ("master_volume_up", "master_volume_down", "blend_up", "blend_down", "labor_up", "labor_down")
            for key_name in volume_keys:
                key = visible("actionControl_" + key_name)
                volume_geometry.append((key.width(), key.height(), key.mapToScene(QPointF(0, 0)).y()))
                assert visible("carTarget_" + key_name).property("text") == "Car 34"
                assert QMetaObject.invokeMethod(key, "clicked")
                assert requests[-1].address == 34 and requests[-1].scope == CommandScope.ENGINE
            assert QMetaObject.invokeMethod(visible("actionControl_SLOW"), "clicked")
            assert requests[-1].address == 41 and requests[-1].scope == CommandScope.TRAIN
            fuel = visible("actionControl_fuel")
            assert fuel.isEnabled()
            assert QMetaObject.invokeMethod(fuel, "clicked")
            assert requests[-1].address == 41 and requests[-1].scope == CommandScope.TRAIN
            assert QMetaObject.invokeMethod(fuel, "held")
            assert requests[-1].address == 41 and requests[-1].scope == CommandScope.TRAIN
            if len(sys.argv) > 1:
                assert window.grabWindow().save(sys.argv[1] + "/train-linked-volume.png")
            links.clearSelection()
            app.processEvents()
            for key_name, geometry in zip(
                volume_keys, volume_geometry
            ):
                key = visible("actionControl_" + key_name)
                assert (key.width(), key.height(), key.mapToScene(QPointF(0, 0)).y()) == geometry
                assert QMetaObject.invokeMethod(key, "clicked")
                assert requests[-1].address == 41 and requests[-1].scope == CommandScope.TRAIN
            assert links.select(34)
            app.processEvents()
            tab = visible("cabInfoTab")
            point = tab.mapToScene(QPointF(tab.width()/2, tab.height()/2)).toPoint()
            QTest.mouseClick(window, Qt.LeftButton, pos=point)
            QTest.qWait(20)
            assert info.model["tmccId"] == 34
            assert QMetaObject.invokeMethod(
                workspace, "changeScope", Q_ARG("QVariant", "TRAIN"), Q_ARG("QVariant", False)
            )
            app.processEvents()
            links.clearSelection()
            app.processEvents()
            assert bar.y() + bar.height() <= window.height()
            if len(sys.argv) > 1:
                assert window.grabWindow().save(sys.argv[1] + "/train-linked-cars.png")
            assert not visible("trainLinkedCarList").property("overflow")
            train.comp_data.consist_comps.append(ConsistComponent(1, 10))
            links.refresh()
            QTest.qWait(30)
            assert visible("trainLinkedCarList").property("overflow")
            indicator = visible("trainLinkedCarScrollIndicator")
            assert indicator.parentItem() is bar, "The list must not clip its overflow indicator"
            assert indicator.y() >= visible("trainLinkedCarList").y() + visible("trainLinkedCarList").height()
            assert indicator.y() + indicator.height() <= bar.height()
            assert 0 < indicator.property("size") < 1
            if len(sys.argv) > 1:
                assert window.grabWindow().save(sys.argv[1] + "/train-linked-overflow.png")
            car_list = visible("trainLinkedCarList")
            car_list.setProperty("contentX", car_list.property("contentWidth") - car_list.width())
            app.processEvents()
            assert indicator.property("position") > 0
            train.comp_data.consist_comps = [ConsistComponent(1, 1)]
            state_changes.publish(CommandScope.TRAIN, 41)
            deadline = monotonic() + 2
            while links.rows and monotonic() < deadline:
                QTest.qWait(5)
            assert links.rows == []
            assert visible("noTrainLinkedCars").property("text") == "None"
            if len(sys.argv) > 1:
                assert window.grabWindow().save(sys.argv[1] + "/no-train-linked-cars.png")
            assert cab.selectAddress("ENGINE", 1)
            workspace.setProperty("activeScope", "ENGINE")
            app.processEvents()
            assert not bar.isVisible()
            active_bar = visible("activeEngineTrainBar")
            assert active_bar.height() > 0
            assert visible("engineIdentity").property("text") == "Engine 1 in TRAIN 41"
            member_tile = visible("activeTile-ENGINE-1")
            assert member_tile.property("color").name() == "#335b58"
            assert visible("activeEngineTrainTitle").property("text") == "Active Engines and Trains"
            assert not visible("activeEngineTrainList").property("overflow")
            selection = context.contextProperty("selectedEngineController")
            train.comp_data.consist_comps.append(ConsistComponent(12, 10))
            selection.selectEngine(12)
            app.processEvents()
            assert visible("engineIdentity").property("text") == "CAR 12 in TRAIN 41"
            selection._engine_command(SimpleNamespace(scope=CommandScope.ENGINE, address=12))
            app.processEvents()
            assert visible("activeTile-ENGINE-12").property("color").name() == "#36556f"
            train.comp_data.consist_comps = [ConsistComponent(1, 1)]
            selection.applyTrainStateChanges(frozenset({StateChange(CommandScope.TRAIN, 41)}))
            for address in (12, 34, 77, 56):
                selection.selectEngine(address)
            QTest.qWait(30)
            active_list = visible("activeEngineTrainList")
            assert active_list.property("overflow")
            assert visible("activeTargetKind-ENGINE-12").property("text") == "CAR"
            assert visible("activeTargetKind-ENGINE-34").property("text") == "CAR"
            assert visible("activeTargetKind-ENGINE-77").property("text") == "ENG"
            indicator = visible("activeEngineTrainScrollIndicator")
            assert indicator.parentItem() is active_bar
            assert indicator.y() >= active_list.y() + active_list.height()
            assert indicator.y() + indicator.height() <= active_bar.height()
            assert 0 < indicator.property("size") < 1
            active_list.setProperty("contentX", active_list.property("contentWidth") - active_list.width())
            QTest.qWait(30)
            assert indicator.property("position") > 0
            assert visible("activeTargetKind-TRAIN-41").property("text") == "TRN"
            if len(sys.argv) > 1:
                assert window.grabWindow().save(sys.argv[1] + "/active-engine-train-overflow.png")
            selection.dismissEngine(12)
            selection.dismissEngine(34)
            QTest.qWait(30)
            assert not active_list.property("overflow")
            assert not indicator.isVisible()

            # Navigate during real pointer holds, rather than emitting click signals.
            train.comp_data.consist_comps = [ConsistComponent(1, 1), ConsistComponent(12, 10), ConsistComponent(34, 10)]
            for navigation in ("car", "tab", "scope"):
                assert cab.selectAddress("TRAIN", 41)
                workspace.setProperty("activeScope", "TRAIN")
                workspace.setProperty("engineCatalogVisible", False)
                links.refresh()
                assert links.select(12)
                assert QMetaObject.invokeMethod(controls, "selectControlPage", Q_ARG("QVariant", 0))
                app.processEvents()
                assert visible("engineIdentity").property("text") == "CAR 12 in TRAIN 41"
                assert any(
                    i.isVisible() and i.property("text") == "Train Speed"
                    for i in descendants(window.contentItem())
                )
                aux = visible("auxControl_car_aux1")
                point = aux.mapToScene(QPointF(aux.width()/2, aux.height()/2)).toPoint()
                before = len(requests)
                QTest.mousePress(window, Qt.LeftButton, pos=point)
                QTest.qWait(230)
                assert len(requests) >= before + 2
                assert all(r.scope == CommandScope.ENGINE and r.address == 12 for r in requests[before:])
                if navigation == "car":
                    assert links.select(34)
                elif navigation == "tab":
                    assert QMetaObject.invokeMethod(controls, "selectControlPage", Q_ARG("QVariant", 1))
                else:
                    assert QMetaObject.invokeMethod(
                        workspace, "changeScope", Q_ARG("QVariant", "ENGINE"), Q_ARG("QVariant", False)
                    )
                app.processEvents()
                stopped = len(requests)
                QTest.qWait(230)
                QTest.mouseRelease(window, Qt.LeftButton, pos=point)
                QTest.qWait(30)
                assert len(requests) == stopped, "A navigation-canceled hold must not repeat or fire on release"

            assert cab.selectAddress("TRAIN", 41)
            workspace.setProperty("activeScope", "TRAIN")
            workspace.setProperty("engineCatalogVisible", False)
            links.refresh()
            assert links.select(12)
            assert QMetaObject.invokeMethod(controls, "selectControlPage", Q_ARG("QVariant", 0))
            controls.setProperty("selectedAnalogMode", "Horn")
            assert QMetaObject.invokeMethod(controls, "syncAnalogMode")
            app.processEvents()
            analog = visible("variableCabControl")
            point = analog.mapToScene(QPointF(analog.width()/2, analog.height()*0.95)).toPoint()
            QTest.mousePress(window, Qt.LeftButton, pos=point)
            QTest.qWait(550)
            assert requests[-1].scope == CommandScope.TRAIN and requests[-1].address == 41
            assert QMetaObject.invokeMethod(controls, "stateInfoTabRequested")
            app.processEvents()
            stopped = len(requests)
            QTest.qWait(550)
            QTest.mouseRelease(window, Qt.LeftButton, pos=point)
            assert len(requests) == stopped, "The train's analog horn must stop repeating when Info opens"
            assert info.model["tmccId"] == 12
            assert visible("engineIdentity").property("text") == "CAR 12 in TRAIN 41"

            # A consist edit invalidates the car's open Info tab and returns to the train.
            train.comp_data.consist_comps = [ConsistComponent(1, 1)]
            links.applyStateChanges(frozenset({StateChange(CommandScope.TRAIN, 41)}))
            app.processEvents()
            assert links.selectedId == 0
            assert not workspace.property("stateInfoVisible")
            assert not workspace.property("engineCatalogVisible")
            assert controls.property("keyCab") is cab

            # DELETE broadcasts must return to the train, including from the linked car's Info tab.
            car = store.get_state(CommandScope.ENGINE, 12)
            for from_info in (False, True):
                train.comp_data.consist_comps = [ConsistComponent(12, 10)]
                links.refresh()
                assert links.select(12)
                app.processEvents()
                if from_info:
                    assert QMetaObject.invokeMethod(controls, "stateInfoTabRequested")
                ComponentStateStore.delete_state(car)
                info.recordCleared.emit("ENGINE", 12)
                app.processEvents()
                assert links.selectedId == 0
                assert not workspace.property("stateInfoVisible")
                assert not workspace.property("engineCatalogVisible")
                assert controls.property("keyCab") is cab
                ComponentStateStore.set_state(CommandScope.ENGINE, 12, car)
                app.processEvents()

            # Overlay content must not retain a command target when a different car is selected.
            train.comp_data.consist_comps = [ConsistComponent(12, 10), ConsistComponent(34, 10)]
            links.refresh()
            assert links.select(12)
            assert QMetaObject.invokeMethod(
                controls, "handleModelHold", Q_ARG("QVariant", {"holdKind": "panel", "holdTarget": "bell_horn"})
            )
            popup = window.findChild(QObject, "cabBellHornPopup")
            assert popup.property("visible")
            assert links.select(34)
            app.processEvents()
            assert not popup.property("visible")
            links.clearSelection()

            # A deferred startup press must not fire its tap or hold action after navigation.
            assert QMetaObject.invokeMethod(controls, "selectControlPage", Q_ARG("QVariant", 0))
            app.processEvents()
            startup = visible("actionControl_startup")
            point = startup.mapToScene(QPointF(startup.width()/2, startup.height()/2)).toPoint()
            QTest.mousePress(window, Qt.LeftButton, pos=point)
            assert QMetaObject.invokeMethod(controls, "stateInfoTabRequested")
            app.processEvents()
            stopped = len(requests)
            QTest.qWait(1050)
            QTest.mouseRelease(window, Qt.LeftButton, pos=point)
            assert len(requests) == stopped, "Canceled deferred presses must not fire on release or on the hold timer"
            assert QMetaObject.invokeMethod(workspace, "closeStateInfo")

            # Relative speed repeats belong to the train and must end when leaving the scope.
            train.comp_data.control_type = 0
            assert cab.selectAddress("TRAIN", 41)
            app.processEvents()
            throttle = visible("targetSpeedThrottle")
            assert throttle.property("springReturn")
            point = throttle.mapToScene(QPointF(throttle.width()/2, throttle.height()*0.1)).toPoint()
            before = len(requests)
            QTest.mousePress(window, Qt.LeftButton, pos=point)
            QTest.qWait(230)
            assert len(requests) >= before + 2
            assert all(r.scope == CommandScope.TRAIN and r.address == 41 for r in requests[before:])
            assert QMetaObject.invokeMethod(
                workspace, "changeScope", Q_ARG("QVariant", "ENGINE"), Q_ARG("QVariant", False)
            )
            app.processEvents()
            stopped = len(requests)
            QTest.qWait(230)
            QTest.mouseRelease(window, Qt.LeftButton, pos=point)
            assert len(requests) == stopped
            train.comp_data.control_type = 2
            assert cab.selectAddress("TRAIN", 41)
            workspace.setProperty("activeScope", "TRAIN")
            workspace.setProperty("engineCatalogVisible", False)
            train.comp_data.consist_comps = [ConsistComponent(12, 10)]
            links.refresh()
            assert links.select(12)
            assert QMetaObject.invokeMethod(controls, "stateInfoTabRequested")
            app.processEvents()
            # The shared state notification must handle deletion even without a DELETE broadcast.
            # noinspection PyProtectedMember
            train._deleted = True
            links.applyStateChanges(frozenset({StateChange(CommandScope.TRAIN, 41)}))
            app.processEvents()
            assert links.selectedId == 0
            assert workspace.property("engineCatalogVisible")
            assert not workspace.property("stateInfoVisible")
        except Exception:
            failures.append(traceback.format_exc())
        finally:
            app.quit()
    QTimer.singleShot(200, checks)
    return app

with (
    patch("PySide6.QtGui.QGuiApplication", side_effect=factory),
    patch("pytrain.comm.command_listener.CommandDispatcher.get", return_value=Mock()),
    patch("pytrain_ui.qt.session.restore_engine", return_value=None),
    patch("pytrain_ui.qt.session.save_engine"),
    patch.object(CommandReq, "send", lambda request, *args, **kwargs: requests.append(request)),
    patch.object(RampSpeedReq, "send", lambda request, *args, **kwargs: requests.append(request)),
    patch.object(LaborEffectUpReq, "send", lambda request, *args, **kwargs: requests.append(request)),
    patch.object(LaborEffectDownReq, "send", lambda request, *args, **kwargs: requests.append(request)),
):
    run_cab(CommandScope.TRAIN, 41, [])
assert not failures, "\n".join(failures)
print("TRAIN_LINK_OK")
"""


@pytest.mark.qt_gui
def test_train_link_controls_target_car_while_sliders_keep_train_target(tmp_path: Path):
    result = subprocess.run(
        [sys.executable, "-c", TRAIN_LINK_CHILD, str(tmp_path)],
        env=dict(os.environ, QT_QPA_PLATFORM="offscreen"),
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "TRAIN_LINK_OK" in result.stdout
    assert "Error:" not in result.stderr, result.stderr
