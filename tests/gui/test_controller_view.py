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


def test_the_slider_row_lands_on_the_keypads_real_fourth_row_bottom() -> None:
    # The whole point: the previous button_size * 4 estimate ran a bit short of the keypad's real
    # rows once their own padding is counted, which is what left the aux row below it squeezed
    # tighter than intended. grid_bbox reports the row's real top and height, so their sum is the
    # real bottom -- not an estimate of it.
    assert mod.slider_row_height_for_keypad_alignment(row_top=0, row_height=360) == 360
    assert mod.slider_row_height_for_keypad_alignment(row_top=4, row_height=360) == 364


def test_slider_row_alignment_never_drops_below_one_pixel() -> None:
    # A keypad reporting a nonsensical (or not-yet-laid-out) bbox must not hand back a zero or
    # negative target height.
    assert mod.slider_row_height_for_keypad_alignment(row_top=0, row_height=0) == 1
    assert mod.slider_row_height_for_keypad_alignment(row_top=-5, row_height=3) == 1


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


def test_the_keypad_alignment_helper_is_wired_up() -> None:
    # Same reasoning again: a helper that quietly stopped being called would look exactly like a
    # slider box whose bottom no longer lines up with the keypad's real 4th row.
    assert len(_calls_to("slider_row_height_for_keypad_alignment")) == 1


def _pack_calls_on(name: str) -> list[ast.Call]:
    """Every <name>.tk.pack(...) call in the module, by the receiver's own variable name.

    _calls_to only matches plain function calls (ast.Name targets); this is a method call on an
    attribute chain, so it needs its own AST walk.
    """
    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "pack"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "tk"
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == name
    ]


def _box_call_for(name: str) -> ast.Call | None:
    """The Box(...) call assigned (possibly via a chained assignment) to name."""
    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", None) == "Box"
            and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
        ):
            return node.value
    return None


def _grid_configure_calls_on(name: str) -> list[ast.Call]:
    """Every <name>.tk.grid_configure(...) call in the module, mirroring _pack_calls_on."""
    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "grid_configure"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "tk"
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == name
    ]


def test_the_rr_speed_box_has_no_align_that_a_later_show_would_reapply() -> None:
    """The bug this fixes: rr_box was built with align="top".

    apply_engine_type() calls rr_box.show()/hide() on every engine-state change, and each show()
    makes guizero grid_forget() then re-grid the cell -- reapplying a sticky derived from align
    ("N" for "top") if one is set, regardless of anything configured manually beforehand. That
    silently pinned the box, and the button inside it, to the top on the very next engine-state
    change. Leaving align unset is what stops that re-grid from ever touching sticky again.
    """
    call = _box_call_for("rr_box")

    assert call is not None, "rr_box is still built from a Box(...) call"
    assert not any(kw.arg == "align" for kw in call.keywords), "align survives every later show()"


def test_the_rr_speed_box_does_not_rely_on_a_sticky_override() -> None:
    """A grid_configure(sticky=...) call here would look like a fix but not survive one.

    Since rr_box.show() is called from apply_engine_type() on every engine-state change, and each
    show() re-grids the cell from scratch, any sticky set once at build time is gone by the next
    engine-state change (see the align test above). Centering has to come from Tk's own default
    (no sticky at all), which is the only setting stable across repeated show()/hide() cycles.
    """
    assert _grid_configure_calls_on("rr_box") == [], "a sticky override here would not survive show()"


def test_the_rr_speed_button_is_centered_in_the_free_space() -> None:
    """The bug this fixes: the button was pinned near the top of its row by a fixed pady=(9,
    0) offset, leaving the rest of the row's free space unused below it rather than around it.

    expand=True gives the pack parcel the whole row instead of just the button's own height, so
    anchor="center" then centers it within that free space -- the same technique btn_row already
    uses to center the freight-sounds pair, which this leaves untouched.
    """
    calls = _pack_calls_on("rr_btn")

    assert len(calls) == 1, "packed exactly once, at build time"
    kwargs = {kw.arg: kw.value for kw in calls[0].keywords}
    assert kwargs.get("anchor") is not None and kwargs["anchor"].value == "center"
    assert kwargs.get("expand") is not None and kwargs["expand"].value is True
    assert "pady" not in kwargs, "a fixed offset would re-pin the button off-center"


def _call_assigned_to(func_name: str, target_name: str) -> ast.Call | None:
    """The <func_name>(...) call assigned (possibly via a chained assignment) to target_name.

    Generalizes _box_call_for to any constructor, so the same source-inspection pattern can
    confirm both what a widget is (a TitleBox) and what it was built with (its title, its
    parent), without a running Tk display.
    """
    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", None) == func_name
            and any(isinstance(t, ast.Name) and t.id == target_name for t in node.targets)
        ):
            return node.value
    return None


