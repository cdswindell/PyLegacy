from __future__ import annotations

import logging
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
        self._height = kwargs.get("height")
        # Every value ever assigned to height, in order. guizero derives a widget's pack fill
        # from this attribute on each repack (Container._pack_widget), so it is the whole
        # mechanism behind a panel reaching down to the scope row -- and the sequence matters:
        # "fill" on show, back to what it was on close.
        self.height_history: list = []

    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, value) -> None:
        self._height = value
        self.height_history.append(value)

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


def test_compact_footer_buttons_stay_tighter_than_portrait() -> None:
    # Inside the row only. The row's distance from the overlay's edges is no longer padding at
    # all -- center_footer_row shares the leftover space around it -- so the pane's lack of
    # vertical slack no longer has to be paid for out of these numbers.
    assert mod.FOOTER_BUTTON_PAD_COMPACT < mod.FOOTER_BUTTON_PAD


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


def test_the_footer_row_is_centred_by_two_equal_expanding_spacers(monkeypatch: pytest.MonkeyPatch) -> None:
    # Tk shares leftover space equally between widgets that expand, and guizero gives a
    # height="fill" box exactly that. Equal on both sides is the whole mechanism: one spacer
    # would leave the row flush against an edge.
    made: list[_Widget] = []
    monkeypatch.setattr(mod, "Box", lambda master, **kwargs: made.append(_Widget(master, **kwargs)) or made[-1])
    overlay = _Widget()

    top, bottom = mod.center_footer_row(overlay)

    assert top.kwargs == {"align": "top", "height": "fill"}
    assert bottom.kwargs == {"align": "bottom", "height": "fill"}
    assert top.kwargs["height"] == bottom.kwargs["height"], "unequal spacers do not centre"
    assert top.master is overlay and bottom.master is overlay


def test_the_bottom_spacer_is_created_first_so_the_row_lands_above_it(monkeypatch: pytest.MonkeyPatch) -> None:
    # pack fills a side in creation order. Create the bottom spacer after the row and it takes
    # the slot above it instead of below, which pushes the row onto the overlay's bottom edge.
    made: list[_Widget] = []
    monkeypatch.setattr(mod, "Box", lambda master, **kwargs: made.append(_Widget(master, **kwargs)) or made[-1])

    mod.center_footer_row(_Widget())

    assert [widget.kwargs["align"] for widget in made] == ["bottom", "top"]


def test_create_popup_centres_the_footer_row_of_every_panel_it_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    # The helper is covered directly above, but that leaves its *wiring* untested: dropping the
    # call from create_popup broke nothing, which is the failure mode that matters. Both
    # branches, because a panel without its own footer button gets a bare Close and used to be
    # the case nobody centred.
    made: list[_Widget] = []

    def make_box(master=None, **kwargs):
        made.append(_Widget(master, **kwargs))
        return made[-1]

    monkeypatch.setattr(mod, "Box", make_box)
    monkeypatch.setattr(mod, "Text", lambda master, **kwargs: _Widget(master, **kwargs))
    monkeypatch.setattr(mod, "PushButton", lambda master, **kwargs: _Widget(master, **kwargs))

    class _Panel(mod.OverlayPanel):
        def __init__(self, has_footer: bool) -> None:
            # OverlayPanel's own __init__ is abstract; create_popup only needs _overlay.
            self._overlay = None
            self._has_footer = has_footer

        @property
        def has_footer(self) -> bool:
            return self._has_footer

        def build(self, body) -> None:
            pass

        def build_footer(self, footer) -> None:
            pass

    for compact in (False, True):
        for label, body_src in (("callable", lambda body: None), ("footer", _Panel(True)), ("bare", _Panel(False))):
            host = _host()
            host.compact = compact
            host.s_18 = 16
            host.s_20 = 20
            manager = mod.PopupManager(host)
            made.clear()

            overlay = manager.create_popup("Options", body_src)

            spacers = [w for w in made if w.master is overlay and w.kwargs.get("height") == "fill"]
            aligns = sorted(w.kwargs["align"] for w in spacers)
            assert aligns == ["bottom", "top"], f"compact={compact} panel={label}"


