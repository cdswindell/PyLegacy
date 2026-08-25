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


# Measured identically on both devices, from the freightgeom logs.
CHROME = {"border": 8, "title": 22, "horn_pad": 1, "bell_extra": 6, "horn_extra": 2}


def _row_width(bell: int, horn: int, chrome: dict | None = None) -> int:
    chrome = chrome or CHROME
    return (
        (horn + chrome["border"] + chrome["horn_extra"])
        + mod.FREIGHT_PAIR_GAP
        + (bell + chrome["border"] + chrome["bell_extra"])
    )


def test_the_horn_is_bigger_than_the_bell_because_it_has_no_label_above_it() -> None:
    """The bug this fixes: both buttons were sized to the bell's budget.

    guizero_base reduces a titled button via titled_button_size precisely so its *cell* matches an
    untitled one. Applying that reduction to an untitled button just leaves the label's height
    idle -- measured on the Pi as bell_box using all 105px of the row while horn_cell used 84.
    """
    bell, horn = mod.freight_pair_sizes(105, 218, CHROME)

    assert horn > bell
    assert horn - bell == CHROME["title"] - CHROME["horn_pad"], "exactly the label's height, reclaimed"


def test_each_button_fills_the_height_of_its_own_half_of_the_row() -> None:
    row = 105
    bell, horn = mod.freight_pair_sizes(row, 400, CHROME)

    assert CHROME["title"] + bell + CHROME["border"] == row, "bell box fills the row"
    assert CHROME["horn_pad"] + horn + CHROME["border"] == row, "horn cell fills the row"


def test_a_shared_width_overflow_comes_off_both_buttons() -> None:
    # The row is centered, so it is clipped at both ends -- neither half can be spared.
    roomy_bell, roomy_horn = mod.freight_pair_sizes(105, 400, CHROME)
    bell, horn = mod.freight_pair_sizes(105, 120, CHROME)

    assert bell < roomy_bell and horn < roomy_horn
    assert _row_width(bell, horn) <= 120


def test_the_sizes_never_drop_below_a_usable_touch_target() -> None:
    bell, horn = mod.freight_pair_sizes(20, 20, CHROME)

    assert (bell, horn) == (mod.FREIGHT_PAIR_MIN, mod.FREIGHT_PAIR_MIN)


def test_negative_insets_are_ignored_rather_than_trusted() -> None:
    # winfo_* can report oddly before layout settles; subtracting a negative would *add* room.
    odd = dict(CHROME, title=-40, horn_pad=-40, border=-8, bell_extra=-6, horn_extra=-2)

    bell, horn = mod.freight_pair_sizes(105, 400, odd)

    assert bell <= 105 and horn <= 105


@pytest.mark.parametrize(
    "name,row_height,parent_width,expected",
    [("pi", 105, 220, (75, 96)), ("deck", 71, 137, (41, 62))],
)
def test_the_model_reproduces_both_devices(name: str, row_height: int, parent_width: int, expected: tuple) -> None:
    """Pinned to the freightgeom logs from the real devices.

    Every inset above was read off those logs and is identical on both, which is what makes a
    measured correction trustworthy rather than another guess. If a layout change moves these, the
    numbers here should be re-derived from a fresh log rather than adjusted to make this pass.
    """
    column_width = parent_width - mod.FREIGHT_CELL_BORDER

    sizes = mod.freight_pair_sizes(row_height, column_width, CHROME)

    assert sizes == expected, name
    assert _row_width(*sizes) <= column_width, f"{name}: row still overflows"


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
    def __init__(self, size: int) -> None:
        self.images = None
        self.applied: list[int] = []
        self._size = size
        self.tk = SimpleNamespace(
            config=lambda **kw: self.applied.append(kw.get("width")),
            # A Tk button requests its configured size plus its border.
            winfo_reqwidth=lambda: self._size + CHROME["border"],
            winfo_reqheight=lambda: self._size + CHROME["border"],
        )


def _boxed(button: _FitButton, extra_w: int, extra_h: int):
    """A container whose requested size is its button plus the chrome around it."""
    return SimpleNamespace(
        tk=SimpleNamespace(
            winfo_reqwidth=lambda: button.tk.winfo_reqwidth() + extra_w,
            winfo_reqheight=lambda: button.tk.winfo_reqheight() + extra_h,
        )
    )


