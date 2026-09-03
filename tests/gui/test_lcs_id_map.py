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
from src.pytrain.gui.controller.lcs_device_registry import AMC2, ASC2, BPC2, SENSOR_TRACK, STM2
from src.pytrain.gui.controller.lcs_id_map import occupant_of, occupants, occupants_of, overlaps
from src.pytrain.pdi.pdi_device import PdiDevice
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
        # Recognized but not programmable, and the map must find it all the same: a
        # module it cannot see is an address it reports as free when it is not.
        self.is_amc2 = device == "amc2"


class FakeStore:
    def __init__(self, **by_scope: list[FakeState]) -> None:
        self._states = {
            CommandScope.ACC: by_scope.get("acc", []),
            CommandScope.SWITCH: by_scope.get("switch", []),
            CommandScope.TRAIN: by_scope.get("train", []),
        }

    def get_all(self, scope: CommandScope) -> list[FakeState]:
        return self._states.get(scope, [])

    # create is named as the real get_state names it, and kept because lcs_id_map passes it
    # positionally as False; nothing here manufactures a state, so the fake never reads it.
    # noinspection PyUnusedLocal,unused-parameter
    def get_state(self, scope: CommandScope, address: int, create: bool = True) -> FakeState | None:
        for state in self._states.get(scope, []):
            if state.address == address:
                return state
        return None


class FakePacket:
    """Stand-in for the CONFIG request itself: a Bpc2Req for a BPC2, an Asc2Req for an ASC2.

    Where a module's settings are. A BPC2's restore-on-power-up flag is the top bit of its
    mode byte, and the request is what unpacks the two apart.
    """

    def __init__(self, mode: int | None = None, restore: bool | None = None) -> None:
        if mode is not None:
            self.mode = mode
        if restore is not None:
            # Only a BPC2's request carries one.
            self.restore = restore


class FakeConfig:
    """Stand-in for a PdiDeviceConfig: the PDI store's entry for one module.

    Built from the CONFIG request the module answered with, which it holds on config, and
    republishing that request's mode byte -- which is the whole of what PdiDeviceConfig
    republishes, and why the settings are readable only from the request.
    """

    def __init__(
        self,
        tmcc_id: int,
        scope: CommandScope,
        mode: int | None = None,
        restore: bool | None = None,
    ) -> None:
        self.tmcc_id = tmcc_id
        self.scope = scope
        if mode is not None:
            # Only ASC2, BPC2 and STM2 configs carry a mode; an AMC2's does not.
            self.mode = mode
        self.config = FakePacket(mode, restore)


class FakePdiStore:
    """
    Stand-in for PdiStateStore: one entry per module type per TMCC ID.
    """

    def __init__(self, configs: dict[PdiDevice, list[FakeConfig]]) -> None:
        self._configs = configs

    def keys(self) -> list[PdiDevice]:
        return list(self._configs.keys())

    def get_all(self, device: PdiDevice) -> list[FakeConfig]:
        return self._configs.get(device, [])


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


class TestSeveralModulesOnOneId:
    """
    More than one module can answer to the same address, even on the same remote key.
    """

    @staticmethod
    def amc2_and_bpc2_at_acc_1() -> FakeStore:
        # The reported layout: an AMC2 and a BPC2, both on ACC 1.
        return FakeStore(
            acc=[FakeState(1, "bpc2", mode=3, num_ids=1), FakeState(1, "amc2", num_ids=1)],
        )

    def test_every_module_on_the_id_is_returned(self):
        found = occupants_of(1, self.amc2_and_bpc2_at_acc_1(), scope=CommandScope.ACC)

        assert [o.device for o in found] == [BPC2, AMC2]
        assert all(o.port_index == 1 for o in found)

    def test_occupant_of_still_answers_with_the_first(self):
        assert occupant_of(1, self.amc2_and_bpc2_at_acc_1()).device is BPC2

    def test_a_module_the_panel_cannot_program_is_still_recognized(self):
        store = FakeStore(acc=[FakeState(1, "amc2", num_ids=1)])
        occupant = occupant_of(1, store)

        assert occupant is not None
        assert occupant.device is AMC2
        assert occupant.device.configurable is False
        # No mode of its own, so it holds what its INFO packet reported on the store's key.
        assert occupant.mode is None
        assert occupant.ports == 1
        assert occupant.effective_scope == CommandScope.ACC

    def test_an_amc2_that_has_not_reported_yet_holds_one_id(self):
        store = FakeStore(acc=[FakeState(4, "amc2")])

        assert occupant_of(4, store).ports == 1
        assert occupant_of(5, store) is None

    def test_nothing_there_is_an_empty_list(self):
        assert occupants_of(40, self.amc2_and_bpc2_at_acc_1()) == []


