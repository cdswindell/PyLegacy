#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from guizero import Box, PushButton

from .accessories.accessory_type import AccessoryType
from .accessory_base import AccessoryBase, S
from .accessory_gui import AccessoryGui
from ..db.accessory_state import AccessoryState
from ..utils.path_utils import find_file


class MilkLoaderGui(AccessoryBase):
    ACCESSORY_TYPE = AccessoryType.MILK_LOADER

    def __init__(
        self,
        power: int,
        conveyor: int,
        eject: int,
        variant: str | None = None,
        *,
        aggregator: AccessoryGui | None = None,
    ):
        """
        Create a GUI to control a K-Line/Lionel Milk Loader.

        :param int power:
            TMCC ID of the ASC2 port used to power the milk loader.

        :param int conveyor:
            TMCC ID of the ASC2 port used to control the conveyor belt.

        :param int eject:
            TMCC ID of the ASC2 port used to eject a milk can.

        :param str variant:
            Optional; Specifies the variant (stable key preferred, but aliases accepted).
        """
        self._power = int(power)
        self._conveyor = int(conveyor)
        self._eject = int(eject)
        self._variant = variant

        self.power_button = self.conveyor_button = self.eject_button = None
        self.power_state = self.conveyor_state = self.eject_state = None

        # Main title + image + eject image (resolved in bind_variant)
        self._title: str | None = None
        self._image: str | None = None
        self._eject_image: str | None = None

        super().__init__(self._title, self._image, aggregator=aggregator)

    def bind_variant(self) -> None:
        """
        Resolve all metadata (title, main image, op images) via registry + configure_accessory().

        This keeps the public constructor signature stable while moving all metadata
        to your centralized registry/config pipeline.
        """
        self.configure_from_registry(
            self.ACCESSORY_TYPE,
            self._variant,
            tmcc_ids={"power": self._power, "conveyor": self._conveyor, "eject": self._eject},
        )

        # Pre-resolve eject image (momentary)
        self._eject_image = find_file(self.config.image_for("eject", "depot-milk-can-eject.jpeg"))

    def get_target_states(self) -> list[S]:
        """
        Bind GUI to AccessoryState objects. TMCC ids are sourced from ConfiguredAccessory.
        """
        assert self.config is not None

        self.power_state = self.state_for("power")
        self.conveyor_state = self.state_for("conveyor")
        self.eject_state = self.state_for("eject")
        return [
            self.power_state,
            self.conveyor_state,
            self.eject_state,
        ]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: AccessoryState) -> None:
        if state == self.eject_state:
            return  # Eject is momentary (press/release handlers)
        with self._cv:
            # LATCH behavior for power / conveyor
            self.toggle_latch(state)
            self.after_state_change(None, self.power_state)

    def after_state_change(self, button: PushButton | None, state: AccessoryState) -> None:
        if state == self.power_state:
            self.gate_widget_on_power(self.power_state, self.eject_button)

    def build_accessory_controls(self, box: Box) -> None:
        """
        Build controls using labels from configured operations.
        """
        assert self.config is not None
        power_label, conveyor_label, eject_label = self.config.labels_for("power", "conveyor", "eject")

        max_text_len = max(len(power_label), len(conveyor_label), len(eject_label)) + 2
        self.power_button = self.make_power_button(self.power_state, power_label, 0, max_text_len, box)
        self.conveyor_button = self.make_power_button(self.conveyor_state, conveyor_label, 1, max_text_len, box)

        self.eject_button = self.make_push_button(
            box,
            state=self.eject_state,
            label=eject_label,
            col=2,
            text_len=max_text_len,
            image=find_file(self.config.image_for("eject")),
        )
        self.after_state_change(None, self.power_state)
