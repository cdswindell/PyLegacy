from __future__ import annotations

import ctypes
import os
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import src.pytrain.gui.bundled_fonts as mod


@pytest.fixture
def bundled_font(monkeypatch):
    font = mod._DigitalDreamFont()
    register = Mock()
    monkeypatch.setattr(mod, "_register_font", register)
    try:
        yield font, register
    finally:
        font.close()


@pytest.mark.parametrize("package", ["src.pytrain.gui", "pytrain.gui"])
def test_font_resource_is_independent_of_working_directory(monkeypatch, tmp_path, bundled_font, package):
    font, register = bundled_font
    monkeypatch.setattr(mod, "__package__", package)
    monkeypatch.chdir(tmp_path)

    assert font.register() is True
    assert font.register() is True
    register.assert_called_once()
    path = register.call_args.args[0]
    assert path.name == "DIGITALDREAM.ttf"
    assert path.read_bytes().startswith(b"\x00\x01\x00\x00")
    font.close()
    assert path.is_file(), "cleanup must not remove fonts from a source tree or installed package"


def test_zipped_package_font_stays_extracted_until_process_cleanup(monkeypatch, tmp_path, bundled_font):
    font, register = bundled_font
    resource = files("src.pytrain.gui").joinpath("fonts/digital-dream/DIGITALDREAM.ttf")
    archive = tmp_path / "gui.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("fonts/digital-dream/DIGITALDREAM.ttf", resource.read_bytes())
    with zipfile.ZipFile(archive) as package:
        monkeypatch.setattr(mod, "files", lambda _package: zipfile.Path(package))
        assert font.register() is True
        path = register.call_args.args[0]
        assert path.is_file()
        assert path.read_bytes() == resource.read_bytes()
        assert font.register() is True
        register.assert_called_once()
        font.close()
        assert not path.exists()


def test_simultaneous_requests_only_register_once(bundled_font):
    font, register = bundled_font
    with ThreadPoolExecutor(max_workers=4) as executor:
        assert all(executor.map(lambda _index: font.register(), range(8)))
    register.assert_called_once()


@pytest.mark.parametrize("error", [OSError("missing library"), RuntimeError("registration failed")])
def test_registration_failure_is_logged_and_not_repeated(bundled_font, caplog, error):
    font, register = bundled_font
    register.side_effect = error

    assert font.register() is False
    assert font.register() is False
    register.assert_called_once()
    assert "Unable to register bundled Digital Dream font" in caplog.text


def test_missing_package_resource_is_a_nonfatal_failure(monkeypatch, tmp_path, bundled_font, caplog):
    font, register = bundled_font
    monkeypatch.setattr(mod, "files", lambda _package: zipfile.Path(tmp_path / "missing.zip"))

    assert font.register() is False
    register.assert_not_called()
    assert "Unable to register bundled Digital Dream font" in caplog.text


@pytest.mark.parametrize("error", [KeyboardInterrupt, SystemExit])
def test_registration_does_not_swallow_cancellation(bundled_font, error):
    font, register = bundled_font
    register.side_effect = error

    with pytest.raises(error):
        font.register()


def test_resource_cleanup_failure_retains_extracted_path_for_retry(monkeypatch, tmp_path, bundled_font, caplog):
    font, _register = bundled_font
    path = tmp_path / "extracted.ttf"
    path.write_bytes(b"font")

    @contextmanager
    def extracted_resource(_resource):
        try:
            yield path
        finally:
            path.unlink()

    resource = Mock()
    resource.joinpath.return_value = resource
    monkeypatch.setattr(mod, "files", lambda _package: resource)
    monkeypatch.setattr(mod, "as_file", extracted_resource)
    unlink = Path.unlink
    attempts = []

    def fail_first_unlink(self, *args, **kwargs):
        attempts.append(self)
        if len(attempts) == 1:
            raise OSError("temporarily busy")
        unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_first_unlink)
    assert font.register() is True

    font.close()
    assert path.exists()
    assert font._resource_path == path
    assert "Unable to release bundled font resource" in caplog.text
    font.close()
    assert not path.exists()
    assert font._resource_path is None


@pytest.mark.parametrize("error", [KeyboardInterrupt, SystemExit])
def test_resource_cleanup_does_not_swallow_cancellation(bundled_font, error):
    font, _register = bundled_font
    resource_context = Mock()
    resource_context.__exit__ = Mock(side_effect=error)
    font._resource_context = resource_context
    try:
        with pytest.raises(error):
            font.close()
        assert font._resource_context is resource_context
    finally:
        font._resource_context = None


