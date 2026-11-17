from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from src.pytrain.gui.accessories.accessory_base import AccessoryBase
from src.pytrain.gui.accessories.accessory_gui_catalog import AccessoryGuiCatalog
from src.pytrain.gui.accessories.accessory_registry import (
    AccessoryRegistry,
    AccessoryTypeSpec,
    OperationSpec,
    PortBehavior,
    VariantSpec,
)
from src.pytrain.gui.accessories.accessory_type import AccessoryType
from src.pytrain.gui.accessories.configured_accessory import ConfiguredAccessory
from src.pytrain.protocol.tmcc1.tmcc1_constants import TMCC1AuxCommandEnum as Aux


@pytest.fixture()
def reg() -> AccessoryRegistry:
    r = AccessoryRegistry.get()
    r.reset_for_tests()
    return r


def _mk_spec(
    *,
    type_: AccessoryType,
    variants: list[VariantSpec],
    operations: list[OperationSpec] | None = None,
) -> AccessoryTypeSpec:
    if operations is None:
        operations = [
            OperationSpec(
                key="power",
                label="Power",
                behavior=PortBehavior.LATCH,
                off_image="off.png",
                on_image="on.png",
            ),
            OperationSpec(
                key="action",
                label="Action",
                behavior=PortBehavior.MOMENTARY_PULSE,
                image="action.png",
            ),
        ]
    return AccessoryTypeSpec(
        type=type_,
        display_name=type_.name.title(),
        operations=tuple(operations),
        variants=tuple(variants),
    )


def test_register_and_duplicate_type_rejected(reg: AccessoryRegistry) -> None:
    spec = _mk_spec(
        type_=AccessoryType.PLAYGROUND,
        variants=[
            VariantSpec(key="v1", display="V1", title="V1", image="v1.jpg", default=True),
        ],
    )
    reg.register(spec)

    with pytest.raises(ValueError, match="already registered"):
        reg.register(spec)


def test_default_variant_explicit_default(reg: AccessoryRegistry) -> None:
    spec = _mk_spec(
        type_=AccessoryType.PLAYGROUND,
        variants=[
            VariantSpec(key="a", display="A", title="A", image="a.jpg"),
            VariantSpec(key="b", display="B", title="B", image="b.jpg", default=True),
        ],
    )
    reg.register(spec)

    d = reg.get_definition(AccessoryType.PLAYGROUND, None)
    assert d.variant.key == "b"


def test_default_variant_fallback_first(reg: AccessoryRegistry) -> None:
    spec = _mk_spec(
        type_=AccessoryType.PLAYGROUND,
        variants=[
            VariantSpec(key="a", display="A", title="A", image="a.jpg"),
            VariantSpec(key="b", display="B", title="B", image="b.jpg"),
        ],
    )
    reg.register(spec)

    d = reg.get_definition(AccessoryType.PLAYGROUND, None)
    assert d.variant.key == "a"


def test_resolve_variant_by_key_display_title_alias(reg: AccessoryRegistry) -> None:
    spec = _mk_spec(
        type_=AccessoryType.PLAYGROUND,
        variants=[
            VariantSpec(
                key="tire_swing",
                display="Tire Swing",
                title="Tire Swing",
                image="Tire-Swing.jpg",
                aliases=("82105", "tire", "tire swing 6-82105"),
                default=True,
            ),
            VariantSpec(
                key="tug_of_war",
                display="Tug of War",
                title="Tug of War",
                image="Tug.jpg",
                aliases=("82107", "tug"),
            ),
        ],
    )
    reg.register(spec)

    # key
    assert reg.get_definition(AccessoryType.PLAYGROUND, "tire_swing").variant.key == "tire_swing"
    # display
    assert reg.get_definition(AccessoryType.PLAYGROUND, "Tire Swing").variant.key == "tire_swing"
    # title
    assert reg.get_definition(AccessoryType.PLAYGROUND, "tug of war").variant.key == "tug_of_war"
    # alias
    assert reg.get_definition(AccessoryType.PLAYGROUND, "82107").variant.key == "tug_of_war"


