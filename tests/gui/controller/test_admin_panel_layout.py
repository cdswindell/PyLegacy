import threading
from threading import Event, RLock
from types import SimpleNamespace

import src.pytrain.gui.controller.admin_panel as mod
import src.pytrain.gui.controller.popup_manager as popup_manager


class _Tk:
    def __init__(self) -> None:
        self.columns = []
        self.configs = []
        self.rows = []
        self.grid = None
        self.grid_propagates = []
        self.pack_configs = []
        self.pack_propagates = []

    def config(self, **kwargs) -> None:
        self.configs.append(kwargs)

    def grid_configure(self, **kwargs) -> None:
        self.grid = kwargs

    def grid_columnconfigure(self, column, **kwargs) -> None:
        self.columns.append((column, kwargs))

    def grid_rowconfigure(self, row, **kwargs) -> None:
        self.rows.append((row, kwargs))

    def grid_propagate(self, value) -> None:
        self.grid_propagates.append(value)

    def pack_configure(self, **kwargs) -> None:
        self.pack_configs.append(kwargs)

    def pack_propagate(self, value) -> None:
        self.pack_propagates.append(value)


class _TitleBox:
    instances = []

    def __init__(self, _parent, **kwargs) -> None:
        self.kwargs = kwargs
        self.tk = _Tk()
        self.text_size = None
        self.instances.append(self)

    @staticmethod
    def decorate_checkbox(*_args, **_kwargs) -> None:
        pass

    def disable(self) -> None:
        pass

    def enable(self) -> None:
        pass


def _panel(compact: bool) -> mod.AdminPanel:
    panel = mod.AdminPanel.__new__(mod.AdminPanel)
    panel._gui = SimpleNamespace(button_size=79, s_10=9, version="PyTrain Client v2.9.3+", controller_profile=None)
    panel._pytrain = SimpleNamespace(is_client=True)
    panel._width = 632
    panel._compact = compact
    panel._admin_buttons = {}  # normally set in __init__, which this factory bypasses
    panel._compact_controls = []
    return panel


def test_compact_titlebox_has_bounded_height_and_equal_control_columns(monkeypatch) -> None:
    monkeypatch.setattr(mod, "TitleBox", _TitleBox)
    panel = _panel(compact=True)

    titlebox = panel._titlebox(object(), "Reload/Refresh", grid=[0, 1, 2, 1])

    assert titlebox.kwargs["height"] == panel.compact_section_height
    assert titlebox.tk.grid_propagates == [False]
    assert titlebox.tk.pack_propagates == []
    assert titlebox.tk.columns == [
        (0, {"weight": 1, "minsize": panel.compact_control_width, "uniform": "admin_controls"}),
        (1, {"weight": 0}),
        (2, {"weight": 1, "minsize": panel.compact_control_width, "uniform": "admin_controls"}),
    ]
    assert titlebox.tk.rows == [(0, {"weight": 0, "minsize": panel.compact_control_height})]
    # No asserted width: self._width is the whole pane, which a section inside admin_box
    # (padx=2 a side, 1px border) can never be given. It fills its column instead, with no
    # padding of its own -- padding here would come off the width its columns share.
    # "fill", not absent: a height with no width trips a guizero warning, and fill is the
    # documented exemption. It also leaves the tk width unset, which is the point.
    assert titlebox.kwargs["width"] == "fill"
    assert titlebox.tk.configs == [], "compact must not assert a pixel width"
    assert titlebox.tk.grid == {"sticky": "nsew", "padx": 0, "pady": 0}
    assert panel._compact_controls == [(titlebox, {"sticky": "nsew", "padx": 0, "pady": 0})]


def test_portrait_titlebox_still_asserts_the_panel_width(monkeypatch) -> None:
    # Portrait has no fixed section heights and no column to stretch into, so it keeps the
    # explicit width it has always had.
    monkeypatch.setattr(mod, "TitleBox", _TitleBox)
    panel = _panel(compact=False)

    # Two portrait paths: without a height it is built bare and given the width by config;
    # with one it takes the same branch compact does, and still gets the explicit width.
    bare = panel._titlebox(object(), "Reload/Refresh", grid=[0, 1, 2, 1])
    sized = panel._titlebox(object(), "Base 3 Database", grid=[0, 2, 2, 1], height=90)

    assert "width" not in bare.kwargs
    assert bare.tk.configs[0] == {"width": panel._width}
    assert sized.kwargs["width"] == panel._width
    assert sized.tk.configs[0] == {"width": panel._width}
    assert panel._compact_controls == []


