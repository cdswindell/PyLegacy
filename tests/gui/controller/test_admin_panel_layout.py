from types import SimpleNamespace

import src.pytrain.gui.controller.admin_panel as mod


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
    assert logging.kwargs["height"] == panel.compact_section_height
    assert scope.kwargs["height"] == panel.compact_section_height
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
        == [{"height": panel.compact_control_height - 4, "pady": 0}]
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
    assert panel.compact_control_width == 300
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
    # than an empty footer, so create_popup keeps the plain centred Close button.
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
    panel = _panel(compact=True)
    panel._gui = SimpleNamespace(s_18=17, s_20=19, cache=lambda _w: None, controller_profile=object())

    panel.build_footer(object())

    assert len(_FooterButton.instances) == 1
    button = _FooterButton.instances[0]
    assert button.kwargs["text"] == "Controls..."
    # create_popup appends Close with align="right" after build_footer returns.
    assert button.kwargs["align"] == "left"


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
