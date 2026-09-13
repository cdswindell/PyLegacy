from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from PIL import Image

from pytrain.gui import pycab_app as mod


@pytest.mark.parametrize("large,size", [(False, 108), (True, 512)])
def test_icons_load_from_package_resources_with_explicit_master(monkeypatch, tmp_path, large, size):
    master, photo = object(), object()
    loaded = []

    def load_photo(**kwargs):
        assert kwargs["master"] is master
        with Image.open(kwargs["file"]) as image:
            assert image.format == "PNG"
            assert image.size == (size, size)
        loaded.append(Path(kwargs["file"]).name)
        return photo

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod.tk, "PhotoImage", load_photo)
    assert mod.load_pycab_icon(master, large=large) is photo
    assert loaded == [f"en-US_pycab_{'large' if large else 'small'}.png"]


@pytest.mark.parametrize("error", [OSError("missing image"), mod.tk.TclError("invalid image")])
def test_unavailable_icon_does_not_prevent_confirmation(monkeypatch, caplog, error):
    monkeypatch.setattr(mod.tk, "PhotoImage", Mock(side_effect=error))
    assert mod.load_pycab_icon(object()) is None
    assert "Unable to load PyCab icon" in caplog.text


def test_logo_label_retains_its_photo(monkeypatch):
    photo, master, label = object(), object(), Mock()
    loader = Mock(return_value=photo)
    label_factory = Mock(return_value=label)
    monkeypatch.setattr(mod, "load_pycab_icon", loader)
    monkeypatch.setattr(mod.tk, "Label", label_factory)
    assert mod.add_pycab_logo(master) is label
    loader.assert_called_once_with(master)
    label_factory.assert_called_once_with(master, image=photo)
    assert label.image is photo
    label.pack.assert_called_once()


def test_missing_logo_leaves_dialog_usable(monkeypatch):
    monkeypatch.setattr(mod, "load_pycab_icon", Mock(return_value=None))
    label = Mock()
    monkeypatch.setattr(mod.tk, "Label", label)
    assert mod.add_pycab_logo(object()) is None
    label.assert_not_called()


@pytest.mark.parametrize("supported", [False, True])
def test_app_sets_and_retains_both_window_icons(monkeypatch, supported):
    root = Mock()
    if not supported:
        root.iconphoto.side_effect = mod.tk.TclError("unsupported")
    large, small = object(), object()
    loader = Mock(side_effect=[large, small])
    monkeypatch.setattr(mod.App, "__init__", lambda self, **_kwargs: setattr(self, "_tk", root))
    monkeypatch.setattr(mod, "load_pycab_icon", loader)
    app = mod.PyCabApp(title="PyCab")
    assert app._pycab_icons == (large, small)
    assert loader.call_args_list == [call(root, large=True), call(root)]
    root.iconphoto.assert_called_once_with(True, large, small)


def test_app_still_starts_when_both_icons_are_unavailable(monkeypatch):
    root = Mock()
    monkeypatch.setattr(mod.App, "__init__", lambda self: setattr(self, "_tk", root))
    monkeypatch.setattr(mod, "load_pycab_icon", Mock(return_value=None))
    app = mod.PyCabApp()
    assert app._pycab_icons == ()
    root.iconphoto.assert_not_called()


@pytest.mark.parametrize("result", [True, False, None])
def test_yesno_uses_branded_dialog_and_returns_a_boolean(monkeypatch, result):
    dialog = Mock(return_value=SimpleNamespace(result=result))
    monkeypatch.setattr(mod, "ConfirmationDialog", dialog)
    app = object.__new__(mod.PyCabApp)
    app._tk = object()
    assert app.yesno("Discard?", "Discard changes?") is bool(result)
    dialog.assert_called_once_with(app.tk, "Discard?", "Discard changes?")


def test_confirmation_body_displays_logo_and_message(monkeypatch):
    logo, label = Mock(), Mock()
    monkeypatch.setattr(mod, "add_pycab_logo", logo)
    monkeypatch.setattr(mod.tk, "Label", label)
    dialog = object.__new__(mod.ConfirmationDialog)
    dialog._message = "Replace this controller?"
    dialog.resizable = Mock()
    master = object()
    dialog.body(master)
    logo.assert_called_once_with(master)
    assert label.call_args.args == (master,)
    assert label.call_args.kwargs["text"] == dialog._message
    assert label.call_args.kwargs["wraplength"] > 0


def test_confirmation_buttons_have_safe_default_and_keyboard_bindings(monkeypatch):
    no, yes = Mock(), Mock()
    buttons = Mock(side_effect=[no, yes])
    monkeypatch.setattr(mod.tk, "Frame", Mock())
    monkeypatch.setattr(mod.tk, "Button", buttons)
    dialog = object.__new__(mod.ConfirmationDialog)
    dialog.bind = Mock()
    dialog.buttonbox()
    assert buttons.call_args_list[0].kwargs["text"] == "No"
    assert buttons.call_args_list[0].kwargs["default"] == "active"
    assert buttons.call_args_list[0].kwargs["command"] == dialog.cancel
    assert buttons.call_args_list[1].kwargs["text"] == "Yes"
    assert buttons.call_args_list[1].kwargs["command"] == dialog.ok
    assert dialog.initial_focus is no
    dialog.bind.assert_any_call("<Return>", dialog._on_return)
    dialog.bind.assert_any_call("<Escape>", dialog.cancel)


@pytest.mark.parametrize("yes_focused", [False, True])
def test_return_requires_explicit_yes_focus(yes_focused):
    dialog = object.__new__(mod.ConfirmationDialog)
    dialog._yes_btn = object()
    dialog.focus_get = Mock(return_value=dialog._yes_btn if yes_focused else object())
    dialog.ok, dialog.cancel = Mock(), Mock()
    dialog._on_return()
    assert dialog.ok.call_count == int(yes_focused)
    assert dialog.cancel.call_count == int(not yes_focused)
    dialog.apply()
    assert dialog.result is True
