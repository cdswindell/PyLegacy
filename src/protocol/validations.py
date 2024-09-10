class Validations:
    @classmethod
    def validate_int(cls, value: int, min_value: int = None, max_value: int = None) -> int:
        try:
            _ = int(value)
        except ValueError:
            raise ValueError(f"'{value}' is not an integer")
        if min_value is not None and value < min_value:
            raise ValueError(f"'{value}' is less than {min_value}")
        if max_value is not None and value > max_value:
            raise ValueError(f"'{value}' is greater than {max_value}")
        return value
