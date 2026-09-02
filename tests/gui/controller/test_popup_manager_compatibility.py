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


# What a guizero repack leaves behind: side/fill only, everything else forgotten.
_REPACKED = {"repacked": True}


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
        self.children: list = []
        if isinstance(master, _Widget):
            master.children.append(self)
            master.display_widgets()

    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, value) -> None:
        self._height = value
        self.height_history.append(value)

    def display_widgets(self) -> None:
        """Emulate the repack guizero does whenever a child is created.

        Container._pack_widget rebuilds each child's option dict from scratch and keeps only side
        and fill, so anything a caller set with pack_configure -- a footer button's padding, say
        -- is discarded. Without this the stub silently made every ordering look correct, and two
        mutations that reorder create_popup or drop restore_footer_packing survived.
        """
        for child in self.children:
            child.tk.packed.append(_REPACKED)

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
    # all -- footer_lead and footer_fill place the row within the overlay -- so the pane's lack
    # of vertical slack no longer has to be paid for out of these numbers.
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


def test_the_leftover_space_all_goes_below_the_footer_row(monkeypatch: pytest.MonkeyPatch) -> None:
    # One expanding box, on the bottom. It was an equal split between two, which is right for a
    # panel that nearly fills the pane and wrong for a short one: half of several hundred pixels
    # left Lights and Tower Dialogs with their buttons floating mid-overlay.
    made: list[_Widget] = []
    monkeypatch.setattr(mod, "Box", lambda master, **kwargs: made.append(_Widget(master, **kwargs)) or made[-1])
    overlay = _Widget()

    fill = mod.footer_fill(overlay)

    assert fill.kwargs == {"align": "bottom", "height": "fill"}
    assert fill.master is overlay


@pytest.mark.parametrize("compact,expected", [(False, mod.FOOTER_LEAD), (True, mod.FOOTER_LEAD_COMPACT)])
def test_the_row_sits_a_fixed_distance_below_the_content(
    monkeypatch: pytest.MonkeyPatch, compact: bool, expected: int
) -> None:
    made: list[_Widget] = []
    monkeypatch.setattr(mod, "Box", lambda master, **kwargs: made.append(_Widget(master, **kwargs)) or made[-1])

    lead = mod.footer_lead(SimpleNamespace(compact=compact), _Widget())

    assert lead.kwargs["height"] == expected
    assert lead.kwargs["align"] == "top"
    # Not decoration: guizero warns when both sizes are ints and one is zero, and a fill is the
    # documented exemption. A bare height= here is the warning that appeared five times before.
    assert lead.kwargs["width"] == "fill"


def test_the_compact_lead_is_what_a_centred_row_used_to_look_like() -> None:
    # The admin panel's whole spare band is 2 * (52 - 40) = 24px, so 12 above and the rest below
    # draws the same picture the equal split did -- which is the one that was signed off. Portrait
    # gets more because it has more to spend.
    assert mod.FOOTER_LEAD_COMPACT == 12
    assert mod.FOOTER_LEAD > mod.FOOTER_LEAD_COMPACT


def test_the_lead_is_created_after_the_row_so_a_tight_band_loses_whitespace_not_buttons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The lead is the only thing here that asks for space unconditionally, and pack allots in
    # creation order. Created before the row, it takes its 12-24px first and a band too tight for
    # both clips the buttons instead of the empty box.
    host = _host()
    created: list[_Widget] = []

    def make(master=None, **kwargs):
        created.append(_Widget(master, **kwargs))
        return created[-1]

    monkeypatch.setattr(mod, "Box", make)
    monkeypatch.setattr(mod, "Text", make)
    monkeypatch.setattr(mod, "PushButton", make)
    manager = mod.PopupManager(host)

    manager.create_popup("Options", lambda _body: None)

    fill = next(w for w in created if w.kwargs.get("height") == "fill")
    close = next(w for w in created if w.kwargs.get("text") == "Close")
    lead = next(w for w in created if w.kwargs.get("height") == mod.FOOTER_LEAD)
    assert created.index(fill) < created.index(close) < created.index(lead)
    # Creating the lead re-packed the overlay's children, and a bare Close is one of them, so its
    # styling had to be replayed afterwards or it renders with no padding at all.
    assert close.tk.packed[-1] == {"padx": mod.FOOTER_BUTTON_PAD, "pady": mod.FOOTER_BUTTON_PAD}