def test_the_restore_pass_keeps_each_controls_own_padding() -> None:
    # Sections fill edge to edge; the controls inside them keep their 2px inset. One shared
    # padding value for both would either pad the sections or crowd the controls.
    panel = _panel(compact=True)
    section, control = SimpleNamespace(tk=_Tk()), SimpleNamespace(tk=_Tk())
    panel._stretch_compact(section, padx=0, pady=0)
    panel._fit_compact_control(control)
    section.tk.grid = {"sticky": "N"}  # what display_widgets leaves behind
    control.tk.grid = {"sticky": "W"}

    panel._apply_compact_grid()

    assert section.tk.grid == {"sticky": "nsew", "padx": 0, "pady": 0}
    assert control.tk.grid == {"sticky": "nsew", "padx": 2, "pady": 2}


def test_compact_admin_action_rows_are_fixed_to_shared_control_height(monkeypatch) -> None:
    _TitleBox.instances = []
    for widget_type in ("Box", "CheckBox", "CheckBoxGroup", "HoldButton", "PushButton", "Text", "TitleBox"):
        monkeypatch.setattr(mod, widget_type, _TitleBox)
    monkeypatch.setattr(mod, "StateWatcher", lambda *_args: None)
    panel = _panel(compact=True)
    panel.hold_threshold = 3
    panel._gui = SimpleNamespace(
        button_size=79,
        s_1=1,
        s_10=9,
        s_18=16,
        s_20=18,
        sync_state=SimpleNamespace(is_synchronized=lambda: True),
        image_presenter=SimpleNamespace(clear_caches=lambda: None),
        rescale_by=lambda value: value,
        do_tmcc_request=lambda *_args: None,
        reload_configured_accessories=lambda: None,
        add_hover_action=lambda _widget: None,
        cache=lambda _widget: None,
    )
    panel._pytrain = SimpleNamespace(debug=False, echo=False)
    panel._wifi_text = lambda *_args, **_kwargs: _TitleBox(None)
    panel._wifi_signal_badge = lambda *_args, **_kwargs: _TitleBox(None)
    panel._refresh_wifi_display = lambda: None

    panel.build(_TitleBox(None))

    admin_actions = next(box for box in _TitleBox.instances if str(box.kwargs.get("text", "")).startswith("Hold for"))
    network = next(box for box in _TitleBox.instances if box.kwargs.get("text") == "Network")
    logging = next(box for box in _TitleBox.instances if box.kwargs.get("text") == "Logging & Debugging")
    scope = next(box for box in _TitleBox.instances if box.kwargs.get("text") == "Scope")
    assert network.kwargs["height"] == panel.compact_network_height
    # The two toggle rows are deliberately shorter than every other section. What they give up
    # used to pay for a hand-sized gap above the footer row; that gap is now
    # popup_manager.FOOTER_LEAD_COMPACT, so nothing here has to size it.
    toggle_section = panel.compact_toggle_height + panel.compact_title_allowance
    assert logging.kwargs["height"] == toggle_section
    assert scope.kwargs["height"] == toggle_section
    assert toggle_section < panel.compact_section_height
    trailing_spacers = [
        box for box in _TitleBox.instances if "text" not in box.kwargs and box.kwargs.get("width") == panel._width
    ]
    assert trailing_spacers == [], "the panel must not add its own footer gap on top of the shared one"
    assert admin_actions.kwargs["height"] == panel.compact_admin_actions_height
    checkbox_controls = {
        box.kwargs.get("text"): box for box in _TitleBox.instances if box.kwargs.get("text") in {"Logging", "Debugging"}
    }
    assert {text: tuple(control.kwargs.get("grid", [])) for text, control in checkbox_controls.items()} == {
        "Logging": (0, 0),
        "Debugging": (2, 0),
    }
    assert (
        checkbox_controls["Logging"].tk.configs
        == checkbox_controls["Debugging"].tk.configs
        == [{"height": panel.compact_toggle_height - 4, "pady": 0}]
    )
    assert admin_actions.tk.rows[-3:] == [
        (row, {"weight": 0, "minsize": panel.compact_control_height, "uniform": "admin_actions"})
        for row in panel.admin_action_rows
    ]
    assert {
        (box.kwargs.get("text"), tuple(box.kwargs.get("grid", [])))
        for box in _TitleBox.instances
        if box.kwargs.get("text") in {"Restart", "Reboot", "Update PyTrain", "Upgrade Pi OS", "Quit", "Shutdown"}
    } == {
        ("Restart", (0, 0)),
        ("Reboot", (2, 0)),
        ("Update PyTrain", (0, 1)),
        ("Upgrade Pi OS", (2, 1)),
        ("Quit", (0, 2)),
        ("Shutdown", (2, 2)),
    }


