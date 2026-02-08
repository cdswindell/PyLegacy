#!/usr/bin/env python3
#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from src.pytrain.gui.accessories.accessory_gui import DEFAULT_CONFIG_FILE
from src.pytrain.gui.accessories.accessory_gui_catalog import AccessoryGuiCatalog
from src.pytrain.gui.accessories.accessory_registry import AccessoryRegistry, PortBehavior
from src.pytrain.gui.accessories.accessory_type import AccessoryType


# -----------------------------------------------------------------------------
# Small helpers
# -----------------------------------------------------------------------------


def _norm(s: str) -> str:
    return " ".join(str(s).strip().lower().split())


def _ask(prompt: str, *, default: str | None = None) -> str:
    if default is None:
        s = input(f"{prompt}: ").strip()
    else:
        s = input(f"{prompt} [{default}]: ").strip()
        if not s:
            s = default
    return s


def _ask_int(
    prompt: str, *, default: int | None = None, min_value: int | None = 1, max_value: int | None = 98
) -> int | None:
    while True:
        s = _ask(prompt, default=str(default) if default is not None else None)
        try:
            v = int(s)
            if min_value is not None and v < min_value:
                print(f"  Please enter an integer between {min_value} and {max_value}.")
                continue
            if max_value is not None and v > max_value:
                print(f"  Please enter an integer between {min_value} and {max_value}.")
                continue
            return v
        except ValueError:
            print("  Please enter a valid integer.")


def _ask_choice_index(prompt: str, choices: list[str], *, default_index: int | None = None) -> int | None:
    """
    Returns index into `choices`.
    Accepts: 1-based index or substring match.
    """
    if not choices:
        raise ValueError("No choices available")

    while True:
        default_txt = None
        if default_index is not None and 0 <= default_index < len(choices):
            default_txt = str(default_index + 1)

        s = _ask(prompt, default=default_txt)
        s_norm = _norm(s)

        # 1-based numeric selection
        if s_norm.isdecimal():
            idx = int(s_norm) - 1
            if 0 <= idx < len(choices):
                return idx
            print(f"  Choose 1..{len(choices)}")
            continue

        # substring match
        matches = [i for i, c in enumerate(choices) if s_norm in _norm(c)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            print("  Ambiguous; matches:")
            for i in matches:
                print(f"   - {i + 1}) {choices[i]}")
            continue

        print("  Invalid selection.")


def _dedup_preserve(items: Iterable[str]) -> list[str]:
    """Deduplicates items while preserving original order"""
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        nx = _norm(x)
        if not nx or nx in seen:
            continue
        seen.add(nx)
        out.append(x)
    return out


def _make_instance_id(
    gui_key: str, variant_key: str | None, *, tmcc_ids: dict[str, int] | None, tmcc_id: int | None
) -> str:
    """
    Human-readable, deterministic-ish.
      - includes gui key
      - includes variant keys (short)
      - includes TMCC ids (sorted by op key) and/or the accessory tmcc_id
    """
    parts: list[str] = [_norm(gui_key).replace(" ", "_")]

    if variant_key:
        vk = _norm(variant_key).replace(" ", "_")
        # keep it from getting silly-long
        if len(vk) > 24:
            vk = vk[:24]
        parts.append(vk)

    nums: list[str] = []
    if tmcc_id is not None:
        nums.append(str(tmcc_id))

    # Appends sorted TMCC IDs to numeric parts
    if tmcc_ids:
        for _, v in sorted(
            tmcc_ids.items(),
            key=lambda kv: int(kv[1]),
        ):
            nums.append(str(int(v)))

    if nums:
        parts.append("-".join(nums))

    return "_".join(parts)


# -----------------------------------------------------------------------------
# Config model we emit for EngineGui
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class AccessoryConfig:
    """
    What we serialize.

    - gui: the short key from AccessoryGuiCatalog ("milk", "gas", ...)
    - type: AccessoryType name (string) so you can resolve in EngineGui
    - variant: variant key (stable)
    - instance_id: human readable id
    - tmcc_ids: per-operation ids (ASC2-style)
    - tmcc_id: overall tmcc id for COMMAND-style accessories (optional)
    """

    gui: str
    type: str
    variant: str
    instance_id: str
    tmcc_ids: dict[str, int] | None = None
    tmcc_id: int | None = None
    display_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "gui": self.gui,
            "type": self.type,
            "variant": self.variant,
            "instance_id": self.instance_id,
        }
        if self.tmcc_ids:
            d["tmcc_ids"] = self.tmcc_ids
        if self.tmcc_id is not None:
            d["tmcc_id"] = self.tmcc_id
        if self.display_name:
            d["display_name"] = self.display_name
        return d


# -----------------------------------------------------------------------------
# Catalog / registry integration
# -----------------------------------------------------------------------------


# noinspection PyTypeChecker
def _catalog_entries(catalog: AccessoryGuiCatalog) -> list[Any]:
    """
    Returns a list of catalog entries.

    Tries common public APIs first; falls back to internal storage.
    """
    for attr in ("entries", "all_entries", "list_entries"):
        fn = getattr(catalog, attr, None)
        if callable(fn):
            v = fn()
            if isinstance(v, dict):
                return list(v.values())
            return list(v)

    # fallback: internal dict
    d = getattr(catalog, "_entries", None)
    if isinstance(d, dict):
        return list(d.values())

    raise RuntimeError("AccessoryConfig: cannot enumerate entries (no entries() and no _entries)")


def _entry_key(entry: Any) -> str:
    return getattr(entry, "key", None) or getattr(entry, "name", None) or str(entry)


def _entry_type(entry: Any) -> AccessoryType:
    t = getattr(entry, "accessory_type", None) or getattr(entry, "type", None)
    if not isinstance(t, AccessoryType):
        raise RuntimeError(f"Catalog entry {_entry_key(entry)!r} has no AccessoryType")
    return t


