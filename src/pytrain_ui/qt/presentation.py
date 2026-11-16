"""Formatting shared by the Qt presentation models."""

from pytrain.db.component_state import LcsState
from pytrain.db.irda_state import IrdaState


def format_road_number(number: str | int | None) -> str:
    """Pad a numeric road number to at least four digits for display."""
    text = str(number).strip() if number is not None else ""
    return text.zfill(4) if text.isascii() and text.isdecimal() else text


def lcs_board_details(state: LcsState | None, *, known_device: bool = False) -> list[dict]:
    if not known_device and not (isinstance(state, IrdaState) or isinstance(state, LcsState) and state.is_lcs):
        return []
    return [
        {"label": label, "value": str(value) if value not in (None, "", "NA") else "—"}
        for label, value in (
            ("Board ID", getattr(state, "board_id", None)),
            ("Model", getattr(state, "model", None)),
            ("Firmware", getattr(state, "firmware", None)),
        )
    ]
