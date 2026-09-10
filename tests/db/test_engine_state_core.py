#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
"""
Characterization tests for `EngineState` and `TrainState`.

`test_engine_state.py` covers speed-ramp arbitration; this module covers everything
else: the derived properties an operator sees, the command handling branches of
`_update_state` that are not throttle related, and the serialization helpers. The
assertions record what these classes do *today*, so that a later correction to any
of them is a deliberate, visible change rather than a silent one.
"""

import pytest

from src.pytrain import CommandScope, TMCC2EffectsControl
from src.pytrain.comm.comm_buffer import CommBuffer
from src.pytrain.db.comp_data import CompData, CompDataMixin
from src.pytrain.db.component_state import UpdateResult
from src.pytrain.db.component_state_store import ComponentStateStore
from src.pytrain.db.components import ConsistComponent
from src.pytrain.db.engine_state import EngineState, TrainState
from src.pytrain.db.prod_info import ProdInfo
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import D4Action, IrdaAction, PdiCommand
from src.pytrain.pdi.d4_req import D4Req
from src.pytrain.pdi.irda_req import IrdaReq
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import (
    CAB1_CONTROL_TYPE,
    CommandSyntax,
    EngineType,
    LEGACY_CONTROL_TYPE,
    TMCC_CONTROL_TYPE,
)
from src.pytrain.protocol.multibyte.multibyte_constants import (
    TMCC2EngineCommandEnumEx,
    TMCC2R4LCEnum,
    UnitAssignment,
)
from src.pytrain.protocol.tmcc1.tmcc1_constants import (
    TMCC1EngineCommandEnum as TMCC1,
    TMCC1HaltCommandEnum,
    TMCC1RRSpeedsEnum,
)
from src.pytrain.protocol.tmcc2.tmcc2_constants import TMCC2EngineCommandEnum as TMCC2, TMCC2RRSpeedsEnum


@pytest.fixture(autouse=True)
def pin_process_globals(monkeypatch):
    """
    Keep an update from asking the Base 3 for a configuration record; see the fixture
    of the same name in `test_engine_state.py` for why both of these are pinned.
    """
    monkeypatch.setattr(CommBuffer, "is_server", staticmethod(lambda: False))
    monkeypatch.setattr(ComponentStateStore, "is_state_synchronized", classmethod(lambda _cls: False))


def new_engine(addr: int = 7, *, legacy: bool = False) -> EngineState:
    state = EngineState(CommandScope.ENGINE)
    state.initialize(CommandScope.ENGINE, addr)
    state._address = addr
    # a record has arrived: without this, an update sends _prepare_update down its
    # never-heard-from path, which re-initializes comp_data underneath the test
    state._empty = False
    if legacy:
        state.comp_data._control_type = LEGACY_CONTROL_TYPE
        state._is_legacy = True
    return state


def new_train(addr: int = 101) -> TrainState:
    state = TrainState(CommandScope.TRAIN)
    state.initialize(CommandScope.TRAIN, addr)
    state._address = addr
    state._empty = False
    return state


class _CompDataRecord(CompDataMixin):
    """A stand-in for the BaseReq / D4Req comp_data record the Base 3 pushes back."""

    def __init__(self, comp_data) -> None:
        super().__init__()
        self._comp_data = comp_data
        self._comp_data_record = True


class TestEngineStateConstruction:
    def test_engine_state_accepts_engine_and_train_scopes(self):
        assert EngineState(CommandScope.ENGINE).scope == CommandScope.ENGINE
        assert EngineState(CommandScope.TRAIN).scope == CommandScope.TRAIN

    @pytest.mark.parametrize("scope", [CommandScope.ACC, CommandScope.SWITCH, CommandScope.ROUTE])
    def test_engine_state_rejects_other_scopes(self, scope):
        with pytest.raises(ValueError, match="expected ENGINE or TRAIN"):
            EngineState(scope)

    def test_a_fresh_engine_reports_nothing_known(self):
        state = new_engine()

        assert state.direction is None
        assert state.direction_label == "--"
        assert state.numeric is None
        assert state.stop_start is None
        assert state.is_started is False
        assert state.is_shutdown is False
        assert state.year is None
        assert state.record_no is None
        assert state.record_no_label == ""
        assert state.is_lcs is False
        assert state.ramp is None
        assert state.is_ramping is False

    def test_default_comp_data_values_drive_the_derived_properties(self):
        # the defaults `initialize` installs are what an engine looks like before its
        # Base 3 record arrives, and most of the properties below are read from them
        state = new_engine()

        assert state.speed == 0
        assert state.target_speed == 0
        assert state.momentum == 0
        assert state.rpm == 0
        assert state.labor == 12
        assert state.train_brake == 0
        assert state.speed_limit == 255
        assert state.max_speed == 255
        assert state.smoke_level is None
        assert state.train_tmcc_id is None
        assert state.train_unit is None
        assert state.bt_id is None
        assert state.engine_type == 255
        assert state.engine_type_label == "NA"
        assert state.control_type == 255
        assert state.control_type_label == "NA"
        assert state.sound_type_label == "NA"
        # 255 is a named entry in the Lionel class table rather than a missing value
        assert state.engine_class_label == "Universal"


