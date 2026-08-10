from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.controller_view as mod


class _DummyTk:
    def config(self, **_kwargs) -> None:
        pass

    def bind(self, _event, _command, add=None) -> None:
        pass

    def focus_set(self) -> None:
        pass


class _DummyWidget:
    def __init__(self, *_args, **kwargs) -> None:
        self.tk = _DummyTk()
        self.font = kwargs.get("font")


@pytest.fixture
def controller_view(monkeypatch: pytest.MonkeyPatch) -> mod.ControllerView:
    monkeypatch.setattr(mod, "Box", _DummyWidget)
    monkeypatch.setattr(mod, "TitleBox", _DummyWidget)
    monkeypatch.setattr(mod, "Text", _DummyWidget)
    monkeypatch.setattr(mod, "Slider", _DummyWidget)
    host = SimpleNamespace(
        s_10=10,
        s_18=18,
        button_size=90,
        slider_height=300,
        digital_font="Digital dream",
    )
    return mod.ControllerView(host)


def test_non_throttle_slider_levels_use_host_digital_font(controller_view: mod.ControllerView) -> None:
    for title in ("Brake", "Moment", "Horn"):
        _, _, level, _ = controller_view.make_slider(_DummyWidget(), title, lambda _value: None, 0, 7)

        assert level.font == "Digital dream"