class TestPdiDeviceStore:
    """
    The PDI device store holds one entry per module type per TMCC ID, each sized from that
    module's own CONFIG packet. It is what sees a module hidden behind a shared component
    record, and what sizes a module the shared record would size wrongly.
    """

    @staticmethod
    def shared_acc_1() -> tuple[FakeStore, FakePdiStore]:
        # The reported layout: an AMC2 and a BPC2 both on ACC 1, sharing one record whose
        # mode and num_ids came from whichever of them reported last -- here the AMC2's,
        # which carries neither, leaving the record claiming a single ID.
        store = FakeStore(acc=[FakeState(1, "bpc2", mode="NA", num_ids=1)])
        pdi = FakePdiStore(
            {
                PdiDevice.BPC2: [FakeConfig(1, CommandScope.ACC, mode=2)],
                PdiDevice.AMC2: [FakeConfig(1, CommandScope.ACC)],
            }
        )
        return store, pdi

    def test_both_modules_on_the_shared_id_are_reported(self):
        store, pdi = self.shared_acc_1()
        found = occupants_of(1, store, scope=CommandScope.ACC, pdi_store=pdi)

        assert [o.device for o in found] == [BPC2, AMC2]

    def test_each_module_is_sized_from_its_own_config(self):
        store, pdi = self.shared_acc_1()
        by_device = {o.device: o for o in occupants_of(1, store, scope=CommandScope.ACC, pdi_store=pdi)}

        # The BPC2's own mode 2 is ACC, 8 TMCC IDs, whatever the shared record says.
        assert by_device[BPC2].mode.key == "acc_8"
        assert by_device[BPC2].ports == 8
        assert by_device[BPC2].last_id == 8
        # An AMC2 declares no modes and holds exactly one ID; it must not inherit the
        # neighbor's block size from the record they share.
        assert by_device[AMC2].mode is None
        assert by_device[AMC2].ports == 1
        assert by_device[AMC2].last_id == 1

    def test_the_shared_records_own_size_no_longer_wins(self):
        store, pdi = self.shared_acc_1()

        # Without the PDI store this is the wrong answer the panel used to show.
        assert occupant_of(1, store, scope=CommandScope.ACC).ports == 1
        assert occupant_of(1, store, scope=CommandScope.ACC, pdi_store=pdi).ports == 8

    def test_interior_ids_of_the_true_block_are_claimed(self):
        store, pdi = self.shared_acc_1()
        found = occupants_of(5, store, scope=CommandScope.ACC, pdi_store=pdi)

        assert [o.device for o in found] == [BPC2]
        assert found[0].port_index == 5

    def test_a_modules_own_mode_decides_its_remote_key(self):
        # A BPC2 in mode 0 is a TR module, however its config was filed.
        pdi = FakePdiStore({PdiDevice.BPC2: [FakeConfig(12, CommandScope.ACC, mode=0)]})
        occupant = occupant_of(12, FakeStore(), scope=CommandScope.TRAIN, pdi_store=pdi)

        assert occupant is not None
        assert occupant.effective_scope == CommandScope.TRAIN
        assert occupant.ports == 8
        assert occupant_of(12, FakeStore(), scope=CommandScope.ACC, pdi_store=pdi) is None

    def test_a_switch_mode_asc2_is_a_switch_however_it_was_filed(self):
        # asc2_req.py files a mode-3 (SW latching) ASC2 with the accessories; the registry
        # mode is the truth, and it claims four switch IDs.
        pdi = FakePdiStore({PdiDevice.ASC2: [FakeConfig(25, CommandScope.ACC, mode=3)]})
        occupant = occupant_of(26, FakeStore(), scope=CommandScope.SWITCH, pdi_store=pdi)

        assert occupant is not None
        assert occupant.mode.key == "sw_latching"
        assert occupant.ports == 4
        assert occupant.port_index == 2

    def test_the_component_state_is_carried_for_seeding(self):
        state = FakeState(1, "bpc2", mode="NA", num_ids=1)
        pdi = FakePdiStore({PdiDevice.BPC2: [FakeConfig(1, CommandScope.ACC, mode=2)]})

        occupant = occupant_of(1, FakeStore(acc=[state]), pdi_store=pdi)
        assert occupant.state is state

    def test_the_config_packet_itself_is_carried_for_seeding_too(self):
        # The settings a module is running with are in its CONFIG packet and nowhere else --
        # a BPC2's restore-on-power-up flag among them -- so the packet travels with the
        # occupant, on the port hit as much as on the base. The store's own entry is not
        # enough: it republishes the mode byte and has no flag to answer with.
        record = FakeConfig(1, CommandScope.ACC, mode=2, restore=True)
        pdi = FakePdiStore({PdiDevice.BPC2: [record]})

        assert occupant_of(1, FakeStore(), pdi_store=pdi).config is record.config
        assert occupant_of(5, FakeStore(), pdi_store=pdi).config is record.config
        assert occupant_of(1, FakeStore(), pdi_store=pdi).config.restore is True
        assert hasattr(record, "restore") is False

    def test_a_store_whose_entries_are_the_packets_is_read_as_it_stands(self):
        # Nothing nested to unwrap, so the entry is the packet: what a store standing in for
        # the real one is, and the shape the mode has always been read from either way.
        packet = FakePacket(mode=2, restore=True)
        packet.tmcc_id, packet.scope = 1, CommandScope.ACC
        pdi = FakePdiStore({PdiDevice.BPC2: [packet]})

        occupant = occupant_of(1, FakeStore(), pdi_store=pdi)
        assert occupant.config is packet
        assert occupant.mode.key == "acc_8"

    def test_a_module_only_the_states_know_has_no_config_record(self):
        # Nothing to invent one from: it was never reported over PDI.
        occupant = occupant_of(9, asc2_at_9())

        assert occupant.device is ASC2
        assert occupant.config is None

    def test_a_module_only_the_states_know_is_still_reported(self):
        # Control traffic identifies a module the PDI store never saw a CONFIG for.
        store = FakeStore(switch=[FakeState(1, "stm2", mode=0, num_ids=16)])
        pdi = FakePdiStore({PdiDevice.BPC2: [FakeConfig(1, CommandScope.ACC, mode=2)]})
        found = occupants_of(1, store, pdi_store=pdi)

        assert [o.device for o in found] == [BPC2, STM2]
        assert [o.ports for o in found] == [8, 16]

    def test_a_module_is_never_listed_twice(self):
        store, pdi = self.shared_acc_1()
        store._states[CommandScope.ACC].append(FakeState(1, "amc2", num_ids=1))

        assert [o.device for o in occupants(store, pdi_store=pdi)] == [BPC2, AMC2]

    def test_overlaps_use_the_true_block_too(self):
        store, pdi = self.shared_acc_1()

        # ACC 6 is inside the BPC2's real 1-8 block, and outside the record's claimed 1-1.
        assert [o.device for o in overlaps(6, 4, store, scope=CommandScope.ACC, pdi_store=pdi)] == [BPC2]
        assert overlaps(6, 4, store, scope=CommandScope.ACC) == []

    def test_an_empty_pdi_store_changes_nothing(self):
        assert occupant_of(9, asc2_at_9(), pdi_store=FakePdiStore({})).device is ASC2