def test_compact_sections_fit_title_and_all_admin_actions() -> None:
    panel = _panel(compact=True)

    assert panel.compact_control_height == 52
    assert panel.compact_control_width == 282
    assert panel.compact_title_allowance == 20
    assert panel.compact_section_height == 72
    assert panel.compact_network_height == 45
    assert panel.compact_admin_actions_height == 176
    assert panel.compact_database_height == 72


def test_scope_group_spans_compact_columns_without_changing_portrait_grid() -> None:
    assert _panel(compact=True).scope_grid == [0, 0, 3, 1]
    assert _panel(compact=False).scope_grid == [0, 0]


def test_popup_title_includes_runtime_version() -> None:
    client = _panel(compact=True)
    server = _panel(compact=True)
    server._pytrain.is_client = False
    server._gui.version = "PyTrain Server v2.9.3+"

    assert client.popup_title == "PyTrain Client v2.9.3+"
    assert server.popup_title == "PyTrain Server v2.9.3+"
    assert _panel(compact=False).popup_title == "Manage PyTrain\nPyTrain Client v2.9.3+"


def test_portrait_database_height_retains_button_size() -> None:
    panel = _panel(compact=False)

    assert panel.compact_database_height == 79


def test_portrait_titlebox_retains_natural_height_and_existing_grid(monkeypatch) -> None:
    monkeypatch.setattr(mod, "TitleBox", _TitleBox)
    panel = _panel(compact=False)

    titlebox = panel._titlebox(object(), "Reload/Refresh", grid=[0, 1, 2, 1])

    assert "height" not in titlebox.kwargs
    assert titlebox.tk.pack_propagates == [True]
    assert titlebox.tk.columns == [(0, {"weight": 1})]


def test_compact_admin_actions_use_three_consecutive_rows() -> None:
    assert _panel(compact=True).admin_action_rows == (0, 1, 2)
    assert _panel(compact=True).admin_action_columns == (0, 2)
    assert _panel(compact=False).admin_action_rows == (0, 2, 4)
    assert _panel(compact=False).admin_action_columns == (0, 1)


def test_compact_controls_have_uniform_padding() -> None:
    control = SimpleNamespace(tk=_Tk())
    panel = _panel(compact=True)

    panel._fit_compact_control(control)

    assert control.tk.configs == [{"height": 1, "pady": 0}]
    assert control.tk.grid == {"sticky": "nsew", "padx": 2, "pady": 2}


def test_compact_image_backed_controls_fill_shared_row() -> None:
    control = SimpleNamespace(tk=_Tk())
    panel = _panel(compact=True)

    panel._fit_compact_control(control, image_backed=True)

    assert control.tk.configs == [{"height": panel.compact_control_height - 4, "pady": 0}]
    assert control.tk.grid == {"sticky": "nsew", "padx": 2, "pady": 2}


def test_portrait_controls_retain_native_geometry() -> None:
    control = SimpleNamespace(tk=_Tk())

    _panel(compact=False)._fit_compact_control(control, image_backed=True)

    assert control.tk.configs == []
    assert control.tk.grid is None


class _FakeHoldButton:
    def __init__(self) -> None:
        self.disabled = False

    def disable(self) -> None:
        self.disabled = True


def _build_upgrade_button(monkeypatch, panel: mod.AdminPanel) -> _FakeHoldButton:
    button = _FakeHoldButton()
    monkeypatch.setattr(panel, "_hold_button", lambda _parent, **_kwargs: button)
    panel._admin_hold_button(
        object(),
        text="Upgrade Pi OS",
        grid=[2, 1],
        on_hold=(panel.do_admin_command, [mod.TMCC1SyncCommandEnum.UPGRADE]),
        enabled=panel.os_upgrade_supported,
    )
    return button


def test_steam_deck_disables_the_os_upgrade_button(monkeypatch) -> None:
    # SteamOS updates itself, and PyTrain.upgrade() gates only on sys.platform ==
    # "linux", which the Deck satisfies -- so the apt path is reachable there.
    monkeypatch.setattr(mod, "is_steam_deck", lambda: True)
    panel = _panel(compact=True)

    button = _build_upgrade_button(monkeypatch, panel)

    assert panel.os_upgrade_supported is False
    assert button.disabled is True
    # Absent from the registry, so a controller chord cannot fire what a finger cannot.
    assert "UPGRADE" not in panel._admin_buttons


