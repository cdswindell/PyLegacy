"""Formatting shared by the Qt presentation models."""

from pytrain.db.component_state import LcsState
from pytrain.db.component_state_store import ComponentStateStore
from pytrain.db.irda_state import IrdaState
from pytrain.protocol.constants import CommandScope, EngineType


def is_pseudo_train(state) -> bool:
    """Hide known command aliases, preserving actual train records even at alias IDs."""
    return (
        state is not None
        and getattr(state, "scope", CommandScope.TRAIN) == CommandScope.TRAIN
        and getattr(state, "record_no", None) is None
        and ComponentStateStore.is_pseudo_train_id(state.tmcc_id)
    )


def target_kind(state, scope: CommandScope) -> str:
    """Use the same locomotive, car/device, and train labels throughout the cab."""
    if scope == CommandScope.TRAIN:
        return "TRN"
    non_engines = {
        EngineType.ACCESSORY,
        EngineType.PASSENGER_CAR,
        EngineType.BREAKDOWN,
        EngineType.RESERVED,
        EngineType.CRANE,
        EngineType.FREIGHT_SOUNDS,
        EngineType.TRANSFORMER,
    }
    return "CAR" if getattr(state, "engine_type", None) in non_engines else "ENG"


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
