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


def _size(aux=200, chrome=20, width=400, label=80):
    """Both budgets, with roomy defaults so a test can bind exactly one of them."""
    return mod.freight_pair_size(aux, chrome, width, label)


def test_the_height_budget_is_the_row_less_the_label_above_the_buttons() -> None:
    # The pair shares row 1 of the sliders column with the "Bell/Horn..." label, so what the
    # buttons can have is the row less that chrome.
    assert _size(aux=120, chrome=20) == 120 - 20 - mod.FREIGHT_PAIR_INSET
    assert _size(aux=120, chrome=40) < _size(aux=120, chrome=20), "more chrome, smaller buttons"
    assert _size(aux=160, chrome=20) > _size(aux=120, chrome=20), "a taller row, bigger buttons"


def test_the_width_budget_binds_when_the_column_is_the_tighter_dimension() -> None:
    # What the photos showed: height alone let the row overrun its column, and because btn_row is
    # centered the overflow clipped the horn's outer edge *and* the title's, giving "Bell/Hor".
    roomy_height = _size(aux=400, width=400, label=80)
    tight_width = _size(aux=400, width=140, label=80)

    assert tight_width < roomy_height
    # Regime 1: both halves scale, so the row is 2p + gap.
    assert 2 * tight_width + mod.FREIGHT_PAIR_GAP <= 140


def test_the_row_fits_its_column_in_either_regime() -> None:
    # The invariant that matters, checked against the row's actual width formula rather than
    # against whichever branch produced it.
    for width in range(60, 420, 7):
        for label in (0, 40, 80, 160):
            size = mod.freight_pair_size(400, 0, width, label)
            row = size + mod.FREIGHT_PAIR_GAP + max(label, size)
            assert row <= width or size == mod.FREIGHT_PAIR_MIN, f"width={width} label={label}"


def test_a_wide_label_pins_the_bell_and_only_the_horn_gives_way() -> None:
    # Past the point where the buttons are narrower than "Bell/Horn...", each pixel off the buttons
    # buys one pixel of row instead of two -- which is why halving an overflow converged so slowly
    # that a four-pass search still left the row overflowing.
    size = mod.freight_pair_size(400, 0, available_width=140, title_label_width=100)

    assert size + mod.FREIGHT_PAIR_GAP + 100 <= 140


def test_the_size_never_drops_below_a_usable_touch_target() -> None:
    # A column narrower than its own label can never fit. Overflowing with a pressable button beats
    # a perfect fit with an invisible one, and Image.resize raises on a zero dimension.
    assert mod.freight_pair_size(20, 200, 400, 80) == mod.FREIGHT_PAIR_MIN
    assert mod.freight_pair_size(400, 0, 10, 200) == mod.FREIGHT_PAIR_MIN
    assert _size(aux=0, chrome=0) == mod.FREIGHT_PAIR_MIN


def test_a_negative_chrome_measurement_cannot_inflate_the_height_budget() -> None:
    # winfo_* can return odd values before layout settles, and subtracting a negative would *add*
    # room the row does not have. Only the chrome needs this: a negative label would take the same
    # regime a zero label does, so clamping it would be dead code.
    assert _size(chrome=-50) == _size(chrome=0)
    assert _size(chrome=-50) < _size(aux=400, chrome=0), "the clamp does not pin it to a constant"


def test_the_freight_bell_is_an_image_asset_that_exists() -> None:
    # The button is blank if this does not resolve, which on screen is indistinguishable from the
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
    source.
    """
    source = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    # Every string literal in the module, *decoded*. Scanning the raw text would miss "\\N{BELL}"
    # and "\\U0001f514", which look nothing like the character but are the character once Python
    # has read them -- a mutation writing the escape form slipped past exactly that. Comments are
    # not literals, so prose about the codepoint stays legal.
    literals = "".join(
        node.value
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )

    assert "\U0001f514" not in literals, "U+1F514 BELL: emoji on the Deck, missing on the Pi"
    assert "\U0001f56d" not in literals, "U+1F56D RINGING BELL: missing from almost every font"
    assert "BELL_KEY" not in source, "the constant is retired; use bell.jpg"


def test_the_pair_size_call_site_passes_every_measurement() -> None:
    """The wiring, which nothing else covers.

    build() is far too large to stub, so no test exercises the call itself. Every parameter is
    required, so dropping one is a TypeError when the GUI builds and PyCharm flags it -- but
    neither of those is a red test run, and a call site that quietly stopped passing the width
    would put the clipping straight back.
    """
    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "freight_pair_size"
    ]

    assert calls, "freight_pair_size is no longer called at all"
    for call in calls:
        assert len(call.args) == 4, "row height, chrome height, column width and label width"