def test_create_popup_positions_the_footer_row_of_every_panel_it_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    # The helpers are covered directly above, but that leaves their *wiring* untested: dropping
    # either call from create_popup broke nothing, which is the failure mode that matters. All
    # three branches, because a panel without its own footer button gets a bare Close and used to
    # be the case nobody positioned.
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
        expected_lead = mod.FOOTER_LEAD_COMPACT if compact else mod.FOOTER_LEAD
        for label, body_src in (("callable", lambda body: None), ("footer", _Panel(True)), ("bare", _Panel(False))):
            host = _host()
            host.compact = compact
            host.s_18 = 16
            host.s_20 = 20
            manager = mod.PopupManager(host)
            made.clear()

            overlay = manager.create_popup("Options", body_src)
            mine = [w for w in made if w.master is overlay]

            where = f"compact={compact} panel={label}"
            assert [w.kwargs["align"] for w in mine if w.kwargs.get("height") == "fill"] == ["bottom"], where
            assert [w.kwargs["align"] for w in mine if w.kwargs.get("height") == expected_lead] == ["top"], where


def test_a_panel_that_declines_close_is_given_none_but_keeps_its_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The LCS panel on a Mac or a PC: the window's own title bar closes it, so a Close
    # inside the window is a second copy of what the window already has. Asked in both
    # branches, since the answer means the same however a panel arranges its own buttons.
    # The band above and below the row is measured rather than counted, so an empty row
    # costs it nothing and the fill and the lead are built either way.
    made: list[_Widget] = []

    def make(master=None, **kwargs):
        made.append(_Widget(master, **kwargs))
        return made[-1]

    monkeypatch.setattr(mod, "Box", make)
    monkeypatch.setattr(mod, "Text", make)
    monkeypatch.setattr(mod, "PushButton", make)

    class _Panel(mod.OverlayPanel):
        def __init__(self, has_footer: bool, has_close: bool) -> None:
            # OverlayPanel's own __init__ is abstract; create_popup only needs _overlay.
            self._overlay = None
            self._has_footer = has_footer
            self._has_close = has_close

        @property
        def has_footer(self) -> bool:
            return self._has_footer

        @property
        def has_close(self) -> bool:
            return self._has_close

        def build(self, body) -> None:
            pass

        def build_footer(self, footer) -> None:
            pass

    for has_footer in (True, False):
        for has_close, expected in ((True, 1), (False, 0)):
            manager = mod.PopupManager(_host())
            made.clear()

            overlay = manager.create_popup("Options", _Panel(has_footer, has_close))
            mine = [w for w in made if w.master is overlay]

            where = f"has_footer={has_footer} has_close={has_close}"
            assert len([w for w in made if w.kwargs.get("text") == "Close"]) == expected, where
            assert [w.kwargs["align"] for w in mine if w.kwargs.get("height") == "fill"] == ["bottom"], where
            assert [w.kwargs["align"] for w in mine if w.kwargs.get("height") == mod.FOOTER_LEAD] == ["top"], where


def test_every_panel_but_the_one_that_says_otherwise_gets_close() -> None:
    # The opt-out is a panel's to take, and the base class does not take it: a panel that
    # says nothing about Close is dismissed by Close and nothing else.
    assert mod.OverlayPanel.has_close.fget(object()) is True


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


def _measurable(height: int, *, mapped: int = 1) -> _Tk:
    tk = _Tk()
    tk.winfo_height = lambda: height
    tk.winfo_ismapped = lambda: mapped
    return tk


def _balanceable(*, below: int, compact: bool, mapped: int = 1):
    """An overlay whose fill box measures ``below`` pixels, ready for the correction pass."""
    host = _host()
    host.compact = compact
    host.app.tk = SimpleNamespace(update_idletasks=lambda: None, after_idle=lambda fn: fn())
    overlay = _Widget()
    overlay.tk = _measurable(0, mapped=mapped)
    lead = _Widget(height=mod.footer_lead_height(host))
    fill = _Widget(height="fill")
    fill.tk = _measurable(below)
    setattr(overlay, mod._FOOTER_BOXES_ATTR, (lead, fill))
    return host, overlay, lead, fill


