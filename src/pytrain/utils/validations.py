#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#


class Validations:
    @classmethod
    def validate_int(
        cls,
        value: int,
        min_value: int = None,
        max_value: int = None,
        label: str = None,
        allow_none: bool = False,
    ) -> int | None:
        if value is None and allow_none is True:
            return value
        if label is None:
            label = f"'{str(value)}'"
            suffix = ""
        else:
            label = f"{label}"
            suffix = f" ({value})"
        try:
            value = int(value)
        except ValueError:
            raise ValueError(f"{label} is not an integer")
        except TypeError:
            raise TypeError(f"{label} is not an integer")
        if min_value is not None and value < min_value:
            raise ValueError(f"{label} must be equal to or greater than {min_value}{suffix}")
        if max_value is not None and value > max_value:
            raise ValueError(f"{label} must be less than or equal to {max_value}{suffix}")
        return value

    @classmethod
    def validate_float(
        cls,
        value: float,
        min_value: float = None,
        max_value: float = None,
        label: str = None,
        allow_none: bool = False,
    ) -> float | None:
        if value is None and allow_none is True:
            return value
        if label is None:
            label = f"'{str(value)}'"
            suffix = ""
        else:
            label = f"{label}"
            suffix = f" ({value})"
        try:
            value = float(value)
        except ValueError:
            raise ValueError(f"{label} is not a floating point number")
        except TypeError:
            raise TypeError(f"{label} is not a floating point number")
        if min_value is not None and value < min_value:
            raise ValueError(f"{label} must be equal to or greater than {min_value}{suffix}")
        if max_value is not None and value > max_value:
            raise ValueError(f"{label} must be less than or equal to {max_value}{suffix}")
        return value
