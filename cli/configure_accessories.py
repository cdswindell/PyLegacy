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
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from src.pytrain.gui.accessories.accessory_gui import DEFAULT_CONFIG_FILE
from src.pytrain.gui.accessories.accessory_gui_catalog import AccessoryGuiCatalog
from src.pytrain.gui.accessories.accessory_registry import AccessoryRegistry, PortBehavior
from src.pytrain.gui.accessories.accessory_type import AccessoryType
from src.pytrain.utils.path_utils import find_file  # <-- adjust if needed


def _clean_accessory_list(
    raw: Any,
    *,
    drop_unknown_keys: bool = False,
) -> tuple[list[dict[str, Any]], list[tuple[Any, str]]]:
    """
    Validate and normalize a raw "accessories" list.

    Returns:
      kept: list of normalized dict entries
      removed: list of (original_entry, reason)

    Rules:
      - entry must be a dict
      - must have: gui (str), type (str), variant (str), instance_id (str)
      - optional: tmcc_ids (dict[str, int-like]), tmcc_id (int-like), display_name (str)
      - if drop_unknown_keys=True, unknown keys are removed from kept entries
    """
    if raw is None:
        return [], []

    if isinstance(raw, dict):
        # tolerate people passing the full payload dict
        raw = raw.get("accessories", [])

    if not isinstance(raw, list):
        return [], [(raw, "accessories is not a list")]

    required_str = ("gui", "type", "variant", "instance_id")
    optional_keys = {"tmcc_ids", "tmcc_id", "display_name"}

    kept: list[dict[str, Any]] = []
    removed: list[tuple[Any, str]] = []

    for entry in raw:
        original = entry

        if not isinstance(entry, dict):
            removed.append((original, "entry is not a dict"))
            continue

        # Required string fields
        missing = [k for k in required_str if k not in entry]
        if missing:
            removed.append((original, f"missing required field(s): {', '.join(missing)}"))
            continue

        bad = [k for k in required_str if not isinstance(entry.get(k), str) or not entry.get(k).strip()]
        if bad:
            removed.append((original, f"required field(s) must be non-empty strings: {', '.join(bad)}"))
            continue

        normalized: dict[str, Any] = {k: str(entry[k]).strip() for k in required_str}

        # Optional display_name
        if "display_name" in entry:
            dn = entry["display_name"]
            if dn is None:
                pass
            elif isinstance(dn, str):
                dn2 = dn.strip()
                if dn2:
                    normalized["display_name"] = dn2
            else:
                removed.append((original, "display_name must be a string (or omitted)"))
                continue

        # Optional tmcc_id (overall)
        if "tmcc_id" in entry:
            tid = entry["tmcc_id"]
            if tid is None:
                pass
            else:
                try:
                    normalized["tmcc_id"] = int(tid)
                except (TypeError, ValueError):
                    removed.append((original, "tmcc_id must be int-like"))
                    continue

        # Optional tmcc_ids (per-op)
        if "tmcc_ids" in entry:
            tids = entry["tmcc_ids"]
            if tids is None:
                pass
            elif not isinstance(tids, dict):
                removed.append((original, "tmcc_ids must be a dict (or omitted)"))
                continue
            else:
                out_ids: dict[str, int] = {}
                ok = True
                for k, v in tids.items():
                    if k is None:
                        ok = False
                        break
                    k2 = str(k).strip()
                    if not k2:
                        ok = False
                        break
                    try:
                        out_ids[k2] = int(v)
                    except (TypeError, ValueError):
                        ok = False
                        break

                if not ok:
                    removed.append((original, "tmcc_ids must map non-empty keys to int-like values"))
                    continue

                if out_ids:
                    normalized["tmcc_ids"] = out_ids

        # Optionally drop unknown keys
        if not drop_unknown_keys:
            # Preserve any other keys verbatim (future-proofing), but only if JSON-serializable is your problem
            # If you prefer strictness, enable drop_unknown_keys=True.
            for k, v in entry.items():
                if k in normalized:
                    continue
                if k in optional_keys:
                    continue
                # keep it
                normalized[k] = v

        kept.append(normalized)

    return kept, removed


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
      - includes TMCC ids (sorted numerically) and/or the accessory tmcc_id
    """
    parts: list[str] = [_norm(gui_key).replace(" ", "_")]

    if variant_key:
        vk = _norm(variant_key).replace(" ", "_")
        if len(vk) > 24:
            vk = vk[:24]
        parts.append(vk)

    nums: list[str] = []
    if tmcc_id is not None:
        nums.append(str(tmcc_id))

    # Append sorted TMCC IDs to numeric parts
    if tmcc_ids:
        for _, v in sorted(tmcc_ids.items(), key=lambda kv: int(kv[1])):
            nums.append(str(int(v)))

    if nums:
        parts.append("-".join(nums))

    return "_".join(parts)


# -----------------------------------------------------------------------------
# Existing file resolution + validation/cleanup
# -----------------------------------------------------------------------------


def _resolve_existing_path(out_path: Path) -> Path:
    """
    Determine where we should read from / write to.

    Priority:
      1) If out_path exists as given, use it.
      2) Else try find_file(out_path.name) in project tree.
      3) Else use out_path as provided (new file).
    """
    if out_path.exists():
        return out_path

    found = find_file(out_path.name)
    if found:
        return Path(found)

    return out_path


def _load_existing_payload(path: Path) -> tuple[list[Any], dict[str, Any] | None]:
    """
    Loads existing JSON.

    Returns:
      - existing accessories list (may contain non-dicts before validation)
      - full payload dict if the source was dict-shaped, else None
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Warning: failed to read existing JSON from {path} ({e}); treating as empty.")
        return [], None

    if not raw.strip():
        return [], None

    try:
        obj = json.loads(raw)
    except Exception as e:
        print(f"Warning: failed to parse existing JSON from {path} ({e}); treating as empty.")
        return [], None

    if isinstance(obj, dict):
        accessories = obj.get("accessories", [])
        if isinstance(accessories, list):
            return list(accessories), obj
        print("Warning: existing JSON dict did not contain 'accessories' list; treating as empty.")
        return [], obj

    if isinstance(obj, list):
        return list(obj), None

    print("Warning: existing JSON shape not recognized; treating as empty.")
    return [], None


