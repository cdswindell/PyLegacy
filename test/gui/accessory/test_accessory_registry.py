from __future__ import annotations

import pytest

from src.pytrain.gui.accessories.accessory_registry import (
    AccessoryRegistry,
    AccessoryTypeSpec,
    OperationSpec,
    PortBehavior,
    VariantSpec,
)
from src.pytrain.gui.accessories.accessory_type import AccessoryType


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