@pytest.mark.parametrize("compact", [False, True])
def test_a_roomy_band_keeps_the_fixed_lead_and_changes_nothing(monkeypatch: pytest.MonkeyPatch, compact: bool) -> None:
    # The common case, and it has to be a genuine no-op: assigning a height re-packs the overlay,
    # so a correction pass that always writes would repack every panel on every show.
    lead_px = mod.FOOTER_LEAD_COMPACT if compact else mod.FOOTER_LEAD
    host, overlay, lead, _fill = _balanceable(below=400, compact=compact)

    mod.balance_footer_row(host, overlay)

    assert lead.height == lead_px
    assert lead.height_history == [], "nothing was assigned, so nothing was re-packed"


@pytest.mark.parametrize(
    "compact,below,expected",
    [
        (True, 4, 8),  # (4 + 12) // 2
        (True, 11, 11),  # (11 + 12) // 2, rounded down
        (False, 6, 15),  # (6 + 24) // 2
        (False, 0, 12),  # nothing below at all
    ],
)
def test_a_band_tighter_than_the_lead_centres_the_row(
    monkeypatch: pytest.MonkeyPatch, compact: bool, below: int, expected: int
) -> None:
    # Less room below the row than above it means the fixed lead has pinned the row against the
    # bottom edge. Even the two up.
    host, overlay, lead, _fill = _balanceable(below=below, compact=compact)

    mod.balance_footer_row(host, overlay)

    assert lead.height == expected


def test_the_correction_settles_instead_of_creeping(monkeypatch: pytest.MonkeyPatch) -> None:
    # It runs on every show, so it has to be stable: once the two sides are level the condition
    # stops firing. Correcting the lead alone is enough because the fill is the expander and
    # re-absorbs the difference, which the second pass sees.
    host, overlay, lead, fill = _balanceable(below=4, compact=True)

    mod.balance_footer_row(host, overlay)
    settled = lead.height
    fill.tk.winfo_height = lambda: settled  # the fill gave back what the lead released

    mod.balance_footer_row(host, overlay)

    assert lead.height == settled
    assert lead.height_history == [settled], "a second pass must not move it again"


def test_an_unmapped_overlay_is_not_measured(monkeypatch: pytest.MonkeyPatch) -> None:
    # winfo_height reads 1 before Tk lays a widget out, which would look like the tightest
    # possible band and centre the row on a band that does not exist yet.
    host, overlay, lead, _fill = _balanceable(below=1, compact=True, mapped=0)

    mod.balance_footer_row(host, overlay)

    assert lead.height_history == []


def test_a_popup_with_no_recorded_spacers_is_left_alone() -> None:
    # The accessory popups: they never get a lead or a fill, and nothing should be inferred.
    host = _host()
    scheduled: list[object] = []
    host.app.tk = SimpleNamespace(after_idle=scheduled.append)

    mod.balance_footer_row(host, _Widget())

    assert scheduled == []


def test_create_popup_records_the_spacer_pair_for_every_panel(monkeypatch: pytest.MonkeyPatch) -> None:
    made: list[_Widget] = []
    monkeypatch.setattr(mod, "Box", lambda master=None, **kwargs: made.append(_Widget(master, **kwargs)) or made[-1])
    monkeypatch.setattr(mod, "Text", lambda master, **kwargs: _Widget(master, **kwargs))
    monkeypatch.setattr(mod, "PushButton", lambda master, **kwargs: _Widget(master, **kwargs))
    host = _host()
    manager = mod.PopupManager(host)

    overlay = manager.create_popup("Options", lambda _body: None)

    lead, fill = getattr(overlay, mod._FOOTER_BOXES_ATTR)
    assert lead.kwargs["height"] == mod.FOOTER_LEAD
    assert fill.kwargs["height"] == "fill"


def test_show_runs_the_correction_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    # Wiring, not the helper: a correction nobody invokes looks exactly like a panel with no
    # problem, which is how the whole feature got reverted the first time.
    host = _host()
    ran: list[str] = []
    host.app.tk = SimpleNamespace(after_idle=lambda fn: ran.append("balanced"))
    manager = mod.PopupManager(host)
    overlay = _Widget(visible=False)
    setattr(overlay, mod._FOOTER_BOXES_ATTR, (_Widget(height=12), _Widget(height="fill")))

    manager.show(overlay)

    assert ran == ["balanced"]


def test_a_popup_that_failed_to_appear_is_not_balanced() -> None:
    host = _host()
    ran: list[str] = []
    host.app.tk = SimpleNamespace(after_idle=lambda fn: ran.append("balanced"))
    manager = mod.PopupManager(host)
    overlay = _Widget(visible=False, fail_place=True)
    setattr(overlay, mod._FOOTER_BOXES_ATTR, (_Widget(height=12), _Widget(height="fill")))

    manager.show(overlay)

    assert ran == []


