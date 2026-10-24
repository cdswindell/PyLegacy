"""Deterministic tests for the configurable, immediate Base 3 write deduplicator."""

from unittest.mock import Mock

import pytest

import src.pytrain.pdi.base_req as base_req_module
from src.pytrain.pdi.base_req import BaseReq
from src.pytrain.pdi.constants import D4Action, PdiCommand
from src.pytrain.pdi.d4_req import D4Req


@pytest.fixture(autouse=True)
def clear_write_history():
    with base_req_module._write_dedup_lock:
        base_req_module._recent_db_writes.clear()
    yield
    with base_req_module._write_dedup_lock:
        base_req_module._recent_db_writes.clear()


def _write(data=b"\x01"):
    return D4Req(
        0x1234,
        PdiCommand.D4_ENGINE,
        D4Action.UPDATE,
        start=56,
        data_length=len(data),
        data_bytes=data,
    )


def test_identical_writes_within_configured_window_are_sent_once(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(base_req_module.time, "monotonic", lambda: clock[0])
    send = Mock()

    BaseReq.process_sync_reqs([_write()], send, deduplicate_writes=True)
    clock[0] += base_req_module.BASE3_WRITE_DEDUP_SECONDS / 2
    BaseReq.process_sync_reqs([_write()], send, deduplicate_writes=True)

    assert send.call_count == 1


def test_write_is_immediate_and_allowed_after_window(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(base_req_module.time, "monotonic", lambda: clock[0])
    send = Mock()

    BaseReq.process_sync_reqs([_write()], send, deduplicate_writes=True)
    assert send.call_count == 1  # No delayed dispatch or buffering.
    clock[0] += base_req_module.BASE3_WRITE_DEDUP_SECONDS
    BaseReq.process_sync_reqs([_write()], send, deduplicate_writes=True)

    assert send.call_count == 2


def test_different_payloads_and_records_are_not_suppressed(monkeypatch):
    monkeypatch.setattr(base_req_module.time, "monotonic", lambda: 100.0)
    send = Mock()
    other_record = D4Req(0x1235, PdiCommand.D4_ENGINE, D4Action.UPDATE, start=56, data_length=1, data_bytes=b"\x01")

    BaseReq.process_sync_reqs([_write(b"\x01"), _write(b"\x02"), other_record], send, deduplicate_writes=True)

    assert send.call_count == 3


def test_queries_and_speed_commands_are_not_deduplicated(monkeypatch):
    monkeypatch.setattr(base_req_module.time, "monotonic", lambda: 100.0)
    send = Mock()
    query = D4Req(0x1234, PdiCommand.D4_ENGINE, D4Action.QUERY)

    BaseReq.process_sync_reqs([query, query], send, deduplicate_writes=True)

    assert send.call_count == 2


def test_client_forwarding_is_never_deduplicated(monkeypatch):
    monkeypatch.setattr(base_req_module.time, "monotonic", lambda: 100.0)
    forward = Mock()

    BaseReq.process_sync_reqs([_write(), _write()], forward)

    assert forward.call_count == 2


def test_window_can_be_reduced_without_changing_tests(monkeypatch):
    monkeypatch.setattr(base_req_module, "BASE3_WRITE_DEDUP_SECONDS", 0.001)
    clock = [100.0]
    monkeypatch.setattr(base_req_module.time, "monotonic", lambda: clock[0])
    send = Mock()

    BaseReq.process_sync_reqs([_write()], send, deduplicate_writes=True)
    clock[0] += base_req_module.BASE3_WRITE_DEDUP_SECONDS
    BaseReq.process_sync_reqs([_write()], send, deduplicate_writes=True)

    assert send.call_count == 2
