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


@pytest.mark.parametrize("button_size", [90, 110], ids=["pi-like", "deck-like"])
@pytest.mark.parametrize("title_overhead", [0, 1, 22, 40])
def test_the_slider_box_lands_on_exactly_four_button_heights(button_size: int, title_overhead: int) -> None:
    # The whole point: the TitleBox (title + numeric readout) plus the Slider, stacked in the same
    # box, must total four button-heights -- not the Slider alone, which is what left the box
    # taller than intended once the title's own height was added on top. Pure in button_size, so
    # the same formula covers the Pi and the Deck without any device-specific branching.
    box_height = button_size * 4

    slider_length = mod.slider_length_for_box_height(box_height, title_overhead)

    assert title_overhead + slider_length == box_height


def test_slider_length_never_drops_below_one_pixel() -> None:
    # An overhead larger than the box budget must not go negative; a slider a few pixels tall is
    # still usable, a slider with negative length is not a valid Tk request.
    assert mod.slider_length_for_box_height(100, 250) == 1


def test_slider_length_ignores_a_negative_overhead_rather_than_trusting_it() -> None:
    # winfo_reqheight can read oddly before layout settles; subtracting a negative would *add*
    # room instead of leaving the box alone.
    assert mod.slider_length_for_box_height(360, -40) == 360


def test_aux_row_gets_whatever_is_left_below_the_fixed_slider_row() -> None:
    # No longer a percentage of the same total the slider row is also a share of -- just the
    # remainder, now that the slider row is pinned to an exact number of button-heights.
    assert mod.aux_row_height_after_slider_row(target_sliders_height=500, slider_row_height=360) == 140


def test_aux_row_never_drops_below_one_pixel() -> None:
    # A keypad no taller than the fixed slider-row budget must not produce a zero or negative aux
    # row -- the RR Speed / Freight Sounds controls still need a cell to live in.
    assert mod.aux_row_height_after_slider_row(target_sliders_height=300, slider_row_height=360) == 1
    assert mod.aux_row_height_after_slider_row(target_sliders_height=360, slider_row_height=360) == 1


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


def test_the_slider_box_sizing_helpers_are_both_wired_up() -> None:
    # Same reasoning as above: build() is far too large to stub, so a helper that quietly stopped
    # being called would look exactly like a slider box that is no longer four button-heights tall.
    assert len(_calls_to("slider_length_for_box_height")) == 1
    assert len(_calls_to("aux_row_height_after_slider_row")) == 1


class _FitButton:
    """A Tk button stub whose requested size follows its configuration, as the real one does.

    Without that, the backstop measures the row as it was *before* the resize and trims a pair that
    already fits.
    """

    def __init__(self, size: int) -> None:
        self.images = None
        self.applied: list[int] = []
        self._size = size
        self.tk = SimpleNamespace(
            config=self._config,
            # A Tk button requests its configured size plus its border.
            winfo_reqwidth=lambda: self._size + CHROME["border"],
            winfo_reqheight=lambda: self._size + CHROME["border"],
        )

    def _config(self, **kwargs) -> None:
        width = kwargs.get("width")
        self.applied.append(width)
        if width is not None:
            self._size = width


def _boxed(button: _FitButton, extra_w: int, extra_h: int):
    """A container whose requested size is its button plus the chrome around it."""
    return SimpleNamespace(
        tk=SimpleNamespace(
            winfo_reqwidth=lambda: button.tk.winfo_reqwidth() + extra_w,
            winfo_reqheight=lambda: button.tk.winfo_reqheight() + extra_h,
        )
    )


