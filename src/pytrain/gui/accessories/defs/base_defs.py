#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

from typing import Iterable


def norm_text(s: str) -> str:
    return " ".join(s.strip().lower().split())


def variant_key_from_filename(filename: str) -> str:
    """
    Make a stable key from an image filename.

    Example:
      "Tire-Swing-6-82105.jpg" -> "tire_swing_6_82105"
    """
    base = filename.rsplit(".", 1)[0]
    base = base.replace("-", " ").strip().lower()
    return "_".join(base.split())


def aliases_from_legacy_key(legacy: str) -> tuple[str, ...]:
    """
    Expand a legacy key like 'tire swing 6-82105' into friendly aliases:
      - progressive name phrases: 'tire', 'tire swing'
      - part number: '6-82105', '682105', '82105'
      - full legacy string
    """
    s = norm_text(legacy)
    parts = s.split()
    if len(parts) < 2:
        return (s,)

    pn = parts[-1]  # e.g., 6-82105 or 30-9161
    name_tokens = parts[:-1]

    progressive = [" ".join(name_tokens[:i]) for i in range(1, len(name_tokens) + 1)]

    pn_nodash = pn.replace("-", "")
    pn_short = pn.split("-")[-1] if "-" in pn else pn

    return dedup_preserve_order((*progressive, pn, pn_nodash, pn_short, s))


def dedup_preserve_order(items: Iterable[str]) -> tuple[str, ...]:
    out: list[str] = []
    for x in items:
        if not x:
            continue
        if x not in out:
            out.append(x)
    return tuple(out)


def print_registry_entry(spec: str):
    from ..accessory_registry import AccessoryRegistry

    reg = AccessoryRegistry.get()

    d_spec = reg.get_spec(spec)  # or AccessoryType.FREIGHT
    print(f"{d_spec.type} variants: {len(d_spec.variants)}")
    for v in d_spec.variants:
        print(f"- key={v.key!r} flavor={getattr(v, 'flavor', None)!r}")
        print(f"  display={v.display!r}")
        print(f"  title={v.title!r}")
        print(f"  default={v.default!r}")
        print(f"  image={v.image!r}")
        print(f"  aliases={v.aliases}")
        if isinstance(v.operation_images, dict):
            print(f"  op images={v.operation_images}")
        elif isinstance(v.operation_images, str):
            print(f"  op images={v.operation_images!r}")
        if isinstance(v.operation_labels, dict):
            print(f"  op labels={v.operation_labels}")
        elif isinstance(v.operation_labels, str):
            print(f"  op label={v.operation_labels!r}")