def test_other_platforms_keep_the_os_upgrade_button(monkeypatch) -> None:
    monkeypatch.setattr(mod, "is_steam_deck", lambda: False)
    panel = _panel(compact=False)

    button = _build_upgrade_button(monkeypatch, panel)

    assert panel.os_upgrade_supported is True
    assert button.disabled is False
    assert panel._admin_buttons["UPGRADE"] is button


def test_admin_panel_is_an_overlay_panel() -> None:
    # create_popup only builds a footer -- and so only puts anything left of Close --
    # for OverlayPanel instances. Without this the Show Controls button has nowhere to go.
    assert issubclass(mod.AdminPanel, mod.OverlayPanel)


def test_landscape_admin_panel_offers_show_controls() -> None:
    panel = _panel(compact=True)
    panel._gui.controller_profile = object()  # a hosting SteamDeckGui loaded one

    assert panel.controls_available is True
    assert panel.has_footer is True


def test_portrait_admin_panel_has_no_footer_at_all() -> None:
    # A stand-alone portrait EngineGui has no hosting SteamDeckGui and so no profile:
    # the help screen would have nothing to describe. has_footer must be False rather
    # than an empty footer, so create_popup keeps the plain centered Close button.
    panel = _panel(compact=False)

    assert panel.controls_available is False
    assert panel.has_footer is False


class _FooterButton:
    instances = []

    def __init__(self, parent, **kwargs) -> None:
        self.parent = parent
        self.kwargs = kwargs
        self.tk = _Tk()
        self.text_size = None
        _FooterButton.instances.append(self)


def test_footer_button_is_left_aligned_so_close_lands_to_its_right(monkeypatch) -> None:
    _FooterButton.instances = []
    monkeypatch.setattr(mod, "PushButton", _FooterButton)
    monkeypatch.setattr(popup_manager, "Text", _FooterButton)
    panel = _panel(compact=True)
    # compact on the gui, not just on the panel: the shared footer helpers read it from the
    # host, the same attribute AdminPanel.__init__ copies into self._compact.
    panel._gui = SimpleNamespace(compact=True, s_18=17, s_20=19, cache=lambda _w: None, controller_profile=object())

    panel.build_footer(object())

    # The button, then the spacer that keeps it clear of Close.
    assert len(_FooterButton.instances) == 2
    button = _FooterButton.instances[0]
    assert button.kwargs["text"] == "Controls..."
    # create_popup appends Close with align="right" after build_footer returns.
    assert button.kwargs["align"] == "left"
    # Sized to the label, not the 13 it inherited from the longer "Show Controls".
    assert button.kwargs["width"] == len("Controls...")


def test_footer_gap_is_a_spacer_widget_not_pack_padding(monkeypatch) -> None:
    # Pack padding does not survive here: create_popup adds Close to this same footer
    # right after build_footer returns, and that runs footer.display_widgets(), which
    # pack_forget()s every sibling and discards its padx. Only a real widget survives.
    _FooterButton.instances = []
    spacers: list[_FooterButton] = []
    monkeypatch.setattr(mod, "PushButton", _FooterButton)
    # The spacer is built by popup_manager.footer_spacer now, shared with StateInfoOverlay.
    monkeypatch.setattr(
        popup_manager,
        "Text",
        lambda _parent, **kwargs: spacers.append(_FooterButton(_parent, **kwargs)) or spacers[-1],
    )
    panel = _panel(compact=True)
    # compact on the gui, not just on the panel: the shared footer helpers read it from the
    # host, the same attribute AdminPanel.__init__ copies into self._compact.
    panel._gui = SimpleNamespace(compact=True, s_18=17, s_20=19, cache=lambda _w: None, controller_profile=object())

    panel.build_footer(object())

    assert len(spacers) == 1, "a spacer widget must separate Controls from Close"
    assert spacers[0].kwargs["align"] == "left", "must pack between Controls and Close"
    assert spacers[0].text_size == popup_manager.FOOTER_GAP_COMPACT


def test_show_controls_closes_the_admin_panel_first(monkeypatch) -> None:
    # Both are popups; leaving this one open behind the other makes Close ambiguous.
    calls: list[str] = []
    panel = _panel(compact=False)
    panel._gui = SimpleNamespace(
        close_popup=lambda: calls.append("close"),
        on_controls_panel=lambda: calls.append("open"),
    )

    panel.show_controls()

    assert calls == ["close", "open"]