def _as_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().lstrip("-").isdecimal():
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _validate_and_normalize_entry(entry: Any) -> tuple[dict[str, Any] | None, str | None]:
    """
    Returns (clean_entry, error_reason).
    If invalid, clean_entry is None and error_reason is a short string.

    Normalizations:
      - trims required strings
      - coerces tmcc_id to int (if int-like)
      - coerces tmcc_ids values to int (if int-like)
      - drops unknown keys to keep file clean
    """
    if not isinstance(entry, dict):
        return None, "not a dict"

    def _req_str(ke: str) -> str | None:
        ve = entry.get(ke)
        if not isinstance(ve, str):
            return None
        v2 = ve.strip()
        return v2 if v2 else None

    gui = _req_str("gui")
    typ = _req_str("type")
    variant = _req_str("variant")
    instance_id = _req_str("instance_id")

    if not gui:
        return None, "missing/invalid 'gui'"
    if not typ:
        return None, "missing/invalid 'type'"
    if not variant:
        return None, "missing/invalid 'variant'"
    if not instance_id:
        return None, "missing/invalid 'instance_id'"

    tmcc_id_raw = entry.get("tmcc_id", None)
    tmcc_id = _as_int(tmcc_id_raw) if tmcc_id_raw is not None else None
    if tmcc_id_raw is not None and tmcc_id is None:
        return None, "invalid 'tmcc_id' (must be int)"

    tmcc_ids_clean: dict[str, int] | None = None
    if "tmcc_ids" in entry and entry["tmcc_ids"] is not None:
        raw_tmcc_ids = entry.get("tmcc_ids")
        if not isinstance(raw_tmcc_ids, dict):
            return None, "invalid 'tmcc_ids' (must be dict)"
        out: dict[str, int] = {}
        for k, v in raw_tmcc_ids.items():
            if not isinstance(k, str) or not k.strip():
                return None, "invalid tmcc_ids key (must be non-empty str)"
            iv = _as_int(v)
            if iv is None:
                return None, f"invalid tmcc_ids[{k!r}] (must be int)"
            out[k.strip()] = int(iv)
        tmcc_ids_clean = out or None

    display_name = entry.get("display_name")
    if display_name is not None and not isinstance(display_name, str):
        return None, "invalid 'display_name' (must be str)"

    # Keep only known keys (easy to change if you'd rather preserve extras)
    clean: dict[str, Any] = {
        "gui": gui,
        "type": typ,
        "variant": variant,
        "instance_id": instance_id,
    }
    if tmcc_ids_clean:
        clean["tmcc_ids"] = tmcc_ids_clean
    if tmcc_id is not None:
        clean["tmcc_id"] = tmcc_id
    if display_name:
        clean["display_name"] = display_name.strip() or display_name

    return clean, None