def _fit_state(*, row_height: int, parent_width: int, size: int = 99):
    bell, horn = _FitButton(size), _FitButton(size)
    return {
        "bell": size,
        "horn": size,
        "row": SimpleNamespace(tk=SimpleNamespace(winfo_reqwidth=lambda: 0, winfo_reqheight=lambda: 0)),
        "cell": SimpleNamespace(
            tk=SimpleNamespace(
                winfo_height=lambda: row_height,
                master=SimpleNamespace(winfo_width=lambda: parent_width),
            )
        ),
        "bell_box": _boxed(bell, CHROME["bell_extra"], CHROME["title"]),
        "horn_cell": _boxed(horn, CHROME["horn_extra"], CHROME["horn_pad"]),
        "bell_btn": (bell, "bell.jpg"),
        "horn_btn": (horn, "horn.jpg"),
    }


def _fit_host(requested: list):
    return SimpleNamespace(
        app=SimpleNamespace(tk=SimpleNamespace(update_idletasks=lambda: None, after=lambda ms, fn: fn())),
        get_image=lambda path, size=None: requested.append((path, size)) or ("normal", "inverted"),
    )


def test_the_fit_gives_the_horn_the_labels_height_and_the_bell_its_own() -> None:
    # End to end against the Pi's geometry: a 105px row in a 220px column.
    requested: list = []
    state = _fit_state(row_height=105, parent_width=220)

    mod._apply_freight_fit(_fit_host(requested), state)

    assert (state["bell"], state["horn"]) == (75, 96)
    assert requested == [("bell.jpg", 75), ("horn.jpg", 96)], "one image each, at its own size"


def test_the_fit_measures_the_column_not_the_cell() -> None:
    """The cell's width tracks its content, so reading it would freeze the horn at its current size.

    Once the buttons shrink, the cell shrinks with them -- the Pi log after the first fix showed
    pair_cell w=178 where the column still allowed 218. Measuring the cell would make that 178 the
    ceiling and the horn could never reclaim the label's height.
    """
    state = _fit_state(row_height=105, parent_width=220)
    # A cell already narrowed to its content, as Tk actually reports it.
    state["cell"].tk.winfo_width = lambda: 178

    mod._apply_freight_fit(_fit_host([]), state)

    assert state["horn"] == 96, "grew past the cell's current width"


def test_the_fit_leaves_a_pair_that_already_fits_untouched() -> None:
    requested: list = []
    state = _fit_state(row_height=105, parent_width=220, size=75)
    state["horn"] = 96
    state["horn_btn"][0]._size = 96

    mod._apply_freight_fit(_fit_host(requested), state)

    assert (state["bell"], state["horn"]) == (75, 96)
    assert requested == [], "every correction costs two images; the settled case must be free"


def test_the_fit_refuses_to_measure_a_cell_that_is_not_laid_out_yet() -> None:
    # winfo_* reports 1 before Tk allocates a widget; taken at face value that cuts to the minimum.
    requested: list = []
    state = _fit_state(row_height=1, parent_width=1)

    mod._apply_freight_fit(_fit_host(requested), state)

    assert (state["bell"], state["horn"]) == (99, 99)
    assert requested == []


def test_the_fit_never_shrinks_below_a_usable_touch_target() -> None:
    state = _fit_state(row_height=30, parent_width=30)

    mod._apply_freight_fit(_fit_host([]), state)

    assert state["bell"] == mod.FREIGHT_PAIR_MIN
    assert state["horn"] == mod.FREIGHT_PAIR_MIN


def test_the_fit_ignores_chrome_that_measures_impossibly() -> None:
    # A button smaller than the size it was given means nothing has been laid out coherently.
    state = _fit_state(row_height=105, parent_width=220)
    state["bell_btn"][0]._size = -40

    mod._apply_freight_fit(_fit_host([]), state)

    assert state["bell"] == 99, "left alone rather than sized from nonsense"


def test_the_fit_survives_a_pair_that_has_gone_away() -> None:
    def boom():
        raise RuntimeError("destroyed")

    state = _fit_state(row_height=105, parent_width=220)
    state["cell"] = SimpleNamespace(tk=SimpleNamespace(winfo_height=boom))

    mod._apply_freight_fit(_fit_host([]), state)


def test_nothing_is_fitted_before_the_pair_has_been_built() -> None:
    # _freight_pair is only set once build() reaches the pair.
    mod.fit_freight_pair(SimpleNamespace())