@pytest.mark.parametrize("platform,backend", [("darwin", "macos"), ("linux", "linux")])
def test_registration_uses_the_platform_backend(monkeypatch, platform, backend):
    monkeypatch.setattr(mod, "sys", SimpleNamespace(platform=platform))
    macos, linux = Mock(), Mock()
    monkeypatch.setattr(mod, "_register_macos_font", macos)
    monkeypatch.setattr(mod, "_register_linux_font", linux)
    path = Path("Digital Dream.ttf")

    mod._register_font(path)

    (macos if backend == "macos" else linux).assert_called_once_with(path)
    (linux if backend == "macos" else macos).assert_not_called()


def test_unsupported_platform_does_not_attempt_native_registration(monkeypatch):
    monkeypatch.setattr(mod, "sys", SimpleNamespace(platform="unsupported"))
    with pytest.raises(OSError, match="not supported"):
        mod._register_font(Path("font.ttf"))


@pytest.mark.parametrize("success", [True, False])
def test_macos_registration_has_process_scope_and_releases_native_resources(monkeypatch, success):
    foundation = SimpleNamespace(CFURLCreateFromFileSystemRepresentation=Mock(return_value=101), CFRelease=Mock())

    def register(_url, _scope, error):
        if not success:
            ctypes.cast(error, ctypes.POINTER(ctypes.c_void_p))[0] = 202
        return success

    core_text = SimpleNamespace(CTFontManagerRegisterFontsForURL=Mock(side_effect=register))
    monkeypatch.setattr(mod.ctypes, "CDLL", Mock(side_effect=[foundation, core_text]))
    path = Path("/fonts/Digital Dream.ttf")

    if success:
        mod._register_macos_font(path)
    else:
        with pytest.raises(OSError, match="Core Text rejected"):
            mod._register_macos_font(path)

    filename = os.fsencode(path)
    foundation.CFURLCreateFromFileSystemRepresentation.assert_called_once_with(None, filename, len(filename), False)
    assert core_text.CTFontManagerRegisterFontsForURL.call_args.args[:2] == (101, 1)
    assert foundation.CFURLCreateFromFileSystemRepresentation.restype is ctypes.c_void_p
    released = [value.args[0] for value in foundation.CFRelease.call_args_list]
    assert [value.value if isinstance(value, ctypes.c_void_p) else value for value in released] == (
        [101] if success else [202, 101]
    )


def test_macos_url_failure_does_not_register_an_invalid_pointer(monkeypatch):
    foundation = SimpleNamespace(CFURLCreateFromFileSystemRepresentation=Mock(return_value=None), CFRelease=Mock())
    core_text = SimpleNamespace(CTFontManagerRegisterFontsForURL=Mock())
    monkeypatch.setattr(mod.ctypes, "CDLL", Mock(side_effect=[foundation, core_text]))

    with pytest.raises(OSError, match="font URL"):
        mod._register_macos_font(Path("font.ttf"))
    core_text.CTFontManagerRegisterFontsForURL.assert_not_called()
    foundation.CFRelease.assert_not_called()


@pytest.mark.parametrize("config,success", [(101, 1), (101, 0), (None, 1)])
def test_linux_uses_the_current_fontconfig_and_checks_success(monkeypatch, config, success):
    fontconfig = SimpleNamespace(
        FcConfigGetCurrent=Mock(return_value=config), FcConfigAppFontAddFile=Mock(return_value=success)
    )
    library = Mock(return_value=fontconfig)
    monkeypatch.setattr(mod.ctypes, "CDLL", library)
    monkeypatch.setattr(mod, "find_library", Mock(return_value="libfontconfig.so.1"))
    path = Path("/fonts/Digital Dream.ttf")

    if config and success:
        mod._register_linux_font(path)
    else:
        with pytest.raises(OSError, match="Fontconfig rejected"):
            mod._register_linux_font(path)

    library.assert_called_once_with("libfontconfig.so.1")
    assert fontconfig.FcConfigGetCurrent.restype is ctypes.c_void_p
    assert fontconfig.FcConfigAppFontAddFile.argtypes == [ctypes.c_void_p, ctypes.c_char_p]
    assert fontconfig.FcConfigAppFontAddFile.restype is ctypes.c_int
    if config:
        fontconfig.FcConfigAppFontAddFile.assert_called_once_with(config, os.fsencode(path))
    else:
        fontconfig.FcConfigAppFontAddFile.assert_not_called()


def test_unavailable_native_library_is_reported(monkeypatch):
    monkeypatch.setattr(mod.ctypes, "CDLL", Mock(side_effect=OSError("missing library")))
    monkeypatch.setattr(mod, "find_library", Mock(return_value=None))
    with pytest.raises(OSError, match="missing library"):
        mod._register_linux_font(Path("font.ttf"))