def test_resolve_variant_substring_match(reg: AccessoryRegistry) -> None:
    spec = _mk_spec(
        type_=AccessoryType.PLAYGROUND,
        variants=[
            VariantSpec(
                key="one",
                display="Alpha Playground",
                title="Alpha Playground",
                image="a.jpg",
                aliases=("alpha",),
                default=True,
            ),
            VariantSpec(
                key="two", display="Beta Playground", title="Beta Playground", image="b.jpg", aliases=("beta",)
            ),
        ],
    )
    reg.register(spec)

    # substring "bet" should match Beta
    assert reg.get_definition(AccessoryType.PLAYGROUND, "bet").variant.key == "two"


def test_get_definition_bundles_operation_images_override(reg: AccessoryRegistry) -> None:
    # OperationSpec defaults (these should be overridden by variant.operation_images)
    ops = [
        OperationSpec(
            key="power",
            label="Power",
            behavior=PortBehavior.LATCH,
            off_image="power_off_default.png",
            on_image="power_on_default.png",
        ),
        OperationSpec(
            key="motion",
            label="Motion",
            behavior=PortBehavior.MOMENTARY_HOLD,
            image="motion_default.gif",
        ),
    ]

    spec = _mk_spec(
        type_=AccessoryType.PLAYGROUND,
        operations=ops,
        variants=[
            VariantSpec(
                key="v1",
                display="V1",
                title="V1",
                image="v1.jpg",
                default=True,
                operation_images={
                    # latch override: off/on
                    "power": {"off": "power_off_override.png", "on": "power_on_override.png"},
                    # momentary override: string
                    "motion": "motion_override.gif",
                },
            ),
        ],
    )
    reg.register(spec)

    d = reg.get_definition(AccessoryType.PLAYGROUND, None)
    by_key = {o.key: o for o in d.operations}

    assert by_key["power"].off_image == "power_off_override.png"
    assert by_key["power"].on_image == "power_on_override.png"
    assert by_key["motion"].image == "motion_override.gif"


def test_operation_label_override(reg: AccessoryRegistry) -> None:
    spec = _mk_spec(
        type_=AccessoryType.PLAYGROUND,
        variants=[
            VariantSpec(
                key="v1",
                display="V1",
                title="V1",
                image="v1.jpg",
                default=True,
                operation_labels={"action": "Do Thing"},
            )
        ],
    )
    reg.register(spec)

    s = reg.get_spec(AccessoryType.PLAYGROUND)
    v = s.variants[0]

    assert reg.get_operation_label(s, "action", variant=v) == "Do Thing"
    assert reg.get_operation_label(s, "power", variant=v) == "Power"  # fallback

    d = reg.get_definition(AccessoryType.PLAYGROUND, None)
    labels = reg.operation_labels(d)
    assert labels["action"] == "Do Thing"
    assert labels["power"] == "Power"


@pytest.mark.parametrize(
    ("gates", "message"),
    [
        (("missing", None), "unknown key 'missing'"),
        (("   ", None), "unknown key"),
        ((42, None), "unknown key"),
        ((" POWER ", None), "Power gate cycle"),
        (("action", "power"), "Power gate cycle"),
    ],
)
def test_invalid_power_gates_are_rejected(reg: AccessoryRegistry, gates: tuple[Any, str | None], message: str) -> None:
    spec = _mk_spec(
        type_=AccessoryType.PLAYGROUND,
        variants=[],
        operations=[
            OperationSpec("power", "Power", PortBehavior.LATCH, gated_by=gates[0]),
            OperationSpec("action", "Action", PortBehavior.LATCH, gated_by=gates[1]),
        ],
    )
    with pytest.raises(ValueError, match=message):
        reg.register(spec)


