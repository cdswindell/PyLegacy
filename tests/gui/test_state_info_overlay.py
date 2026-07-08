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


class FakeClearButton:
    def __init__(self) -> None:
        self.enabled = False
        self.on_hold = None
        self.cancel_calls = 0

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False

    def cancel_interaction(self) -> None:
        self.cancel_calls += 1


class FakeField:
    def __init__(self) -> None:
        self.value = None
        self.initial_value = None
        self.editable = False
        self.text_bold = None


class FakeTitle:
    def __init__(self) -> None:
        self.text_bold = None


def _info_overlay(host: object) -> mod.StateInfoOverlay:
    info = mod.StateInfoOverlay.__new__(mod.StateInfoOverlay)
    info._gui = host
    info._overlay = object()
    info.clear_btn = FakeClearButton()
    info.details = {
        "number": (FakeTitle(), FakeField()),
        "name": (FakeTitle(), FakeField()),
    }
    return info


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

    info._post_close_action(overlay)

    assert field.committed is False
    assert field.cancelled is True
    assert field.is_editing is False
    assert host.closed_overlay is overlay


def test_update_enables_clear_button_for_deletable_state() -> None:
    host = SimpleNamespace(_prod_info_cache={}, active_accessory=None)
    state = SimpleNamespace(is_deletable=True, road_number="1234", road_name="Hudson")
    info = _info_overlay(host)

    info.update(state)

    assert info.clear_btn.enabled is True
    assert info.clear_btn.on_hold == (info.clear_record, [state])
    assert info.details["number"][1].value == "1234"
    assert info.details["number"][1].editable is True
    assert info.details["name"][1].value == "Hudson"
    assert info.details["name"][1].editable is True


def test_update_disables_clear_button_for_non_deletable_state() -> None:
    host = SimpleNamespace(_prod_info_cache={}, active_accessory=None)
    state = SimpleNamespace(is_deletable=False, road_number="19", road_name="LCS Device")
    info = _info_overlay(host)
    info.clear_btn.on_hold = object()

    info.update(state)

    assert info.clear_btn.enabled is False
    assert info.clear_btn.on_hold is None


def test_clear_record_cancels_button_closes_overlay_and_delegates() -> None:
    closed = []
    cleared = []
    host = SimpleNamespace(
        popup_manager=SimpleNamespace(close=lambda overlay: closed.append(overlay)),
        clear_record=lambda state: cleared.append(state),
    )
    state = object()
    info = _info_overlay(host)

    info.clear_record(state)

    assert info.clear_btn.cancel_calls == 1
    assert closed == [info.overlay]
    assert cleared == [state]
