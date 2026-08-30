import os
import sys
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

# The default search roots used by the vast majority of callers. Only lookups that
# use exactly these roots are served from the process-lifetime index; any other
# ``places`` (e.g. cache directories that may be written to at runtime) are walked
# fresh on every call so newly-written files are always found.
DEFAULT_PLACES: Tuple[str, ...] = (".", "../")

# Directory names that make up a Python virtual environment / installation prefix.
# When one of these lives directly under an interpreter prefix (``sys.prefix``,
# ``sys.base_prefix`` or ``$VIRTUAL_ENV``) it is pruned from the walk so we never
# descend into ``site-packages`` and the thousands of files it contains.
_ENV_SUBDIRS = {
    "bin",
    "lib",
    "lib64",
    "include",
    "share",
    "man",
    "Scripts",
    "Lib",
    "DLLs",
    "site-packages",
}

# Cache of built indexes, keyed by ``(places, want_dirs)``. Only default-``places``
# indexes are ever stored here (see ``_index_for``).
_INDEX_CACHE: dict[tuple, dict[str, list[str]]] = {}

_VENV_ROOTS: set[str] | None = None


def reset_path_index() -> None:
    """Clear the cached filename/dirname indexes.

    Intended primarily for tests; the index is otherwise process-lifetime because
    bundled assets do not appear or disappear while the program runs.
    """
    _INDEX_CACHE.clear()


def _venv_roots() -> set[str]:
    """Resolved paths of the active interpreter/virtualenv prefixes."""
    global _VENV_ROOTS
    if _VENV_ROOTS is None:
        roots: set[str] = set()
        for p in (sys.prefix, getattr(sys, "base_prefix", None), os.environ.get("VIRTUAL_ENV")):
            if not p:
                continue
            try:
                roots.add(str(Path(p).resolve()))
            except OSError:
                continue
        _VENV_ROOTS = roots
    return _VENV_ROOTS


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


def _build_index(places: Tuple, want_dirs: bool) -> dict[str, list[str]]:
    """Walk each search root once, building ``{basename: [resolved_path, ...]}``.

    Paths are recorded in walk order across ``places`` (``.`` before ``../`` for the
    default roots), so the first entry for a given name matches the file/directory
    the previous implementation returned first. Dot/``EXCLUDE`` directories and the
    active virtualenv/site-packages subtrees are pruned from the walk.
    """
    index: dict[str, list[str]] = {}
    venv_roots = _venv_roots()

    for d in places:
        if not os.path.isdir(d):
            continue

        for root, dirs, files in os.walk(os.fspath(d)):
            # Prune directories in-place so os.walk never descends into them. Dot and
            # EXCLUDE dirs are pruned because the original loop skipped any root whose
            # resolved parts contained such a component; virtualenv subdirs are pruned
            # to keep the one-time walk cheap without touching real project assets.
            resolved_root: str | None = None
            kept: list[str] = []
            for cd in dirs:
                if cd.startswith(".") or cd in EXCLUDE:
                    continue
                if cd in _ENV_SUBDIRS:
                    if resolved_root is None:
                        resolved_root = str(Path(root).resolve())
                    if resolved_root in venv_roots:
                        continue
                kept.append(cd)
            dirs[:] = kept

            if root.startswith("./.") or root.startswith("./venv/"):
                continue

            root_path = Path(root).resolve()
            parts = root_path.parts
            if any(p.startswith(".") or p in EXCLUDE for p in parts):
                continue

            names = dirs if want_dirs else files
            for name in names:
                if name.startswith(".") or name in EXCLUDE:
                    continue
                index.setdefault(name, []).append(str(root_path / name))

    return index


def _index_for(places: Tuple, want_dirs: bool) -> dict[str, list[str]]:
    """Return the index for ``places``, caching only the default-``places`` result.

    Non-default ``places`` (such as the cache-directory lookups in ``prod_info``)
    are walked fresh on every call so freshly-written files are always visible.
    """
    if tuple(places) == DEFAULT_PLACES:
        key = (DEFAULT_PLACES, want_dirs)
        index = _INDEX_CACHE.get(key)
        if index is None:
            index = _build_index(places, want_dirs)
            _INDEX_CACHE[key] = index
        return index
    return _build_index(places, want_dirs)


def find_dir(target: str | Path, places: Tuple = DEFAULT_PLACES) -> str | None:
    name, concrete = _normalize_target(target)

    # Short-circuit: exact path already exists
    if concrete and concrete.is_dir():
        return str(concrete)

    matches = _index_for(places, want_dirs=True).get(name)
    return matches[0] if matches else None


def find_file(target: str | Path, places: Tuple = DEFAULT_PLACES) -> str | None:
    name, concrete = _normalize_target(target)

    # Short-circuit: exact path already exists
    if concrete and concrete.is_file():
        return str(concrete)

    matches = _index_for(places, want_dirs=False).get(name)
    return matches[0] if matches else None