def test_power_gate_resolves_case_insensitively_even_when_declared_later(reg: AccessoryRegistry) -> None:
    spec = _mk_spec(
        type_=AccessoryType.PLAYGROUND,
        variants=[VariantSpec(key="v1", display="V1", title="V1", image="v1.jpg")],
        operations=[
            OperationSpec("action", "Action", PortBehavior.LATCH, gated_by=" POWER "),
            OperationSpec("power", "Power", PortBehavior.LATCH),
        ],
    )
    reg.register(spec)
    definition = reg.get_definition(spec.type, None)
    assert definition.operations[0].gated_by == " POWER "


@pytest.mark.parametrize(
    ("behavior", "metadata", "message"),
    [
        (PortBehavior.COMMAND, {}, "requires command"),
        (PortBehavior.COMMAND, {"command_on": Aux.AUX_NUMBER_9}, "requires command"),
        (PortBehavior.COMMAND, {"command_off": Aux.AUX_NUMBER_8}, "requires command"),
        (
            PortBehavior.COMMAND,
            {"command_on": "AUX_NUMBER_9", "command_off": Aux.AUX_NUMBER_8},
            "CommandDefEnum members",
        ),
        (
            PortBehavior.COMMAND,
            {"command_on": Aux.AUX_NUMBER_9, "command_off": 8},
            "CommandDefEnum members",
        ),
        (PortBehavior.COMMAND, {"command": "BRAKE"}, "CommandDefEnum members"),
        (
            PortBehavior.COMMAND,
            {"command": Aux.BRAKE, "command_on": Aux.AUX_NUMBER_9, "command_off": Aux.AUX_NUMBER_8},
            "cannot combine",
        ),
        (PortBehavior.COMMAND, {"command": Aux.RELATIVE_SPEED}, "requires valid integer command_data"),
        (
            PortBehavior.COMMAND,
            {"command": Aux.RELATIVE_SPEED, "command_data": True},
            "requires valid integer command_data",
        ),
        (
            PortBehavior.COMMAND,
            {"command": Aux.RELATIVE_SPEED, "command_data": 20},
            "requires valid integer command_data",
        ),
        (PortBehavior.COMMAND, {"command": Aux.BRAKE, "command_data": 1}, "does not accept command_data"),
        (
            PortBehavior.COMMAND,
            {"command_on": Aux.NUMERIC, "command_off": Aux.AUX_NUMBER_8},
            "must encode their own data",
        ),
        (PortBehavior.COMMAND, {"command": Aux.BRAKE, "repeat": 0}, "positive integer in milliseconds"),
        (PortBehavior.COMMAND, {"command": Aux.BRAKE, "repeat": True}, "positive integer in milliseconds"),
        (PortBehavior.COMMAND, {"command": Aux.BRAKE, "repeat": 100.5}, "positive integer in milliseconds"),
        (PortBehavior.COMMAND, {"command": Aux.BRAKE, "repeat": -100}, "positive integer in milliseconds"),
        (PortBehavior.LATCH, {"command": Aux.BRAKE}, "must use COMMAND"),
        (
            PortBehavior.MOMENTARY_PULSE,
            {"command_on": Aux.AUX_NUMBER_9, "command_off": Aux.AUX_NUMBER_8},
            "must use COMMAND",
        ),
        (PortBehavior.LATCH, {"command_data": 1}, "must use COMMAND"),
        (PortBehavior.MOMENTARY_HOLD, {"repeat": 100}, "must use COMMAND"),
    ],
)
def test_invalid_command_metadata_is_rejected(
    reg: AccessoryRegistry, behavior: PortBehavior, metadata: dict[str, Any], message: str
) -> None:
    spec = _mk_spec(
        type_=AccessoryType.PLAYGROUND,
        variants=[],
        operations=[OperationSpec("action", "Action", behavior, **metadata)],
    )
    with pytest.raises(ValueError, match=message):
        reg.register(spec)


