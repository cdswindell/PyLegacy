#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#

import pytest

from src.pytrain.utils.validations import Validations


# noinspection PyTypeChecker
class TestValidateInt:
    def test_returns_int_when_already_int(self):
        assert Validations.validate_int(5) == 5

    @pytest.mark.parametrize("value, expected", [("42", 42), ("5", 5)])
    def test_converts_string_digits_to_int(self, value, expected):
        assert Validations.validate_int(value) == expected

    @pytest.mark.parametrize("value", [5.4, 5.99])
    def test_truncates_float_to_int(self, value):
        assert Validations.validate_int(value) == 5

    def test_rejects_none_by_default(self):
        with pytest.raises(TypeError) as ei:
            Validations.validate_int(None)
        assert str(ei.value) == "'None' is not an integer"

    def test_allows_none_when_flag_true(self):
        assert Validations.validate_int(None, allow_none=True) is None

    def test_raises_type_error_for_non_castable_type(self):
        class Obj: ...

        value = Obj()
        with pytest.raises(TypeError) as ei:
            Validations.validate_int(value)  # int(Obj()) raises TypeError
        assert str(ei.value) == f"'{value}' is not an integer"

    @pytest.mark.parametrize("value", ["abc", "text"])
    def test_raises_value_error_for_non_numeric_string_default_label(self, value):
        with pytest.raises(ValueError) as ei:
            Validations.validate_int(value)
        assert str(ei.value) == f"'{value}' is not an integer"

    def test_raises_value_error_for_non_numeric_string_custom_label(self):
        with pytest.raises(ValueError) as ei:
            Validations.validate_int("abc", label="Speed")
        assert str(ei.value) == "Speed is not an integer"

    @pytest.mark.parametrize("value, minimum", [(-1, 0), (5, 10)])
    def test_min_value_enforced_no_label(self, value, minimum):
        with pytest.raises(ValueError) as ei:
            Validations.validate_int(value, min_value=minimum)
        assert str(ei.value) == f"'{value}' must be equal to or greater than {minimum}"

    def test_min_value_enforced_with_label_and_suffix(self):
        with pytest.raises(ValueError) as ei:
            Validations.validate_int(-1, min_value=0, label="Speed")
        assert str(ei.value) == "Speed must be equal to or greater than 0 (-1)"

    @pytest.mark.parametrize("value", [11, 15])
    def test_max_value_enforced_no_label(self, value):
        with pytest.raises(ValueError) as ei:
            Validations.validate_int(value, max_value=10)
        assert str(ei.value) == f"'{value}' must be less than or equal to 10"

    @pytest.mark.parametrize("value, label", [(11, "Speed"), (15, "Value")])
    def test_max_value_enforced_with_label_and_suffix(self, value, label):
        with pytest.raises(ValueError) as ei:
            Validations.validate_int(value, max_value=10, label=label)
        assert str(ei.value) == f"{label} must be less than or equal to 10 ({value})"

    def test_boundary_values_ok(self):
        assert Validations.validate_int(0, min_value=0) == 0
        assert Validations.validate_int(10, max_value=10) == 10

    def test_value_inside_bounds_ok(self):
        assert Validations.validate_int(5, min_value=1, max_value=10) == 5


# noinspection PyTypeChecker
class TestValidateFloat:
    def test_returns_float_when_already_float(self):
        assert Validations.validate_float(3.14) == 3.14

    def test_converts_int_to_float(self):
        assert Validations.validate_float(3) == 3.0

    def test_converts_string_number_to_float(self):
        assert Validations.validate_float("2.5") == 2.5

    def test_allows_none_when_flag_true(self):
        assert Validations.validate_float(None, allow_none=True) is None

    def test_raises_value_error_for_non_numeric_string_default_label(self):
        with pytest.raises(ValueError) as ei:
            Validations.validate_float("x")
        assert str(ei.value) == "'x' is not a floating point number"

    def test_raises_value_error_for_non_numeric_string_custom_label(self):
        with pytest.raises(ValueError) as ei:
            Validations.validate_float("x", label="Ratio")
        assert str(ei.value) == "Ratio is not a floating point number"

    def test_min_value_enforced_no_label(self):
        with pytest.raises(ValueError) as ei:
            Validations.validate_float(-0.1, min_value=0.0)
        assert str(ei.value) == "'-0.1' must be equal to or greater than 0.0"

    def test_min_value_enforced_with_label_and_suffix(self):
        with pytest.raises(ValueError) as ei:
            Validations.validate_float(-0.1, min_value=0.0, label="Ratio")
        assert str(ei.value) == "Ratio must be equal to or greater than 0.0 (-0.1)"

    def test_max_value_enforced_no_label(self):
        with pytest.raises(ValueError) as ei:
            Validations.validate_float(1.1, max_value=1.0)
        assert str(ei.value) == "'1.1' must be less than or equal to 1.0"

    def test_max_value_enforced_with_label_and_suffix(self):
        with pytest.raises(ValueError) as ei:
            Validations.validate_float(1.1, max_value=1.0, label="Ratio")
        assert str(ei.value) == "Ratio must be less than or equal to 1.0 (1.1)"

    def test_boundary_values_ok(self):
        assert Validations.validate_float(0.0, min_value=0.0) == 0.0
        assert Validations.validate_float(1.0, max_value=1.0) == 1.0

    def test_value_inside_bounds_ok(self):
        assert Validations.validate_float(0.5, min_value=0.0, max_value=1.0) == 0.5
