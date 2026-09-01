#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
from __future__ import annotations

from typing import Any

from src.pytrain.gui.controller import lcs_id_map
from src.pytrain.gui.controller.lcs_device_registry import ASC2, BPC2, SENSOR_TRACK, STM2
from src.pytrain.gui.controller.lcs_id_map import occupant_of, occupants, overlaps
from src.pytrain.protocol.constants import CommandScope


class FakeState:
    """
    Minimal stand-in for an LcsProxyState: only what lcs_id_map reads.
    """

    def __init__(
        self,
        address: int,
        device: str,
        mode: Any = "NA",
        num_ids: int | None = None,
        parent: Any = None,
    ) -> None:
        self.address = address
        self.mode = mode
        self.num_ids = num_ids
        self.parent = parent
        self.port = address - parent.address + 1 if parent is not None else 1
        self.is_asc2 = device == "asc2"
        self.is_bpc2 = device == "bpc2"
        self.is_stm2 = device == "stm2"
        self.is_sensor_track = device == "sensor_track"


class FakeStore:
    def __init__(self, **by_scope: list[FakeState]) -> None:
        self._states = {
            CommandScope.ACC: by_scope.get("acc", []),
            CommandScope.SWITCH: by_scope.get("switch", []),
            CommandScope.TRAIN: by_scope.get("train", []),
        }

    def get_all(self, scope: CommandScope) -> list[FakeState]:
        return self._states.get(scope, [])


def asc2_at_9() -> FakeStore:
    base = FakeState(9, "asc2", mode=0)
    ports = [FakeState(9 + i, "asc2", mode=0, parent=base) for i in range(1, 8)]
    return FakeStore(acc=[base] + ports)


class TestOccupantOf:
    def test_base_hit(self):
        occupant = occupant_of(9, asc2_at_9())
        assert occupant is not None
        assert occupant.device is ASC2
        assert occupant.base_id == 9
        assert occupant.ports == 8
        assert occupant.port_index == 1
        assert occupant.is_base is True
        assert occupant.last_id == 16
        assert occupant.mode.key == "acc_8"

    def test_interior_port_hit(self):
        occupant = occupant_of(12, asc2_at_9())
        assert occupant is not None
        assert occupant.base_id == 9
        assert occupant.port_index == 4
        assert occupant.is_base is False

    def test_last_port_hit(self):
        assert occupant_of(16, asc2_at_9()).port_index == 8

    def test_unowned_id(self):
        assert occupant_of(17, asc2_at_9()) is None
        assert occupant_of(8, asc2_at_9()) is None

    def test_empty_store(self):
        assert occupant_of(1, FakeStore()) is None
        assert occupants(FakeStore()) == []

    def test_non_lcs_state_ignored(self):
        store = FakeStore(acc=[FakeState(5, "none")])
        assert occupant_of(5, store) is None

    def test_sensor_track_single_port(self):
        irda_state = FakeState(3, "none")
        store = FakeStore(acc=[FakeState(3, "sensor_track", parent=irda_state)])
        occupant = occupant_of(3, store)
        assert occupant is not None
        assert occupant.device is SENSOR_TRACK
        assert occupant.ports == 1
        assert occupant.last_id == 3
        assert occupant_of(4, store) is None
        assert [item.base_id for item in overlaps(3, 1, store)] == [3]

    def test_switch_and_train_scopes(self):
        store = FakeStore(
            switch=[FakeState(20, "stm2", mode=0)],
            train=[FakeState(12, "bpc2", mode=0)],
        )
        stm2 = occupant_of(30, store)
        assert stm2.device is STM2
        assert stm2.scope == CommandScope.SWITCH
        assert stm2.ports == 16
        bpc2 = occupant_of(13, store)
        assert bpc2.device is BPC2
        assert bpc2.scope == CommandScope.TRAIN
        assert bpc2.port_index == 2


class TestBlockSize:
    def test_num_ids_overrides_registry_default(self):
        # mode 0 declares 8 ports, but the module's INFO packet says 4
        store = FakeStore(acc=[FakeState(9, "asc2", mode=0, num_ids=4)])
        occupant = occupant_of(9, store)
        assert occupant.ports == 4
        assert occupant.last_id == 12
        assert occupant_of(13, store) is None

    def test_registry_default_when_info_missing(self):
        store = FakeStore(switch=[FakeState(20, "stm2", mode=1)])
        assert occupant_of(20, store).ports == 8

    def test_unknown_mode_falls_back_to_one_port(self):
        store = FakeStore(acc=[FakeState(50, "asc2", mode="NA")])
        occupant = occupant_of(50, store)
        assert occupant.mode is None
        assert occupant.ports == 1