# -----------------------------------------------------------------------------
# Interactive prompts
# -----------------------------------------------------------------------------


def prompt_accessory(catalog: AccessoryGuiCatalog, registry: AccessoryRegistry) -> AccessoryConfig:
    entries = _catalog_entries(catalog)
    labels = [f"{_entry_type(e).clean_title}" for e in entries]

    print("\nAccessory type:")
    for i, lab in enumerate(labels, start=1):
        print(f"  {i}) {lab}")

    idx = _ask_choice_index("Choose accessory", labels)
    entry = entries[idx]
    gui_key = _entry_key(entry)
    acc_type = _entry_type(entry)

    # Registry spec + variants
    spec = registry.get_spec(acc_type)
    variants = list(spec.variants)

    if not variants:
        raise RuntimeError(f"{acc_type.name}: no variants registered")

    # auto-select if only one variant
    if len(variants) == 1:
        vs = variants[0]
        print(f"Variant: only one available -> {vs.display} ({vs.key})")
    else:
        print("\nVariant:")
        v_labels = [f"{v.display}  [{v.key}]" for v in variants]
        for i, lab in enumerate(v_labels, start=1):
            mark = " (default)" if getattr(variants[i - 1], "default", False) else ""
            print(f"  {i}) {lab}{mark}")
        # default index if present
        default_idx = next((i for i, v in enumerate(variants) if getattr(v, "default", False)), 0)
        vid_x = _ask_choice_index("Choose variant", v_labels, default_index=default_idx)
        vs = variants[vid_x]

    variant_key = vs.key

    # Determine if this accessory has COMMAND-style ops
    # If so, we ask once for "accessory tmcc id", and we *do not* ask per-op TMCC ids for COMMAND ops.
    has_command_ops = any(op.behavior == PortBehavior.COMMAND for op in spec.operations)

    tmcc_ids: dict[str, int] = {}
    tmcc_id_overall: int | None = None

    if has_command_ops:
        # overall id for the command accessory
        tmcc_id_overall = _ask_int(f"TMCC ID for {gui_key} ({acc_type.name})")

    # Per-operation ids (skip COMMAND ops)
    for op in spec.operations:
        if op.behavior == PortBehavior.COMMAND:
            # user explicitly requested: omit prompt for TMCC ID for COMMAND ops
            continue
        tmcc_ids[op.key] = _ask_int(f"TMCC ID for operation '{op.key}' ({op.label})")

    # Optional display name override
    default_display_name = vs.title
    display_name = _ask(
        "Display name override (leave blank to use default)",
        default=default_display_name,
    ).strip()

    # If unchanged, omit from config so EngineGui uses registry default
    if display_name == default_display_name:
        display_name = None

    # Auto instance_id (human-readable) based on ids
    instance_id = _make_instance_id(
        gui_key=gui_key,
        variant_key=variant_key,
        tmcc_ids=tmcc_ids if tmcc_ids else None,
        tmcc_id=tmcc_id_overall,
    )

    # sanity: duplicate instance_id is annoying
    print(f"instance_id -> {instance_id}")

    return AccessoryConfig(
        gui=gui_key,
        type=acc_type.name.lower(),
        variant=variant_key,
        instance_id=instance_id,
        tmcc_ids=tmcc_ids if tmcc_ids else None,
        tmcc_id=tmcc_id_overall,
        display_name=display_name,
    )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    default = DEFAULT_CONFIG_FILE
    ap = argparse.ArgumentParser(
        description="Interactive builder for accessory config (JSON).",
    )
    ap.add_argument(
        "-o",
        "--out",
        default=default,
        help=f"Output JSON path (default: {default!r})",
    )
    ap.add_argument(
        "--append",
        action="store_true",
        help="Append to existing file (if present) instead of overwriting.",
    )
    args = ap.parse_args(argv)

    out_path = Path(args.out)

    catalog = AccessoryGuiCatalog()
    registry = AccessoryRegistry.get()
    registry.bootstrap()

    existing: list[dict[str, Any]] = []
    if args.append and out_path.exists():
        try:
            existing_obj = json.loads(out_path.read_text(encoding="utf-8"))
            if isinstance(existing_obj, dict) and isinstance(existing_obj.get("accessories"), list):
                existing = list(existing_obj["accessories"])
            elif isinstance(existing_obj, list):
                existing = list(existing_obj)
            else:
                print("Warning: existing JSON shape not recognized; starting fresh.")
        except Exception as e:
            print(f"Warning: failed to read existing JSON ({e}); starting fresh.")

    accessories: list[AccessoryConfig] = []
    seen_instance_ids = {a.get("instance_id") for a in existing if isinstance(a, dict)}

    print("Accessory Configurator")
    print("Press Ctrl+C to quit at any prompt.\n")
    try:
        while True:
            cfg = prompt_accessory(catalog, registry)

            if cfg.instance_id in seen_instance_ids:
                print(f"Error: duplicate instance_id: {cfg.instance_id}")
                print("Pick a different variant/IDs or edit the JSON later.\n")
                continue

            seen_instance_ids.add(cfg.instance_id)
            accessories.append(cfg)

            more = _ask("Add another accessory? (y/n)", default="y")
            if _norm(more) not in ("y", "yes"):
                break
    except (KeyboardInterrupt, EOFError):
        pass

    payload = {
        "schema": "pytrain.accessory_config.v1",
        "accessories": [*existing, *(a.to_dict() for a in accessories)],
    }
    if accessories:
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"\nWrote: {out_path.resolve()}")
        print(f"Accessories: {len(payload['accessories'])}")
    else:
        print("\nNo accessories configured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
