import re

# noinspection PyPackageRequirements
import pytest

from src.pytrain.utils.validations import Validations
from test.test_base import TestBase


class TestValidations(TestBase):
    def test_validate_int(self):
        # assert valid integers do not generate exceptions
        assert Validations.validate_int(5) == 5

        # test floats are converted
        assert Validations.validate_int(5.4) == 5  # type: ignore
        assert Validations.validate_int(5.99) == 5  # type: ignore

        # test numeric strings are converted
        assert Validations.validate_int("5") == 5  # type: ignore

        # test non-numeric strings  throw ValueError
        v = "text"
        with pytest.raises(ValueError, match="'text' is not an integer"):
            assert Validations.validate_int(v) == 10  # type: ignore

        # test None throw TypeError
        v = None
        with pytest.raises(TypeError, match="'None' is not an integer"):
            assert Validations.validate_int(v) == 10  # type: ignore

        # test minimum value
        v = 5
        with pytest.raises(ValueError, match=f"'{v}' must be equal to or greater than {10}"):
            assert Validations.validate_int(5, min_value=10) == 10

        # test maximum value
        v = 15
        with pytest.raises(ValueError, match=f"'{v}' must be less than or equal to {10}"):
            assert Validations.validate_int(15, max_value=10) == 10

        # test label
        with pytest.raises(ValueError, match=re.escape("Value must be less than or equal to 10 (15)")):
            assert Validations.validate_int(15, max_value=10, label="Value") == 10