class _WifiWidget:
    """A guizero-ish widget that records show()/hide(), the calls that repack siblings."""

    def __init__(self, visible: bool = True) -> None:
        self.visible = visible
        self.value = ""
        self.bg = None
        self.text_color = None
        self.calls: list[str] = []

    def show(self) -> None:
        self.visible = True
        self.calls.append("show")

    def hide(self) -> None:
        self.visible = False
        self.calls.append("hide")


class _HeldButton:
    def __init__(self, holding: bool) -> None:
        self.is_holding = holding


def _wifi_panel(monkeypatch, *, connected: bool = True) -> mod.AdminPanel:
    panel = _panel(compact=False)
    panel._wifi_box = SimpleNamespace(text="")
    panel._wifi_ssid = _WifiWidget(visible=connected)
    panel._wifi_signal = _WifiWidget(visible=connected)
    panel._wifi_ip = _WifiWidget()
    status = (
        ("WiFi", "Sprucewood", "10.0.0.4", "78%", "green") if connected else ("Ethernet", None, "10.0.0.4", None, "")
    )
    # _refresh_wifi_display now paints the worker's cache rather than querying inline.
    panel._wifi_lock = RLock()
    panel._wifi_cache = status
    panel._wifi_query_running = False
    monkeypatch.setattr(type(panel), "_wifi_status", lambda _self: status)
    monkeypatch.setattr(type(panel), "_signal_text_color", staticmethod(lambda _color: "black"))
    return panel


def test_unchanged_wifi_visibility_does_not_repack(monkeypatch) -> None:
    # show()/hide() call master.display_widgets(), which re-packs every sibling. Doing
    # that every 5s reflowed the panel for nothing -- and a reflow mid-hold generates the
    # pointer crossings that canceled the hold.
    panel = _wifi_panel(monkeypatch, connected=True)

    panel._refresh_wifi_display()

    assert panel._wifi_ssid.calls == []
    assert panel._wifi_signal.calls == []


def test_changed_wifi_visibility_still_updates(monkeypatch) -> None:
    # The suppression must not stop a real state change from being shown.
    panel = _wifi_panel(monkeypatch, connected=True)
    panel._wifi_ssid.visible = False
    panel._wifi_signal.visible = False

    panel._refresh_wifi_display()

    assert panel._wifi_ssid.calls == ["show"]
    assert panel._wifi_signal.calls == ["show"]


def test_wifi_refresh_is_skipped_while_a_button_is_held(monkeypatch) -> None:
    panel = _wifi_panel(monkeypatch)
    panel._admin_buttons = {"UPDATE": _HeldButton(True)}
    panel._overlay = SimpleNamespace(visible=True, tk=SimpleNamespace(after=lambda _ms, _f: "after-1"))
    refreshed: list[str] = []
    queried: list[str] = []
    monkeypatch.setattr(type(panel), "_refresh_wifi_display", lambda _self: refreshed.append("refresh"))
    monkeypatch.setattr(type(panel), "_start_wifi_query", lambda _self: queried.append("query"))

    panel._refresh_wifi_if_visible()

    assert refreshed == []
    assert queried == [], "a blocking probe must not be started mid-hold either"
    # ...but the loop must keep running, or strength never updates again.
    assert panel._wifi_refresh_after_id == "after-1"


def test_wifi_refresh_resumes_once_the_hold_ends(monkeypatch) -> None:
    panel = _wifi_panel(monkeypatch)
    panel._admin_buttons = {"UPDATE": _HeldButton(False)}
    panel._overlay = SimpleNamespace(visible=True, tk=SimpleNamespace(after=lambda _ms, _f: "after-1"))
    refreshed: list[str] = []
    queried: list[str] = []
    monkeypatch.setattr(type(panel), "_refresh_wifi_display", lambda _self: refreshed.append("refresh"))
    monkeypatch.setattr(type(panel), "_start_wifi_query", lambda _self: queried.append("query"))

    panel._refresh_wifi_if_visible()

    assert refreshed == ["refresh"]
    assert queried == ["query"]


def test_hold_in_progress_reports_any_held_button() -> None:
    panel = _panel(compact=False)
    panel._admin_buttons = {"QUIT": _HeldButton(False), "UPDATE": _HeldButton(True)}

    assert panel.hold_in_progress is True

    panel._admin_buttons["UPDATE"] = _HeldButton(False)
    assert panel.hold_in_progress is False


