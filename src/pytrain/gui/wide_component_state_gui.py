#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
from __future__ import annotations

from .component_state_gui import ComponentStateGui


class WideComponentStateGui(ComponentStateGui):
    """
    Convenience wrapper for ultra-wide displays (e.g. 1920x480).
    Renders two virtual 800x480 screens by default, with optional third screen.
    """

    def __init__(
            self,
            label: str = None,
            initial: str = "Power Districts",
            width: int = None,
            height: int = None,
            scale_by: float = 1.0,
            exclude_unnamed: bool = False,
            screens: int = 2,
    ) -> None:
        super().__init__(
            label=label,
            initial=initial,
            width=width,
            height=height,
            scale_by=scale_by,
            exclude_unnamed=exclude_unnamed,
            screens=screens,
        )