class TestStoreDefault:
    def test_no_store_built_is_not_an_error(self, monkeypatch):
        monkeypatch.setattr(lcs_id_map, "_store", lambda store=None: None)
        monkeypatch.setattr(lcs_id_map, "_pdi_store", lambda pdi_store=None: None)
        assert occupants() == []
        assert occupant_of(1) is None
        assert overlaps(1, 8) == []

    def test_a_pdi_store_alone_is_enough(self, monkeypatch):
        # An embedded panel can be handed a component store; a process that only ever
        # registered PDI devices still knows what is out there.
        pdi = FakePdiStore({PdiDevice.STM2: [FakeConfig(1, CommandScope.SWITCH, mode=0)]})
        monkeypatch.setattr(lcs_id_map, "_store", lambda store=None: None)
        monkeypatch.setattr(lcs_id_map, "_pdi_store", lambda pdi_store=None: pdi)

        occupant = occupant_of(16)
        assert occupant is not None
        assert occupant.device is STM2
        assert occupant.ports == 16
        assert occupant.state is None

    def test_a_pdi_store_that_was_never_built_is_not_an_error(self, monkeypatch):
        from src.pytrain.pdi import pdi_state_store as pss

        monkeypatch.setattr(pss.PdiStateStore, "is_built", classmethod(lambda cls: False))
        assert lcs_id_map._pdi_store() is None