def test_the_wifi_query_runs_off_the_tk_thread(monkeypatch) -> None:
    # The point of the worker: WiFiInfo.query() shells out and the address lookup opens a
    # socket. Blocking the Tk thread on those every 5s is a visible hitch, and was part of
    # what disturbed an in-flight hold.
    panel = _panel(compact=False)
    panel._wifi_lock = RLock()
    panel._wifi_cache = None
    panel._wifi_query_running = False
    ran_on: list[str] = []
    finished = Event()

    def fake_status(_self):
        ran_on.append(threading.current_thread().name)
        return ("WiFi", "Sprucewood", "10.0.0.4", "78%", "green")

    monkeypatch.setattr(type(panel), "_wifi_status", fake_status)
    original = mod.AdminPanel._wifi_query_worker

    def worker(self) -> None:
        original(self)
        finished.set()

    monkeypatch.setattr(type(panel), "_wifi_query_worker", worker)

    panel._start_wifi_query()

    assert finished.wait(5), "worker never completed"
    assert ran_on and ran_on[0] != threading.current_thread().name
    assert panel._wifi_cache == ("WiFi", "Sprucewood", "10.0.0.4", "78%", "green")
    assert panel._wifi_query_running is False


def test_only_one_wifi_query_runs_at_a_time() -> None:
    # WiFiInfo caches the interface it found, so overlapping queries would race on it.
    panel = _panel(compact=False)
    panel._wifi_lock = RLock()
    panel._wifi_cache = None
    panel._wifi_query_running = True  # one already in flight
    started: list[str] = []
    panel._wifi_query_worker = lambda: started.append("worker")

    panel._start_wifi_query()

    assert started == []


def test_display_leaves_widgets_alone_until_the_first_query_lands(monkeypatch) -> None:
    # Better to keep showing the previous values than to flash placeholders in and out.
    panel = _wifi_panel(monkeypatch)
    panel._wifi_cache = None
    panel._wifi_ssid.value = "Sprucewood"

    panel._refresh_wifi_display()

    assert panel._wifi_ssid.value == "Sprucewood"
    assert panel._wifi_ssid.calls == []


def test_a_failing_query_keeps_the_last_good_value_and_clears_the_flag(monkeypatch) -> None:
    # A background probe must never take the GUI down, nor wedge the single-flight guard.
    panel = _panel(compact=False)
    panel._wifi_lock = RLock()
    panel._wifi_cache = ("WiFi", "Old", "10.0.0.4", "50%", "green")
    panel._wifi_query_running = True

    def boom(_self):
        raise OSError("no interface")

    monkeypatch.setattr(type(panel), "_wifi_status", boom)

    panel._wifi_query_worker()

    assert panel._wifi_cache == ("WiFi", "Old", "10.0.0.4", "50%", "green")
    assert panel._wifi_query_running is False


class _StubHoldButton:
    instances: list["_StubHoldButton"] = []

    def __init__(self, _parent, **kwargs) -> None:
        self.kwargs = kwargs
        self.tk = _CallableTkStub()
        _StubHoldButton.instances.append(self)

    def disable(self) -> None:
        return


class _CallableTkStub:
    def config(self, **_kwargs) -> None:
        return

    def grid_configure(self, **_kwargs) -> None:
        return


def _built_hold_button(monkeypatch, *, steam_deck: bool) -> _StubHoldButton:
    _StubHoldButton.instances = []
    monkeypatch.setattr(mod, "HoldButton", _StubHoldButton)
    monkeypatch.setattr(mod, "is_steam_deck", lambda: steam_deck)
    panel = _panel(compact=steam_deck)
    panel._gui = SimpleNamespace(
        s_18=17, s_20=19, rescale_by=lambda v: v, add_hover_action=lambda _b: None, cache=lambda *_w: None
    )
    panel.hold_threshold = 3
    monkeypatch.setattr(type(panel), "_fit_compact_control", lambda _self, _c, image_backed=False: None)
    panel._hold_button(object(), text="Reboot", grid=[0, 0])
    return _StubHoldButton.instances[0]


def test_touch_recovery_is_enabled_on_the_steam_deck(monkeypatch) -> None:
    # Its touch stream interrupts a held contact, so a 3-second hold never completes.
    button = _built_hold_button(monkeypatch, steam_deck=True)

    assert button.kwargs["press_recovery_ms"] == mod.PRESS_RECOVERY_MS


def test_the_pi_gets_no_touch_recovery(monkeypatch) -> None:
    # The Pi has never shown the problem, and the recovery is not free: it defers every
    # release and binds <Motion>. Zero leaves that path exactly as it was.
    button = _built_hold_button(monkeypatch, steam_deck=False)

    assert button.kwargs["press_recovery_ms"] == 0