class TestEngineStateWithoutARecord:
    """
    A state exists as soon as a command names its address, which can be long before the
    Base 3 sends its record. Every property has to answer from something in that window,
    and the whole export path has to survive it: these all used to raise `AttributeError`
    on the record they assumed was there, while `speed` and the engine type flags beside
    them guarded for it.
    """

    @staticmethod
    def bare_engine(addr: int = 7) -> EngineState:
        state = EngineState(CommandScope.ENGINE)
        state._address = addr
        return state

    @pytest.mark.parametrize(
        "prop",
        [
            "bt_id",
            "bt_int",
            "control_type",
            "engine_class",
            "engine_type",
            "fuel_level",
            "fuel_level_pct",
            "labor",
            "max_speed",
            "momentum",
            "rr_speed",
            "smoke_level",
            "soft_status",
            "sound_type",
            "speed",
            "speed_limit",
            "target_speed",
            "train_brake",
            "train_tmcc_id",
            "train_unit",
            "water_level",
            "water_level_pct",
        ],
    )
    def test_a_property_with_nothing_to_report_answers_nothing(self, prop):
        assert getattr(self.bare_engine(), prop) is None

    @pytest.mark.parametrize(
        "prop",
        [
            "has_lights",
            "has_throttle",
            "is_acela",
            "is_crane",
            "is_diesel",
            "is_electric",
            "is_freight",
            "is_passenger",
            "is_rpm",
            "is_steam",
            "is_transformer",
        ],
    )
    def test_a_capability_flag_with_nothing_to_report_is_not_claimed(self, prop):
        # `False`, not merely falsy: these guards were once written as `self.comp_data and
        # ...`, which answers None against a `-> bool` annotation, so a client saw null
        # both for "this engine has no smoke unit" and for "we have not heard yet"
        assert getattr(self.bare_engine(), prop) is False

    def test_is_cab1_on_empty_record_answers_false(self):
        assert self.bare_engine().is_cab1 is False

    def test_the_labels_of_an_engine_with_no_record_read_not_available(self):
        state = self.bare_engine()

        assert state.control_type_label == "NA"
        assert state.control_type_text == "NA"
        assert state.engine_type_label == "NA"
        assert state.engine_class_label == "NA"
        assert state.sound_type_label == "NA"
        assert state.momentum_label == "NA"
        assert state.momentum_text == "NA"
        assert state.labor_label == "NA"
        assert state.train_brake_label == "NA"
        assert state.fuel_level_label == "NA"
        assert state.water_level_label == "NA"
        assert state.rpm_label == "NA"
        assert state.smoke_text == ""

    def test_an_engine_with_no_record_can_still_be_exported(self, monkeypatch):
        # the symptom of the unguarded properties: any client update or CSV export of an
        # engine that had heard nothing from the Base threw rather than reporting nothing
        monkeypatch.setattr(ProdInfo, "is_capable", staticmethod(lambda: False))
        state = self.bare_engine()

        d = state.as_dict()
        assert d["tmcc_id"] == 7
        assert d["scope"] == "engine"
        assert d["speed"] is None
        assert d["control"] is None
        assert d["engine_type"] is None

        row = state.as_csv(include_state=True)
        assert row["address"] == 7
        assert row["control"] == "NA"
        assert row["speed"] is None

        # the replay packets carry no record, only what the state itself holds
        assert all(isinstance(packet, bytes) for packet in state.as_bytes())

    def test_a_train_with_no_record_reports_no_consist(self):
        train = TrainState(CommandScope.TRAIN)
        train._address = 21

        assert train.consist_flags is None
        assert train.consist_components is None

        d = train.as_dict()
        assert d["flags"] is None
        assert d["components"] == {}


class TestEngineStateProtocolFlavor:
    def test_a_short_address_without_a_control_type_is_tmcc(self):
        state = new_engine(addr=7)

        assert state.is_legacy is False
        assert state.is_tmcc is True
        assert state.syntax is CommandSyntax.TMCC

    def test_a_four_digit_address_is_always_legacy(self):
        state = new_engine(addr=1234)

        assert state.is_legacy is True
        assert state.syntax is CommandSyntax.LEGACY

    @pytest.mark.parametrize(
        "control_type, is_legacy, is_cab1",
        [(LEGACY_CONTROL_TYPE, True, False), (TMCC_CONTROL_TYPE, False, False), (CAB1_CONTROL_TYPE, False, True)],
    )
    def test_the_control_type_decides_the_flavor_of_a_short_address(self, control_type, is_legacy, is_cab1):
        state = new_engine(addr=7)
        state.comp_data._control_type = control_type

        assert state.is_legacy is is_legacy
        assert state.is_cab1 is is_cab1

    def test_is_tmcc_is_the_negation_of_is_legacy(self):
        # both answer from one source of truth: an engine that has sent a Legacy command
        # but whose record has not arrived used to answer yes to both, and every
        # flavor-sensitive branch below it could then take contradictory paths
        state = new_engine(addr=7)
        state._is_legacy = True

        assert state.control_type == 255  # the record says nothing
        assert state.is_legacy is True
        assert state.is_tmcc is False

        state._is_legacy = False

        assert state.is_legacy is False
        assert state.is_tmcc is True

    def test_control_type_text_marks_a_four_digit_engine(self):
        state = new_engine(addr=1234, legacy=True)

        assert state.control_type_text == "Legacy"
        state._is_d4 = True
        assert state.control_type_text == "Legacy 4D"

    def test_control_type_text_leaves_an_unknown_control_type_alone(self):
        state = new_engine()
        state._is_d4 = True

        assert state.control_type_text == "NA"


