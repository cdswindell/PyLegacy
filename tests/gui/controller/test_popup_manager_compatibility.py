from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.popup_manager as mod


class _Tk:
    def __init__(self, fail_place: bool = False) -> None:
        self.fail_place = fail_place
        self.placed: list[tuple[int, int]] = []
        self.forgotten = 0
        self.configured: list[dict] = []
        self.packed: list[dict] = []

    def place(self, *, x: int, y: int) -> None:
        if self.fail_place:
            raise RuntimeError("no window")
        self.placed.append((x, y))

    def place_forget(self) -> None:
        self.forgotten += 1

    def config(self, **kwargs) -> None:
        self.configured.append(kwargs)

    def pack_configure(self, **kwargs) -> None:
        self.packed.append(kwargs)


class _Widget:
    def __init__(self, master=None, *, visible: bool = True, fail_place: bool = False, **kwargs) -> None:
        self.master = master
        self.kwargs = kwargs
        self.visible = visible
        self.tk = _Tk(fail_place=fail_place)

    def hide(self) -> None:
        self.visible = False

    def show(self) -> None:
        self.visible = True


def _host() -> SimpleNamespace:
    app = SimpleNamespace(display_calls=0)

    def display_widgets() -> None:
        app.display_calls += 1

    app.display_widgets = display_widgets
    host = SimpleNamespace(
        app=app,
        button_size=90,
        emergency_box_width=600,
        s_18=27,
        s_20=30,
        popup_position=(12, 34),
        controller_box=_Widget(),
        keypad_box=_Widget(visible=False),
        amc2_ops_box=None,
        sensor_track_box=None,
        image_box=_Widget(),
        acc_overlay=_Widget(),
        engine_ops_cells={},
        locked=nullcontext,
        cache=lambda *_args: None,
        compact=False,
    )
    return host


def test_create_popup_is_app_rooted_hidden_and_does_not_repack_host(monkeypatch: pytest.MonkeyPatch) -> None:
    host = _host()
    made: list[_Widget] = []

    def make_box(master=None, **kwargs):
        if master is host.app:
            master.display_widgets()
        widget = _Widget(master, **kwargs)
        made.append(widget)
        return widget

    monkeypatch.setattr(mod, "Box", make_box)
    monkeypatch.setattr(mod, "Text", lambda master, **kwargs: _Widget(master, **kwargs))
    monkeypatch.setattr(mod, "PushButton", lambda master, **kwargs: _Widget(master, **kwargs))
    manager = mod.PopupManager(host)
    built: list[object] = []

    overlay = manager.create_popup("Options", lambda body: built.append(body))

    assert overlay is made[0]
    assert overlay.master is host.app
    assert overlay.visible is False
    assert host.app.display_calls == 0
    assert callable(host.app.display_widgets)
    assert len(built) == 1


def test_get_or_create_caches_overlay_by_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mod, "Box", _Widget)
    manager = mod.PopupManager(_host())
    overlay = _Widget()
    calls: list[str] = []
    monkeypatch.setattr(
        manager,
        "create_popup",
        lambda *_args, **_kwargs: calls.append("create") or overlay,
    )

    first = manager.get_or_create("lights", "Lights", lambda _body: None)
    second = manager.get_or_create("lights", "Lights", lambda _body: None)

    assert first is overlay
    assert second is overlay
    assert calls == ["create"]


def test_show_and_close_restore_host_content_image_and_accessory() -> None:
    host = _host()
    manager = mod.PopupManager(host)
    overlay = _Widget(visible=False)

    manager.show(overlay, hide_image_box=True)

    assert overlay.tk.placed == [(12, 34)]
    assert overlay.visible is True
    assert host.controller_box.visible is False
    assert host.image_box.visible is False
    assert host.acc_overlay.visible is False

    manager.close()

    assert overlay.visible is False
    assert overlay.tk.forgotten == 1
    assert host.controller_box.visible is True
    assert host.image_box.visible is True
    assert host.acc_overlay.visible is True


def test_failed_show_restores_content_and_image_and_button_state() -> None:
    host = _host()
    host.acc_overlay.visible = False
    manager = mod.PopupManager(host)
    overlay = _Widget(visible=False, fail_place=True)
    button = SimpleNamespace(restore_calls=0)
    button.restore_color_state = lambda: setattr(button, "restore_calls", button.restore_calls + 1)

    manager.show(overlay, hide_image_box=True, button=button)

    assert manager._state.current_popup is None
    assert host.controller_box.visible is True
    assert host.image_box.visible is True
    assert button.restore_calls == 1


