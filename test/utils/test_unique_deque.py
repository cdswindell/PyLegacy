#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#
import pytest

from src.pytrain.utils.unique_deque import UniqueDeque


class TestUniqueDequeue:
    def test_create_no_args(self) -> None:
        ud = UniqueDeque()
        assert ud is not None
        assert ud.maxlen is None
        assert len(ud) == 0

    def test_getters_fail_on_zero_len_unique_deque(self) -> None:
        ud = UniqueDeque()
        assert ud is not None
        assert ud.maxlen is None
        assert len(ud) == 0

        with pytest.raises(IndexError):
            ud.pop()

        with pytest.raises(IndexError):
            ud.popleft()

        with pytest.raises(IndexError):
            del ud[0]

        with pytest.raises(ValueError):
            ud.remove(0)

    def test_clear(self):
        ud = UniqueDeque(range(0, 10))
        assert ud is not None
        assert len(ud) == 10
        ud.clear()
        assert len(ud) == 0
        assert ud is not None

    def test_insert(self):
        ud = UniqueDeque()
        with pytest.raises(NotImplementedError):
            ud.insert(0, 1)

    def test_remove(self):
        ud = UniqueDeque(range(0, 10))
        assert ud is not None
        assert len(ud) == 10
        assert 5 in ud
        ud.remove(5)
        assert 5 not in ud
        assert len(ud) == 9

    def test_popleft(self):
        ud = UniqueDeque(range(0, 10))
        assert ud is not None
        assert len(ud) == 10
        assert ud.popleft() == 0
        assert len(ud) == 9
        assert 0 not in ud

    def test_pop(self):
        ud = UniqueDeque(range(0, 10))
        assert ud is not None
        assert len(ud) == 10
        assert ud.pop() == 9
        assert len(ud) == 9
        assert 10 not in ud

    def test_extendleft(self):
        ud = UniqueDeque()
        assert ud is not None
        ud.extendleft(range(0, 10))
        assert len(ud) == 10
        for i in range(0, 10):
            assert ud[i] == 9 - i

        # add the range back, length and order shouldn't change
        ud.extendleft(range(0, 10))
        assert len(ud) == 10
        for i in range(0, 10):
            assert ud[i] == 9 - i

    def test_extend(self):
        ud = UniqueDeque()
        assert ud is not None
        ud.extend(range(0, 10))
        assert len(ud) == 10
        for i in range(0, 10):
            assert ud[i] == i

        # add the range back using extendleft, order should change
        ud.extendleft(range(0, 10))
        assert len(ud) == 10
        for i in range(0, 10):
            assert ud[i] == 9 - i

    def test_copy(self):
        ud = UniqueDeque(range(0, 10))
        assert ud is not None
        assert len(ud) == 10

        ud2 = ud.copy()
        assert len(ud) == len(ud2)
        assert ud.maxlen == ud2.maxlen
        for i in range(0, 10):
            assert ud[i] == ud2[i]

        # should not be able to add duplicate entries
        ud2.extend(range(0, 10))
        assert len(ud) == len(ud2)
        assert ud.maxlen == ud2.maxlen
        for i in range(0, 10):
            assert ud[i] == ud2[i]

    def test_appendleft(self):
        ud = UniqueDeque(range(0, 10))
        assert ud is not None
        assert len(ud) == 10

        # append the last value to the queue, it should now become the first
        ud.appendleft(9)
        assert len(ud) == 10
        assert ud[0] == 9
        assert ud[9] == 8

    def test_append(self):
        ud = UniqueDeque(range(0, 10))
        assert ud is not None
        assert len(ud) == 10

        # append the first value to the queue, it should now become the last
        ud.append(0)
        assert len(ud) == 10
        assert ud[0] == 1
        assert ud[9] == 0

    def test_maxlen_eviction_append_and_appendleft(self):
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

    def test_uniqueness_moves_existing_to_ends(self):
        ud = UniqueDeque([1, 2, 3, 4, 5])
        # append existing should move to end, length unchanged
        ud.append(2)
        assert list(ud) == [1, 3, 4, 5, 2]
        assert len(ud) == 5

        # appendleft existing should move to front, length unchanged
        ud.appendleft(4)
        assert list(ud) == [4, 1, 3, 5, 2]
        assert len(ud) == 5

    def test_add_returns_new_and_iadd_mutates(self):
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

    def test_setitem_behavior_for_existing_and_new_values(self):
        ud = UniqueDeque([10, 20, 30])
        # Setting to an existing value should be ignored (value already seen)
        ud.__setitem__(1, 10)
        assert list(ud) == [10, 20, 30]  # unchanged

        # Setting to a new value should be applied
        ud.__setitem__(1, 40)
        # 40 wasn't seen before, so update should occur
        assert list(ud) == [10, 40, 30]

    def test_push_alias_for_appendleft(self):
        ud = UniqueDeque([1, 2, 3])
        ud.push(2)  # move existing to front
        assert list(ud) == [2, 1, 3]
        ud.push(4)  # add new at front
        assert list(ud) == [4, 2, 1, 3]

    def test_not_implemented_ops(self):
        ud = UniqueDeque([1, 2, 3])
        with pytest.raises(NotImplementedError):
            _ = ud * 2
        with pytest.raises(NotImplementedError):
            ud *= 2
        with pytest.raises(NotImplementedError):
            _ = ud.__reduce__()  # direct call to confirm it's not implemented
