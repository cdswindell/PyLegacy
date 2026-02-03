#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from guizero import Box, PushButton, Text

from ..db.accessory_state import AccessoryState
from ..protocol.command_req import CommandReq
from ..protocol.constants import CommandScope
from ..protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum
from ..utils.path_utils import find_file
from .accessories.accessory_type import AccessoryType
from .accessory_base import AccessoryBase, S
from .accessory_gui import AccessoryGui


class MilkLoaderGui(AccessoryBase):
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
        self._power = power
        self._conveyor = conveyor
        self._eject = eject
        self._variant = variant

        self.power_button = self.conveyor_button = self.eject_button = None
        self.power_state = self.conveyor_state = self.eject_state = None

        # Main title + image from definition variant
        self._title = None
        self._image = None
        self._eject_image = None

        super().__init__(self._title, self._image, aggregator=aggregator)

    def bind_variant(self) -> None:
        # Definition is GUI-agnostic and includes variant + bundled per-operation assets (filenames)
        definition = self.registry.get_definition(AccessoryType.MILK_LOADER, self._variant)
        self.title = self._title = definition.variant.title
        self.image_file = self._image = find_file(definition.variant.image)
        self._eject_image = find_file(self._find_assets(definition, "eject").image)

    @staticmethod
    def _find_assets(definition, key: str):
        nk = " ".join(key.strip().lower().split())
        for op in definition.operations:
            if " ".join(op.key.strip().lower().split()) == nk:
                return op
        raise KeyError(f"MilkLoaderGui: operation assets not found: {key}")

    def get_target_states(self) -> list[S]:
        self.power_state = self._state_store.get_state(CommandScope.ACC, self._power)
        self.conveyor_state = self._state_store.get_state(CommandScope.ACC, self._conveyor)
        self.eject_state = self._state_store.get_state(CommandScope.ACC, self._eject)
        return [
            self.power_state,
            self.conveyor_state,
            self.eject_state,
        ]

    def is_active(self, state: AccessoryState) -> bool:
        return state.is_aux_on

    def switch_state(self, state: AccessoryState) -> None:
        with self._cv:
            if state == self.eject_state:
                # Eject is momentary (press/release handlers)
                return

            # LATCH behavior for power / conveyor
            print(f"MilkLoaderGui: switch_state: {state} {state.is_aux_on}")
            CommandReq(TMCC1AuxCommandEnum.AUX2_OPT_ONE, state.tmcc_id).send()

            if state == self.power_state:
                # If power is off, disable eject; if power is on, enable eject
                print(f"MilkLoaderGui: power_state: {state} {state.is_aux_on}")
                if state.is_aux_on:
                    self.queue_message(lambda: self.eject_button.enable())
                else:
                    self.queue_message(lambda: self.eject_button.disable())

    def build_accessory_controls(self, box: Box) -> None:
        max_text_len = len("Conveyor") + 2
        self.power_button = self.make_power_button(self.power_state, "Power", 0, max_text_len, box)
        self.conveyor_button = self.make_power_button(self.conveyor_state, "Conveyor", 1, max_text_len, box)

        eject_box = Box(box, layout="auto", border=2, grid=[2, 0], align="top")
        tb = Text(eject_box, text="Eject", align="top", size=self.s_16, underline=True)
        tb.width = max_text_len
        self.eject_button = PushButton(
            eject_box,
            image=self._eject_image,
            align="top",
            height=self.s_72,
            width=self.s_72,
        )
        self.eject_button.when_left_button_pressed = self.when_pressed
        self.eject_button.when_left_button_released = self.when_released
        self.register_widget(self.eject_state, self.eject_button)
        if not self.is_active(self.power_state):
            self.eject_button.disable()
