#
#  PyTrain: a library for controlling Lionel Legacy engines, trains, switches, and accessories.
#
#  Copyright (c) 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#
#  SPDX-FileCopyrightText: 2024-2026 Dave Swindell <pytraininfo.gmail.com>
#  SPDX-License-Identifier: LGPL-3.0-only
#

from __future__ import annotations

import atexit
import ctypes
import logging
import os
import sys
from ctypes.util import find_library
from importlib.resources import as_file, files
from pathlib import Path
from threading import RLock

log = logging.getLogger(__name__)
DIGITAL_DREAM_FAMILY = "Digital dream"


def _register_macos_font(path: Path) -> None:
    core_foundation = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    core_text = ctypes.CDLL("/System/Library/Frameworks/CoreText.framework/CoreText")
    core_foundation.CFURLCreateFromFileSystemRepresentation.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        ctypes.c_long,
        ctypes.c_ubyte,
    ]
    core_foundation.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
    core_foundation.CFRelease.argtypes = [ctypes.c_void_p]
    core_foundation.CFRelease.restype = None
    core_text.CTFontManagerRegisterFontsForURL.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    core_text.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool

    filename = os.fsencode(path)
    url = core_foundation.CFURLCreateFromFileSystemRepresentation(None, filename, len(filename), False)
    if not url:
        raise OSError("Unable to create the bundled font URL")
    error = ctypes.c_void_p()
    try:
        # kCTFontManagerScopeProcess: never install the font for other applications.
        if not core_text.CTFontManagerRegisterFontsForURL(url, 1, ctypes.byref(error)):
            raise OSError("Core Text rejected the bundled font")
    finally:
        try:
            if error.value:
                core_foundation.CFRelease(error)
        finally:
            core_foundation.CFRelease(url)


def _register_linux_font(path: Path) -> None:
    fontconfig = ctypes.CDLL(find_library("fontconfig") or "libfontconfig.so.1")
    fontconfig.FcConfigGetCurrent.argtypes = []
    fontconfig.FcConfigGetCurrent.restype = ctypes.c_void_p
    fontconfig.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    fontconfig.FcConfigAppFontAddFile.restype = ctypes.c_int
    config = fontconfig.FcConfigGetCurrent()
    if not config or not fontconfig.FcConfigAppFontAddFile(config, os.fsencode(path)):
        raise OSError("Fontconfig rejected the bundled font")


def _register_font(path: Path) -> None:
    if sys.platform == "darwin":
        _register_macos_font(path)
    elif sys.platform.startswith("linux"):
        _register_linux_font(path)
    else:
        raise OSError(f"Bundled font registration is not supported on {sys.platform}")


class _DigitalDreamFont:
    def __init__(self) -> None:
        self._lock = RLock()
        self._attempted = False
        self._registered = False
        self._resource_context = None
        self._resource_path: Path | None = None
        self._temporary = False

    def register(self) -> bool:
        with self._lock:
            if self._attempted:
                return self._registered
            try:
                resource = files(__package__).joinpath("fonts").joinpath("digital-dream").joinpath("DIGITALDREAM.ttf")
                self._temporary = not isinstance(resource, Path)
                self._resource_context = as_file(resource)
                self._resource_path = self._resource_context.__enter__()
                _register_font(self._resource_path)
                self._registered = True
            except Exception as exc:
                log.warning("Unable to register bundled Digital Dream font; using TkDefaultFont: %s", exc)
            self._attempted = True
            return self._registered

    def close(self) -> None:
        # Only called at process exit, not GUI teardown: another GUI may still use the font.
        with self._lock:
            try:
                if self._resource_context is not None:
                    self._resource_context.__exit__(None, None, None)
                # A generator context manager cannot retry a failed unlink. Retain the
                # extracted path until removal succeeds, but never remove source/package files.
                if self._temporary and self._resource_path is not None:
                    self._resource_path.unlink(missing_ok=True)
            except Exception as exc:
                log.warning("Unable to release bundled font resource: %s", exc)
                return
            self._resource_context = None
            self._resource_path = None


_digital_dream = _DigitalDreamFont()
atexit.register(_digital_dream.close)


def register_digital_font() -> bool:
    """Register once per process, retaining any extracted package resource until exit."""
    return _digital_dream.register()