def test_create_popup_leaves_the_overlay_unsized(monkeypatch: pytest.MonkeyPatch) -> None:
    # The invariant the previous attempt at extending panels broke. Sizing the overlay at
    # construction time -- height="fill" in particular -- puts a fill widget in the host's pack
    # before EngineGui measures the tree for its image baseline, and portrait lost its engine
    # image box. Whatever the mechanism, construction must stay inert: the extension belongs at
    # show time, where no measurement is taken afterwards.
    host = _host()
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
            self._overlay = None

        def build(self, body) -> None:
            pass

        def build_footer(self, footer) -> None:
            pass

    # Both branches: a plain callable body and an OverlayPanel with a footer.
    for body_src in (lambda body: None, _Panel()):
        made.clear()
        overlay = manager.create_popup("Options", body_src)

        assert "height" not in overlay.kwargs
        assert "width" not in overlay.kwargs


def _geom_tk(*, y: int, h: int, cls: str = "Frame", mapped: int = 1):
    return SimpleNamespace(
        winfo_rooty=lambda: y,
        winfo_height=lambda: h,
        winfo_ismapped=lambda: mapped,
        winfo_class=lambda: cls,
        update_idletasks=lambda: None,
    )


def test_show_schedules_the_geometry_report_once_the_overlay_is_on_screen(caplog) -> None:
    # The report itself is covered below; this pins its *wiring*, which is the half that goes
    # missing silently -- a diagnostic nobody calls looks exactly like a panel with no problem.
    host = _host()
    scheduled: list[tuple[int, object]] = []
    host.app.tk = SimpleNamespace(after=lambda ms, fn: scheduled.append((ms, fn)))
    manager = mod.PopupManager(host)
    overlay = _Widget(visible=False)

    with caplog.at_level("DEBUG", logger=mod.log.name):
        manager.show(overlay)

    assert [ms for ms, _ in scheduled] == [mod.POPUP_GEOM_DELAY_MS]
    assert callable(scheduled[0][1])


def test_a_popup_that_never_appeared_is_not_measured(caplog) -> None:
    # fail_place sends show() down its rollback path. Measuring there would report the geometry
    # of an overlay that was just hidden again.
    host = _host()
    scheduled: list[tuple[int, object]] = []
    host.app.tk = SimpleNamespace(after=lambda ms, fn: scheduled.append((ms, fn)))
    manager = mod.PopupManager(host)

    with caplog.at_level("DEBUG", logger=mod.log.name):
        manager.show(_Widget(visible=False, fail_place=True))

    assert scheduled == []


def test_the_geometry_report_names_the_gap_left_to_the_scope_row(caplog) -> None:
    host = _host()
    host.app.tk = SimpleNamespace(update_idletasks=lambda: None)
    host.scope_box = SimpleNamespace(tk=_geom_tk(y=700, h=70))
    overlay = SimpleNamespace(
        tk=_geom_tk(y=100, h=480),
        children=[SimpleNamespace(tk=_geom_tk(y=500, h=40, cls="Frame"))],
    )

    with caplog.at_level("DEBUG", logger=mod.log.name):
        mod._report_popup_geometry(host, overlay)

    report = "\n".join(caplog.messages)
    # 100 + 480 = 580; the scope row starts at 700, so the panel stops 120px short.
    assert "bottom=580" in report
    assert "scope_top=700" in report
    assert "gap=120" in report
    # The child's own band, so a footer row's centre can be checked against the band below the
    # content without re-deriving either by hand: 500..540 inside an overlay ending at 580.
    assert "y=500" in report
    assert "bottom=540" in report


def test_the_geometry_report_survives_a_widget_that_cannot_be_measured(caplog) -> None:
    # It runs half a second after the popup opened, by which time the popup may be gone.
    host = _host()
    host.app.tk = SimpleNamespace(update_idletasks=lambda: None)

    def boom():
        raise RuntimeError("destroyed")

    with caplog.at_level("DEBUG", logger=mod.log.name):
        mod._report_popup_geometry(host, SimpleNamespace(tk=SimpleNamespace(winfo_rooty=boom)))


def _only_root_handler(monkeypatch: pytest.MonkeyPatch, level: int) -> None:
    monkeypatch.setattr(logging.getLogger(), "handlers", [logging.NullHandler(level=level)])


