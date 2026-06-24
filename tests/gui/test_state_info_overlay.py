from __future__ import annotations

from types import SimpleNamespace

import src.pytrain.gui.controller.state_info_overlay as mod


class FakeEditableText:
    def __init__(self, editing: bool = True) -> None:
        self.is_editing = editing
        self.committed = False
        self.cancelled = False

    def commit_edit(self) -> None:
        self.committed = True
        self.is_editing = False

    def cancel_edit(self) -> None:
        self.cancelled = True
        self.is_editing = False


# noinspection PyTypeChecker
def test_popup_close_cancels_active_inline_edits_and_delegates(monkeypatch) -> None:
    monkeypatch.setattr(mod, "EditableText", FakeEditableText)
    field = FakeEditableText()
    host = SimpleNamespace(closed_overlay=None)
    host.on_state_info_closed = lambda ov: setattr(host, "closed_overlay", ov)
    overlay = object()

    info = mod.StateInfoOverlay.__new__(mod.StateInfoOverlay)
    info._gui = host
    info.details = {"name": (object(), field)}

    info._on_popup_closed(overlay)

    assert field.committed is False
    assert field.cancelled is True
    assert field.is_editing is False
    assert host.closed_overlay is overlay