class TestEngineStateSpeedProperties:
    def test_speed_is_scaled_for_a_tmcc_engine(self):
        state = new_engine()
        state.comp_data._speed = 199

        # a TMCC engine's record still stores speed on the 0-199 Legacy scale
        assert state.speed == 31

    def test_speed_is_reported_verbatim_for_a_legacy_engine(self):
        state = new_engine(legacy=True)
        state.comp_data._speed = 120

        assert state.speed == 120

    def test_speed_is_none_without_a_record(self):
        state = EngineState(CommandScope.ENGINE)
        state._address = 7

        assert state.speed is None

    @pytest.mark.parametrize(
        "legacy, max_speed, speed_limit, expected",
        [
            (True, 255, 255, 199),  # neither set: the Legacy ceiling
            (False, 255, 255, 31),  # neither set: the TMCC ceiling
            (True, 120, 255, 120),  # only max speed
            (True, 255, 100, 100),  # only speed limit
            (True, 120, 100, 100),  # both: the lower one wins
            (False, 199, 199, 31),  # a TMCC engine is capped at 31 whatever the record says
        ],
    )
    def test_speed_max_resolves_the_limits(self, legacy, max_speed, speed_limit, expected):
        state = new_engine(legacy=legacy)
        state.comp_data._max_speed = max_speed
        state.comp_data._speed_limit = speed_limit

        assert state.speed_max == expected

    def test_speeds_reports_the_quartet_the_ui_draws(self):
        state = new_engine(legacy=True)
        state.comp_data._speed = 60
        state.comp_data._target_speed = 80
        state.comp_data._speed_limit = 255
        state.comp_data._max_speed = 255

        assert state.speeds == (60, 80, None, 199)

        state.comp_data._speed_limit = 100
        state.comp_data._max_speed = 150
        assert state.speeds == (60, 80, 100, 150)

    def test_decode_speed_info_expands_the_never_set_sentinel(self):
        # the sentinel expands to the ceiling of the engine's own scale, and to the same
        # ceiling `speed_max` reports: the Legacy arm used to answer 195 against its 199,
        # so the same engine logged a limit its own display contradicted
        state = new_engine()

        assert state.decode_speed_info(255) == 31
        assert state.decode_speed_info(30) == 30
        assert state.decode_speed_info(255) == state.speed_max

        state.comp_data._control_type = LEGACY_CONTROL_TYPE
        assert state.decode_speed_info(255) == 199
        assert state.decode_speed_info(255) == state.speed_max

    def test_rr_speed_names_the_railroad_speed_band(self):
        state = new_engine(legacy=True)
        state.comp_data._speed = 0

        assert state.rr_speed.name == "STOP_HOLD"

        state.comp_data._speed = 145
        assert state.rr_speed.name == "NORMAL"

    #
    # a railroad speed names a band of speed steps, and an engine is running at that
    # railroad speed anywhere inside the band; the band used to be resolved from its
    # first step alone, so the speed limit panel read blank at every step but the eight
    # band starts
    #
    @pytest.mark.parametrize(
        "legacy, command, speeds",
        [
            (True, TMCC2.ABSOLUTE_SPEED, TMCC2RRSpeedsEnum),
            (False, TMCC1.ABSOLUTE_SPEED, TMCC1RRSpeedsEnum),
        ],
    )
    def test_every_speed_step_of_a_band_reports_that_band(self, legacy, command, speeds):
        state = new_engine(legacy=legacy)

        for band in speeds:
            for step in band.value:
                state.update(CommandReq.build(command, state.address, data=step))

                assert state.speed == step
                assert state.rr_speed is band

    def test_update_target_speed_follows_the_speed_when_not_ramping(self):
        state = new_engine(legacy=True)
        state.comp_data._speed = 45

        state.update_target_speed()

        assert state.target_speed == 45
        assert state.is_ramping is False

    def test_update_target_speed_with_a_target_arms_the_ramping_flag(self):
        state = new_engine(legacy=True)
        state.comp_data._speed = 45

        state.update_target_speed(target_speed=90)

        assert state.target_speed == 90
        assert state.is_ramping is True

    def test_a_target_equal_to_the_speed_disarms_the_ramping_flag(self):
        state = new_engine(legacy=True)
        state.comp_data._speed = 45

        state.update_target_speed(target_speed=45)

        assert state.is_ramping is False

    def test_a_ramp_that_arrived_is_wound_up_on_the_next_speedless_update(self):
        state = new_engine(legacy=True)
        state.comp_data._speed = 45
        state.update_target_speed(target_speed=90)
        state.comp_data._speed = 90

        state.update_target_speed()

        assert state.is_ramping is False
        assert state.target_speed == 90

    def test_a_ramp_still_under_way_keeps_its_target(self):
        state = new_engine(legacy=True)
        state.comp_data._speed = 45
        state.update_target_speed(target_speed=90)

        state.update_target_speed()

        assert state.is_ramping is True
        assert state.target_speed == 90

    def test_a_speed_written_before_the_record_arrives_is_read_back_unchanged(self):
        # a 4-digit engine is Legacy by its address alone, so the codec has to answer
        # from the state rather than from a record that carries no control type yet:
        # answering from the record scaled the speed down on the way back out
        state = new_engine(addr=1234)

        state.update(CommandReq.build(TMCC2.ABSOLUTE_SPEED, state.address, data=75))

        assert state.comp_data.is_legacy is False  # the record still says nothing
        assert state.comp_data._speed == 75
        assert state.speed == 75
        assert state.target_speed == 75

    def test_sync_target_speed_ignores_a_missing_target_or_record(self):
        state = new_engine(legacy=True)
        state.comp_data._target_speed = 40

        state.sync_target_speed(None)
        assert state.target_speed == 40

        bare = EngineState(CommandScope.ENGINE)
        bare._address = 7
        bare.sync_target_speed(20)  # no record to write to; must not raise


