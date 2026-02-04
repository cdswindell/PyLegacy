#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from guizero import Box, PushButton, Text

from .accessories.accessory_type import AccessoryType
from .accessories.config import ConfiguredAccessory, configure_accessory
from .accessory_base import AccessoryBase, S
from .accessory_gui import AccessoryGui
from ..db.accessory_state import AccessoryState
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
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

        # New: configured model (definition + resolved assets + tmcc wiring)
        self._cfg: ConfiguredAccessory | None = None

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
        definition = self.registry.get_definition(self.ACCESSORY_TYPE, self._variant)

        # Bind wiring (TMCC ids) to the definition
        self._cfg = configure_accessory(
            definition,
            tmcc_ids={
                "power": self._power,
                "conveyor": self._conveyor,
                "eject": self._eject,
            },
            # per-instance overrides can be added later without changing signature
            operation_images=None,
            instance_id=None,
            display_name=None,
        )
        # make sure we have a configuration
        assert self._cfg is not None

        # Apply main title/image to the AccessoryBase fields
        self.title = self._title = self._cfg.title
        self.image_file = self._image = find_file(self._cfg.definition.variant.image)

        # Pre-resolve eject image (momentary)
        eject_op = self._cfg.operation("eject")
        self._eject_image = find_file(eject_op.image or "depot-milk-can-eject.jpeg")

    def get_target_states(self) -> list[S]:
        """
        Bind GUI to AccessoryState objects. TMCC ids are sourced from ConfiguredAccessory.
        """
        power_id = self._cfg.tmcc_id_for("power")
        conveyor_id = self._cfg.tmcc_id_for("conveyor")
        eject_id = self._cfg.tmcc_id_for("eject")

        self.power_state = self._state_store.get_state(CommandScope.ACC, power_id)
        self.conveyor_state = self._state_store.get_state(CommandScope.ACC, conveyor_id)
        self.eject_state = self._state_store.get_state(CommandScope.ACC, eject_id)

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
            CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()
            self.after_state_change(None, self.power_state)

    def after_state_change(self, button: PushButton | None, state: AccessoryState) -> None:
        if state == self.power_state:
            if self.eject_button is None:
                return  # defensive programming
            # If power is off, disable eject; if power is on, enable eject
            if state.is_aux_on:
                self.queue_message(lambda: self.eject_button.enable())
            else:
                self.queue_message(lambda: self.eject_button.disable())

    def build_accessory_controls(self, box: Box) -> None:
        """
        Build controls using labels from configured operations.
        """
        power_label = self._cfg.operation("power").label
        conveyor_label = self._cfg.operation("conveyor").label
        eject_label = self._cfg.operation("eject").label

        max_text_len = max(len(power_label), len(conveyor_label), len(eject_label)) + 2

        self.power_button = self.make_power_button(self.power_state, power_label, 0, max_text_len, box)
        self.conveyor_button = self.make_power_button(self.conveyor_state, conveyor_label, 1, max_text_len, box)

        eject_op = self._cfg.operation("eject")
        height = eject_op.height or self.s_72
        width = eject_op.width or self.s_72

        eject_box = Box(box, layout="auto", border=2, grid=[2, 0], align="top")
        tb = Text(eject_box, text=eject_label, align="top", size=self.s_16, underline=True)
        tb.width = max_text_len
        self.eject_button = PushButton(
            eject_box,
            image=self._eject_image,
            align="top",
            height=height,
            width=width,
        )
        self.eject_button.when_left_button_pressed = self.when_pressed
        self.eject_button.when_left_button_released = self.when_released
        self.register_widget(self.eject_state, self.eject_button)

        # Robust initial gating
        self.after_state_change(None, self.power_state)