def test_geometry_is_not_measured_when_no_handler_wants_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    # Every report costs two Tk round-trips per child, and nobody should pay them in normal
    # operation. Checking the logger alone would not save it: set_up_logging puts the root logger
    # at DEBUG unconditionally and filters on the handlers, so isEnabledFor is always true and
    # -debug is visible only in the handler levels.
    host = _host()
    scheduled: list[object] = []
    host.app.tk = SimpleNamespace(after=lambda ms, fn: scheduled.append(fn))
    _only_root_handler(monkeypatch, logging.INFO)

    mod.log_popup_geometry(host, _Widget())

    assert scheduled == []
    assert mod.log.isEnabledFor(logging.DEBUG), "the logger says yes; only the handler says no"
    assert mod.debug_diagnostics_enabled() is False


def test_geometry_is_measured_as_soon_as_a_handler_wants_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    # The other half: flipping -debug at runtime moves handler levels, so the trace comes back
    # without a restart.
    host = _host()
    scheduled: list[object] = []
    host.app.tk = SimpleNamespace(after=lambda ms, fn: scheduled.append(fn))
    _only_root_handler(monkeypatch, logging.DEBUG)

    mod.log_popup_geometry(host, _Widget())

    assert len(scheduled) == 1
    assert mod.debug_diagnostics_enabled() is True


@pytest.mark.parametrize("compact", [False, True])
def test_showing_a_panel_extends_it_to_the_scope_row_and_closing_gives_it_back(compact: bool) -> None:
    # Both modes: the ask covers portrait as well as the Deck, and portrait is the one that broke
    # when this was attempted at construction time instead.
    host = _host()
    host.compact = compact
    manager = mod.PopupManager(host)
    overlay = _Widget(visible=False)

    manager.show(overlay)

    assert overlay.height == "fill"

    manager.close()

    assert overlay.height is None
    assert overlay.height_history == ["fill", None]


def test_a_popup_that_failed_to_appear_is_left_collapsed() -> None:
    # place() raises before the overlay is expanded, so the rollback has nothing to undo. An
    # overlay left carrying a fill it never got to use would claim the pane's leftover space
    # while invisible.
    host = _host()
    manager = mod.PopupManager(host)
    overlay = _Widget(visible=False, fail_place=True)

    manager.show(overlay)

    assert overlay.height_history == []
    assert overlay.height is None


def test_closing_restores_whatever_height_the_overlay_was_built_with() -> None:
    # Reversible rather than reset-to-None: create_popup builds the overlay unsized today, and a
    # test says so, but collapse should not be the thing that silently discards a size if that
    # ever changes.
    host = _host()
    manager = mod.PopupManager(host)
    overlay = _Widget(visible=False, height=240)

    manager.show(overlay)
    assert overlay.height == "fill"

    manager.close()

    assert overlay.height == 240


def test_an_overlay_marked_no_expand_is_left_alone() -> None:
    # The configured-accessory popups: they mount a GUI that owns its own layout.
    host = _host()
    manager = mod.PopupManager(host)
    overlay = _Widget(visible=False)
    setattr(overlay, mod._NO_EXPAND_ATTR, True)

    manager.show(overlay)

    assert overlay.height_history == []
    assert overlay.height is None


def test_accessory_popups_are_marked_no_expand_when_built(monkeypatch: pytest.MonkeyPatch) -> None:
    # Covers the wiring, not the helper: create_popup is the only place that knows which overlay
    # hosts a mounted accessory GUI.
    host = _host()
    made: list[_Widget] = []

    def make_box(master=None, **kwargs):
        made.append(_Widget(master, **kwargs))
        return made[-1]

    monkeypatch.setattr(mod, "Box", make_box)
    monkeypatch.setattr(mod, "Text", lambda master, **kwargs: _Widget(master, **kwargs))
    monkeypatch.setattr(mod, "HoldButton", lambda master, **kwargs: _Widget(master, **kwargs))
    monkeypatch.setattr(mod.PopupManager, "_get_close_acc_images", lambda *_a: (None, None))
    host.add_vspace = lambda *_args: None
    host.button_size = 90
    manager = mod.PopupManager(host)

    class _Adapter(mod.ConfiguredAccessoryAdapter):
        # Only the surface create_popup touches; the real adapter needs a live accessory config,
        # and both state and gui are read-only properties on it.
        state = SimpleNamespace(is_asc2=False)
        gui = SimpleNamespace(mount_gui=lambda _overlay: None)

        def __init__(self) -> None:
            pass

        def ensure_gui(self, *, aggregator=None, extra_kwargs=None):
            return self.gui

        def attach_overlay(self, overlay) -> None:
            pass

    overlay = manager.create_popup("Station", _Adapter())

    assert getattr(overlay, mod._NO_EXPAND_ATTR, False) is True