class TestEngineStateDerivedProperties:
    def test_fuel_and_water_are_reported_as_percentages(self):
        state = new_engine()
        state.comp_data._fuel_level = 255
        state.comp_data._water_level = 128

        assert state.fuel_level == 255
        assert state.fuel_level_pct == 100
        assert state.water_level == 128
        assert state.water_level_pct == 50
        assert state.fuel_level_label == "255"
        assert state.water_level_label == "128"

    def test_a_missing_level_stays_missing(self):
        state = new_engine()
        state.comp_data._fuel_level = None
        state.comp_data._water_level = None

        assert state.fuel_level_pct is None
        assert state.water_level_pct is None
        assert state.fuel_level_label == "NA"

    @pytest.mark.parametrize(
        "raw, momentum, text",
        [(0, 0, "Low"), (127, 7, "High"), (63, 3, "Med 3")],
    )
    def test_momentum_is_converted_to_the_tmcc_scale(self, raw, momentum, text):
        state = new_engine()
        state.comp_data._momentum = raw

        assert state.momentum == momentum
        assert state.momentum_label == str(momentum)
        assert state.momentum_text == text

    def test_train_brake_is_converted_to_the_tmcc_scale(self):
        state = new_engine()
        state.comp_data._train_brake = 15

        assert state.train_brake == 7
        assert state.train_brake_label == "7"

    def test_rpm_and_labor_share_a_single_byte(self):
        state = new_engine()
        state.comp_data._engine_type = 0  # diesel, so RPM is meaningful
        state.comp_data._rpm_labor = CompData.encode_rpm_labor(rpm=5, labor=14)

        assert state.is_rpm is True
        assert state.rpm == 5
        assert state.rpm_label == "5"
        assert state.labor == 14
        assert state.labor_label == "14"

    def test_a_non_rpm_engine_reports_no_rpm(self):
        state = new_engine()
        state.comp_data._engine_type = 1  # steam
        state.comp_data._rpm_labor = CompData.encode_rpm_labor(rpm=5, labor=14)

        assert state.is_rpm is False
        assert state.rpm == 0
        assert state.rpm_label == "NA"
        # labor is still read straight from the record
        assert state.labor == 14

    @pytest.mark.parametrize(
        "engine_type, expected",
        [
            (0, {"is_diesel", "is_rpm", "has_throttle", "has_lights"}),
            (1, {"is_steam", "has_throttle", "has_lights"}),
            (2, {"is_electric", "has_throttle", "has_lights"}),
            (5, {"is_passenger"}),
            (8, {"is_electric", "is_acela", "has_throttle", "has_lights"}),
            (9, {"is_crane", "has_throttle"}),
            (12, {"is_freight"}),
            (15, {"is_transformer", "has_throttle"}),
        ],
    )
    def test_the_engine_type_decides_the_capability_flags(self, engine_type, expected):
        state = new_engine()
        state.comp_data._engine_type = engine_type
        flags = {
            "is_rpm",
            "is_steam",
            "is_electric",
            "is_diesel",
            "is_crane",
            "is_passenger",
            "is_freight",
            "is_transformer",
            "is_acela",
            "has_throttle",
            "has_lights",
        }

        assert {flag for flag in flags if getattr(state, flag)} == expected

    def test_the_type_labels_come_from_the_lionel_tables(self):
        state = new_engine()
        state.comp_data._engine_type = 1
        state.comp_data._engine_class = 1
        state.comp_data._sound_type = 1
        state.comp_data._control_type = LEGACY_CONTROL_TYPE

        assert state.engine_type_label == "Steam"
        assert state.engine_type_enum is EngineType.STEAM
        assert state.engine_class_label == "Switcher"
        assert state.sound_type_label == "RailSounds"
        assert state.control_type_label == "Legacy"

    def test_the_bluetooth_id_is_rendered_as_hex(self):
        state = new_engine()
        state.comp_data._bt_id = 0xABCD

        assert state.bt_int == 0xABCD
        assert state.bt_id == "ABCD"

    def test_an_unset_bluetooth_id_is_none(self):
        state = new_engine()
        state.comp_data._bt_id = 0xFFFF

        assert state.bt_id is None

    @pytest.mark.parametrize(
        "smoke, label, text",
        [
            (TMCC2EffectsControl.SMOKE_OFF, "-", "Off"),
            (TMCC2EffectsControl.SMOKE_LOW, "L", "Low"),
            (TMCC2EffectsControl.SMOKE_MEDIUM, "M", "Med"),
            (TMCC2EffectsControl.SMOKE_HIGH, "H", "High"),
        ],
    )
    def test_the_smoke_level_carries_a_label_and_a_caption(self, smoke, label, text):
        state = new_engine(legacy=True)
        state.comp_data.smoke_tmcc = smoke

        assert state.smoke_level is smoke
        assert state.smoke_label == label
        assert state.smoke_text == text

    @pytest.mark.parametrize("smoke", [1, 2, 3])
    def test_a_tmcc_engine_reports_any_smoke_level_as_on(self, smoke):
        # the record holds one Base 3 level whatever syntax wrote it, so a TMCC engine can
        # hold a level its own two word vocabulary cannot name; every level above off is
        # on, where the map back to a TMCC command answered off for medium and high
        state = new_engine()
        state.comp_data._smoke = smoke

        assert state.smoke_level is TMCC1.SMOKE_ON
        assert state.smoke_label == "+"

    def test_a_tmcc_engine_reports_the_base_level_of_zero_as_off(self):
        state = new_engine()
        state.comp_data._smoke = 0

        assert state.smoke_level is TMCC1.SMOKE_OFF
        assert state.smoke_label == "-"

    def test_an_unreported_smoke_level_has_no_caption(self):
        state = new_engine(legacy=True)
        state.comp_data._smoke = 255

        assert state.smoke_level is None
        assert state.smoke_label is None
        assert state.smoke_text == ""

    def test_the_train_assignment_is_read_from_the_record(self):
        state = new_engine()
        state.comp_data._train_tmcc_id = 12
        state.comp_data._train_unit = int(UnitAssignment.HEAD_FORWARD)

        assert state.train_tmcc_id == 12
        assert state.train_unit is UnitAssignment.HEAD_FORWARD

    def test_an_unassigned_engine_belongs_to_no_train(self):
        state = new_engine()
        state.comp_data._train_tmcc_id = 255
        state.comp_data._train_unit = 255

        assert state.train_tmcc_id is None
        assert state.train_unit is None

    def test_soft_status_is_passed_through(self):
        state = new_engine()
        state.comp_data._soft_status = 3

        assert state.soft_status == 3


