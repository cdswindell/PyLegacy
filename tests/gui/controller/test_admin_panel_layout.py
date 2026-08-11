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
    panel._gui = SimpleNamespace(button_size=79, s_10=9, version="PyTrain Client v2.9.3+")
    panel._pytrain = SimpleNamespace(is_client=True)
    panel._width = 632
    panel._compact = compact
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
    assert network.kwargs["height"] == panel.compact_section_height
    assert logging.kwargs["height"] == panel.compact_section_height
    assert scope.kwargs["height"] == panel.compact_section_height
    assert admin_actions.kwargs["height"] == panel.compact_admin_actions_height
    assert {
        (box.kwargs.get("text"), tuple(box.kwargs.get("grid", [])))
        for box in _TitleBox.instances
        if box.kwargs.get("text") in {"Logging", "Debugging"}
    } == {("Logging", (0, 0)), ("Debugging", (2, 0))}
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

    assert panel.compact_control_height == 44
    assert panel.compact_control_width == 300
    assert panel.compact_title_allowance == 20
    assert panel.compact_section_height == 64
    assert panel.compact_admin_actions_height == 152
    assert panel.compact_database_height == 64


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


def test_portrait_controls_retain_native_geometry() -> None:
    control = SimpleNamespace(tk=_Tk())

    _panel(compact=False)._fit_compact_control(control)

    assert control.tk.configs == []
    assert control.tk.grid is None
