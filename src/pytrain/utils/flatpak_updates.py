"""Discover published PyCab Flatpak updates without modifying an installation.

The GitHub release is authoritative; the connected PyTrain server is not.
This module is intentionally independent of PyTrain's pip/git update paths.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from dataclasses import dataclass
from urllib.request import Request, urlopen

RELEASE_TAG_FILE = Path('/app/share/pycab/release-tag')


def installed_flatpak_tag() -> str | None:
    """Return embedded bundle release tag only inside our Flatpak sandbox."""
    if os.environ.get('FLATPAK_ID') != 'io.github.cdswindell.PyCab':
        return None
    try:
        tag = RELEASE_TAG_FILE.read_text(encoding='utf-8').strip()
        version_key(tag)
        return tag
    except (OSError, ValueError):
        return None


RELEASE_URL = "https://api.github.com/repos/cdswindell/PyCab-Flatpak/releases/latest"
_RELEASE_TAG = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:-(\d+))?$")
_REQUIRED_ASSETS = frozenset({"PyCab.flatpak", "PyCab.flatpak.sha256"})


def version_key(tag: str) -> tuple[int, int, int, int]:
    """Compare stable PyCab tags, including packaging-only rebuild revisions."""
    match = _RELEASE_TAG.fullmatch(tag)
    if match is None:
        raise ValueError(f"Invalid PyCab release tag: {tag!r}")
    major, minor, patch, revision = match.groups()
    return int(major), int(minor), int(patch), int(revision or 0)


@dataclass(frozen=True)
class FlatpakUpdate:
    installed_tag: str
    available_tag: str
    release_url: str

    @property
    def available(self) -> bool:
        return version_key(self.available_tag) > version_key(self.installed_tag)


def check_flatpak_update(installed_tag: str, *, timeout: float = 5.0) -> FlatpakUpdate:
    """Check GitHub for a complete, published Flatpak release.

    Call from a worker, never from the GUI thread. Network and JSON errors
    propagate to the caller so failures are not misreported as 'up to date'.
    """
    version_key(installed_tag)
    request = Request(
        RELEASE_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "PyCab-update-checker"},
    )
    with urlopen(request, timeout=timeout) as response:
        release = json.load(response)

    tag = release["tag_name"]
    version_key(tag)
    if release.get("draft") or release.get("prerelease"):
        raise ValueError("Latest GitHub release is not a stable published release")
    assets = {asset["name"] for asset in release.get("assets", [])}
    if not _REQUIRED_ASSETS.issubset(assets):
        raise ValueError("Latest PyCab release is missing the Flatpak bundle or checksum")
    return FlatpakUpdate(installed_tag, tag, release["html_url"])
