class Validations:
    @classmethod
    def validate_int(cls, value: int, min_value: int = None, max_value: int = None, label: str = None) -> int:
        if label is None:
            label = f"'{str(value)}'"
        else:
            label = f"{label}"
        try:
            value = int(value)
        except ValueError:
            raise ValueError(f"{label} is not an integer")
        except TypeError:
            raise TypeError(f"{label} is not an integer")
        if min_value is not None and value < min_value:
            raise ValueError(f"{label} must be greater or equal to {min_value}")
        if max_value is not None and value > max_value:
            raise ValueError(f"{label} must be less or equal to {max_value}")
        return value
