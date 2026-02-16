#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations, annotations

from collections import Counter
from dataclasses import replace
from typing import Any, Iterable, Mapping, Sequence, TypeVar

from ..accessory_registry import VariantSpec

T = TypeVar("T")


def _norm_alias(s: str) -> str:
    return " ".join(str(s).strip().lower().split())


def prune_non_unique_variant_aliases(
    variants: Sequence[VariantSpec],
    *,
    keep: Iterable[str] = (),
) -> tuple[VariantSpec, ...]:
    """
    Remove aliases that are NOT unique across variants.

    Rule:
      - If a normalized alias appears in >1 variant, remove it from ALL variants.
      - `keep` are aliases that should never be removed (rare; usually leave empty).

    Returns a new tuple of VariantSpec with updated aliases (dataclasses.replace()).
    """
    keep_norm = {_norm_alias(x) for x in keep if isinstance(x, str) and x.strip()}

    # Count aliases across all variants
    counts: Counter[str] = Counter()
    for v in variants:
        for a in v.aliases:
            na = _norm_alias(a)
            if na:
                counts[na] += 1

    # Aliases to drop everywhere (except those in keep)
    drop = {a for a, c in counts.items() if c > 1 and a not in keep_norm}

    pruned: list[VariantSpec] = []
    for v in variants:
        new_aliases: list[str] = []
        seen: set[str] = set()
        for a in v.aliases:
            na = _norm_alias(a)
            if not na or na in drop:
                continue
            if na in seen:
                continue
            seen.add(na)
            # Keep original string form (but de-duped by normalized form)
            new_aliases.append(a)
        pruned.append(replace(v, aliases=tuple(new_aliases)))

    return tuple(pruned)


def norm_text(s: str) -> str:
    return " ".join(s.strip().lower().split())


def _norm_key(s: str) -> str:
    return " ".join(str(s).strip().lower().split())


def _iter_alias_values(v: Any) -> Iterable[str]:
    """
    Accept a str, list/tuple/set of strs, etc. Yield strings only.
    """
    if v is None:
        return ()
    if isinstance(v, str):
        return (v,)
    if isinstance(v, (list, tuple, set, frozenset)):
        return tuple(x for x in v if isinstance(x, str))
    # ignore unsupported shapes
    return ()


def extra_aliases_from_module(
    module_globals: Mapping[str, Any],
    *,
    legacy_key: str | None = None,
    filename: str | None = None,
    title: str | None = None,
) -> tuple[str, ...]:
    """
    Look for a module-level dict named ALIASES and return additional aliases.

    Expected ALIASES shapes (any of these):
      - {"lionelville culvert loader 6-82029": {"loader", "lionelville loader"}}
      - {"Lionelville-Culvert-Unloader-6-82030.jpg": {"unloader", "lionelville unloader"}}

    Matching is case/space-insensitive and tries (in order):
      - legacy_key
      - filename
      - title

    Returns a de-duped tuple preserving order.
    """
    aliases_map = module_globals.get("ALIASES")
    if not isinstance(aliases_map, dict):
        return ()

    needles: list[str] = []
    if legacy_key:
        needles.append(_norm_key(legacy_key))
    if filename:
        needles.append(_norm_key(filename))
        # also try basename without extension as a convenience
        if "." in filename:
            needles.append(_norm_key(filename.rsplit(".", 1)[0]))
    if title:
        needles.append(_norm_key(title))

    if not needles:
        return ()

    out: list[str] = []

    for k, v in aliases_map.items():
        nk = _norm_key(k)
        if any(n == nk for n in needles):
            for a in _iter_alias_values(v):
                na = _norm_key(a)
                if na and na not in out:
                    out.append(na)

    return tuple(out)


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
    d_spec = reg.get_spec(spec)

    print(f"Accessory: {d_spec.display_name} Op Btn: {d_spec.op_btn_image}")
    print(f"{d_spec.type} operations: {len(d_spec.operations)} variants: {len(d_spec.variants)}")
    print("Operations:")
    for o in d_spec.operations:
        print(f"- key={o.key!r}")
        print(f"  label={o.label!r}")
        print(f"  behavior={o.behavior.name!r}")
        if o.image:
            print(f"  image={o.image}")
        if o.on_image:
            print(f"  image={o.on_image}")
        if o.off_image:
            print(f"  image={o.off_image}")
    print("\nVariants:")
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