def test_the_rr_speed_button_now_sits_inside_a_titled_speed_limit_box() -> None:
    """The RR Speeds button is now built inside its own titled box, titled "Speed Limit...", the
    same treatment already given to throttle/brake/momentum/horn and to the freight
    "Bell/Horn..." pair -- so its purpose reads on screen instead of being a bare, unlabeled
    button. Applies to both the Pi and Steam Deck layouts, since both go through this same
    build() method.
    """
    title_box_call = _call_assigned_to("TitleBox", "rr_title_box")
    assert title_box_call is not None, "rr_title_box is still built from a TitleBox(...) call"
    title_arg = title_box_call.args[1]
    assert isinstance(title_arg, ast.Constant) and title_arg.value == "Speed Limit..."

    # A titled box built next to the button, rather than around it, would look identical in a
    # diff but not on screen -- so the button's own parent has to be checked too.
    button_call = _call_assigned_to("HoldButton", "rr_btn")
    assert button_call is not None, "rr_btn is still built from a HoldButton(...) call"
    parent_arg = button_call.args[0]
    assert isinstance(parent_arg, ast.Name) and parent_arg.id == "rr_title_box"


def test_the_rr_speed_titlebox_is_also_centered_in_the_free_space() -> None:
    """Wrapping the button in a titled box adds a second widget between it and rr_box; if
    that new widget were not centered too, the button inside it would still end up pinned
    off-center despite the button's own pack call still asking to be centered.
    """
    calls = _pack_calls_on("rr_title_box")

    assert len(calls) == 1, "packed exactly once, at build time"
    kwargs = {kw.arg: kw.value for kw in calls[0].keywords}
    assert kwargs.get("anchor") is not None and kwargs["anchor"].value == "center"
    assert kwargs.get("expand") is not None and kwargs["expand"].value is True


class _FitButton:
    """A Tk button stub whose requested size follows its configuration, as the real one does.

    Without that, the backstop measures the row as it was *before* the resize and trims a pair that
    already fits.
    """

    def __init__(self, size: int) -> None:
        self.images = None
        self.applied: list[int] = []
        self.size = size
        self.tk = SimpleNamespace(
            config=self._config,
            # A Tk button requests its configured size plus its border.
            winfo_reqwidth=lambda: self.size + CHROME["border"],
            winfo_reqheight=lambda: self.size + CHROME["border"],
        )

    def _config(self, **kwargs) -> None:
        width = kwargs.get("width")
        self.applied.append(width)
        if width is not None:
            self.size = width


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
                    (horn.size + CHROME["border"] + CHROME["horn_extra"])
                    + mod.FREIGHT_PAIR_GAP
                    + max(label_floor, bell.size + CHROME["border"] + CHROME["bell_extra"])
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
    state["horn_btn"][0].size = 96

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
    state["bell_btn"][0].size = -40

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

    The Deck's scale_by is 0.9, so s_10 there renders at 9 -- no smaller than that default. The
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
    assert mod.freight_horn_after_trim(bell=4, horn=20, trim=100) == mod.FREIGHT_PAIR_MIN
    assert mod.freight_horn_after_trim(bell=60, horn=70, trim=100) == 60


# ---------------------------------------------------------------------------
# The colored border on the direction keys (_setup_controller_behaviors)
# ---------------------------------------------------------------------------

_BORDER = 3  # what the host would answer for border_size; the setup only passes it along


class _OpsButton:
    """A HoldButton double: what the behavior setup sets on one is all this has to hold."""

    def __init__(self) -> None:
        self.border_thickness = 0
        self.text_size = None
        self.on_press = "the command the layout gave it"
        self.on_repeat = None
        self.on_hold = None
        self.repeat_interval = None
        self.hold_threshold = None

    def update_command(self, command, args=None) -> None:
        self.on_press = (command, args or [])


class _OpsCells(dict):
    """host.engine_ops_cells, answering every op key the setup asks for."""

    def __missing__(self, key):
        self[key] = (key, _OpsButton())
        return self[key]


# The behavior setup is private and called only from ControllerView's own build.
# noinspection PyProtectedMember
def _behaviors(*built: tuple[str, str]) -> tuple[_OpsCells, mod.ControllerView]:
    # `built` is the keys of any cells that exist before the setup runs. Only the extra function
    # column needs them: it is built conditionally, so the setup has to find its buttons rather
    # than ask for them, and _OpsCells conjures a button for anything asked for by name.
    cells = _OpsCells()
    for key in built:
        _ = cells[key]
    host = SimpleNamespace(s_12=12, border_size=_BORDER, engine_ops_cells=cells)
    # The hold callbacks are read off the host and stored, never called here.
    for name in (
        "on_lights",
        "on_extra",
        "on_crew_dialog",
        "on_conductor_actions",
        "on_bell_horn_options",
        "on_steward_dialogs",
        "on_tower_dialog",
        "on_station_dialogs",
        "on_engine_command",
    ):
        setattr(host, name, lambda *_args: None)
    view = mod.ControllerView(host)
    view._setup_controller_behaviors()
    return cells, view


