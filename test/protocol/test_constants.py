import pytest

from src.protocol.constants import SwitchState
from ..test_base import TestBase


class TestConstants(TestBase):
    def test_by_name_mixin(self):
        # assert all enums are found
        for ss in SwitchState:
            assert SwitchState.by_name(ss.name) == ss

        # assert by_name is case-insensitive
        assert SwitchState.by_name('through') == SwitchState.THROUGH
        assert SwitchState.by_name('THROUGH') == SwitchState.THROUGH

        # assert non-members return None
        assert SwitchState.by_name('NOT_PRESENT') is None

    # assert None return None
    assert SwitchState.by_name(str(None)) is None

    # check ValueError is thrown
    with pytest.raises(ValueError, match="'NOT_PRESENT' is not a valid SwitchState"):
        SwitchState.by_name('NOT_PRESENT', raise_exception=True)

    # check ValueError is thrown
    with pytest.raises(ValueError, match="None is not a valid SwitchState"):
        SwitchState.by_name(None, raise_exception=True)  # noqa

    # check ValueError is thrown
    with pytest.raises(ValueError, match="Empty is not a valid SwitchState"):
        SwitchState.by_name("  ", raise_exception=True)