class TestEngineStateDirectionAndAux:
    @pytest.mark.parametrize(
        "direction, is_forward, is_reverse, label",
        [
            (TMCC1.FORWARD_DIRECTION, True, False, "FW"),
            (TMCC2.FORWARD_DIRECTION, True, False, "FW"),
            (TMCC1.REVERSE_DIRECTION, False, True, "RV"),
            (TMCC2.REVERSE_DIRECTION, False, True, "RV"),
            (None, False, False, "--"),
        ],
    )
    def test_direction_flags_follow_the_recorded_direction(self, direction, is_forward, is_reverse, label):
        state = new_engine()
        state._direction = direction

        assert state.is_forward is is_forward
        assert state.is_reverse is is_reverse
        assert state.direction_label == label

    def test_a_toggle_without_a_known_direction_yields_nothing(self):
        state = new_engine(legacy=True)

        assert state._change_direction(TMCC2.TOGGLE_DIRECTION) is TMCC2.TOGGLE_DIRECTION

    def test_a_toggle_against_the_other_syntax_yields_nothing(self):
        state = new_engine(legacy=True)
        state._direction = TMCC1.FORWARD_DIRECTION

        assert state._change_direction(TMCC2.TOGGLE_DIRECTION) is None

    def test_an_explicit_direction_passes_through_change_direction(self):
        state = new_engine(legacy=True)
        state._direction = TMCC2.FORWARD_DIRECTION

        assert state._change_direction(TMCC2.REVERSE_DIRECTION) is TMCC2.REVERSE_DIRECTION

    def test_aux1_option_one_is_what_aux_on_means(self):
        state = new_engine()

        assert state.is_aux_on is False
        assert state.is_aux_off is True

        state.update(CommandReq.build(TMCC1.AUX1_OPTION_ONE, state.address))

        assert state.aux1 is TMCC1.AUX1_OPTION_ONE
        assert state.is_aux_on is True
        assert state.is_aux_off is False

    def test_aux2_option_one_alternates_the_aux2_state(self):
        state = new_engine()

        state.update(CommandReq.build(TMCC1.AUX2_OPTION_ONE, state.address))
        assert state.aux2 is TMCC1.AUX2_ON
        assert state.is_aux2 is True

        # the second press is inside the one second window the alternation is guarded by
        state._last_command = None
        state.update(CommandReq.build(TMCC1.AUX2_OPTION_ONE, state.address))
        assert state.aux2 is TMCC1.AUX2_ON

    def test_an_explicit_aux2_command_is_recorded_as_sent(self):
        state = new_engine()

        state.update(CommandReq.build(TMCC1.AUX2_OFF, state.address))

        assert state.aux2 is TMCC1.AUX2_OFF
        assert state.is_aux2 is False

    def test_is_aux1_is_answered_from_the_aux1_setting(self):
        state = new_engine()

        state.update(CommandReq.build(TMCC1.AUX1_ON, state.address))

        assert state.aux1 is TMCC1.AUX1_ON
        assert state.is_aux1 is True

    #
    # the first record an engine sends is where its direction comes from: nothing in
    # the command stream tells us which way an engine already sitting on the layout is
    # facing, so bit zero of the record's soft status is the only sighting of it
    #
    @pytest.mark.parametrize("soft_status, direction", [(0, TMCC1.FORWARD_DIRECTION), (1, TMCC1.REVERSE_DIRECTION)])
    def test_a_first_record_initializes_the_direction(self, soft_status, direction):
        state = new_engine()
        state.comp_data._soft_status = soft_status

        state._update_state(_CompDataRecord(state.comp_data))

        assert state.direction is direction

    @pytest.mark.parametrize("soft_status, direction", [(0, TMCC2.FORWARD_DIRECTION), (1, TMCC2.REVERSE_DIRECTION)])
    def test_a_legacy_engine_initializes_its_direction_in_its_own_syntax(self, soft_status, direction):
        state = new_engine(legacy=True)
        state.comp_data._soft_status = soft_status

        state._update_state(_CompDataRecord(state.comp_data))

        assert state.direction is direction

    def test_a_record_that_never_reached_the_soft_status_leaves_the_direction_unknown(self):
        # a truncated record decodes no soft status at all: the direction stays unknown
        # rather than being reported as forward, and the update must still go through
        state = new_engine()
        state.comp_data._soft_status = None

        state._update_state(_CompDataRecord(state.comp_data))

        assert state.direction is None

    def test_only_the_first_record_initializes_the_direction(self):
        state = new_engine()
        state.comp_data._soft_status = 0
        state._update_state(_CompDataRecord(state.comp_data))

        state.comp_data._soft_status = 1
        state._update_state(_CompDataRecord(state.comp_data))

        # after the first record the command stream is the authority on direction, so a
        # later record cannot reach back and overwrite it
        assert state.direction is TMCC1.FORWARD_DIRECTION

    def test_a_direction_command_is_not_overruled_by_a_later_first_record(self):
        # the byte is the Base's account of an engine nobody was listening to, so it is
        # only worth reading while we know nothing: a record arriving after the operator
        # had already reversed the engine used to turn it around again
        state = new_engine()
        state.update(CommandReq.build(TMCC1.REVERSE_DIRECTION, state.address))
        state.comp_data._soft_status = 0  # the Base says forward

        state._update_state(_CompDataRecord(state.comp_data))

        assert state.direction is TMCC1.REVERSE_DIRECTION


