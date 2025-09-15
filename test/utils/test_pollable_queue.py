#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

import os
import select
from queue import Full

import pytest

# Import from the project package layout
from src.pytrain.utils.pollable_queue import PollableQueue


def _select_readable(fd, timeout=0.2) -> bool:
    r, _, _ = select.select([fd], [], [], timeout)
    return bool(r)


def test_fileno_is_valid() -> None:
    q = PollableQueue(4)
    fd = q.fileno()
    assert isinstance(fd, int)
    # FD should be positive and selectable
    assert fd > 0
    # Not readable initially
    assert _select_readable(fd, timeout=0.05) is False


def test_select_ready_on_put_and_clears_on_get() -> None:
    q = PollableQueue(4)
    fd = q.fileno()

    # Put an item -> should signal readability
    q.put("a")
    assert _select_readable(fd, timeout=0.5) is True

    # get() must consume the socket byte and return the item
    item = q.get()
    assert item == "a"

    # No pending signals after get
    assert _select_readable(fd, timeout=0.05) is False


def test_multiple_puts_and_gets_signal_and_drain() -> None:
    q = PollableQueue(10)
    fd = q.fileno()

    items = list(range(5))
    for x in items:
        q.put(x)

    # Readable after enqueuing
    assert _select_readable(fd, timeout=0.5) is True

    # Drain and verify order
    out = [q.get() for _ in items]
    assert out == items

    # Socket drained as well
    assert _select_readable(fd, timeout=0.05) is False


def test_put_when_full_does_not_signal_extra_bytes() -> None:
    # Fill capacity to 1
    q = PollableQueue(1)
    fd = q.fileno()

    q.put("first")
    # Should be readable for the single enqueued item
    assert _select_readable(fd, timeout=0.5) is True

    # Second put should fail and must not add a socket byte
    with pytest.raises(Full):
        q.put("second", block=False)

    # Drain the first (and only) signal and item
    assert q.get() == "first"

    # After consuming, there should be no pending readability, ensuring
    # the failed put didn't add an extra byte to the socket
    assert _select_readable(fd, timeout=0.05) is False


def test_non_posix_fallback_socket_pair(monkeypatch) -> None:
    # Force non-POSIX branch by monkeypatching os.name
    monkeypatch.setattr(os, "name", "nt", raising=False)
    q = PollableQueue(2)
    fd = q.fileno()

    # Basic signaling semantics should still hold
    assert _select_readable(fd, timeout=0.05) is False
    q.put(123)
    assert _select_readable(fd, timeout=0.5) is True
    assert q.get() == 123
    assert _select_readable(fd, timeout=0.05) is False