def test_embedded_popup_is_parented_and_layout_suspended_within_host_root(monkeypatch: pytest.MonkeyPatch) -> None:
    host = _host()
    pane = SimpleNamespace(display_calls=0)
    pane.display_widgets = lambda: setattr(pane, "display_calls", pane.display_calls + 1)
    host.root = pane
    made: list[_Widget] = []

    def make_box(master=None, **kwargs):
        if master is pane:
            master.display_widgets()
        widget = _Widget(master, **kwargs)
        made.append(widget)
        return widget

    monkeypatch.setattr(mod, "Box", make_box)
    monkeypatch.setattr(mod, "Text", lambda master, **kwargs: _Widget(master, **kwargs))
    monkeypatch.setattr(mod, "PushButton", lambda master, **kwargs: _Widget(master, **kwargs))
    manager = mod.PopupManager(host)

    overlay = manager.create_popup("Options", lambda _body: None)

    assert overlay.master is pane
    assert pane.display_calls == 0
    assert host.app.display_calls == 0


def test_compact_close_button_uses_reduced_height_without_changing_portrait(monkeypatch: pytest.MonkeyPatch) -> None:
    buttons: list[_Widget] = []

    def make_button(master, **kwargs):
        button = _Widget(master, **kwargs)
        buttons.append(button)
        return button

    monkeypatch.setattr(mod, "PushButton", make_button)
    manager = mod.PopupManager(_host())

    portrait = _Widget()
    manager.add_close_btn(manager._host, None, portrait)
    assert buttons[-1].tk.configured[-1]["pady"] == 4
    assert buttons[-1].tk.packed[-1] == {"padx": 20, "pady": 20}

    manager._host.compact = True
    compact = _Widget()
    manager.add_close_btn(manager._host, None, compact)
    assert buttons[-1].tk.configured[-1]["pady"] == 1
    assert buttons[-1].tk.packed[-1] == {
        "padx": mod.FOOTER_BUTTON_PAD_COMPACT,
        "pady": mod.FOOTER_BUTTON_PAD_COMPACT,
    }


def _footer_button() -> _Widget:
    return _Widget()


def test_a_footer_button_records_the_packing_it_was_given() -> None:
    # Recorded because creating the next sibling discards it: guizero re-packs every child
    # keeping only side/fill, so whichever button is added last is the only one that keeps
    # its padding. That is why Close looked inset and the button beside it did not.
    host = SimpleNamespace(compact=True, s_18=16, s_20=20)
    btn = _footer_button()

    mod.style_footer_button(host, btn)

    assert btn.tk.packed[-1] == {
        "padx": mod.FOOTER_BUTTON_PAD_COMPACT,
        "pady": mod.FOOTER_BUTTON_PAD_COMPACT,
    }
    assert getattr(btn, mod._FOOTER_PACK_ATTR) == btn.tk.packed[-1]


def test_footer_buttons_are_styled_identically_in_each_mode() -> None:
    # The defect was three copies of one style. Whatever a panel puts in its footer has to
    # come out matching Close, in both modes.
    for compact, size, inner_pady, pad in (
        (True, 16, 1, mod.FOOTER_BUTTON_PAD_COMPACT),
        (False, 20, 4, mod.FOOTER_BUTTON_PAD),
    ):
        host = SimpleNamespace(compact=compact, s_18=16, s_20=20)
        close, other = _footer_button(), _footer_button()

        mod.style_footer_button(host, close)
        mod.style_footer_button(host, other)

        assert close.tk.configured == other.tk.configured, f"compact={compact}"
        assert close.tk.packed == other.tk.packed, f"compact={compact}"
        assert close.text_size == other.text_size == size
        assert close.tk.configured[-1]["pady"] == inner_pady
        assert close.tk.packed[-1] == {"padx": pad, "pady": pad}


def test_restoring_replays_only_the_buttons_that_were_styled() -> None:
    host = SimpleNamespace(compact=True, s_18=16, s_20=20)
    styled, plain = _footer_button(), _footer_button()
    mod.style_footer_button(host, styled)
    footer = SimpleNamespace(children=[styled, plain])
    styled.tk.packed.clear()  # what display_widgets leaves behind
    plain.tk.packed.clear()

    mod.restore_footer_packing(footer)

    assert styled.tk.packed == [{"padx": mod.FOOTER_BUTTON_PAD_COMPACT, "pady": mod.FOOTER_BUTTON_PAD_COMPACT}]
    assert plain.tk.packed == [], "a spacer is re-packed by guizero; it has no padding to restore"


def test_adding_close_repairs_the_packing_of_the_button_beside_it(monkeypatch: pytest.MonkeyPatch) -> None:
    # The end-to-end shape: a panel styles its own button, then create_popup adds Close --
    # which is the creation that wipes the first one. add_close_btn has to put it back.
    host = _host()
    host.compact = True
    host.s_18 = 16
    host.s_20 = 20
    made: list[_Widget] = []
    monkeypatch.setattr(mod, "PushButton", lambda master, **kwargs: made.append(_Widget(master, **kwargs)) or made[-1])
    manager = mod.PopupManager(host)
    panel_btn = _footer_button()
    mod.style_footer_button(host, panel_btn)
    footer = SimpleNamespace(children=[panel_btn], tk=_Tk())
    panel_btn.tk.packed.clear()  # guizero drops it when Close is created

    manager.add_close_btn(host, None, footer)

    assert panel_btn.tk.packed[-1] == made[-1].tk.packed[-1]


