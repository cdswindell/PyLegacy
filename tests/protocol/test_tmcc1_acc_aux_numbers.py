from __future__ import annotations

from typing import Any

import pytest

from src.pytrain.comm.comm_buffer import CommBuffer
from src.pytrain.protocol.command_req import CommandReq
from src.pytrain.protocol.constants import CommandScope
from src.pytrain.protocol.tmcc1.tmcc1_constants import (
    TMCC1_ACC_NUMERIC_COMMAND,
    TMCC1_COMMAND_TO_ALIAS_MAP,
    TMCC1AuxCommandEnum,
    TMCC1EngineCommandEnum,
)

DIGITS = list(range(10))


class TestAccAuxNumbers:
    @pytest.mark.parametrize("digit", DIGITS)
    def test_members_exist(self, digit):
        member = TMCC1AuxCommandEnum.by_name(f"AUX_NUMBER_{digit}")
        assert member is not None
        assert member.command_def.is_aux1_prefixed is True
        assert member.command_def.alias == (TMCC1AuxCommandEnum.NUMERIC, digit)
        assert member.command_def.bits == TMCC1_ACC_NUMERIC_COMMAND | digit

    @pytest.mark.parametrize("digit", DIGITS)
    def test_as_bytes_is_the_numeric(self, digit):
        req = CommandReq(TMCC1AuxCommandEnum.by_name(f"AUX_NUMBER_{digit}"), address=5, scope=CommandScope.ACC)
        expected = CommandReq(TMCC1AuxCommandEnum.NUMERIC, address=5, scope=CommandScope.ACC, data=digit)
        assert req.as_bytes == expected.as_bytes

    def test_aux1_prefix_is_generated_at_acc_scope(self, monkeypatch):
        sent: list[Any] = []

        class _Buffer:
            @staticmethod
            def enqueue_command(cmd, delay=0):
                _ = delay
                sent.append(cmd)

        monkeypatch.setattr(CommBuffer, "build", staticmethod(lambda **_kwargs: _Buffer()), raising=True)
        req = CommandReq(TMCC1AuxCommandEnum.AUX_NUMBER_3, address=5, scope=CommandScope.ACC)
        req.send()
        prefix = CommandReq(TMCC1AuxCommandEnum.AUX1_OPT_ONE, address=5, scope=CommandScope.ACC).as_bytes
        as_bytes = [cmd if isinstance(cmd, bytes) else cmd.as_bytes for cmd in sent]
        assert as_bytes == [prefix, prefix, req.as_bytes]

    def test_alias_map_untouched(self):
        # the alias map is built from the engine enum only; the new ACC members must not appear in it
        assert all(isinstance(member, TMCC1EngineCommandEnum) for member in TMCC1_COMMAND_TO_ALIAS_MAP.values())
        assert not any(isinstance(member, TMCC1AuxCommandEnum) for member in TMCC1_COMMAND_TO_ALIAS_MAP.values())
