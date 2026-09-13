"""Toolkit-neutral equipment operation capabilities.

These tags are extracted from EngineGui's ENGINE_OPS_LAYOUT. They describe which
families of operations apply to each ControllerView equipment type without
carrying any GuiZero layout or widget information into the presentation-neutral
layer.

Protocol-level controls such as TMCC2 train brake and quilling horn deliberately
do not live here; those are resolved from TMCC generation in profiles.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EquipmentCapabilities:
    type_key: str
    operation_tags: frozenset[str]

    def supports_tag(self, tag: str) -> bool:
        return tag == "*" or tag in self.operation_tags


_EQUIPMENT_CAPABILITIES: dict[str, EquipmentCapabilities] = {
    "a": EquipmentCapabilities("a", frozenset({"vo", "e", "bs", "d", "a"})),
    "d": EquipmentCapabilities("d", frozenset({"c", "vo", "cp", "e", "bs", "sm", "d"})),
    "f": EquipmentCapabilities("f", frozenset({"c", "vo", "cp", "pf", "f"})),
    "l": EquipmentCapabilities("l", frozenset({"c", "vo", "cp", "e", "l"})),
    "p": EquipmentCapabilities("p", frozenset({"c", "vo", "cp", "pf", "p"})),
    "s": EquipmentCapabilities("s", frozenset({"c", "vo", "cp", "e", "bs", "sm", "s"})),
    "r": EquipmentCapabilities("r", frozenset({"c", "vo", "cp", "r"})),
    "t": EquipmentCapabilities("t", frozenset({"t"})),
}


def equipment_capabilities(type_key: str) -> EquipmentCapabilities:
    """Return the operation-tag capabilities for a ControllerView type key."""
    return _EQUIPMENT_CAPABILITIES.get(type_key, EquipmentCapabilities(type_key, frozenset()))


def operation_tag_applies(tag: str, type_key: str) -> bool:
    """Return whether an ENGINE_OPS_LAYOUT semantic tag applies to a type."""
    return equipment_capabilities(type_key).supports_tag(tag)