def _popup_with_title(monkeypatch: pytest.MonkeyPatch, title: str, *, button_size: int = 133, compact: bool = False):
    made: list[_Widget] = []
    texts: list[_Widget] = []

    def make_box(master=None, **kwargs):
        made.append(_Widget(master, **kwargs))
        return made[-1]

    def make_text(master=None, **kwargs):
        texts.append(_Widget(master, **kwargs))
        return texts[-1]

    monkeypatch.setattr(mod, "Box", make_box)
    monkeypatch.setattr(mod, "Text", make_text)
    monkeypatch.setattr(mod, "PushButton", lambda master, **kwargs: _Widget(master, **kwargs))
    host = _host()
    host.button_size = button_size
    host.compact = compact
    manager = mod.PopupManager(host)

    manager.create_popup(title, lambda _body: None)

    title_row = next(w for w in made if w.kwargs.get("width") == host.emergency_box_width)
    return title_row, texts[0]


def test_a_popup_title_is_centered_in_its_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """The title used to sit at the top of a fixed-height row on both devices.

    It has no align, so guizero passes no side and Tk packs it at the top; the row's height is
    button_size // 3 with pack_propagate off, which is 44px on the Pi against 26px on a Deck pane.
    The Deck looked centered only because its row happens to match its text height, while the Pi
    left ~20px empty beneath. fill=Y stretches the Label to the row instead, and a Label's anchor
    defaults to center, so the text lands in the middle of whatever height the row has.
    """
    _title_row, title = _popup_with_title(monkeypatch, "Bell/Horn Options")

    assert title.kwargs["height"] == "fill"
    # No align, which is what makes guizero add expand=YES alongside fill=Y (base.py _pack_widget:
    # `side is None and fill == Y`). Given a side it would fill without centering.
    assert "align" not in title.kwargs


def test_centering_the_title_does_not_resize_its_row(monkeypatch: pytest.MonkeyPatch) -> None:
    # The band itself must not move: only where the text sits inside it changes.
    for button_size, expected in ((133, 44), (80, 26)):  # Pi, then a Deck pane
        title_row, _title = _popup_with_title(monkeypatch, "Bell/Horn Options", button_size=button_size)

        assert title_row.kwargs["height"] == expected


def test_a_multi_line_title_still_gets_a_taller_row(monkeypatch: pytest.MonkeyPatch) -> None:
    title_row, title = _popup_with_title(monkeypatch, "Two\nLines")

    assert title_row.kwargs["height"] == 2 * (133 // 3)
    assert title.kwargs["height"] == "fill", "still centered, in the taller row"


def test_a_portrait_title_is_nudged_down_off_the_rows_top_edge(monkeypatch: pytest.MonkeyPatch) -> None:
    # Centered was very slightly high to the eye. The nudge is pack padding, which with fill=Y
    # shrinks the parcel the label stretches into from the top, so the centered text moves by half
    # of it -- 4 reads as 2px.
    _title_row, title = _popup_with_title(monkeypatch, "Bell/Horn Options", compact=False)

    # Last wins: guizero packs the title once at its own creation, and the nudge is applied after.
    assert title.tk.packed[-1] == {"pady": (mod.TITLE_TOP_PAD, 0)}
    assert mod.TITLE_TOP_PAD > 0


def test_a_compact_title_is_not_nudged(monkeypatch: pytest.MonkeyPatch) -> None:
    # A Deck pane's title row is 26px against the Pi's 44px, and its text nearly fills it. There is
    # no slack to spend, so padding the top would push the text into the bottom edge instead.
    _title_row, title = _popup_with_title(monkeypatch, "Bell/Horn Options", button_size=80, compact=True)

    assert all("pady" not in options for options in title.tk.packed)


def test_the_nudge_still_leaves_the_title_centered(monkeypatch: pytest.MonkeyPatch) -> None:
    # It shifts a centered label, it does not replace the centering: drop the fill and the padding
    # would push a top-packed title further down instead of nudging a centered one.
    _title_row, title = _popup_with_title(monkeypatch, "Bell/Horn Options", compact=False)

    assert title.kwargs["height"] == "fill"
    assert "align" not in title.kwargs
