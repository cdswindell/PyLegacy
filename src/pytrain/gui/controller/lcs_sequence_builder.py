#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""
Turns ``(device, mode, base_id, options)`` into the ordered Cab-remote presses that
program an LCS module, the PDI GETs that read it back, and the human-readable list
the review page shows.

Every supported device goes through this one path; the panel has exactly one write
path and never sends a PDI ``CONFIG SET``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping

from ...pdi.pdi_req import PdiReq
from ...protocol.command_req import CommandReq
from .lcs_device_registry import LcsDevice, LcsMode, MAX_TMCC_ID, Press, max_base


@dataclass(frozen=True)
class LcsProgram:
    """
    The complete result of building a programming sequence.
    """

    device: LcsDevice
    mode: LcsMode
    base_id: int
    presses: List[CommandReq] = field(default_factory=list)
    verify: List[PdiReq] = field(default_factory=list)
    display: List[str] = field(default_factory=list)

    @property
    def program_instruction(self) -> str:
        if self.device.program_button == "PROGRAM":
            return (
                f"Hold the {self.device.label}'s PROGRAM button until the Program LED blinks about "
                f"twice a second, then release. Pressing PROGRAM again before the sequence finishes "
                f"exits program mode with no change."
            )
        return f"Hold the {self.device.label}'s PGM button for 1 second; the red LED blinks slowly."


def included_presses(mode: LcsMode, options: Mapping[str, Any] | None = None) -> tuple[Press, ...]:
    return tuple(press for press in mode.presses if press.is_included(options))


def _press_text(press: Press, base_id: int, options: Mapping[str, Any] | None) -> str:
    label = press.resolved_label(options).format(id=base_id, digit=press.digit(options))
    return f"{label} ({press.note})" if press.note else label


def build_program(
    device: LcsDevice,
    mode: LcsMode,
    base_id: int,
    options: Mapping[str, Any] | None = None,
) -> LcsProgram:
    """
    Build the presses, read-back GETs, and display list for the given selection.
    """
    if mode not in device.modes:
        raise ValueError(f"Mode {mode.key} does not belong to {device.label}")
    if not isinstance(base_id, int) or not 1 <= base_id <= MAX_TMCC_ID:
        raise ValueError(f"Invalid base TMCC ID: {base_id}")
    if base_id > max_base(mode):
        raise ValueError(f"Base TMCC ID {base_id} exceeds {max_base(mode)} for {device.label} {mode.ports_label}")

    options = dict(options or {})
    for option in device.options:
        if option.key not in options and option.default is not None:
            options[option.key] = option.default
    for option in device.options:
        if option.required and options.get(option.key) is None:
            raise ValueError(f"Option '{option.key}' is required for {device.label}")

    presses: List[CommandReq] = []
    display: List[str] = []
    for i, press in enumerate(included_presses(mode, options), start=1):
        presses.append(press.build(base_id, options))
        display.append(f"{i}. {_press_text(press, base_id, options)}")

    verify: List[PdiReq] = [device.pdi_device.config(base_id), device.pdi_device.info(base_id)]

    return LcsProgram(
        device=device,
        mode=mode,
        base_id=base_id,
        presses=presses,
        verify=verify,
        display=display,
    )
