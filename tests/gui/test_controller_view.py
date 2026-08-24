import ast
import pathlib
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


def test_the_freight_pair_size_comes_from_its_row_not_from_what_is_drawn_in_it() -> None:
    # It used to be max(bell_box.winfo_height() * 0.85, aux_row_height * 0.70), so a bell the font
    # could not draw shrank the whole pair. Only the row feeds it now.
    assert mod.freight_pair_size(100) == 70
    assert mod.freight_pair_size(68) == 47
    # Never zero: a zero-sized button is unclickable, and Image.resize would raise on it.
    assert mod.freight_pair_size(1) == 1
    assert mod.freight_pair_size(0) == 1


def test_the_freight_bell_is_an_image_asset_that_exists() -> None:
    # The button is blank if this does not resolve, which is indistinguishable on screen from the
    # missing-glyph rectangle it replaced.
    from src.pytrain.utils.path_utils import find_file

    for asset in ("bell.jpg", "horn.jpg"):
        assert find_file(asset), asset


def test_no_bell_codepoint_is_used_as_a_button_label() -> None:
    """Guards the regression that started this: a bell *glyph* cannot work on both devices.

    The Pi has no font containing U+1F514, so it draws a missing-glyph rectangle; the Deck's color
    emoji font claims it and draws a colored bitmap that ignores the button's foreground. U+1F56D
    RINGING BELL has no emoji form but almost no font ships it either. No headless test can catch
    this by rendering -- it depends on the fonts installed on the device -- so the guard is on the
    source: the module must not name a bell codepoint at all.
    """
    source = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    # Every string literal in the module, *decoded*. Scanning the raw text instead would miss
    # "\\N{BELL}" and "\\U0001f514", which look nothing like the character but are the character
    # once Python has read them -- a mutation that wrote the escape form slipped past exactly that.
    # Comments are not literals, so prose about the codepoint stays legal.
    literals = "".join(
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )

    assert "\U0001f514" not in literals, "U+1F514 BELL: emoji on the Deck, missing on the Pi"
    assert "\U0001f56d" not in literals, "U+1F56D RINGING BELL: missing on almost every font"
    assert "BELL_KEY" not in source, "the constant is retired; use bell.jpg"
