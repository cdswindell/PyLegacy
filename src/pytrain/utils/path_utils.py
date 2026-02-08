import os
from pathlib import Path
from typing import Tuple

EXCLUDE = {
    "__pycache__",
    ".tox",
    ".github",
    ".idea",
    ".git",
    "venv",
}


def _normalize_target(target: str | Path) -> tuple[str, Path | None]:
    """
    Normalize target into:
      - basename to match during os.walk
      - optional concrete Path to short-circuit if it exists
    """
    if isinstance(target, Path):
        if target.exists():
            return target.name, target.resolve()
        return target.name, None
    return target, None


def find_dir(target: str | Path, places: Tuple = (".", "../")) -> str | None:
    name, concrete = _normalize_target(target)

    # Short-circuit: exact path already exists
    if concrete and concrete.is_dir():
        return str(concrete)

    for d in places:
        if not os.path.isdir(d):
            continue

        for root, dirs, _ in os.walk(d):
            if root.startswith("./.") or root.startswith("./venv/"):
                continue

            root_path = Path(root).resolve()
            parts = root_path.parts

            if any(p.startswith(".") or p in EXCLUDE for p in parts):
                continue

            for cd in dirs:
                if cd.startswith(".") or cd in EXCLUDE:
                    continue
                if cd == name:
                    return str(root_path / cd)

    return None


def find_file(target: str | Path, places: Tuple = (".", "../")) -> str | None:
    name, concrete = _normalize_target(target)

    # Short-circuit: exact path already exists
    if concrete and concrete.is_file():
        return str(concrete)

    for d in places:
        if not os.path.isdir(d):
            continue

        for root, _, files in os.walk(d):
            if root.startswith("./.") or root.startswith("./venv/"):
                continue

            root_path = Path(root).resolve()
            parts = root_path.parts

            if any(p.startswith(".") or p in EXCLUDE for p in parts):
                continue

            for file in files:
                if file.startswith(".") or file in EXCLUDE:
                    continue
                if file == name:
                    return str(root_path / file)

    return None