def test_the_direction_keys_are_given_a_border_to_carry_their_color() -> None:
    # Which direction is in force is shown by setting each key's background (see the pair set
    # from throttle_state in ControllerView.update) -- and a color on a button's face is not
    # something macOS paints, so the border is what shows there.
    cells, _view = _behaviors()

    for key in (("FORWARD_DIRECTION", "e"), ("REVERSE_DIRECTION", "e")):
        assert cells[key][1].border_thickness == _BORDER, key


def test_no_other_engine_op_key_wears_a_border() -> None:
    # Every other op key is a plain command whose face never changes color, and each is sized
    # to its cell: a border on one would be chrome the keypad did not budget for.
    directions = {("FORWARD_DIRECTION", "e"), ("REVERSE_DIRECTION", "e")}
    cells, _view = _behaviors()

    bordered = [key for key, (_key, btn) in cells.items() if btn.border_thickness and key not in directions]
    assert bordered == []


# ---------------------------------------------------------------------------
# The extra function column beside the sliders (EXTRA_FUNCTIONS_WIDE)
# ---------------------------------------------------------------------------

# A Steam Deck pane: 1280 less the 2px divider, halved. Its sliders column measures 137 (see
# FREIGHT_CELL_BORDER), and its keypad is four cells of a button plus its padding.
_DECK = dict(row_width=639, keypad_width=336, sliders_width=137, cell_width=84)
# The portrait panel, where the keypad and the 220px sliders column already use the whole row.
_PORTRAIT = dict(row_width=480, keypad_width=260, sliders_width=220, cell_width=65)


def test_a_row_with_a_spare_button_of_width_gets_the_extra_column() -> None:
    # The point of measuring rather than gating on the device: what earns the column is room,
    # so the next handheld wide enough gets it without this code learning what it is.
    assert mod.extra_column_fits(**_DECK) is True


def test_a_row_already_spoken_for_does_not() -> None:
    # Portrait: the keypad and the sliders leave nothing, and the column must not be squeezed in
    # beside them -- the layout there stays exactly what it has always been.
    assert mod.extra_column_fits(**_PORTRAIT) is False


def test_the_column_has_to_fit_whole() -> None:
    # A partial column is a clipped button, so the test is for a full cell, not for whatever is
    # left over. Exactly enough is enough; one pixel short is not.
    exact = mod.EXTRA_COLUMN_SLACK + 336 + 137 + 84

    assert mod.extra_column_fits(exact, 336, 137, 84) is True
    assert mod.extra_column_fits(exact - 1, 336, 137, 84) is False


@pytest.mark.parametrize("unmeasured", ["row_width", "keypad_width", "sliders_width", "cell_width"])
@pytest.mark.parametrize("reading", [0, 1, -5])
def test_a_measurement_that_has_not_settled_yet_gets_no_column(unmeasured: str, reading: int) -> None:
    # A widget Tk has not laid out reports 1 -- the trap freight_pair_size's docstring describes.
    # Believing it here would add a column against a row that was never really measured, or (for
    # the keypad and the sliders) against a row that looks empty.
    assert mod.extra_column_fits(**{**_DECK, unmeasured: reading}) is False


def test_the_fit_test_is_wired_up() -> None:
    # Same reasoning as the freight helpers above: build() is far too large to stub, so a gate
    # that quietly stopped being called would look exactly like a column that appears on a panel
    # with no room for it -- or never appears at all.
    calls = _calls_to("extra_column_fits")

    assert len(calls) == 1, "asked once, during build"
    assert len(calls[0].args) == 4, "the row, the keypad, the sliders, and one cell"


def test_the_extra_column_is_created_before_the_sliders() -> None:
    """Creation order is the whole of its position, and nothing on screen explains why.

    Both boxes are packed to the right of the controls row, and two right-aligned children stack
    right-to-left: the one created *first* is the one that ends up outboard. Creating this box
    after the sliders -- the obvious reading of "add it to the right of them" -- puts the column
    between the keypad and the sliders instead. A "pack before" fixes that for exactly as long as
    it takes for one of the row's children to be shown or hidden, because guizero's
    display_widgets re-packs them all in creation order with freshly built options.
    """
    column = _box_call_for("extra_functions")
    sliders = _box_call_for("sliders")

    assert column is not None, "the column's box is still built from a Box(...) call"
    assert sliders is not None
    assert column.lineno < sliders.lineno, "created after the sliders, it would land inboard of them"
    align = {kw.arg: kw.value for kw in column.keywords}.get("align")
    assert align is not None and align.value == "right", "outboard, on the slider side of the row"