def test_the_footer_spacer_tracks_the_mode() -> None:
    # StateInfoOverlay's copy was a fixed host.s_72 -- an enormous gap beside a compact Close.
    made: list[_Widget] = []

    for compact, expected in ((True, mod.FOOTER_GAP_COMPACT), (False, mod.FOOTER_GAP)):
        cached: list[object] = []
        host = SimpleNamespace(compact=compact, cache=cached.append)
        original = mod.Text
        try:
            mod.Text = lambda master, **kwargs: made.append(_Widget(master, **kwargs)) or made[-1]
            spacer = mod.footer_spacer(host, object())
        finally:
            mod.Text = original

        assert spacer.text_size == expected, f"compact={compact}"
        assert cached == [spacer], "the spacer has to be cached like any other widget"


def test_create_popup_centres_the_footer_row_it_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    # The helper is covered directly above, but that leaves its *wiring* untested: dropping
    # the call from create_popup broke nothing, which is the failure mode that matters.
    host = _host()
    host.compact = True
    host.s_18 = 16
    host.s_20 = 20
    made: list[_Widget] = []

    def make_box(master=None, **kwargs):
        made.append(_Widget(master, **kwargs))
        return made[-1]

    monkeypatch.setattr(mod, "Box", make_box)
    monkeypatch.setattr(mod, "Text", lambda master, **kwargs: _Widget(master, **kwargs))
    monkeypatch.setattr(mod, "PushButton", lambda master, **kwargs: _Widget(master, **kwargs))
    manager = mod.PopupManager(host)

    class _Panel(mod.OverlayPanel):
        has_footer = True

        def __init__(self) -> None:
            # OverlayPanel's own __init__ is abstract; create_popup only needs _overlay.
            self._overlay = None

        def build(self, body) -> None:
            pass

        def build_footer(self, footer) -> None:
            pass

    manager.create_popup("Options", _Panel())

    footer = next(widget for widget in made if widget.kwargs.get("align") == "bottom")
    assert footer.tk.packed[-1] == {"expand": True}


def test_the_overlay_fills_the_band_down_to_the_scope_buttons(monkeypatch: pytest.MonkeyPatch) -> None:
    # The overlay is a side=top packed child of the pane and the scope box is side=bottom, so
    # the band between them is the overlay's parcel. guizero maps height="fill" to Tk's fill=Y
    # plus expand for a top/bottom side, which is what makes every panel reach the scope row
    # instead of stopping wherever its content happens to end.
    host = _host()
    made: list[_Widget] = []
    monkeypatch.setattr(mod, "Box", lambda master=None, **kwargs: made.append(_Widget(master, **kwargs)) or made[-1])
    monkeypatch.setattr(mod, "Text", lambda master, **kwargs: _Widget(master, **kwargs))
    monkeypatch.setattr(mod, "PushButton", lambda master, **kwargs: _Widget(master, **kwargs))
    manager = mod.PopupManager(host)

    overlay = manager.create_popup("Options", lambda _body: None)

    assert overlay.kwargs["height"] == "fill"
    assert overlay is made[0]


def test_centring_expands_the_parcel_without_filling_it() -> None:
    # expand grows the *parcel* so pack has room to centre in; fill would stretch the widget
    # itself and there would be nothing to centre.
    widget = _Widget()

    mod.center_in_leftover(widget)

    assert widget.tk.packed == [{"expand": True}]
    assert "fill" not in widget.tk.packed[-1]


def test_a_widget_that_cannot_be_packed_does_not_break_the_popup() -> None:
    class _Unpackable:
        tk = SimpleNamespace(pack_configure=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("gone")))

    mod.center_in_leftover(_Unpackable())
    mod.center_in_leftover(None)


def test_a_footerless_popup_centres_its_close_button(monkeypatch: pytest.MonkeyPatch) -> None:
    # For a panel with no footer row, Close *is* the row -- so it gets the same treatment.
    host = _host()
    buttons: list[_Widget] = []
    monkeypatch.setattr(mod, "Box", lambda master=None, **kwargs: _Widget(master, **kwargs))
    monkeypatch.setattr(mod, "Text", lambda master, **kwargs: _Widget(master, **kwargs))
    monkeypatch.setattr(
        mod, "PushButton", lambda master, **kwargs: buttons.append(_Widget(master, **kwargs)) or buttons[-1]
    )
    manager = mod.PopupManager(host)

    manager.create_popup("Options", lambda _body: None)

    assert buttons[-1].tk.packed[-1] == {"expand": True}


def test_add_close_btn_hands_the_button_back() -> None:
    # Its caller has to be able to place the button; returning None was why the footerless
    # path could not be centred.
    host = _host()
    manager = mod.PopupManager(host)
    made: list[_Widget] = []
    original = mod.PushButton
    try:
        mod.PushButton = lambda master, **kwargs: made.append(_Widget(master, **kwargs)) or made[-1]
        returned = manager.add_close_btn(host, None, _Widget())
    finally:
        mod.PushButton = original

    assert returned is made[-1]
