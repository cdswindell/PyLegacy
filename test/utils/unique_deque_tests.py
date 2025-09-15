#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

import pytest

from src.pytrain.utils.unique_deque import UniqueDeque


def test_maxlen_eviction_append_and_appendleft():
    # maxlen with append evicts from left
    ud = UniqueDeque(range(0, 3), maxlen=3)
    assert list(ud) == [0, 1, 2]
    ud.append(3)
    assert list(ud) == [1, 2, 3]  # 0 evicted

    # maxlen with appendleft evicts from right
    ud2 = UniqueDeque(range(0, 3), maxlen=3)
    assert list(ud2) == [0, 1, 2]
    ud2.appendleft(-1)
    assert list(ud2) == [-1, 0, 1]  # 2 evicted


def test_uniqueness_moves_existing_to_ends():
    ud = UniqueDeque([1, 2, 3, 4, 5])
    # append existing should move to end, length unchanged
    ud.append(2)
    assert list(ud) == [1, 3, 4, 5, 2]
    assert len(ud) == 5

    # appendleft existing should move to front, length unchanged
    ud.appendleft(4)
    assert list(ud) == [4, 1, 3, 5, 2]
    assert len(ud) == 5


def test_add_returns_new_and_iadd_mutates():
    base = UniqueDeque([1, 2, 3])
    other = [3, 4, 5]

    # __add__ returns a new UniqueDeque; base unchanged
    added = base + other
    assert isinstance(added, UniqueDeque)
    assert list(base) == [1, 2, 3]
    assert list(added) == [1, 2, 3, 4, 5]  # 3 deduped

    # __iadd__ mutates in place
    base += other
    assert list(base) == [1, 2, 3, 4, 5]


def test_setitem_behavior_for_existing_and_new_values():
    ud = UniqueDeque([10, 20, 30])
    # Setting to an existing value should be ignored (value already seen)
    ud.__setitem__(1, 10)
    assert list(ud) == [10, 20, 30]  # unchanged

    # Setting to a new value should be applied
    ud.__setitem__(1, 40)
    # 40 wasn't seen before, so update should occur
    assert list(ud) == [10, 40, 30]


def test_push_alias_for_appendleft():
    ud = UniqueDeque([1, 2, 3])
    ud.push(2)  # move existing to front
    assert list(ud) == [2, 1, 3]
    ud.push(4)  # add new at front
    assert list(ud) == [4, 2, 1, 3]


def test_not_implemented_ops():
    ud = UniqueDeque([1, 2, 3])
    with pytest.raises(NotImplementedError):
        _ = ud * 2
    with pytest.raises(NotImplementedError):
        ud *= 2
    with pytest.raises(NotImplementedError):
        _ = ud.__reduce__()  # direct call to confirm it's not implemented