class TestEngineStateCommandHandling:
    def test_a_numeric_command_is_remembered(self):
        state = new_engine()

        state.update(CommandReq.build(TMCC1.NUMERIC, state.address, data=3))

        assert state.numeric == 3
        assert state._numeric_cmd is TMCC1.NUMERIC

    def test_a_tmcc1_aux1_prefixed_numeric_becomes_a_startup(self):
        state = new_engine()
        state.update(CommandReq.build(TMCC1.AUX1_OPTION_ONE, state.address))

        state.update(CommandReq.build(TMCC1.NUMERIC, state.address, data=3))

        assert state.stop_start is TMCC1.START_UP_IMMEDIATE
        assert state.is_started is True
        assert state.is_shutdown is False

    def test_a_tmcc1_aux1_prefixed_five_becomes_a_shutdown(self):
        state = new_engine()
        state.update(CommandReq.build(TMCC1.AUX1_OPTION_ONE, state.address))

        state.update(CommandReq.build(TMCC1.NUMERIC, state.address, data=5))

        assert state.stop_start is TMCC1.SHUTDOWN_IMMEDIATE
        assert state.is_shutdown is True

    def test_startup_and_shutdown_commands_are_recorded(self):
        state = new_engine(legacy=True)

        state.update(CommandReq.build(TMCC2.START_UP_IMMEDIATE, state.address))
        assert state.is_started is True

        state.update(CommandReq.build(TMCC2.SHUTDOWN_DELAYED, state.address))
        assert state.is_shutdown is True
        assert state.is_started is False

    def test_a_train_brake_command_is_written_to_the_record(self):
        state = new_engine(legacy=True)

        state.update(CommandReq.build(TMCC2.TRAIN_BRAKE, state.address, data=5))

        assert state.train_brake == 5

    @pytest.mark.parametrize(
        "command, expected",
        [
            (TMCC2.MOMENTUM_LOW, 0),
            (TMCC2.MOMENTUM_MEDIUM, 3),
            (TMCC2.MOMENTUM_HIGH, 7),
        ],
    )
    def test_the_momentum_commands_set_their_notch(self, command, expected):
        state = new_engine(legacy=True)

        state.update(CommandReq.build(command, state.address))

        assert state.momentum == expected

    def test_the_legacy_momentum_command_carries_its_own_notch(self):
        state = new_engine(legacy=True)

        state.update(CommandReq.build(TMCC2.MOMENTUM, state.address, data=4))

        assert state.momentum == 4

    def test_an_rpm_command_is_written_to_the_record(self):
        state = new_engine(legacy=True)
        state.comp_data._engine_type = 0

        state.update(CommandReq.build(TMCC2.DIESEL_RPM, state.address, data=6))

        assert state.rpm == 6

    def test_a_labor_command_is_written_to_the_record(self):
        state = new_engine(legacy=True)

        state.update(CommandReq.build(TMCC2.ENGINE_LABOR, state.address, data=20))

        assert state.labor == 20

    def test_an_absolute_speed_command_moves_speed_and_target_together(self):
        state = new_engine(legacy=True)

        state.update(CommandReq.build(TMCC2.ABSOLUTE_SPEED, state.address, data=75))

        assert state.speed == 75
        assert state.target_speed == 75

    def test_a_railroad_speed_command_resolves_its_alias(self):
        state = new_engine(legacy=True)

        state.update(CommandReq.build(TMCC2.SPEED_RESTRICTED, state.address))

        assert state.speed == int(TMCC2.SPEED_RESTRICTED.alias[1])

    def test_a_target_speed_command_leaves_the_engine_ramping(self):
        state = new_engine(legacy=True)
        state.comp_data._speed = 20

        state.update(CommandReq.build(TMCC2EngineCommandEnumEx.TARGET_SPEED, state.address, data=90))

        assert state.target_speed == 90
        assert state.speed == 20
        assert state.is_ramping is True

    def test_a_smoke_command_is_written_to_the_record(self):
        state = new_engine(legacy=True)

        state.update(CommandReq.build(TMCC2EffectsControl.SMOKE_MEDIUM, state.address))

        assert state.smoke_level is TMCC2EffectsControl.SMOKE_MEDIUM

    #
    # a TMCC1 smoke keypress reaches state in either of two forms, and the numeric one
    # used to be resolved through the general alias map, which is many to one and last
    # wins and at the time answered AUX_NUMBER_9 for (NUMERIC, 9), so it recorded the
    # opposite of what the operator asked for; the bare form matched no branch at all and
    # was dropped. The smoke commands own those keys again, pinned in test_constants.py
    #
    @pytest.mark.parametrize(
        "command, data, smoke, raw",
        [
            (TMCC1.SMOKE_ON, None, TMCC1.SMOKE_ON, 1),
            (TMCC1.NUMERIC, 9, TMCC1.SMOKE_ON, 1),
            (TMCC1.SMOKE_OFF, None, TMCC1.SMOKE_OFF, 0),
            (TMCC1.NUMERIC, 8, TMCC1.SMOKE_OFF, 0),
        ],
    )
    def test_a_tmcc1_smoke_command_is_written_to_the_record(self, command, data, smoke, raw):
        state = new_engine()
        state.comp_data._smoke = 255

        state.update(CommandReq.build(command, state.address, data=data))

        assert state.comp_data.smoke == raw
        assert state.smoke_level is smoke

    @pytest.mark.parametrize(
        "smoke, raw",
        [
            (TMCC2EffectsControl.SMOKE_OFF, 0),
            (TMCC2EffectsControl.SMOKE_LOW, 1),
            (TMCC2EffectsControl.SMOKE_MEDIUM, 2),
            (TMCC2EffectsControl.SMOKE_HIGH, 3),
        ],
    )
    def test_a_legacy_smoke_level_survives_a_record_with_no_control_type(self, smoke, raw):
        # the record stores one Base 3 level whatever syntax the command arrived in: a
        # 4-digit engine is Legacy by its address alone, and answering from the record
        # instead sent every level it cannot express -- medium and high -- to off
        state = new_engine(addr=1234)
        state.comp_data._smoke = 255

        state.update(CommandReq.build(smoke, state.address))

        assert state.comp_data.is_legacy is False  # the record says nothing
        assert state.comp_data.smoke == raw
        assert state.smoke_level is smoke

    def test_a_tmcc1_keypress_on_a_legacy_engine_records_a_level(self):
        # a Legacy engine can be driven from a CAB-1: the level is stored on the one
        # Base 3 scale, so it reads back as the Legacy level of the same value
        state = new_engine(legacy=True)
        state.comp_data._smoke = 255

        state.update(CommandReq.build(TMCC1.SMOKE_ON, state.address))

        assert state.comp_data.smoke == 1
        assert state.smoke_level is TMCC2EffectsControl.SMOKE_LOW

    @pytest.mark.parametrize("command", [TMCC1HaltCommandEnum.HALT, TMCC2.SYSTEM_HALT])
    def test_a_halt_stops_the_engine_and_kills_the_accessories(self, command):
        state = new_engine(legacy=True)
        state.comp_data._speed = 80
        state.comp_data._target_speed = 100
        state.comp_data.rpm_tmcc = 6
        state.comp_data.labor_tmcc = 20
        state._numeric = 3

        state.update(CommandReq.build(command, state.address))

        assert state.speed == 0
        assert state.target_speed == 0
        assert state.comp_data.rpm_tmcc == 0
        assert state.labor == 12
        assert state.numeric is None
        assert state.aux1 is TMCC2.AUX1_OFF
        assert state.aux2 is TMCC2.AUX2_OFF
        assert state.is_ramping is False

    def test_a_direction_command_that_changes_nothing_reports_no_change(self):
        state = new_engine(legacy=True)
        state._direction = TMCC2.FORWARD_DIRECTION

        assert state._update_state(CommandReq.build(TMCC2.FORWARD_DIRECTION, state.address)) is UpdateResult.NO_CHANGE

    def test_a_direction_command_that_changes_direction_is_an_update(self):
        state = new_engine(legacy=True)
        state._direction = TMCC2.FORWARD_DIRECTION

        assert state._update_state(CommandReq.build(TMCC2.REVERSE_DIRECTION, state.address)) is UpdateResult.UPDATED
        assert state.direction is TMCC2.REVERSE_DIRECTION

    def test_no_command_at_all_is_ignored(self):
        state = new_engine()

        assert state._update_state(None) is UpdateResult.IGNORED

    def test_the_train_address_and_unit_come_from_an_r4lc_command(self):
        state = new_engine(legacy=True)

        state.update(CommandReq.build(TMCC2R4LCEnum.TRAIN_ADDRESS, state.address, data=9))
        assert state.train_tmcc_id == 9

        state.update(CommandReq.build(TMCC2R4LCEnum.TRAIN_UNIT, state.address, data=1))
        assert state.train_unit is UnitAssignment.HEAD_FORWARD

    def test_a_base_memory_field_update_is_applied_to_the_record(self):
        state = new_engine(legacy=True)
        req = BaseReq(
            state.address,
            pdi_command=PdiCommand.BASE_MEMORY,
            scope=CommandScope.ENGINE,
            start=0x6B,  # max speed
            data_length=1,
            data_bytes=b"\x78",
        )
        req._status = 0

        state.update(req)

        assert state.max_speed == 0x78

    def test_an_irda_data_record_carries_the_production_year(self):
        state = new_engine()
        req = IrdaReq(state.address, PdiCommand.IRDA_RX, IrdaAction.DATA, scope=CommandScope.ENGINE)
        req._prod_year = 2021

        state.update(req)

        assert state.year == 2021

    def test_a_record_supplies_a_target_speed_for_an_engine_already_moving(self):
        # a record reports the speed the engine is running at but carries no target of
        # its own, so an engine already moving when its record arrives would otherwise
        # read as bound for a stop
        state = new_engine(legacy=True)
        state.update(CommandReq.build(TMCC2.ABSOLUTE_SPEED, state.address, data=40))
        state.comp_data.target_speed = 0

        state._update_state(_CompDataRecord(state.comp_data))

        assert state.target_speed == 40

    def test_a_record_leaves_a_standing_engine_bound_for_nowhere(self):
        state = new_engine(legacy=True)
        state.comp_data.speed = 0
        state.comp_data.target_speed = 0

        state._update_state(_CompDataRecord(state.comp_data))

        assert state.target_speed == 0

    def test_a_record_leaves_the_target_alone_while_a_ramp_owns_it(self):
        # a ramp writes the target itself, one step at a time, and a record arriving
        # mid-ramp must not push it back up to wherever the engine has reached
        state = new_engine(legacy=True)
        state.comp_data.speed = 40
        state.comp_data.target_speed = 0
        state.is_ramping = True

        state._update_state(_CompDataRecord(state.comp_data))

        assert state.target_speed == 0

    def test_a_d4_mapping_records_the_four_digit_record_number(self):
        state = new_engine(addr=1234, legacy=True)

        state.update(D4Req(17, PdiCommand.D4_ENGINE, D4Action.MAP, tmcc_id=1234))

        assert state.record_no == 17
        assert state.record_no_label == "ID: 17"


