#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from .base_defs import aliases_from_legacy_key, dedup_preserve_order, variant_key_from_filename
from ..accessory_registry import (
    AccessoryRegistry,
    AccessoryTypeSpec,
    OperationSpec,
    PortBehavior,
    VariantSpec,
)
from ..accessory_type import AccessoryType

"""
Playground accessory definition (GUI-agnostic).

Ports / operations:
  - motion: momentary_hold (press/release)

Per-variant overrides:
  - motion image comes from _MOTION_IMAGE[variant_image]
  - motion label comes from _MOTION_TEXT[variant_image] via VariantSpec.operation_labels
"""

# Source data you provided
_VARIANTS = {
    "tire swing 6-82105": "Tire-Swing-6-82105.jpg",
    "tug of war 6-82107": "Tug-of-War-6-82107.jpg",
    "Playground-6-82104.jpg": "Playground-6-82104.jpg",
    "Swing-6-14199.jpg": "Swing-6-14199.jpg",
}

_TITLES = {
    "Tire-Swing-6-82105.jpg": "Tire Swing",
    "Tug-of-War-6-82107.jpg": "Tug of War",
    "Playground-6-82104.jpg": "Playground",
    "Swing-6-14199.jpg": "Swings",
}

_MOTION_IMAGE = {
    "Tire-Swing-6-82105.jpg": "tire-swing-child.jpg",
    "Tug-of-War-6-82107.jpg": "tug-of-war.jpg",
    "Playground-6-82104.jpg": "motion.gif",
    "Swing-6-14199.jpg": "swing.gif",
}

_MOTION_TEXT = {
    "Tire-Swing-6-82105.jpg": "Swing",
    "Tug-of-War-6-82107.jpg": "Pull",
    "Playground-6-82104.jpg": "Motion",
    "Swing-6-14199.jpg": "Swing",
}

DEFAULT_PLAYGROUND = "Playground-6-82104.jpg"


def register_playground(registry: AccessoryRegistry) -> None:
    """
    Register Playground accessory type metadata.
    """
    operations = (
        OperationSpec(
            key="motion",
            label="Action",
            behavior=PortBehavior.MOMENTARY_HOLD,
            image="motion.gif",  # default (overridden per-variant)
            width=72,
            height=72,
        ),
    )

    variants: list[VariantSpec] = []
    for legacy_name, filename in _VARIANTS.items():
        title = _TITLES.get(filename, filename.rsplit(".", 1)[0])
        motion_image = _MOTION_IMAGE.get(filename)
        motion_label = _MOTION_TEXT.get(filename)

        # Allow both “legacy key style” and “filename as key” inputs
        legacy_aliases = aliases_from_legacy_key(legacy_name) if " " in legacy_name else (legacy_name.strip().lower(),)

        # Extra helpful aliases
        base_no_ext = filename.rsplit(".", 1)[0]
        extra_aliases = (title, title.lower(), base_no_ext.lower(), filename.lower())

        op_images = {"motion": motion_image} if motion_image else None
        op_labels = {"motion": motion_label} if motion_label else None

        variants.append(
            VariantSpec(
                key=variant_key_from_filename(filename),
                display=title,
                title=title,
                image=filename,
                default=(filename == DEFAULT_PLAYGROUND),
                aliases=dedup_preserve_order((*legacy_aliases, *extra_aliases)),
                operation_images=op_images,
                operation_labels=op_labels,
            )
        )

    spec = AccessoryTypeSpec(
        type=AccessoryType.PLAYGROUND,
        display_name="Playground",
        operations=operations,
        variants=tuple(variants),
    )

    registry.register(spec)


if __name__ == "__main__":  # pragma: no cover
    reg = AccessoryRegistry.get()
    reg.reset_for_tests()

    register_playground(reg)

    d_spec = reg.get_spec("playground")
    print(f"{d_spec.type} variants: {len(d_spec.variants)}")
    for v in d_spec.variants:
        print(f"- key={v.key!r} default={getattr(v, 'default', False)!r}")
        print(f"  display={v.display!r}")
        print(f"  title={v.title!r}")
        print(f"  image={v.image!r}")
        print(f"  aliases={v.aliases}")
        print(f"  op images={v.operation_images}")
        print(f"  op labels={v.operation_labels}")
