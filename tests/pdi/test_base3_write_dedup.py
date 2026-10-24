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
    req = D4Req(
        0x1234,
        PdiCommand.D4_ENGINE,
        D4Action.UPDATE,
        start=56,
        data_length=len(data),
        data_bytes=data,
    )
    # Mirror the metadata attached by BaseReq.updates_to_reqs() from CompData's UpdatePkg.
    req._update_dedup_key = (req.scope, 1234, 56, len(data), data)
    return req


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
    clock[0] = 100.0 + base_req_module.BASE3_WRITE_DEDUP_SECONDS * 2
    BaseReq.process_sync_reqs([_write()], send, deduplicate_writes=True)

    assert send.call_count == 2


def test_different_payloads_and_records_are_not_suppressed(monkeypatch):
    monkeypatch.setattr(base_req_module.time, "monotonic", lambda: 100.0)
    send = Mock()
    other_record = _write()
    other_record._update_dedup_key = (other_record.scope, 1235, 56, 1, b"\x01")

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


def test_a_b_a_at_same_destination_sends_all_three(monkeypatch):
    """The final A is a real state transition, not a duplicate of the first A."""
    clock = [100.0]
    monkeypatch.setattr(base_req_module.time, "monotonic", lambda: clock[0])
    send = Mock()

    for payload in (b"\\x01", b"\\x02", b"\\x01"):
        BaseReq.process_sync_reqs([_write(payload)], send, deduplicate_writes=True)
        clock[0] += 0.005

    assert send.call_count == 3
    assert [call.args[0]._update_dedup_key[-1] for call in send.call_args_list] == [
        b"\\x01",
        b"\\x02",
        b"\\x01",
    ]


def test_a_b_b_at_same_destination_suppresses_only_last_b(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(base_req_module.time, "monotonic", lambda: clock[0])
    send = Mock()

    for payload in (b"\\x01", b"\\x02", b"\\x02"):
        BaseReq.process_sync_reqs([_write(payload)], send, deduplicate_writes=True)
        clock[0] += 0.005

    assert send.call_count == 2
