#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from unittest.mock import Mock, PropertyMock, patch

import pytest

from src.pytrain.db.comp_data import RouteData
from src.pytrain.db.component_state import RouteState, SwitchState
from src.pytrain.db.components import RouteComponent
from src.pytrain.gui.controller.route_draft import RouteDraft
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import PdiCommand
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope


def make_route(tmcc_id, components=()):
    route = RouteState()
    route._address = tmcc_id
    route.initialize(CommandScope.ROUTE, tmcc_id)
    route.comp_data.components = list(components)
    route._is_known = True
    return route


def values(draft):
    return tuple((c.tmcc_id, c.flags) for c in draft.components)


class TestRouteDraft:
    @pytest.mark.parametrize("tmcc_id", [0, 100, -1, True, None, "7", 7.0])
    def test_invalid_route_ids(self, tmcc_id):
        with pytest.raises(ValueError, match="Route ID"):
            RouteDraft(tmcc_id)

    @pytest.mark.parametrize("tmcc_id", [1, 99])
    def test_route_id_boundaries(self, tmcc_id):
        draft = RouteDraft(tmcc_id)
        assert draft.tmcc_id == tmcc_id
        assert draft.components == ()
        assert not draft.dirty
        draft.validate({}.get)

    def test_draft_copies_input_and_component_snapshots(self):
        original = [RouteComponent(8, 0x81), RouteComponent(1, 0)]
        draft = RouteDraft(7, iter(original))
        assert isinstance(draft.components, tuple)
        assert values(draft) == ((8, 0x81), (1, 0))
        original[0].flags = 0
        original.clear()
        snapshot = draft.components
        snapshot[0].tmcc_id = 99
        snapshot[1].flags = 3
        assert values(draft) == ((8, 0x81), (1, 0))
        assert not draft.dirty

    def test_edit_remove_sort_and_dirty_tracking(self):
        draft = RouteDraft(7, [RouteComponent(8, 1)])
        draft.set_component(None, 1, 0, {}.get)
        assert values(draft) == ((8, 1), (1, 0))
        assert draft.dirty
        draft.remove(1)
        assert not draft.dirty
        draft.set_component(0, 8, 1, {}.get)
        assert not draft.dirty
        draft.set_component(0, 99, 0, {}.get)
        assert draft.dirty
        draft.mark_saved()
        assert not draft.dirty
        draft.remove(0)
        assert draft.dirty
        draft.mark_saved()
        assert not draft.dirty

    def test_limit_allows_replacement_and_removal_but_not_append(self):
        draft = RouteDraft(7, [RouteComponent(i, 0) for i in range(1, 17)])
        with pytest.raises(ValueError, match="16"):
            draft.set_component(None, 99, 1, {}.get)
        assert not draft.dirty
        assert len(draft.components) == 16
        draft.set_component(0, 99, 1, {}.get)
        assert values(draft)[0] == (99, 1)
        draft.remove(0)
        draft.set_component(None, 1, 1, {}.get)
        assert len(draft.components) == 16
        with pytest.raises(ValueError, match="16"):
            RouteDraft(7, [RouteComponent(1, 0)] * 17)

    @pytest.mark.parametrize("index", [-1, 1, True, "0", 0.0])
    def test_invalid_index_does_not_modify_draft(self, index):
        draft = RouteDraft(7, [RouteComponent(1, 0)])
        with pytest.raises(ValueError, match="Select"):
            draft.remove(index)
        with pytest.raises(ValueError, match="Select"):
            draft.set_component(index, 2, 1, {}.get)
        with pytest.raises(ValueError, match="Select"):
            draft.move(index, 1)
        assert values(draft) == ((1, 0),)
        assert not draft.dirty

    @pytest.mark.parametrize("tmcc_id, flags", [(0, 0), (100, 0), (True, 0), (1, -1), (1, 256), (1, 255), (1, None)])
    def test_invalid_component_does_not_modify_draft(self, tmcc_id, flags):
        draft = RouteDraft(7, [RouteComponent(1, 0)])
        with pytest.raises(ValueError):
            draft.set_component(0, tmcc_id, flags, {}.get)
        assert values(draft) == ((1, 0),)
        assert not draft.dirty

    @pytest.mark.parametrize("flags", [0x02, 0x06, 0x82, 0xFE])
    def test_stored_out_flags_survive_load_reselect_reorder_and_save(self, flags):
        raw = bytes([flags, 8, 0, 1]) + b"\xff" * 28
        state = make_route(7, RouteComponent.from_bytes(raw))
        before = state.comp_data.as_bytes()
        draft = RouteDraft(7, state.components)
        assert values(draft) == ((8, flags), (1, 0))
        assert not draft.dirty
        draft.set_component(0, 8, 1, {}.get)
        assert values(draft) == ((8, flags), (1, 0))
        assert not draft.dirty
        draft.move(0, 1)
        draft.set_metadata("Yard", "0007")
        with patch.object(BaseReq, "send") as send_base, patch.object(CommandReq, "send") as send_command:
            requests = draft.build_requests(state, {}.get)
        send_base.assert_not_called()
        send_command.assert_not_called()
        assert requests[2].data_bytes == bytes([0, 1, flags, 8]) + b"\xff" * 28
        reopened = RouteDraft(7, RouteComponent.from_bytes(requests[2].data_bytes))
        assert values(reopened) == ((1, 0), (8, flags))
        assert state.comp_data.as_bytes() == before

    def test_nested_route_with_stored_out_variant_can_be_validated_and_saved(self):
        nested = make_route(8, RouteComponent.from_bytes(b"\x02\x05" + b"\xff" * 30))
        draft = RouteDraft(7, [RouteComponent(8, 3)])
        request = draft.build_request(make_route(7), {8: nested}.get)
        assert request.data_bytes == b"\x03\x08" + b"\xff" * 30
        assert nested.components[0].flags == 2

    def test_switch_ids_do_not_require_lookup(self):
        lookup = Mock(side_effect=AssertionError("Switch lookup is not needed"))
        draft = RouteDraft(7)
        draft.set_component(None, 1, 0, lookup)
        draft.set_component(None, 99, 1, lookup)
        draft.validate(lookup)
        lookup.assert_not_called()

    def test_self_reference_is_rejected_without_lookup(self):
        draft = RouteDraft(7)
        lookup = Mock(side_effect=AssertionError("Self-reference needs no lookup"))
        with pytest.raises(ValueError, match="itself"):
            draft.set_component(None, 7, 3, lookup)
        assert draft.components == ()
        assert not draft.dirty
        lookup.assert_not_called()

    @pytest.mark.parametrize("back_reference", [7, 8])
    def test_indirect_and_existing_nested_cycles_are_rejected(self, back_reference):
        routes = {
            8: make_route(8, [RouteComponent(9, 3)]),
            9: make_route(9, [RouteComponent(back_reference, 3)]),
        }
        draft = RouteDraft(7)
        with pytest.raises(ValueError, match="itself|recursion"):
            draft.set_component(None, 8, 3, routes.get)
        assert draft.components == ()
        assert not draft.dirty

    @pytest.mark.parametrize("missing", ["absent", "unloaded", "initialized", "deleted"])
    def test_unverifiable_referenced_routes_are_rejected(self, missing):
        route = None if missing == "absent" else RouteState()
        if missing == "initialized":
            route.initialize(CommandScope.ROUTE, 8)
        elif missing == "deleted":
            route = make_route(8)
            route._deleted = True
        draft = RouteDraft(7, [RouteComponent(8, 3)])
        with pytest.raises(ValueError, match="Route 8.*loaded"):
            draft.validate({8: route}.get)

    def test_shared_subroutes_and_loaded_empty_route_are_valid(self):
        routes = {
            8: make_route(8, [RouteComponent(10, 3)]),
            9: make_route(9, [RouteComponent(10, 3)]),
            10: make_route(10, [RouteComponent(99, 0)]),
            99: make_route(99),
        }
        lookup = Mock(side_effect=routes.get)
        draft = RouteDraft(7, [RouteComponent(i, 3) for i in (8, 9, 99)])
        draft.validate(lookup)
        assert [call.args[0] for call in lookup.call_args_list] == [8, 10, 9, 99]

    def test_missing_deep_reference_is_rejected(self):
        draft = RouteDraft(7, [RouteComponent(8, 3)])
        with pytest.raises(ValueError, match="Route 9"):
            draft.validate({8: make_route(8, [RouteComponent(9, 3)])}.get)

    def test_build_request_revalidates_graph_after_edit(self):
        routes = {8: make_route(8)}
        draft = RouteDraft(7)
        draft.set_component(None, 8, 3, routes.get)
        routes[8].comp_data.components = [RouteComponent(7, 3)]
        with pytest.raises(ValueError, match="itself"):
            draft.build_request(make_route(7), routes.get)
        assert draft.dirty

    def test_build_request_preserves_live_state_metadata_and_flags_without_sending(self):
        state = make_route(7, [RouteComponent(1, 0x80), RouteComponent(8, 0x83)])
        state.comp_data.set_road_name_req("Yard Route")
        state.comp_data.set_road_number_req(1234)
        state.comp_data.prev_link = 6
        state.comp_data.next_link = 9
        draft = RouteDraft(7, state.components)
        draft.set_component(None, 99, 0x81, {8: make_route(8)}.get)
        before = state.comp_data.as_bytes()
        before_state = state.__dict__.copy()
        with (
            patch.object(BaseReq, "send") as send_base,
            patch.object(CommandReq, "send") as send_command,
            patch.object(RouteComponent, "as_request", new_callable=PropertyMock) as as_request,
        ):
            req = draft.build_request(state, {8: make_route(8)}.get)
        send_base.assert_not_called()
        send_command.assert_not_called()
        as_request.assert_not_called()
        assert isinstance(req, BaseReq)
        assert req.pdi_command == PdiCommand.BASE_MEMORY
        assert req.scope == CommandScope.ROUTE
        assert req.tmcc_id == 7
        assert req.flags == 0xC3
        assert req.start == 0x60
        assert req.data_length == 32
        assert req.data_bytes == b"\x80\x01\x83\x08\x81\x63" + b"\xff" * 26
        assert state.comp_data.as_bytes() == before
        assert state.__dict__ == before_state
        assert draft.dirty
        draft.mark_saved()
        assert not draft.dirty

    def test_cleared_request_and_uninitialized_target(self):
        state = RouteState()
        state._address = 7
        draft = RouteDraft(7, [RouteComponent(1, 0)])
        draft.remove(0)
        req = draft.build_request(state, {}.get)
        assert req.data_bytes == b"\xff" * 32
        assert req.start == 0x60
        assert state.comp_data is None

    @pytest.mark.parametrize("state", [None, SwitchState(), make_route(8)])
    def test_build_request_rejects_wrong_target(self, state):
        with pytest.raises(ValueError, match="route 7"):
            RouteDraft(7).build_request(state, {}.get)

    def test_saved_request_works_with_existing_refresh_contract(self):
        state = make_route(7)
        draft = RouteDraft(7, [RouteComponent(1, 0)])
        req = draft.build_request(state, {}.get)
        callback = Mock()
        with patch("src.pytrain.pdi.base3_db_refresh_manager.Base3DbRefreshManager.request_refresh") as refresh:
            assert BaseReq.process_sync_reqs([req, state], callback=callback)
        callback.assert_called_once_with(req)
        refresh.assert_called_once_with(state)

    def test_append_edit_and_move_keep_sequence_and_selected_index(self):
        draft = RouteDraft(7, [RouteComponent(8, 0x80), RouteComponent(2, 1)])
        draft.set_component(None, 1, 0, {}.get)
        draft.set_component(1, 99, 1, {}.get)
        assert values(draft) == ((8, 0x80), (99, 1), (1, 0))
        draft.mark_saved()
        assert draft.move(2, -1) == 1
        assert values(draft) == ((8, 0x80), (1, 0), (99, 1))
        assert draft.dirty
        assert draft.move(1, 1) == 2
        assert not draft.dirty
        assert draft.move(0, 100) == 2
        assert values(draft) == ((99, 1), (1, 0), (8, 0x80))
        assert draft.move(2, -100) == 0
        assert not draft.dirty

    def test_move_boundaries_and_clear_preserve_metadata(self):
        draft = RouteDraft(7, [RouteComponent(8, 0x81)], "Yard", "0007")
        for delta in (-1, 0, 1):
            assert draft.move(0, delta) == 0
            assert not draft.dirty
        draft.clear()
        assert draft.components == ()
        assert (draft.road_name, draft.road_number) == ("Yard", "0007")
        assert draft.dirty
        draft.mark_saved()
        draft.clear()
        assert not draft.dirty
        with pytest.raises(ValueError, match="Select"):
            draft.move(0, 1)

    @pytest.mark.parametrize("delta", [None, True, 1.0, "1"])
    def test_invalid_move_delta_is_atomic(self, delta):
        draft = RouteDraft(7, [RouteComponent(8, 0x80), RouteComponent(1, 1)])
        with pytest.raises(ValueError, match="integer"):
            draft.move(0, delta)
        assert values(draft) == ((8, 0x80), (1, 1))
        assert not draft.dirty

    @pytest.mark.parametrize("flags, mode", [(0x80, 1), (0xFD, 0), (0x7C, 1), (0x41, 0), (0x02, 0), (0xFE, 0)])
    def test_switch_mode_edit_preserves_all_other_flag_bits(self, flags, mode):
        draft = RouteDraft(7, [RouteComponent(8, flags)])
        draft.set_component(0, 8, mode, {}.get)
        assert values(draft) == ((8, (flags & ~0x03) | mode),)

    def test_metadata_and_components_share_dirty_baseline(self):
        draft = RouteDraft(7, road_name="Yard", road_number="0007")
        assert not draft.dirty
        draft.set_metadata("Main", "0007")
        assert draft.dirty
        draft.set_metadata("Yard", "0007")
        assert not draft.dirty
        draft.set_metadata("Yard", "99")
        draft.set_component(None, 8, 0, {}.get)
        draft.mark_saved()
        assert not draft.dirty
        draft.set_metadata("", "")
        draft.clear()
        assert draft.dirty
        draft.mark_saved()
        assert not draft.dirty

    @pytest.mark.parametrize(
        "road_name, road_number",
        [
            ("x" * 32, "1"),
            (None, "1"),
            ("Caf\u00e9", "1"),
            ("Yard", None),
            ("Yard", 7),
            ("Yard", "12345"),
            ("Yard", "-1"),
            ("Yard", "+1"),
            ("Yard", "1.0"),
            ("Yard", " 1"),
            ("Yard", "\u0661"),
            ("Yard", "\u00b2"),
        ],
    )
    def test_invalid_metadata_is_atomic(self, road_name, road_number):
        draft = RouteDraft(7, road_name="Original", road_number="0007")
        with pytest.raises(ValueError):
            draft.set_metadata(road_name, road_number)
        assert (draft.road_name, draft.road_number) == ("Original", "0007")
        assert not draft.dirty
        with pytest.raises(ValueError):
            RouteDraft(7, road_name=road_name, road_number=road_number)

    def test_unified_save_uses_metadata_apis_without_sending_or_live_mutation(self):
        state = make_route(7, [RouteComponent(8, 0x80), RouteComponent(1, 1)])
        state.comp_data.set_road_name_req("Original")
        state.comp_data.set_road_number_req(1234)
        state.comp_data.prev_link = 3
        state.comp_data.next_link = 8
        before = state.comp_data.as_bytes()
        before_state = state.__dict__.copy()
        draft = RouteDraft(7, state.components, state.comp_data.road_name, state.comp_data.road_number)
        draft.set_metadata("x" * 31, "7")
        draft.move(0, 1)
        metadata = RouteData(None, 7)
        expected = [metadata.set_road_name_req("x" * 31), metadata.set_road_number_req(7)]
        with (
            patch.object(BaseReq, "send") as send_base,
            patch.object(CommandReq, "send") as send_command,
            patch.object(RouteComponent, "as_request", new_callable=PropertyMock) as as_request,
            patch.object(BaseReq, "process_sync_reqs") as sync,
        ):
            requests = draft.build_requests(state, {}.get)
        send_base.assert_not_called()
        send_command.assert_not_called()
        as_request.assert_not_called()
        sync.assert_not_called()
        assert isinstance(requests, list)
        assert len(requests) == 3
        assert [req.as_bytes for req in requests[:2]] == [req.as_bytes for req in expected]
        assert [req.start for req in requests] == [0x04, 0x24, 0x60]
        assert requests[2].data_bytes == b"\x01\x01\x80\x08" + b"\xff" * 28
        assert all(isinstance(req, BaseReq) and req.pdi_command == PdiCommand.BASE_MEMORY for req in requests)
        assert all(req.tmcc_id == 7 and req.scope == CommandScope.ROUTE and req.flags == 0xC3 for req in requests)
        assert state.comp_data.as_bytes() == before
        assert state.__dict__ == before_state
        assert draft.dirty
        draft.mark_saved()
        assert not draft.dirty

    def test_unified_save_works_with_existing_refresh_contract(self):
        state = make_route(7)
        draft = RouteDraft(7, road_name="Yard", road_number="1234")
        requests = draft.build_requests(state, {}.get)
        callback = Mock()
        with patch("src.pytrain.pdi.base3_db_refresh_manager.Base3DbRefreshManager.request_refresh") as refresh:
            assert BaseReq.process_sync_reqs([*requests, state], callback=callback)
        assert [call.args[0] for call in callback.call_args_list] == requests
        refresh.assert_called_once_with(state)

    @pytest.mark.parametrize("initialized", [False, True])
    @pytest.mark.parametrize(
        "road_number, expected", [("", b"\x00" + b"\xff" * 4), ("0000", b"\x00" + b"\xff" * 4), ("9999", b"\x049999")]
    )
    def test_empty_route_saves_with_provisional_or_unloaded_state(self, initialized, road_number, expected):
        state = RouteState()
        state._address = 7
        if initialized:
            state.initialize(CommandScope.ROUTE, 7)
        original_data = state.comp_data
        before = original_data.as_bytes() if original_data else None
        draft = RouteDraft(7, road_number=road_number)
        requests = draft.build_requests(state, {}.get)
        assert len(requests) == 3
        assert requests[0].data_bytes == b"\x00" + b"\xff" * 31
        assert requests[1].data_bytes == expected
        assert requests[2].data_bytes == b"\xff" * 32
        assert state.comp_data is original_data
        assert (state.comp_data.as_bytes() if state.comp_data else None) == before
        assert not draft.dirty

    def test_unified_save_graph_and_encoding_errors_leave_live_state_unchanged(self):
        state = make_route(7, [RouteComponent(1, 0)])
        before = state.comp_data.as_bytes()
        routes = {8: make_route(8)}
        draft = RouteDraft(7, state.components)
        draft.set_component(None, 8, 3, routes.get)
        draft.set_metadata("Changed", "1234")
        routes[8].comp_data.components = [RouteComponent(7, 3)]
        with pytest.raises(ValueError, match="itself"):
            draft.build_requests(state, routes.get)
        routes[8].comp_data.components = []
        with patch.object(RouteData, "set_road_number_req", side_effect=ValueError("Cannot encode")):
            with pytest.raises(ValueError, match="Cannot encode"):
                draft.build_requests(state, routes.get)
        assert state.comp_data.as_bytes() == before
        assert draft.dirty
        assert values(draft) == ((1, 0), (8, 3))
        assert (draft.road_name, draft.road_number) == ("Changed", "1234")

    @pytest.mark.parametrize("state", [None, SwitchState(), make_route(8)])
    def test_unified_save_rejects_wrong_target(self, state):
        with pytest.raises(ValueError, match="route 7"):
            RouteDraft(7).build_requests(state, {}.get)

    def test_deleted_target_rejects_both_save_apis(self):
        state = make_route(7)
        state._deleted = True
        draft = RouteDraft(7)
        with pytest.raises(ValueError, match="route 7"):
            draft.build_request(state, {}.get)
        with pytest.raises(ValueError, match="route 7"):
            draft.build_requests(state, {}.get)

    def test_cancel_by_discarding_draft_leaves_live_metadata_and_components_unchanged(self):
        state = make_route(7, [RouteComponent(8, 0x81), RouteComponent(1, 0)])
        state.comp_data.set_road_name_req("Original")
        state.comp_data.set_road_number_req(7)
        before = state.comp_data.as_bytes()
        draft = RouteDraft(7, state.components, state.comp_data.road_name, state.comp_data.road_number)
        draft.set_metadata("Changed", "9999")
        draft.move(0, 1)
        draft.set_component(0, 99, 1, {}.get)
        draft.clear()
        del draft
        assert state.comp_data.as_bytes() == before
        reopened = RouteDraft(7, state.components, state.comp_data.road_name, state.comp_data.road_number)
        assert values(reopened) == ((8, 0x81), (1, 0))
        assert (reopened.road_name, reopened.road_number) == ("Original", "0007")
        assert not reopened.dirty