def _fit_state(*, row_height: int, parent_width: int, size: int = 99, label_floor: int = 0):
    bell, horn = _FitButton(size), _FitButton(size)
    return {
        "bell": size,
        "horn": size,
        # The row's requested width, as Tk reports it: the horn's cell tracks its button, but the
        # bell's box is floored by its own label -- which is the whole reason a backstop exists.
        "row": SimpleNamespace(
            tk=SimpleNamespace(
                winfo_reqwidth=lambda: (
                    (horn._size + CHROME["border"] + CHROME["horn_extra"])
                    + mod.FREIGHT_PAIR_GAP
                    + max(label_floor, bell._size + CHROME["border"] + CHROME["bell_extra"])
                ),
                winfo_reqheight=lambda: 0,
            )
        ),
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


def test_the_backstop_takes_a_residual_overflow_off_the_horn() -> None:
    """The Deck's remaining bug: the bell box's extra width is a *floor*, not additive chrome.

    A LabelFrame cannot be narrower than its own title, so once the bell button shrinks past the
    label the box stops shrinking and freight_pair_sizes under-counts the row. Measured on the Deck
    as bell_box reqw=78 against a 49px button -- 29px that the additive model booked as 6.
    """
    requested: list = []
    # 78px label floor in a 135px column: exactly the Deck's numbers.
    state = _fit_state(row_height=71, parent_width=137, label_floor=78)

    mod._apply_freight_fit(_fit_host(requested), state)

    row = (state["horn"] + 8 + 2) + mod.FREIGHT_PAIR_GAP + max(78, state["bell"] + 8 + 6)
    assert row <= 137 - mod.FREIGHT_CELL_BORDER, f"row still {row}"
    assert state["horn"] < 62, "the horn gave way, since shrinking a floored bell buys nothing"


def test_the_backstop_leaves_the_bell_alone() -> None:
    # Trimming a bell whose box is pinned by its label reduces the row by nothing, so it would be
    # pure loss -- a smaller icon for no gain in fit.
    state = _fit_state(row_height=71, parent_width=137, label_floor=78)
    unfloored = _fit_state(row_height=71, parent_width=137, label_floor=0)

    mod._apply_freight_fit(_fit_host([]), state)
    mod._apply_freight_fit(_fit_host([]), unfloored)

    assert state["bell"] == unfloored["bell"], "the floor changed the horn, not the bell"


def test_no_backstop_when_the_row_already_fits() -> None:
    # It costs two images; the settled case has to be free.
    requested: list = []
    state = _fit_state(row_height=105, parent_width=220, label_floor=0)

    mod._apply_freight_fit(_fit_host(requested), state)

    assert (state["bell"], state["horn"]) == (75, 96)
    assert requested == [("bell.jpg", 75), ("horn.jpg", 96)], "sized once, not trimmed again"


def test_the_trim_is_the_measured_shortfall() -> None:
    assert mod.freight_horn_trim(154, 135) == 19
    assert mod.freight_horn_trim(135, 135) == 0
    assert mod.freight_horn_trim(100, 135) == 0, "already fitting, nothing to trim"


def _deck(**overrides):
    """A host with the Deck's real font ladder: scale_by is 0.9, so s_10 lands on 9."""
    ladder = {f"s_{n}": round(n * 0.9) for n in (18, 14, 12, 10, 8, 6)}
    return SimpleNamespace(compact=True, **{**ladder, **overrides})


def test_only_a_compact_pane_shrinks_the_pairs_title() -> None:
    # The Deck's title floors its LabelFrame at 78px against a 49px button -- the box stops
    # shrinking with the button and the row overflows. Portrait renders correctly and must not move.
    portrait = SimpleNamespace(compact=False, s_8=12)

    assert mod.freight_title_size(_deck()) == _deck().s_8
    assert mod.freight_title_size(portrait) is None, "None leaves the default font in place"
    assert mod.freight_title_size(SimpleNamespace(s_8=12)) is None, "a host with no flag is portrait"


def test_the_compact_title_is_smaller_than_the_default_it_replaces() -> None:
    """Nothing sets a global text size, so an unstyled TitleBox uses Tk's ~9-10pt default.

    The Deck's scale_by is 0.9, so ``s_10`` there renders at 9 -- no smaller than that default. The
    first attempt asked for exactly that and changed the label's width by nothing, which is why the
    backstop still had to gut the horn. The size chosen has to be visibly below the default, not
    merely below the *portrait* default.
    """
    tk_default_ish = 9

    assert mod.freight_title_size(_deck()) < tk_default_ish, "s_10 would have tied it at 9"


def test_the_horn_is_given_a_visible_relief() -> None:
    # flat or sunken would leave it looking borderless, which is the reported symptom.
    assert mod.FREIGHT_HORN_RELIEF in {"ridge", "raised", "groove", "solid"}


def test_the_horn_config_and_the_title_size_are_both_wired_up() -> None:
    """Wiring for the two cosmetic fixes, which nothing else covers.

    Both live inside build(), which is too large to stub, and both are invisible to every geometry
    test -- so all three of these changes survived a mutation pass before this existed.
    """
    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))

    assert len(_calls_to("freight_title_size")) == 1, "the title size is asked for exactly once"
    # Inlining max(MIN, horn - trim) at the call site is the same code minus the bell floor, so it
    # reads as harmless and silently allows the lopsided pair back.
    assert len(_calls_to("freight_horn_after_trim")) == 1, "the trim goes through the balance guard"

    relief_uses = [
        node for node in ast.walk(tree) if isinstance(node, ast.Attribute) and node.attr == "FREIGHT_HORN_RELIEF"
    ] + [node for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id == "FREIGHT_HORN_RELIEF"]
    assert len(relief_uses) >= 2, "declared and applied; only declared means the horn has no edge"


def test_the_trim_never_leaves_the_horn_smaller_than_the_bell() -> None:
    """A backstop against the trim overrunning, not the cause of the reported symptom.

    The horn has strictly more room than the bell -- no label above it -- so a horn that ends up
    smaller means the trim overran rather than that the horn deserves less. A few pixels of clipped
    title edge is a better trade than a visibly lopsided pair.

    Note the Deck's measured case does *not* reach this floor: a 19px trim takes 62 to 43, still
    above the 41px bell. So this guard was never what made the horn look small there -- the label
    floor forcing the trim in the first place was, and that is what the smaller title font fixes.
    """
    assert mod.freight_horn_after_trim(bell=41, horn=62, trim=19) == 43, "the Deck's case, unclamped"
    assert mod.freight_horn_after_trim(bell=41, horn=62, trim=30) == 41, "a deeper trim is clamped"
    assert mod.freight_horn_after_trim(bell=41, horn=62, trim=5) == 57, "a trim that fits is applied"
    assert mod.freight_horn_after_trim(bell=41, horn=62, trim=0) == 62


def test_the_trim_still_respects_the_touch_target_floor() -> None:
    # Both floors apply; whichever is higher wins.
    assert mod.freight_horn_after_trim(bell=4, horn=20, trim=100) == mod.FREIGHT_PAIR_MIN
    assert mod.freight_horn_after_trim(bell=60, horn=70, trim=100) == 60
