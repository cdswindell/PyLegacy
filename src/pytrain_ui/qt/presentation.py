"""Formatting shared by the Qt presentation models."""


def format_road_number(number: str | int | None) -> str:
    """Pad a numeric road number to at least four digits for display."""
    text = str(number).strip() if number is not None else ""
    return text.zfill(4) if text.isascii() and text.isdecimal() else text
