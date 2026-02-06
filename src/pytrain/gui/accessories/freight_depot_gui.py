#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from guizero import Box, PushButton

from .accessory_base import AccessoryBase, S
from .accessory_gui import AccessoryGui
from .accessory_type import AccessoryType
from ...db.accessory_state import AccessoryState
from ...utils.path_utils import find_file


class FreightDepotGui(AccessoryBase):
    ACCESSORY_TYPE = AccessoryType.FREIGHT_DEPOT

    def __init__(
        self,
        power: int,
        conveyor: int,
        load: int,
        variant: str = None,
        *,
        aggregator: AccessoryGui = None,
    ):
        """
        Create a GUI to control a K-Line Freight Depot.

        :param int power:
            TMCC ID of the ACS2 port used to power the freight depot.

        :param int conveyor:
            TMCC ID of the ACS2 port is used to control the conveyor belt.

        :param int load:
            TMCC ID of the ACS2 port used to load a package.

        :param str variant:
            Optional; Specifies the variant (K-line, etc.).
        """

        # identify the accessory
        self._power = int(power)
        self._conveyor = int(conveyor)
        self._load = int(load)
        self._variant = variant

        self.power_button = self.conveyor_button = self.load_button = None
        self.power_state = self.conveyor_state = self.load_state = None

        # Main title + image + load image (resolved in bind_variant)
        self._title: str | None = None
        self._image: str | None = None

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
            tmcc_ids={"power": self._power, "conveyor": self._conveyor, "load": self._load},
        )

    def get_target_states(self) -> list[S]:
        """
        Bind GUI to AccessoryState objects. TMCC ids are sourced from ConfiguredAccessory.
        """
        assert self.config is not None

        self.power_state = self.state_for("power")
        self.conveyor_state = self.state_for("conveyor")
        self.load_state = self.state_for("load")
        return [
            self.power_state,
            self.conveyor_state,
            self.load_state,
        ]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: AccessoryState) -> None:
        if state == self.load_state:
            return  # Eject is momentary (press/release handlers)
        with self._cv:
            # LATCH behavior for power / conveyor
            self.toggle_latch(state)
            self.after_state_change(None, self.power_state)

    def after_state_change(self, button: PushButton | None, state: AccessoryState) -> None:
        if state == self.power_state:
            self.gate_widget_on_power(self.power_state, self.load_button)

    def build_accessory_controls(self, box: Box) -> None:
        power_label, belt_label, load_label = self.config.labels_for("power", "conveyor", "load")
        max_text_len = max(len(power_label), len(belt_label), len(load_label)) + 2

        self.power_button = self.make_power_button(self.power_state, power_label, 0, max_text_len, box)
        self.conveyor_button = self.make_power_button(self.conveyor_state, belt_label, 1, max_text_len, box)

        self.load_button = self.make_push_button(
            box,
            state=self.load_state,
            label=load_label,
            col=2,
            text_len=max_text_len,
            image=find_file(self.config.image_for("load")),
        )
        self.after_state_change(None, self.power_state)
