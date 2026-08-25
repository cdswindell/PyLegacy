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


def test_the_provisional_size_is_capped_by_both_dimensions_of_the_cell() -> None:
    # A starting value only. It cannot account for the "Bell/Horn..." label, because at build time
    # an empty TitleBox reports a requested height of 1 -- measured on the Pi as chrome_height=1
    # while the same pass read the sliders column correctly at 221. Two rounds of arithmetic were
    # built on that 1.
    assert mod.freight_pair_size(105, 400) == 105 - mod.FREIGHT_PAIR_INSET
    assert mod.freight_pair_size(400, 221) == (221 - mod.FREIGHT_PAIR_GAP) // 2
    assert mod.freight_pair_size(0, 0) == mod.FREIGHT_PAIR_MIN, "never an unclickable button"


def test_the_shrink_takes_whichever_axis_overflows_more() -> None:
    # A pixel off each button buys two of width but only one of height: both halves scale
    # horizontally, while vertically only the bell's box grows -- the label above it is fixed.
    assert mod.freight_pair_shrink(6, 23) == 23, "height dominated"
    assert mod.freight_pair_shrink(40, 5) == 20, "width dominated, halved"
    assert mod.freight_pair_shrink(0, 0) == 0
    assert mod.freight_pair_shrink(-10, -10) == 0, "already fitting, nothing to give back"
    assert mod.freight_pair_shrink(1, 0) == 1, "a 1px overflow still costs a pixel, not zero"


def test_one_correction_lands_on_the_fitting_size_from_any_overflow() -> None:
    """The property that makes a single pass enough, checked against the Pi's measured geometry.

    At ``pair_size=98`` the log gave ``btn_row reqw=224 reqh=128`` inside a ``218x105`` cell, so the
    row is ``2 * size + 28`` wide and ``size + 30`` tall. The overflow therefore grows with the
    size at exactly the rate the shrink removes it, so the fixed point does not depend on where the
    provisional happened to land.
    """
    cell_w, cell_h = 218, 105
    fits = lambda p: 2 * p + 28 <= cell_w and p + 30 <= cell_h  # noqa: E731

    landed = set()
    for start in range(75, 200):
        shrink = mod.freight_pair_shrink((2 * start + 28) - cell_w, (start + 30) - cell_h)
        landed.add(max(mod.FREIGHT_PAIR_MIN, start - shrink))

    assert landed == {75}, landed
    assert fits(75) and not fits(76), "75 is the largest size that fits, not merely one that does"


def test_the_correction_only_ever_shrinks() -> None:
    """A size already inside the cell is left alone, which is safe because the provisional
    over-shoots by construction: it caps against both cell dimensions *without* subtracting any
    chrome, and chrome can only reduce the true optimum. So there is never an under-shoot to grow.
    """
    cell_w, cell_h = 218, 105

    for start in (20, 40, 60, 74):
        shrink = mod.freight_pair_shrink((2 * start + 28) - cell_w, (start + 30) - cell_h)
        assert shrink == 0, start

    # And the provisional really is on the shrink side of the optimum for the Pi's numbers.
    assert mod.freight_pair_size(105, 221) >= 75


def test_a_pair_that_already_fits_is_not_resized() -> None:
    # Every correction regenerates two images, so the common case has to be free.
    assert mod.freight_pair_shrink(-6, -23) == 0


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


def _calls_to(name: str) -> list:
    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
    return [node for node in ast.walk(tree) if isinstance(node, ast.Call) and getattr(node.func, "id", None) == name]


def test_the_provisional_size_and_the_correction_are_both_wired_up() -> None:
    """The wiring, which nothing else covers.

    build() is far too large to stub, so no test exercises either call. The provisional alone is
    what shipped twice and clipped twice -- it cannot account for the label's chrome -- so a
    correction that quietly stopped being called would look exactly like those two turns.
    """
    provisional = _calls_to("freight_pair_size")
    assert len(provisional) == 1, "sized once, during build"
    assert len(provisional[0].args) == 2, "row height and column width"

    assert len(_calls_to("fit_freight_pair")) == 1, "corrected once, from the show path"


def _geom_widget(*, w: int, h: int, reqw: int, reqh: int, parent: tuple[int, int] = (400, 200)):
    return SimpleNamespace(
        tk=SimpleNamespace(
            winfo_ismapped=lambda: 1,
            winfo_rootx=lambda: 10,
            winfo_rooty=lambda: 20,
            winfo_width=lambda: w,
            winfo_height=lambda: h,
            winfo_reqwidth=lambda: reqw,
            winfo_reqheight=lambda: reqh,
            master=SimpleNamespace(winfo_width=lambda: parent[0], winfo_height=lambda: parent[1]),
        )
    )


def _geom_host(scheduled: list):
    return SimpleNamespace(
        app=SimpleNamespace(
            tk=SimpleNamespace(
                after=lambda ms, fn: scheduled.append((ms, fn)),
                update_idletasks=lambda: None,
            )
        )
    )


def test_the_geometry_report_shows_what_was_asked_for_beside_what_was_given(caplog) -> None:
    # The whole point: a photograph shows which edge is clipped, not which term in the arithmetic
    # is wrong. reqw against w is what distinguishes "the button is too big" from "the column is
    # pinned narrower than the row needs".
    host = _geom_host([])
    widgets = {"btn_row": _geom_widget(w=150, h=60, reqw=192, reqh=66)}
    computed = {"pair_size": 94, "label_width": 80}

    with caplog.at_level("DEBUG", logger=mod.log.name):
        mod._report_freight_geometry(host, widgets, computed)

    report = "\n".join(caplog.messages)
    assert "pair_size=94" in report and "label_width=80" in report
    assert "w=150" in report and "reqw=192" in report, "allocated and requested, side by side"
    assert "parent=400x200" in report