def _tk_calls_on(name: str, method: str) -> list[ast.Call]:
    """Every <name>.tk.<method>(...) call in the module, generalizing _pack_calls_on."""
    tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == method
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "tk"
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == name
    ]


def test_the_extra_column_holds_its_place_when_its_keys_hide() -> None:
    """Every key in the column is an engine key, so all five hide together.

    A keypad column never empties -- each cell position stacks one variant per engine type and
    something is always showing -- but this one does, on any freight or passenger car. Left to
    track its content the box would collapse to nothing there and slide the sliders across the
    row, then back again on the next engine. The sliders column is pinned for the same reason.
    """
    calls = _tk_calls_on("extra_functions", "grid_propagate")

    assert len(calls) == 1, "pinned exactly once, at build time"
    assert calls[0].args and calls[0].args[0].value is False
    assert _tk_calls_on("extra_functions", "config"), "propagation off with no size is a 1px column"


def test_a_row_with_no_room_loses_the_box_without_repacking_its_neighbors() -> None:
    """The portrait panel has never had this column and must not change because of it.

    guizero's hide() runs display_widgets, which re-packs every child of the row from scratch
    with freshly built options -- taking the fill the sliders were packed with off a layout that
    has nothing to do with this change. pack_forget drops the one box and touches nothing else.
    """
    assert len(_tk_calls_on("extra_functions", "pack_forget")) == 1

    hides = [
        node
        for node in ast.walk(ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"hide", "show"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "extra_functions"
    ]
    assert hides == [], "guizero visibility here re-packs the keypad and the sliders with it"


def test_every_button_in_the_extra_column_is_an_alias_of_a_real_command() -> None:
    # The column repeats buttons that are already on screen, so each cell carries a name of its
    # own -- a cell is registered under (command, engine-type tag) and two cells cannot share one
    # key. A name with no entry in the table is a button that would send nothing at all.
    from src.pytrain.utils.path_utils import find_file

    for row in mod.EXTRA_FUNCTIONS_WIDE:
        for cell in row:
            for command, image, _label, _title, scope in cell:
                assert command in mod.COMMAND_ALIASES, command
                real = mod.COMMAND_ALIASES[command]
                assert real not in mod.COMMAND_ALIASES, f"{command} resolves to another alias"
                assert scope == "e", "the column follows the same show/hide rules as the ops keys"
                assert find_file(image), image


# noinspection PyProtectedMember
def test_the_extra_column_inherits_the_holds_of_the_buttons_it_copies() -> None:
    # A duplicate that ignores a press-and-hold is a duplicate that behaves differently from the
    # button it copies: Start Up and Shut Down would lose their delayed variants.
    wide = [(alias, "e") for alias in mod.COMMAND_ALIASES]
    cells, _view = _behaviors(*wide)

    for alias, real in mod.COMMAND_ALIASES.items():
        assert cells[(alias, "e")][1].on_hold == cells[(real, "e")][1].on_hold, alias

    # Two of them have one to inherit; the rest -- Labor Effect, Speed Roll -- have none, and
    # equal-to-nothing on every button is how a copy that never happened would also read.
    held = sorted(alias for alias in mod.COMMAND_ALIASES if cells[(alias, "e")][1].on_hold is not None)
    assert held == ["SHUTDOWN_IMMEDIATE_WIDE", "START_UP_IMMEDIATE_WIDE"]


# noinspection PyProtectedMember
def test_a_hold_is_only_copied_onto_a_button_that_was_built() -> None:
    # The column is conditional, so on a narrow panel none of its buttons exist. Asking for one
    # by name would conjure it (KeyError against the real engine_ops_cells) and configure a hold
    # on a button nobody can press.
    cells, _view = _behaviors()

    assert [key for key in cells if key[0].endswith("_WIDE")] == []


# noinspection PyProtectedMember
def test_the_info_row_can_be_asked_for_by_name_so_its_height_can_be_reserved() -> None:
    # The row (Mom, Brake, Smoke, Speed Lim, Effort, RPM) is built while the controller box is
    # hidden, so it is not packed when EngineGui sizes the engine image and contributes nothing
    # to the controller box's requested height -- which is why the row itself has to be
    # reachable to be measured. See EngineGui.controller_info_reserve.
    view = mod.ControllerView(SimpleNamespace())

    assert view.controller_info_box is None, "nothing to measure before the controller is built"

    row = _DummyWidget()
    view._controller_info_box = row

    assert view.controller_info_box is row