class TestOverlaps:
    def test_detects_overlap(self):
        store = FakeStore(switch=[FakeState(28, "stm2", mode=1)])
        found = overlaps(20, 16, store)
        assert [o.base_id for o in found] == [28]

    def test_no_overlap_when_blocks_are_disjoint(self):
        store = FakeStore(switch=[FakeState(40, "stm2", mode=1)])
        assert overlaps(20, 16, store) == []

    def test_ignore_base_omits_the_module_being_reconfigured(self):
        store = asc2_at_9()
        assert [o.base_id for o in overlaps(9, 8, store)] == [9]
        assert overlaps(9, 8, store, ignore_base=9) == []


class TestScope:
    """
    A TMCC ID is only an address together with the remote key that reaches it.
    """

    @staticmethod
    def crowded_id_1() -> FakeStore:
        # The reported layout: an STM2 based at SW 1 and a BPC2 on ACC 1. Two addresses.
        return FakeStore(
            acc=[FakeState(1, "bpc2", mode=3, num_ids=1)],
            switch=[FakeState(1, "stm2", mode=0, num_ids=16)],
        )

    def test_scope_picks_between_two_modules_on_the_same_number(self):
        store = self.crowded_id_1()

        assert occupant_of(1, store, scope=CommandScope.SWITCH).device is STM2
        assert occupant_of(1, store, scope=CommandScope.ACC).device is BPC2
        assert occupant_of(1, store, scope=CommandScope.TRAIN) is None

    def test_the_switch_block_extends_past_the_accessory_on_its_base(self):
        store = self.crowded_id_1()

        assert occupant_of(9, store, scope=CommandScope.SWITCH).device is STM2
        assert occupant_of(9, store, scope=CommandScope.ACC) is None

    def test_omitting_the_scope_still_returns_every_module(self):
        store = self.crowded_id_1()

        assert {o.device for o in occupants(store)} == {STM2, BPC2}
        assert occupant_of(1, store) is not None

    def test_effective_scope_comes_from_the_registry_not_the_store(self):
        # asc2_req.py files a switch-mode ASC2 with the accessories; the registry knows
        # mode 2 is a switch, and that is the key the module really answers to.
        store = FakeStore(acc=[FakeState(25, "asc2", mode=2, num_ids=4)])
        occupant = occupant_of(25, store)

        assert occupant.scope == CommandScope.ACC
        assert occupant.effective_scope == CommandScope.SWITCH
        assert occupant_of(25, store, scope=CommandScope.SWITCH).device is ASC2
        assert occupant_of(25, store, scope=CommandScope.ACC) is None

    def test_the_store_scope_is_the_fallback_when_the_mode_is_unknown(self):
        store = FakeStore(acc=[FakeState(50, "asc2", mode="NA")])
        occupant = occupant_of(50, store)

        assert occupant.mode is None
        assert occupant.effective_scope == CommandScope.ACC

    def test_overlaps_only_reports_blocks_on_the_same_key(self):
        # An STM2 based at SW 20 with 16 inputs runs through a switch-mode ASC2 at 25,
        # and through nothing at all on the accessory keys.
        store = FakeStore(
            acc=[FakeState(25, "asc2", mode=2, num_ids=4), FakeState(22, "bpc2", mode=2, num_ids=8)],
        )
        found = overlaps(20, 16, store, scope=CommandScope.SWITCH)

        assert [(o.device, o.base_id, o.last_id) for o in found] == [(ASC2, 25, 28)]
        assert overlaps(1, 16, self.crowded_id_1(), ignore_base=1, scope=CommandScope.SWITCH) == []

    def test_the_same_module_kind_on_two_keys_is_two_modules(self):
        # De-duplication is per module, and a base under two remote keys is two of them.
        store = FakeStore(
            acc=[FakeState(9, "asc2", mode=0, num_ids=8)],
            switch=[FakeState(9, "asc2", mode=2, num_ids=4)],
        )

        assert len(occupants(store)) == 2
        assert occupant_of(9, store, scope=CommandScope.ACC).ports == 8
        assert occupant_of(9, store, scope=CommandScope.SWITCH).ports == 4


class TestStoreDefault:
    def test_no_store_built_is_not_an_error(self, monkeypatch):
        monkeypatch.setattr(lcs_id_map, "_store", lambda store=None: None)
        assert occupants() == []
        assert occupant_of(1) is None
        assert overlaps(1, 8) == []