def test_drag_off_cancel_applies_to_both_platforms(monkeypatch) -> None:
    # This one was asked for as a feature, not a Deck workaround: before it, the progress
    # overlay canceled on any crossing regardless, so both platforms already canceled on
    # a drag-off -- just far too eagerly.
    for steam_deck in (True, False):
        button = _built_hold_button(monkeypatch, steam_deck=steam_deck)
        assert button.kwargs["cancel_on_leave"] is True


class _Rb:
    """Stands in for a guizero RadioButton: its `grid` attribute and its tk widget."""

    def __init__(self) -> None:
        self.grid = None
        self.tk = _Tk()


def test_a_two_option_group_is_regridded_onto_the_checkbox_columns() -> None:
    # The Scope radios must land in the same columns as the Logging/Debugging checkboxes,
    # with a spacer between, or the row reads as misaligned against the one above it.
    panel = _panel(compact=True)
    spacers = []
    panel.spacer = lambda parent, grid: spacers.append((parent, grid))
    left, right = _Rb(), _Rb()
    group = SimpleNamespace(_rbuttons=[left, right], tk=_Tk())

    panel._mirror_two_up_columns(group)

    assert left.grid == [0, 0]
    assert right.grid == [2, 0]
    assert spacers == [(group, [1, 0])]
    # Column numbers alone left "All" a different width from "Debugging": the frame sized
    # its columns to each label. Mirror the TitleBox geometry and stretch into it.
    assert group.tk.columns == [
        (0, {"weight": 1, "minsize": panel.compact_control_width, "uniform": "admin_controls"}),
        (2, {"weight": 1, "minsize": panel.compact_control_width, "uniform": "admin_controls"}),
        (1, {"weight": 0}),
    ]
    assert group.tk.grid == {"sticky": "nsew", "padx": 2, "pady": 2}
    for option in (left, right):
        assert option.tk.grid == {"sticky": "nsew", "padx": 2, "pady": 2}
        assert option.tk.configs == [{"height": panel.compact_toggle_height - 4, "pady": 0}]


def test_a_portrait_group_is_regridded_but_not_stretched() -> None:
    # Portrait has no fixed section heights to stretch into, and never asked for the
    # compact sizing. The column move is all it needs.
    panel = _panel(compact=False)
    panel.spacer = lambda parent, grid: None
    left, right = _Rb(), _Rb()
    group = SimpleNamespace(_rbuttons=[left, right], tk=_Tk())

    panel._mirror_two_up_columns(group)

    assert (left.grid, right.grid) == ([0, 0], [2, 0])
    assert group.tk.columns == []
    assert group.tk.grid is None
    assert panel._compact_controls == []


def test_a_group_that_is_not_two_up_keeps_guizeros_own_packing() -> None:
    # Only the two-option case has a checkbox row to mirror. A third option would have no
    # column to go to, so leave the group alone rather than mangle it.
    panel = _panel(compact=True)
    called = []
    panel.spacer = lambda parent, grid: called.append(grid)

    panel._mirror_two_up_columns(SimpleNamespace(_rbuttons=[_Rb(), _Rb(), _Rb()]))
    panel._mirror_two_up_columns(SimpleNamespace(_rbuttons=[]))
    panel._mirror_two_up_columns(SimpleNamespace())

    assert called == []


def test_the_scope_radios_are_the_same_width_as_the_logging_checkboxes() -> None:
    # Equal width is what keeps the two rows aligned, and what stopped the pair from
    # overflowing a TitleBox pinned to 98% of the panel width.
    panel = _panel(compact=True)

    per_option = panel.control_half_width

    assert per_option * 2 < panel._width, "a pair plus padding has to fit the panel"
    assert per_option == int(panel._width / 2.48)


def test_compact_grid_options_are_restored_after_creation_wipes_them() -> None:
    # guizero re-grids every sibling whenever a widget is created, and tk's grid() replaces
    # the whole option set -- so only the last control added kept its sticky and padding.
    # That is why Shutdown rendered 8px taller than the five buttons above it.
    panel = _panel(compact=True)
    first, last = SimpleNamespace(tk=_Tk()), SimpleNamespace(tk=_Tk())
    panel._fit_compact_control(first)
    panel._fit_compact_control(last)
    first.tk.grid = {"column": 0, "row": 2, "sticky": "W"}  # what display_widgets leaves

    panel._apply_compact_grid()

    assert first.tk.grid == {"sticky": "nsew", "padx": 2, "pady": 2}
    assert last.tk.grid == {"sticky": "nsew", "padx": 2, "pady": 2}


