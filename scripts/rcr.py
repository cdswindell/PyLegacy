#!/usr/bin/env python3

#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
#
#
"""
Rewrite PyTrain legacy copyright headers to the new SPDX style.

Old style (example):
#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories
#
#  Copyright (c) 2024-2025 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-License-Identifier: LPGL
#
#

New style (example):
#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

# --- Config you might tweak ---
DEFAULT_EXTS = {".py"}
DEFAULT_TARGET_END_YEAR = "2026"
DEFAULT_AUTHOR = "Dave Swindell <pytraininfo.gmail.com>"
OLD_PROJECT_LINE = "PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories"
NEW_PROJECT_LINE = "PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories."


@dataclass(frozen=True)
class RewriteResult:
    path: Path
    changed: bool
    reason: str


def _iter_files(root: Path, exts: set[str]) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip common junk
        dirnames[:] = [d for d in dirnames if
                       d not in {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache"}]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix in exts:
                yield p


# Matches header block near the top (we only search first N chars for speed/safety).
# Captures:
#  - project line (w/ or w/out final period)
#  - the year token (2024 or 2024-2025 or 2024-2026)
#  - author name/email (rest of copyright line)
#  - old SPDX id (LPGL etc.)
HEADER_RE = re.compile(
    r"""
    (?P<block>
        (?:[ \t]*\#.*\n)*?
        [ \t]*\#[ \t]{2}PyTrain:\ a\ library\ for\ controlling\ Lionel\ Legacy\ engines,\ trains,\ switches,\ and\ accessories\.?\s*\n
        (?:[ \t]*\#.*\n)*?
        [ \t]*\#[ \t]{2}Copyright\ \(c\)\ (?P<years>2024(?:-(?:2025|2026))?)\ (?P<author>.+?)\s*\n
        (?:[ \t]*\#.*\n)*?
        [ \t]*\#[ \t]{2}SPDX-License-Identifier:\ (?P<spdx_old>[A-Za-z0-9.\-+]+)\s*\n
        (?:[ \t]*\#.*\n)*?
    )
    """,
    re.VERBOSE | re.MULTILINE,
)


def _normalize_author(author: str, fallback: str) -> str:
    author = author.strip()
    # If the captured author looks empty or weird, fall back
    if not author or author == "#":
        return fallback
    return author


def _new_header(author: str, end_year: str) -> str:
    years_new = f"2024-{end_year}"
    lines = [
        "#",
        f"#  {NEW_PROJECT_LINE}",
        "#",
        f"#  Copyright (c) {years_new} {author}",
        "#",
        f"#  SPDX-FileCopyrightText: {years_new} {author}",
        "#  SPDX-License-Identifier: LGPL-3.0-only",
        "#",
        "",
    ]
    return "\n".join(lines)


def rewrite_text(text: str, *, end_year: str, default_author: str) -> Tuple[str, bool, str]:
    # Only consider the beginning of the file; we don’t want to rewrite random mid-file comments.
    head_limit = 8000
    head = text[:head_limit]

    m = HEADER_RE.search(head)
    if not m:
        return text, False, "no matching old PyTrain header found"

    author = _normalize_author(m.group("author"), default_author)

    # Replace the matched legacy header block with the new header
    start, end = m.start("block"), m.end("block")
    new_head = head[:start] + _new_header(author, end_year) + head[end:]

    # --- NEW: strip any immediate trailing "blank comment" separator lines left behind ---
    # This removes lines that are just "#" (optionally with whitespace), and also removes
    # extra blank lines right after the header, then adds exactly one blank line.
    lines = new_head.splitlines(True)  # keep line endings

    # Find the end of the inserted new header by searching for the SPDX-License line we just inserted
    spdx_line = "#  SPDX-License-Identifier: LGPL-3.0-only\n"
    try:
        spdx_idx = next(i for i, ln in enumerate(lines) if ln == spdx_line)
    except StopIteration:
        # Fallback: don't postprocess if something unexpected happened
        out = new_head + text[head_limit:]
        return out, True, "rewrote header (no post-trim)"

    # The new header ends a couple lines after SPDX line: it includes "#\n" and "\n"
    # We'll start trimming *after* the first blank line following the inserted header.
    j = spdx_idx + 1

    # Advance over the remainder of the header we generated: any line that is exactly "#\n" or "\n"
    while j < len(lines) and (lines[j].strip() == "#" or lines[j].strip() == ""):
        j += 1

    # Now trim any additional legacy separator junk: pure "#" lines and blank lines
    k = j
    while k < len(lines) and (lines[k].strip() == "#" or lines[k].strip() == ""):
        k += 1

    # Rebuild: keep everything up through j, then force exactly one blank line, then continue at k
    trimmed = "".join(lines[:j]).rstrip("\n") + "\n\n" + "".join(lines[k:])

    out = trimmed + text[head_limit:]
    return out, True, "rewrote header (trimmed trailing separators)"


def process_file(path: Path, *, end_year: str, default_author: str, dry_run: bool) -> RewriteResult:
    try:
        original = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return RewriteResult(path, False, "skipped (not utf-8)")
    except OSError as e:
        return RewriteResult(path, False, f"error reading: {e}")

    rewritten, changed, reason = rewrite_text(original, end_year=end_year, default_author=default_author)
    if changed and not dry_run:
        try:
            path.write_text(rewritten, encoding="utf-8", newline="\n")
        except OSError as e:
            return RewriteResult(path, False, f"error writing: {e}")

    return RewriteResult(path, changed, reason)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Rewrite PyTrain legacy copyright headers to new SPDX style.")
    parser.add_argument("root", nargs="?", default=".", help="Root directory to scan (default: .)")
    parser.add_argument("--ext", action="append", default=[],
                        help="File extension to include (repeatable). Default: .py")
    parser.add_argument("--end-year", default=DEFAULT_TARGET_END_YEAR,
                        help=f"Target end year (default: {DEFAULT_TARGET_END_YEAR})")
    parser.add_argument("--author", default=DEFAULT_AUTHOR, help=f"Fallback author string (default: {DEFAULT_AUTHOR})")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change, but do not write files")
    args = parser.parse_args(argv)

    exts = set(args.ext) if args.ext else set(DEFAULT_EXTS)
    exts = {e if e.startswith(".") else f".{e}" for e in exts}

    root = Path(args.root).resolve()
    if not root.exists():
        print(f"Root does not exist: {root}", file=sys.stderr)
        return 2

    changed = 0
    scanned = 0
    for p in _iter_files(root, exts):
        scanned += 1
        r = process_file(p, end_year=args.end_year, default_author=args.author, dry_run=args.dry_run)
        if r.changed:
            changed += 1
            prefix = "WOULD UPDATE" if args.dry_run else "UPDATED"
            print(f"{prefix}: {r.path}")
        # Uncomment if you want per-file reasons:
        # else:
        #     print(f"SKIP: {r.path} ({r.reason})")

    print(f"\nScanned: {scanned}  Changed: {changed}  Dry-run: {args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
