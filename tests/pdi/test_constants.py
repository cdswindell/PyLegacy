#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

#
#  Tests for src/pytrain/pdi/constants.py
#
import itertools

import pytest

from src.pytrain.pdi.constants import (
    ALL_GETs,
    ALL_RXs,
    ALL_SETs,
    Amc2Action,
    Asc2Action,
    Bpc2Action,
    CommonAction,
    D4Action,
    PdiCommand,
    Ser2Action,
    Stm2Action,
    WiFiAction,
)


def test_pdi_command_basic_classification_flags():
    # Spot-check a variety of commands and their flags
    assert PdiCommand.PING.is_ping is True
    assert PdiCommand.PING.is_tmcc is False
    assert PdiCommand.TMCC_TX.is_tmcc is True
    assert PdiCommand.TMCC4_RX.is_tmcc is True

    # Base family classified as base/sendable
    for cmd in (
        PdiCommand.BASE_ENGINE,
        PdiCommand.BASE_TRAIN,
        PdiCommand.BASE_ACC,
        PdiCommand.BASE,
        PdiCommand.BASE_ROUTE,
        PdiCommand.BASE_SWITCH,
        PdiCommand.BASE_MEMORY,
        PdiCommand.UPDATE_ENGINE_SPEED,
        PdiCommand.UPDATE_TRAIN_SPEED,
    ):
        assert cmd.is_base is True
        assert cmd.is_sendable is True

    # D4 family
    assert PdiCommand.D4_ENGINE.is_d4 is True
    assert PdiCommand.D4_TRAIN.is_d4 is True
    assert PdiCommand.D4_ENGINE.is_receivable is True  # d4 are receivable
    assert PdiCommand.D4_TRAIN.is_sendable is True  # and sendable

    # GET/SET/RX suffix helpers
    assert PdiCommand.WIFI_GET.is_get is True
    assert PdiCommand.WIFI_SET.is_set is True
    assert PdiCommand.WIFI_RX.is_receive is True

    # Domain helpers
    assert PdiCommand.IRDA_GET.is_irda is True
    assert PdiCommand.WIFI_PING.is_wifi is True
    assert PdiCommand.ASC2_RX.is_asc2 is True
    assert PdiCommand.AMC2_SET.is_amc2 is True
    assert PdiCommand.STM2_GET.is_stm2 is True
    assert PdiCommand.SER2_RX.is_ser2 is True
    assert PdiCommand.BPC2_SET.is_bpc2 is True
    assert PdiCommand.BLOCK_RX.is_block is True

    # LCS grouping (any of these implies LCS)
    for cmd in (
        PdiCommand.WIFI_GET,
        PdiCommand.ASC2_SET,
        PdiCommand.IRDA_RX,
        PdiCommand.SER2_GET,
        PdiCommand.BPC2_RX,
        PdiCommand.STM2_SET,
        PdiCommand.AMC2_RX,
    ):
        assert cmd.is_lcs is True

    # as_bytes returns single byte
    assert PdiCommand.PING.as_bytes == bytes([PdiCommand.PING.value])


def test_pdi_command_collections_suffix_sets_are_consistent():
    # The suffix-derived sets should match name endings for the enum
    rx_by_name = {e for e in PdiCommand if e.name.endswith("_RX")}
    set_by_name = {e for e in PdiCommand if e.name.endswith("_SET")}
    get_by_name = {e for e in PdiCommand if e.name.endswith("_GET")}
    assert ALL_RXs == rx_by_name
    assert ALL_SETs == set_by_name
    assert ALL_GETs == get_by_name


def test_pdi_action_common_properties_and_bytes():
    # Every PdiAction should expose .bits and .as_bytes consistent with ActionDef
    all_action_enums = [CommonAction, WiFiAction, Asc2Action, Amc2Action, Ser2Action, Bpc2Action, Stm2Action, D4Action]
    for enum_cls in all_action_enums:
        for action in enum_cls:
            # bits must be int and in byte range 0..255 for to_bytes(1)
            assert isinstance(action.bits, int)
            assert 0 <= action.bits <= 0xFF
            assert action.as_bytes == action.bits.to_bytes(1, "big")
            # __repr__ contains the friendly title and the flags summary
            r = repr(action)
            assert action.title in r
            # flags are rendered as g/x, s/x, r/x
            assert any(flag in r for flag in ("g", "x", "s"))
            if action.is_gettable:
                assert action.opts.count("g") == 1
            if action.is_settable:
                assert action.opts.count("s") == 1
            if action.is_responses:
                assert action.opts.count("r") == 1


def test_common_action_is_config_detection():
    # is_config is specialized: compares bits to CommonAction.CONFIG.bits
    for act in CommonAction:
        if act is CommonAction.CONFIG:
            assert act.is_config is True
        else:
            assert act.is_config is False


def test_d4_action_capabilities_matrix():
    # D4Action definitions specify gettable/settable/responds; verify a few
    expected = {
        D4Action.QUERY: (True, False, True),
        D4Action.UPDATE: (False, True, True),
        D4Action.NEXT_REC: (True, False, True),
        D4Action.CLEAR: (False, True, True),
        D4Action.MAP: (True, False, True),
        D4Action.FIRST_REC: (True, False, True),
        D4Action.COUNT: (True, False, True),
    }
    for act, (g, s, r) in expected.items():
        val = act.value  # ActionDef
        assert val.is_gettable is g
        assert val.is_settable is s
        assert val.is_responses is r


@pytest.mark.parametrize(
    "enum_cls",
    [CommonAction, WiFiAction, Asc2Action, Amc2Action, Ser2Action, Bpc2Action, Stm2Action, D4Action],
)
def test_pdi_action_repr_has_option_flags(enum_cls):
    # Ensure repr of actions renders the three flags indicators
    for action in enum_cls:
        rep = repr(action)
        # ensure the three-character flags like [gsr]/[xxr]/etc appear
        assert "[" in rep and "]" in rep
        # at least 3 of g/x/s/x/r/x markers total
        flag_chunk = rep.split("[")[-1].split("]")[0]
        assert len(flag_chunk) == 3
        assert set(flag_chunk).issubset({"g", "s", "r", "x"})


def test_action_bytes_do_not_collide_within_each_enum():
    # Within a given action enum class, bits should be unique to avoid ambiguity
    for enum_cls in (CommonAction, WiFiAction, Asc2Action, Amc2Action, Ser2Action, Bpc2Action, Stm2Action, D4Action):
        bits = [a.bits for a in enum_cls]
        assert len(bits) == len(set(bits)), f"Duplicate action bits in {enum_cls.__name__}"


def test_pdi_command_sendable_receivable_logic_spotchecks():
    # Sendable: base, d4, *_GET, *_SET
    # Receivable: *_RX or d4
    assert PdiCommand.WIFI_GET.is_sendable is True
    assert PdiCommand.WIFI_SET.is_sendable is True
    assert PdiCommand.WIFI_RX.is_sendable is False
    assert PdiCommand.WIFI_RX.is_receivable is True

    assert PdiCommand.D4_ENGINE.is_sendable is True
    assert PdiCommand.D4_ENGINE.is_receivable is True

    # Non-lcs standalones
    assert PdiCommand.PING.is_sendable is False
    assert PdiCommand.PING.is_receivable is False


def test_as_bytes_single_byte_roundtrip_subset():
    # Basic sanity: the bytes value matches integer value of the command
    for cmd in itertools.islice(iter(PdiCommand), 0, 10):
        assert cmd.as_bytes == bytes([cmd.value])