def test_portrait_records_no_compact_controls_to_restore() -> None:
    # The re-apply pass must be a no-op off the Deck: portrait never asked for the compact
    # sizing in the first place.
    panel = _panel(compact=False)
    control = SimpleNamespace(tk=_Tk())

    panel._fit_compact_control(control)
    panel._apply_compact_grid()

    assert panel._compact_controls == []
    assert control.tk.grid is None


def test_no_titlebox_is_given_a_height_without_a_width(monkeypatch) -> None:
    # guizero emits "You must specify a width and a height" when it gets one and not the
    # other, and it emitted five of them -- one per section -- when compact stopped passing
    # a width. Any size kwarg at all means both must be present.
    monkeypatch.setattr(mod, "TitleBox", _TitleBox)

    for compact in (True, False):
        panel = _panel(compact=compact)
        for kwargs in ({}, {"height": 90}):
            box = panel._titlebox(object(), "Section", grid=[0, 0, 2, 1], **kwargs)
            sized = {"width", "height"} & box.kwargs.keys()
            assert sized in ({"width", "height"}, set()), f"compact={compact} kwargs={box.kwargs}"


def test_two_control_columns_and_their_spacer_fit_inside_a_section() -> None:
    # The invariant the truncation broke. A section receives self._width minus admin_box's
    # chrome; two column floors plus the spacer between them have to fit inside that, or
    # grid_propagate(False) leaves Tk clipping the right-hand column instead of negotiating.
    # Measured on the Deck: floor 300 demanded 628 of 620, and the right column lost 8px.
    for width in (480, 560, 632, 640, 800, 1024):
        panel = _panel(compact=True)
        panel._width = width
        available = width - mod.SECTION_CHROME_PX
        demanded = 2 * panel.compact_control_width + mod.COLUMN_SPACER_PX

        assert demanded <= available, f"width={width}: columns demand {demanded} of {available}"


def test_the_column_floor_leaves_the_columns_a_usable_share() -> None:
    # Conservative is fine, useless is not: weight hands the slack back, but the floor still
    # has to be most of a half-width or a column could collapse before weight is applied.
    panel = _panel(compact=True)
    half = (panel._width - mod.SECTION_CHROME_PX - mod.COLUMN_SPACER_PX) / 2

    assert 0.85 * half <= panel.compact_control_width <= half


def test_the_compact_admin_box_carries_no_chrome_of_its_own(monkeypatch) -> None:
    # Border and pack padding on admin_box come straight off the width the two control
    # columns share, and the admingeom trace showed the loss landing entirely on the right as
    # unused white space. Portrait keeps them.
    for compact, border, padx in ((True, 0, 0), (False, 1, 2)):
        _TitleBox.instances = []
        for widget_type in ("Box", "CheckBox", "CheckBoxGroup", "HoldButton", "PushButton", "Text", "TitleBox"):
            monkeypatch.setattr(mod, widget_type, _TitleBox)
        monkeypatch.setattr(mod, "StateWatcher", lambda *_args: None)
        panel = _panel(compact=compact)
        panel.hold_threshold = 3
        panel._gui = SimpleNamespace(
            button_size=79,
            s_1=1,
            s_2=2,  # portrait-only spacers use this; the compact path never reaches them
            s_10=9,
            s_18=16,
            s_20=18,
            sync_state=SimpleNamespace(is_synchronized=lambda: True),
            image_presenter=SimpleNamespace(clear_caches=lambda: None),
            rescale_by=lambda value: value,
            do_tmcc_request=lambda *_args: None,
            reload_configured_accessories=lambda: None,
            add_hover_action=lambda _widget: None,
            cache=lambda _widget: None,
        )
        panel._pytrain = SimpleNamespace(debug=False, echo=False)
        panel._wifi_text = lambda *_args, **_kwargs: _TitleBox(None)
        panel._wifi_signal_badge = lambda *_args, **_kwargs: _TitleBox(None)
        panel._refresh_wifi_display = lambda: None

        panel.build(_TitleBox(None))

        admin_box = next(
            box for box in _TitleBox.instances if box.kwargs.get("layout") == "grid" and "text" not in box.kwargs
        )
        assert admin_box.kwargs["border"] == border, f"compact={compact}"
        assert admin_box.tk.pack_configs[-1]["padx"] == padx, f"compact={compact}"