class TestEngineStateSerialization:
    def test_as_dict_reports_the_state_a_client_renders(self, monkeypatch):
        monkeypatch.setattr(ProdInfo, "is_capable", staticmethod(lambda: False))
        state = new_engine(legacy=True)
        state.comp_data._speed = 60
        state.comp_data._target_speed = 60
        state.comp_data._engine_type = 0
        state.comp_data._engine_class = 0
        state.comp_data._sound_type = 1
        state.comp_data._momentum = 127
        state.comp_data._fuel_level = 255
        state.comp_data.smoke_tmcc = TMCC2EffectsControl.SMOKE_LOW
        state._direction = TMCC2.FORWARD_DIRECTION

        d = state.as_dict()

        assert d["scope"] == "engine"
        assert d["tmcc_id"] == 7
        assert d["speed"] == 60
        assert d["target_speed"] == 60
        assert d["momentum"] == 7
        assert d["direction"] == "forward_direction"
        assert d["smoke"] == "smoke_low"
        assert d["control"] == "legacy"
        assert d["sound_type"] == "railsounds"
        assert d["engine_type"] == "diesel"
        assert d["engine_class"] == "locomotive"
        # 255 is Lionel's "never set", and never reaches a client as a number
        assert d["max_speed"] is None
        assert d["speed_limit"] is None
        assert d["record_no"] is None

    def test_as_csv_headers_and_row_agree(self, monkeypatch):
        monkeypatch.setattr(ProdInfo, "is_capable", staticmethod(lambda: False))
        state = new_engine(legacy=True)
        state.comp_data._engine_type = 0
        state.comp_data._sound_type = 1
        state.comp_data._speed = 40
        state.comp_data._fuel_level = 255

        headers = EngineState._csv_headers(include_state=True)
        row = state.as_csv(include_state=True)

        assert headers == [
            "address",
            "road_number",
            "road_name",
            "type",
            "control",
            "sound",
            "target",
            "speed",
            "speed_limit",
            "momentum",
            "rpm",
            "effort",
            "fuel",
            "water",
        ]
        # `water` is only reported for a steam engine, so the row is a subset
        assert set(row) <= set(headers)
        assert row["speed"] == 40
        assert row["type"] == "Diesel"
        assert row["control"] == "Legacy"
        assert row["fuel"] == 100
        assert "water" not in row

    def test_as_bytes_carries_the_record_and_the_state_the_base_does_not_hold(self):
        state = new_engine(addr=12, legacy=True)
        state._start_stop = TMCC2.START_UP_IMMEDIATE
        state._direction = TMCC2.FORWARD_DIRECTION
        state.comp_data.smoke_tmcc = TMCC2EffectsControl.SMOKE_LOW
        state._aux1 = TMCC2.AUX1_ON
        state._aux2 = TMCC2.AUX2_OFF

        packets = state.as_bytes()

        assert isinstance(packets, list)
        assert all(isinstance(packet, bytes) for packet in packets)
        # the Base 3 record, then startup, smoke, direction, aux1, aux2
        assert len(packets) == 6

    def test_as_bytes_reports_only_the_record_for_a_pdi_sourced_engine(self):
        state = new_engine(addr=12, legacy=True)
        state._start_stop = TMCC2.START_UP_IMMEDIATE
        state._pdi_source = True

        assert len(state.as_bytes()) == 1

    def test_repr_names_the_engine_and_its_state(self):
        state = new_engine(legacy=True)
        state.comp_data._speed = 60
        state.comp_data._engine_type = 0
        state._direction = TMCC2.FORWARD_DIRECTION

        text = repr(state)

        assert text.startswith("Engine 0007")
        assert "Speed: 060" in text
        assert "FWD" in text
        assert "Diesel" in text

    def test_repr_says_so_when_nothing_is_known(self):
        state = EngineState(CommandScope.ENGINE)
        state._address = 123

        assert repr(state) == "Engine 0123: no information provided from Base 2/3"

    def test_production_year_and_road_number(self):
        # the year used to be assigned over the road number rather than to the slot the
        # format string reserves for it, so the two could never be shown together
        state = new_engine(legacy=True)
        state.comp_data._road_number = state._road_number = "1234"
        state._prod_year = 2021

        text = repr(state)

        assert "Released: 2021" in text
        assert "#1234" in text


