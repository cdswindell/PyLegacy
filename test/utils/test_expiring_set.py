#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

# test/utils/test_expiring_set.py
import pytest

import src.pytrain.utils.expiring_set as expiring_set_mod
from src.pytrain.utils.expiring_set import ExpiringSet


class FakeTime:
    def __init__(self, start=0.0):
        self._t = float(start)

    def __call__(self):
        return self._t

    def advance(self, dt):
        self._t += float(dt)


@pytest.fixture()
def fake_time(monkeypatch):
    ft = FakeTime(start=1_000.0)
    # The module imports "time" directly: from time import time
    # so we must patch the name "time" in the module.
    monkeypatch.setattr(expiring_set_mod, "time", ft)
    return ft


def test_add_and_contains_with_expiry(fake_time):
    s = ExpiringSet(max_age_seconds=2.0)
    key = b"\x01\x02"

    # Initially not contained
    assert key not in s
    assert s.contains(key) is False
    assert len(s) == 0

    # Add at t=1000
    s.add(key)
    assert len(s) == 1
    assert key in s
    assert s.contains(key) is True

    # Advance to just before expiry
    fake_time.advance(1.9)
    assert key in s
    assert s.contains(key) is True
    # Length should still be 1
    assert len(s) == 1

    # Advance past _age
    fake_time.advance(0.2)  # total 2.1 > _age
    # contains should purge and return False
    assert s.contains(key) is False
    # Length should drop after check purges
    assert len(s) == 0


def test_len_after_expiry_timestamp(fake_time):
    s = ExpiringSet(max_age_seconds=1.0)
    s.add(b"\x01\x02")
    s.add(b"\x03\x04")
    assert len(s) == 2

    fake_time.advance(0.9)
    assert len(s) == 2

    s.add(b"\x03\x05")
    fake_time.advance(0.2)
    assert len(s) == 1

    fake_time.advance(0.9)
    assert len(s) == 0


def test_readd_after_expiry_updates_timestamp(fake_time):
    s = ExpiringSet(max_age_seconds=1.0)
    key = b"\xaa"

    s.add(key)
    assert key in s

    # Expire the entry
    fake_time.advance(2.0)
    assert s.contains(key) is False
    assert key not in s

    # Re-add; should be present again with a fresh timestamp
    s.add(key)
    assert key in s
    # Not expired yet
    assert s.contains(key) is True


def test_discard_and_remove(fake_time):
    s = ExpiringSet(max_age_seconds=1.0)
    key = b"\x10"

    # discard on missing should be no-op
    s.discard(key)

    # add then discard
    s.add(key)
    assert key in s
    s.discard(key)
    assert key not in s
    assert len(s) == 0

    # add then remove works
    s.add(key)
    assert key in s
    s.remove(key)
    assert key not in s
    assert len(s) == 0

    # remove on missing raises
    with pytest.raises(KeyError):
        s.remove(key)


def test_clear(fake_time):
    s = ExpiringSet(max_age_seconds=5.0)
    s.add(b"\x01")
    s.add(b"\x02")
    assert len(s) == 2

    s.clear()
    assert len(s) == 0
    assert s.contains(b"\x01") is False
    assert s.contains(b"\x02") is False


def test_dunder_contains_delegates(fake_time, monkeypatch):
    s = ExpiringSet(max_age_seconds=2.0)
    key = b"\xfe"

    # Spy on contains to ensure __contains__ calls it
    called = {"count": 0}

    orig_contains = s.contains

    def wrapped_contains(v):
        called["count"] += 1
        return orig_contains(v)

    monkeypatch.setattr(s, "contains", wrapped_contains)
    s.add(key)

    assert (key in s) is True
    assert called["count"] >= 1  # __contains__ calls contains


def test_repr_is_string_and_does_not_error(fake_time):
    s = ExpiringSet(max_age_seconds=10.0)
    s.add(b"\xde\xad\xbe\xef")

    # The representation may or may not include items depending on TTL calc;
    # this is a smoke test ensuring it returns a string without raising.
    r = repr(s)
    assert isinstance(r, str)