def test_the_geometry_report_is_scheduled_rather_than_taken_immediately(monkeypatch) -> None:
    # The pair is hidden until a freight or crane engine is selected, and an unmapped widget
    # reports width 1 -- so measuring at the moment of show() would report nothing useful.
    monkeypatch.setattr(mod, "debug_diagnostics_enabled", lambda: True)
    scheduled: list = []

    mod.log_freight_geometry(_geom_host(scheduled), {}, {})

    assert [ms for ms, _ in scheduled] == [mod.FREIGHT_GEOM_DELAY_MS]
    assert callable(scheduled[0][1])


def test_no_geometry_is_measured_unless_debug_output_is_wanted(monkeypatch) -> None:
    # Two Tk round-trips per widget, every time a freight engine is selected.
    monkeypatch.setattr(mod, "debug_diagnostics_enabled", lambda: False)
    scheduled: list = []

    mod.log_freight_geometry(_geom_host(scheduled), {}, {})

    assert scheduled == []


def test_the_geometry_report_survives_a_widget_that_cannot_be_measured(caplog) -> None:
    # It runs half a second after selection, by which time the engine may have changed again.
    def boom():
        raise RuntimeError("destroyed")

    host = _geom_host([])
    widgets = {"gone": SimpleNamespace(tk=SimpleNamespace(winfo_ismapped=boom))}

    with caplog.at_level("DEBUG", logger=mod.log.name):
        mod._report_freight_geometry(host, widgets, {"pair_size": 1})


def test_the_show_site_asks_for_the_geometry_report() -> None:
    # Wiring. build() is too large to stub, and a diagnostic nobody calls looks exactly like a
    # panel with no problem -- which is how this whole sizing question stayed unmeasured.
    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "log_freight_geometry"
    ]

    assert len(calls) == 1, "called exactly once, from the show path"


class _FitButton:
    def __init__(self) -> None:
        self.images = None
        self.sizes: list[int] = []
        self.tk = SimpleNamespace(config=lambda **kw: self.sizes.append(kw.get("width")))


def _fit_state(*, cell: tuple[int, int], row_req: tuple[int, int], size: int = 98):
    """A pair whose row asks for ``row_req`` inside a cell allocated ``cell``."""
    bell, horn = _FitButton(), _FitButton()
    return {
        "size": size,
        "row": SimpleNamespace(
            tk=SimpleNamespace(winfo_reqwidth=lambda: row_req[0], winfo_reqheight=lambda: row_req[1])
        ),
        "cell": SimpleNamespace(tk=SimpleNamespace(winfo_width=lambda: cell[0], winfo_height=lambda: cell[1])),
        "buttons": ((bell, "bell.jpg"), (horn, "horn.jpg")),
    }


def _fit_host(requested: list):
    return SimpleNamespace(
        app=SimpleNamespace(tk=SimpleNamespace(update_idletasks=lambda: None, after=lambda ms, fn: fn())),
        get_image=lambda path, size=None: requested.append((path, size)) or ("normal", "inverted"),
    )


def test_the_fit_resizes_both_buttons_to_the_measured_overflow() -> None:
    # The Pi's numbers: a 224x128 row in a 218x105 cell at size 98 -> 23 off each button.
    requested: list = []
    state = _fit_state(cell=(218, 105), row_req=(224, 128), size=98)

    mod._apply_freight_fit(_fit_host(requested), state)

    assert state["size"] == 75
    assert requested == [("bell.jpg", 75), ("horn.jpg", 75)], "both halves, one image each"
    for button, _asset in state["buttons"]:
        assert button.sizes == [75]


def test_the_fit_leaves_a_pair_that_already_fits_untouched() -> None:
    # Every correction regenerates two images, and this runs on every engine selection.
    requested: list = []
    state = _fit_state(cell=(218, 105), row_req=(180, 100), size=75)

    mod._apply_freight_fit(_fit_host(requested), state)

    assert state["size"] == 75
    assert requested == []


def test_the_fit_refuses_to_measure_a_cell_that_is_not_laid_out_yet() -> None:
    """winfo_width reports 1 before Tk allocates the widget.

    Taken at face value that reads as a colossal overflow and would cut both buttons straight to
    FREIGHT_PAIR_MIN -- turning "slightly clipped" into "unusable". Leaving the provisional size
    alone is the safe failure.
    """
    requested: list = []
    state = _fit_state(cell=(1, 1), row_req=(224, 128), size=98)

    mod._apply_freight_fit(_fit_host(requested), state)

    assert state["size"] == 98
    assert requested == []


def test_the_fit_never_shrinks_below_a_usable_touch_target() -> None:
    requested: list = []
    state = _fit_state(cell=(30, 20), row_req=(400, 300), size=98)

    mod._apply_freight_fit(_fit_host(requested), state)

    assert state["size"] == mod.FREIGHT_PAIR_MIN


def test_the_fit_survives_a_pair_that_has_gone_away() -> None:
    # It is scheduled, so the engine may have changed by the time it runs.
    def boom():
        raise RuntimeError("destroyed")

    state = _fit_state(cell=(218, 105), row_req=(224, 128))
    state["cell"] = SimpleNamespace(tk=SimpleNamespace(winfo_width=boom))

    mod._apply_freight_fit(_fit_host([]), state)


def test_nothing_is_fitted_before_the_pair_has_been_built() -> None:
    # _freight_pair is only set once build() reaches the pair.
    mod.fit_freight_pair(SimpleNamespace())