def _write_payload(path: Path, accessories: list[dict[str, Any]]) -> None:
    payload = {
        "schema": "pytrain.accessory_config.v1",
        "accessories": accessories,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _open_in_editor(path: Path) -> None:
    """
    Open file in $EDITOR if available; otherwise best-effort platform default.
    Blocks until editor exits.
    """
    editor = os.environ.get("EDITOR")
    if editor:
        try:
            subprocess.call([editor, str(path)])
            return
        except Exception as e:
            print(f"Warning: failed to launch $EDITOR={editor!r}: {e}")

    if sys.platform == "darwin":
        subprocess.call(["open", str(path)])
    elif os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        subprocess.call(["xdg-open", str(path)])


def _startup_existing_file_flow(
    out_path: Path,
    *,
    default_choice: str | None = None,
    verify_existing: bool = False,
    clean_existing: bool = False,
    clean_only: bool = False,
) -> None | tuple[Path, list[Any]] | tuple[Path, list[dict[str, Any]]]:
    """
    If an existing file is present:
      - If it's empty / has no accessories, do NOT prompt; treat as empty and proceed.
      - Otherwise, optionally verify/clean before the normal Clear/Edit/Append prompt.

    Returns:
      (resolved_path, existing_accessories)
    """
    resolved = _resolve_existing_path(out_path)

    if not resolved.exists():
        return resolved, []

    raw_accessories, _payload = _load_existing_payload(resolved)

    kept, removed = _clean_accessory_list(raw_accessories)

    if verify_existing or clean_existing or clean_only:
        if removed:
            print(f"\nExisting config validation: {resolved}")
            print(f"  Total entries: {len(raw_accessories)}")
            print(f"  Valid entries: {len(kept)}")
            print(f"  Removed entries: {len(removed)}")
            reasons: dict[str, int] = {}
            for _, r in removed:
                reasons[r] = reasons.get(r, 0) + 1
            for r, n in sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0])):
                print(f"   - {r}: {n}")
        else:
            print(f"\nExisting config validation: {resolved} (all entries look valid)")

        if clean_existing or clean_only:
            _write_payload(resolved, kept)
            print(f"Cleaned file written: {resolved} (accessories={len(kept)})")

        if clean_only:
            raise SystemExit(0)

    # If empty / no configured accessories, don't prompt
    if len(kept) == 0:
        return resolved, []

    existing = kept

    print(f"\nFound existing config: {resolved}")
    print(f"Existing accessories: {len(existing)}")

    default_choice = _norm(default_choice or "")
    dflt = "A" if default_choice in ("a", "append") else "A"

    try:
        while True:
            choice = _ask("Use existing file? (C)lear / (E)dit / (A)ppend / (Q)uit", default=dflt).strip().lower()

            if choice in ("a", "append", ""):
                return resolved, existing

            if choice in ("c", "clear", "new", "reset"):
                return resolved, []

            if choice in ("e", "edit"):
                if not resolved.exists():
                    _write_payload(resolved, [])
                _open_in_editor(resolved)

                raw2, _ = _load_existing_payload(resolved)
                kept2, removed2 = _clean_accessory_list(raw2)
                if removed2:
                    print(f"Note: after edit, {len(removed2)} malformed entries were ignored.")
                if len(kept2) == 0:
                    return resolved, []
                print(f"Reloaded accessories: {len(kept2)}")
                existing = kept2
                continue

            if choice in ("q", "quit", "exit"):
                raise SystemExit(0)

            print("  Please choose C, E, A, or Q.")
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(0)


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

    spec = registry.get_spec(acc_type)
    variants = list(spec.variants)

    if not variants:
        raise RuntimeError(f"{acc_type.name}: no variants registered")

    if len(variants) == 1:
        vs = variants[0]
        print(f"Variant: only one available -> {vs.display} ({vs.key})")
    else:
        print("\nVariant:")
        v_labels = [f"{v.display}  [{v.key}]" for v in variants]
        for i, lab in enumerate(v_labels, start=1):
            mark = " (default)" if getattr(variants[i - 1], "default", False) else ""
            print(f"  {i}) {lab}{mark}")
        default_idx = next((i for i, v in enumerate(variants) if getattr(v, "default", False)), 0)
        vid_x = _ask_choice_index("Choose variant", v_labels, default_index=default_idx)
        vs = variants[vid_x]

    variant_key = vs.key

    has_command_ops = any(op.behavior == PortBehavior.COMMAND for op in spec.operations)

    tmcc_ids: dict[str, int] = {}
    tmcc_id_overall: int | None = None

    if has_command_ops:
        tmcc_id_overall = _ask_int(f"TMCC ID for {gui_key} ({acc_type.name})")

    for op in spec.operations:
        if op.behavior == PortBehavior.COMMAND:
            continue
        tmcc_ids[op.key] = _ask_int(f"TMCC ID for operation '{op.key}' ({op.label})")

    default_display_name = vs.title
    print(f"Default display name: {default_display_name}")
    display_name = _ask("Display name override (leave blank to use default)", default="").strip()

    if not display_name or display_name == default_display_name:
        display_name = None

    instance_id = _make_instance_id(
        gui_key=gui_key,
        variant_key=variant_key,
        tmcc_ids=tmcc_ids if tmcc_ids else None,
        tmcc_id=tmcc_id_overall,
    )

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
        help="Default to 'append' when an existing file is found.",
    )
    ap.add_argument(
        "--verify-existing",
        action="store_true",
        help="Validate existing file and report malformed entries (does not modify file).",
    )
    ap.add_argument(
        "--clean-existing",
        action="store_true",
        help="Validate existing file, remove malformed entries, and write cleaned file before continuing.",
    )
    ap.add_argument(
        "--clean-only",
        action="store_true",
        help="Clean existing file (like --clean-existing) and exit.",
    )
    args = ap.parse_args(argv)

    if args.clean_only:
        args.clean_existing = True

    out_path = Path(args.out)

    catalog = AccessoryGuiCatalog()
    registry = AccessoryRegistry.get()
    registry.bootstrap()

    resolved_path, existing = _startup_existing_file_flow(
        out_path,
        default_choice="append" if args.append else None,
        verify_existing=args.verify_existing,
        clean_existing=args.clean_existing,
        clean_only=args.clean_only,
    )

    accessories: list[AccessoryConfig] = []
    seen_instance_ids = {a.get("instance_id") for a in existing if isinstance(a, dict)}

    print("\nAccessory Configurator")
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

    payload_accessories = [*existing, *(a.to_dict() for a in accessories)]
    payload = {
        "schema": "pytrain.accessory_config.v1",
        "accessories": payload_accessories,
    }

    if accessories or existing:
        resolved_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"\nWrote: {resolved_path.resolve()}")
        print(f"Accessories: {len(payload['accessories'])}")
    else:
        print("\nNo accessories configured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