class TestEngineStateKnownDefects:
    """
    Behavior that looks wrong but is what the code does today. Each of these is pinned
    so that a correction is a deliberate, visible change to this file.
    """

    def test_a_four_digit_engine_cannot_be_serialized_before_its_record_number_arrives(self):
        # NOTE: characterizes today's behavior. `as_bytes` builds a D4 request from
        # `record_no`, which is None until a D4 mapping arrives, so a client asking for
        # the state of a 4-digit engine anywhere in that window gets an exception rather
        # than the state the Base has already reported
        state = new_engine(addr=1234, legacy=True)

        assert state.record_no is None
        with pytest.raises(TypeError):
            state.as_bytes()

    def test_a_runt_first_record_spends_the_one_chance_to_read_the_direction(self):
        # NOTE: characterizes today's behavior. The one-shot flag is spent before the
        # guard below it is evaluated, so a first record that never reached the soft
        # status byte leaves the direction unknown -- and no later record can supply it
        state = new_engine()
        state.comp_data._soft_status = None
        state._update_state(_CompDataRecord(state.comp_data))

        state.comp_data._soft_status = 1
        state._update_state(_CompDataRecord(state.comp_data))

        assert state.direction is None

    @pytest.mark.parametrize("prop", ["is_legacy", "is_tmcc", "rr_speed", "speed_max", "speeds", "syntax"])
    def test_a_state_with_no_address_cannot_report_its_protocol_flavor(self, prop):
        # NOTE: characterizes today's behavior. `is_legacy` compares the address to 99
        # before checking that there is one, and every property that asks it which scale
        # to read inherits the failure
        state = EngineState(CommandScope.ENGINE)

        assert state.address is None
        with pytest.raises(TypeError):
            getattr(state, prop)

    def test_a_state_with_no_address_cannot_say_that_it_knows_nothing(self):
        # NOTE: characterizes today's behavior. The early return formats the address with
        # `:04`, which None cannot satisfy, so the one thing this branch exists to report
        # is the one thing it cannot
        state = EngineState(CommandScope.ENGINE)

        with pytest.raises(TypeError):
            repr(state)


class TestTrainStateCore:
    def test_a_multi_digit_train_is_legacy_by_its_address(self):
        train = new_train()

        assert train.comp_data.is_legacy is False  # the record says nothing
        assert train.is_legacy is True
        assert train.is_tmcc is False

    @pytest.mark.parametrize(
        "control_type, is_legacy",
        [(LEGACY_CONTROL_TYPE, True), (TMCC_CONTROL_TYPE, False), (CAB1_CONTROL_TYPE, False), (255, False)],
    )
    def test_a_train_under_a_hundred_takes_its_flavor_from_its_record(self, control_type, is_legacy):
        # a train used to carry a hard-coded Legacy flag that no record could overrule,
        # so a genuinely TMCC train was driven and rendered as Legacy
        train = new_train(addr=21)
        train.comp_data._control_type = control_type

        assert train.is_legacy is is_legacy
        assert train.is_tmcc is not is_legacy

    def test_a_legacy_command_makes_a_train_legacy(self):
        # nothing in the record says which protocol a train speaks until the base fills
        # in its control type, so a Legacy command is the other sighting we get of it
        train = new_train(addr=21)

        assert train.is_legacy is False

        train.update(CommandReq.build(TMCC2.NUMERIC, train.address, data=1, scope=CommandScope.TRAIN))

        assert train.is_legacy is True

    def test_a_train_rejects_any_other_scope(self):
        with pytest.raises(ValueError, match="expected TRAIN"):
            TrainState(CommandScope.ENGINE)

    def test_a_train_without_a_head_engine_reports_no_capabilities(self, monkeypatch):
        monkeypatch.setattr(ComponentStateStore, "get_state", staticmethod(lambda *_args, **_kw: None))
        train = new_train()

        assert train.head is None
        assert train.is_rpm is False
        assert train.is_steam is False
        assert train.is_diesel is False
        assert train.has_throttle is False
        assert train.has_lights is False

    def test_a_train_reports_its_transformer_type_from_its_own_record(self):
        # unlike the other capability flags, transformer is not delegated to the head
        train = new_train()
        train.comp_data._engine_type = 15

        assert train.is_transformer is True

    def test_a_train_without_a_consist_is_exported_with_no_components(self):
        # `consist_comps` is None until a record arrives, and exporting a train used to
        # iterate it unguarded
        train = new_train()

        assert train.consist_components is None

        d = train.as_dict()

        assert d["components"] == {}
        assert d["flags"] == 255  # the default the record has not overwritten yet

    def test_a_train_as_dict_carries_its_consist(self):
        train = new_train()
        train.comp_data._consist_flags = 0b10101010
        train.comp_data._consist_comps = [
            ConsistComponent(tmcc_id=11, flags=0b00000001),
            ConsistComponent(tmcc_id=22, flags=0b00000100),
        ]

        d = train.as_dict()

        assert d["scope"] == "train"
        assert d["flags"] == 0b10101010
        assert set(d["components"]) == {11, 22}

    def test_a_speed_written_to_a_train_is_read_back_unchanged(self):
        # a train's record carries no control type, so a codec answering from the record
        # read a Legacy speed back on the TMCC scale and divided it down; both halves now
        # answer from the state's own view of the protocol flavor
        train = new_train()

        train.update(CommandReq.build(TMCC2.ABSOLUTE_SPEED, train.address, data=75, scope=CommandScope.TRAIN))

        assert train.comp_data.is_legacy is False  # the record still says nothing
        assert train.comp_data._speed == 75
        assert train.speed == 75
        assert train.target_speed == 75

    def test_a_train_whose_record_says_legacy_reads_its_speed_back_unchanged(self):
        train = new_train()
        train.comp_data._control_type = LEGACY_CONTROL_TYPE

        train.update(CommandReq.build(TMCC2.ABSOLUTE_SPEED, train.address, data=75, scope=CommandScope.TRAIN))

        assert train.speed == 75
