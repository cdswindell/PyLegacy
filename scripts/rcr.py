#!/usr/bin/env python3
#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#
"""
Rewrite PyTrain legacy copyright headers to the new SPDX style.

Also provides normalization utilities:
  - remove a blank line immediately after a shebang (#!...) line
  - CI-friendly check mode
  - shebang-only mode

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
    header_changed: bool
    shebang_changed: bool
    reason: str


def _iter_files(path: Path, exts: set[str]) -> Iterable[Path]:
    """
    Yield files to process.

    - If path is a file: yield it if its suffix matches.
    - If path is a directory: recursively yield matching files under it.
    """
    if path.is_file():
        if path.suffix in exts:
            yield path
        return

    if not path.is_dir():
        return

    for dirpath, dirnames, filenames in os.walk(path):
        # Skip common junk
        dirnames[:] = [
            d
            for d in dirnames
            if d
               not in {
                   ".git",
                   ".venv",
                   "venv",
                   "__pycache__",
                   ".mypy_cache",
                   ".pytest_cache",
               }
        ]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix in exts:
                yield p


ENCODING_RE = re.compile(r"^#.*coding[:=][ \t]*([-\w.]+)", re.IGNORECASE)


def _split_prefix(text: str) -> tuple[str, str]:
    lines = text.splitlines(True)
    i = 0
    prefix = []

    # shebang
    if i < len(lines) and lines[i].startswith("#!"):
        prefix.append(lines[i]);
        i += 1
        # allow exactly one blank line after shebang (we normalize later anyway)
        if i < len(lines) and lines[i].strip() == "":
            prefix.append(lines[i]);
            i += 1

    # encoding cookie (must be in first 2 physical lines of the *file*)
    # If there was a shebang, the cookie can be on line 2; otherwise line 1 or 2.
    for _ in range(2):
        if i < len(lines) and ENCODING_RE.match(lines[i]):
            prefix.append(lines[i]);
            i += 1
            break

    return "".join(prefix), "".join(lines[i:])


# Matches legacy header block near the top (we only search first N chars for speed/safety).
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


def has_new_header(text: str) -> bool:
    """
    Detect the new SPDX header near the top of the file.
    """
    head = text[:8000]
    return (
            "SPDX-FileCopyrightText:" in head
            and "SPDX-License-Identifier: LGPL-3.0-only" in head
            and f"#  {NEW_PROJECT_LINE}" in head
    )


def _fix_shebang_spacing(text: str) -> str:
    """
    Remove exactly ONE blank line immediately after the shebang line, if present.

    Turns this:
      #!/usr/bin/env python3
      <blank>
      #

    Into:
      #!/usr/bin/env python3
      #
    """
    lines = text.splitlines(True)
    if not lines or not lines[0].startswith("#!"):
        return text

    if len(lines) >= 2 and lines[1].strip() == "":
        del lines[1]
        return "".join(lines)

    return text

def _normalize_author(author: str, fallback: str) -> str:
    author = author.strip()
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
    ]
    # End with exactly one newline; do NOT add extra blank lines.
    return "\n".join(lines) + "\n"

def rewrite_text(text: str, *, end_year: str, default_author: str) -> Tuple[str, bool, str]:
    """
    Rewrite a legacy header to the new one.

    Returns (new_text, header_changed, reason).
    """
    head_limit = 8000

    prefix, body = _split_prefix(text)
    head = body[:head_limit]
    m = HEADER_RE.search(head)
    if not m:
        return text, False, "no matching old PyTrain header found"

    author = _normalize_author(m.group("author"), default_author)

    start, end = m.start("block"), m.end("block")
    inserted = _new_header(author, end_year)
    new_head = head[:start] + inserted + head[end:]

    # Post-trim: keep exactly ONE '#' line at end of header,
    # then exactly ONE blank line before the next real content.
    lines = new_head.splitlines(True)
    inserted_lines = inserted.splitlines(True)

    end_idx = None
    for i in range(0, len(lines) - len(inserted_lines) + 1):
        if lines[i: i + len(inserted_lines)] == inserted_lines:
            end_idx = i + len(inserted_lines)  # first line AFTER inserted header
            break

    if end_idx is None:
        out = new_head + text[head_limit:]
        return out, True, "rewrote header (no post-trim)"

    # Remove any immediate legacy separator lines after the inserted header
    j = end_idx
    while j < len(lines):
        stripped = lines[j].strip()
        if stripped == "" or stripped == "#":
            j += 1
            continue
        break

    rebuilt = "".join(lines[:end_idx]).rstrip("\n") + "\n\n" + "".join(lines[j:])
    out = prefix + rebuilt + text[head_limit:]
    return out, True, "rewrote legacy header"


def process_file(
        path: Path,
        *,
        end_year: str,
        default_author: str,
        dry_run: bool,
        shebang_only: bool,
) -> RewriteResult:
    try:
        original = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return RewriteResult(path, False, False, False, "skipped (not utf-8)")
    except OSError as e:
        return RewriteResult(path, False, False, False, f"error reading: {e}")

    # Always normalize shebang spacing first (even if header is already new)
    after_shebang = _fix_shebang_spacing(original)
    shebang_changed = (after_shebang != original)

    if shebang_only:
        if shebang_changed and not dry_run:
            try:
                path.write_text(after_shebang, encoding="utf-8", newline="\n")
            except OSError as e:
                return RewriteResult(path, False, False, False, f"error writing: {e}")

        return RewriteResult(
            path=path,
            changed=shebang_changed,
            header_changed=False,
            shebang_changed=shebang_changed,
            reason="normalized shebang spacing" if shebang_changed else "no change",
        )

    # Auto-skip header rewrite if already has the new header
    # but still allow shebang-only normalization to write.
    if has_new_header(after_shebang):
        if shebang_changed and not dry_run:
            try:
                path.write_text(after_shebang, encoding="utf-8", newline="\n")
            except OSError as e:
                return RewriteResult(path, False, False, False, f"error writing: {e}")

        return RewriteResult(
            path=path,
            changed=shebang_changed,
            header_changed=False,
            shebang_changed=shebang_changed,
            reason="already has new header"
                   + ("; normalized shebang spacing" if shebang_changed else ""),
        )

    # Otherwise, rewrite header (working from the shebang-normalized text)
    rewritten, header_changed, reason = rewrite_text(
        after_shebang, end_year=end_year, default_author=default_author
    )

    # After header rewrite, also enforce the shebang rule again (in case insertion moved things)
    final_text = _fix_shebang_spacing(rewritten)
    shebang_changed = shebang_changed or (final_text != rewritten)

    changed = header_changed or shebang_changed

    if changed and not dry_run:
        try:
            path.write_text(final_text, encoding="utf-8", newline="\n")
        except OSError as e:
            return RewriteResult(path, False, False, False, f"error writing: {e}")

    return RewriteResult(
        path=path,
        changed=changed,
        header_changed=header_changed,
        shebang_changed=shebang_changed,
        reason=reason,
    )

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rewrite PyTrain legacy copyright headers to new SPDX style."
    )
    parser.add_argument("root", nargs="?", default=".", help="File or directory to scan (default: .)")
    parser.add_argument(
        "--ext",
        action="append",
        default=[],
        help="File extension to include (repeatable). Default: .py",
    )
    parser.add_argument(
        "--end-year",
        default=DEFAULT_TARGET_END_YEAR,
        help=f"Target end year (default: {DEFAULT_TARGET_END_YEAR})",
    )
    parser.add_argument(
        "--author",
        default=DEFAULT_AUTHOR,
        help=f"Fallback author string (default: {DEFAULT_AUTHOR})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would change, but do not write files")
    parser.add_argument("--check", action="store_true", help="Do not write; exit non-zero if any file would change")
    parser.add_argument("--shebang-only", action="store_true",
                        help="Only normalize blank line after shebang; do not rewrite headers")
    parser.add_argument("--quiet", action="store_true", help="Only print summary (useful for CI logs)")

    args = parser.parse_args(argv)

    if args.check:
        args.dry_run = True

    exts = set(args.ext) if args.ext else set(DEFAULT_EXTS)
    exts = {e if e.startswith(".") else f".{e}" for e in exts}

    target = Path(args.root).resolve()
    if not target.exists():
        print(f"Path does not exist: {target}", file=sys.stderr)
        return 2

    scanned = 0
    changed = 0
    header_changed = 0
    shebang_changed = 0

    for p in _iter_files(target, exts):
        scanned += 1
        r = process_file(
            p,
            end_year=args.end_year,
            default_author=args.author,
            dry_run=args.dry_run,
            shebang_only=args.shebang_only,
        )

        if r.changed:
            changed += 1
            if r.header_changed:
                header_changed += 1
            if r.shebang_changed:
                shebang_changed += 1

            if not args.quiet:
                if args.check:
                    action = "WOULD CHANGE"
                elif args.dry_run:
                    action = "WOULD UPDATE"
                else:
                    action = "UPDATED"

                bits: List[str] = []
                if r.header_changed:
                    bits.append("header")
                if r.shebang_changed:
                    bits.append("shebang")
                detail = ",".join(bits) if bits else "unknown"

                print(f"{action}: {r.path} [{detail}]")
        else:
            # Optional verbose skip reporting:
            # if not args.quiet and args.dry_run and r.reason:
            #     print(f"SKIP: {r.path} ({r.reason})")
            pass

    if not args.quiet:
        print()

    print(
        f"Scanned: {scanned}  Changed: {changed}  "
        f"(header: {header_changed}, shebang: {shebang_changed})  "
        f"Dry-run: {args.dry_run}  Check: {args.check}  Shebang-only: {args.shebang_only}"
    )

    if args.check and changed > 0:
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())