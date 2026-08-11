from types import SimpleNamespace

import src.pytrain.gui.controller.admin_panel as mod


class _Tk:
    def __init__(self) -> None:
        self.columns = []
        self.grid = None
        self.pack_propagates = []

    def config(self, **_kwargs) -> None:
        pass

    def grid_configure(self, **kwargs) -> None:
        self.grid = kwargs

    def grid_columnconfigure(self, column, **kwargs) -> None:
        self.columns.append((column, kwargs))

    def pack_propagate(self, value) -> None:
        self.pack_propagates.append(value)


class _TitleBox:
    def __init__(self, _parent, **kwargs) -> None:
        self.kwargs = kwargs
        self.tk = _Tk()
        self.text_size = None


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
    assert titlebox.tk.pack_propagates == [False]
    assert titlebox.tk.columns == [
        (0, {"weight": 1, "uniform": "admin_controls"}),
        (1, {"weight": 0}),
        (2, {"weight": 1, "uniform": "admin_controls"}),
    ]


def test_compact_sections_fit_title_and_all_admin_actions() -> None:
    panel = _panel(compact=True)

    assert panel.compact_control_height == 36
    assert panel.compact_section_height == 44
    assert panel.compact_admin_actions_height == 116
    assert panel.compact_database_height == 44


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