def test_builtin_power_gates_and_command_bindings_are_exposed_in_resolved_operations(reg: AccessoryRegistry) -> None:
    reg.bootstrap()
    for accessory_type, action in (
        (AccessoryType.FIRE_STATION, "alarm"),
        (AccessoryType.GAS_STATION, "action"),
        (AccessoryType.CONTROL_TOWER, "action"),
        (AccessoryType.FREIGHT_DEPOT, "load"),
        (AccessoryType.HOBBY_SHOP, "action"),
        (AccessoryType.MILK_LOADER, "eject"),
        (AccessoryType.STATION, "platform"),
    ):
        operations = {op.key: op for op in reg.get_definition(accessory_type, None).operations}
        assert operations[action].gated_by == "power"
        assert operations["power"].gated_by is None
        assert operations["power"].pulse_duration is None
        if "conveyor" in operations:
            assert operations["conveyor"].gated_by is None

    station = reg.get_definition(AccessoryType.STATION, None)
    platform = next(op for op in station.operations if op.key == "platform")
    assert platform.behavior == PortBehavior.LATCH
    assert platform.pulse_duration is None

    operations = {op.key: op for op in reg.get_definition(AccessoryType.SMOKE_FLUID_LOADER, None).operations}
    assert operations["lights"].command_on is Aux.AUX_NUMBER_9
    assert operations["lights"].command_off is Aux.AUX_NUMBER_8
    assert operations["lights"].repeat is None
    for key, speed in (("boom_left", 2), ("boom_right", -2)):
        assert operations[key].command is Aux.RELATIVE_SPEED
        assert operations[key].command_data == speed
        assert operations[key].repeat == 100
    assert operations["dispense"].command is Aux.BRAKE
    assert operations["dispense"].pulse_duration is None


@pytest.mark.parametrize("duration", [0, 0.5, 250.0, 251, 2560, True])
def test_invalid_asc2_pulse_duration_is_rejected(reg: AccessoryRegistry, duration: Any) -> None:
    spec = _mk_spec(
        type_=AccessoryType.FIRE_STATION,
        variants=[],
        operations=[OperationSpec("alarm", "Alarm", PortBehavior.MOMENTARY_PULSE, pulse_duration=duration)],
    )
    with pytest.raises(ValueError, match="pulse_duration must be"):
        reg.register(spec)


def test_pulse_duration_requires_pulse_behavior(reg: AccessoryRegistry) -> None:
    spec = _mk_spec(
        type_=AccessoryType.FIRE_STATION,
        variants=[],
        operations=[OperationSpec("power", "Power", PortBehavior.LATCH, pulse_duration=250)],
    )
    with pytest.raises(ValueError, match="must use MOMENTARY_PULSE"):
        reg.register(spec)


@pytest.mark.parametrize("duration", [None, 10, 250, 2550])
def test_resolved_operation_keeps_pulse_duration(reg: AccessoryRegistry, duration: int | None) -> None:
    spec = _mk_spec(
        type_=AccessoryType.FIRE_STATION,
        variants=[VariantSpec(key="v1", display="V1", title="V1", image="v1.jpg")],
        operations=[OperationSpec("alarm", "Alarm", PortBehavior.MOMENTARY_PULSE, pulse_duration=duration)],
    )
    reg.register(spec)
    expected = 200 if duration is None else duration
    assert spec.operations[0].pulse_duration == expected
    assert reg.get_definition(spec.type, None).operations[0].pulse_duration == expected


@pytest.mark.parametrize(
    ("addresses", "expected"),
    [
        ({"tmcc_id": 60}, 60),
        ({"tmcc_ids": {"action": 61}}, 61),
        ({"tmcc_id": 60, "tmcc_ids": {"action": 61}}, 61),
    ],
)
def test_legacy_culvert_gui_binds_configured_address(
    reg: AccessoryRegistry, addresses: dict[str, Any], expected: int
) -> None:
    reg.bootstrap()
    configured = ConfiguredAccessory({"gui": "culvert", **addresses}, reg, AccessoryGuiCatalog())

    with patch.object(AccessoryBase, "__init__", return_value=None):
        gui = configured.create_gui(aggregator=None)

    # Inspect the resolved address without starting Tk or layout communication.
    # noinspection PyProtectedMember
    assert gui._action == expected
