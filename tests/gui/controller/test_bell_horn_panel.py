from __future__ import annotations

import unicodedata as ud
from types import SimpleNamespace

import pytest

import src.pytrain.gui.controller.bell_horn_panel as mod
from src.pytrain.gui.controller.engine_gui_conf import (
    BELL_KEY,
    CYCLE_KEY,
    FONT_SIZE_EXCEPTIONS,
    PAUSE_KEY,
    PLAY_KEY,
    PLAY_PAUSE_KEY,
)

# The codepoint that renders as a blue-and-white emoji wherever a color emoji font is installed.
EMOJI_PAUSE = "⏸"


class _Box:
    def __init__(self, _parent=None, **kwargs) -> None:
        self.kwargs = kwargs
        self.tk = SimpleNamespace(
            grid_rowconfigure=lambda *_a, **_kw: None,
            grid_columnconfigure=lambda *_a, **_kw: None,
        )


class _Text:
    def __init__(self, _parent=None, **kwargs) -> None:
        self.kwargs = kwargs
        self.text_size = None
        self.text_bold = None


# Whatever the panel asks a button for: its label and the font size it named (None = take the
# shared default that _build_keypad_button picks from FONT_SIZE_EXCEPTIONS).
S_24 = 24


def _keys(compact: bool, monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int | None]]:
    labels: list[tuple[str, int | None]] = []
    monkeypatch.setattr(mod, "Box", _Box)
    monkeypatch.setattr(mod, "Text", _Text)
    monkeypatch.setattr(mod, "find_file", lambda name: name)
    host = SimpleNamespace(
        button_size=90,
        s_20=20,
        s_24=S_24,
        compact=compact,
        cache=lambda *_args: None,
        on_engine_command=lambda *_args: None,
    )
    host.make_keypad_button = lambda *args, **kwargs: (
        labels.append((args[1], kwargs.get("size"))),
        (object(), object()),
    )[1]

    panel = mod.BellHornPanel.__new__(mod.BellHornPanel)
    panel._gui = host
    panel.build(_Box())
    return labels


def _build(compact: bool, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Build the panel and return the labels it asked for, in order."""
    return [label for label, _size in _keys(compact, monkeypatch)]


def test_neither_device_uses_the_emoji_pause_codepoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """U+23F8's default Unicode presentation is emoji, and SteamOS ships Noto Color Emoji.

    Its glyph is a blue rounded square with white bars, and being a bitmap it ignores the button's
    foreground color -- so half of "play slash pause" came out wrong on the Deck while the same
    string rendered correctly on the Pi. A U+FE0E text-presentation selector does not help: it was
    probed on the Deck and the emoji glyph still won, so the codepoint has to be avoided outright.

    One glyph for both devices. It was briefly Deck-only, then adopted for portrait too because it
    simply looks better -- so this asserts the codepoint is gone from *either* mode, not just one.
    """
    for compact in (True, False):
        labels = _build(compact=compact, monkeypatch=monkeypatch)

        assert PLAY_PAUSE_KEY in labels, f"compact={compact}"
        assert EMOJI_PAUSE not in "".join(labels), f"compact={compact}: an emoji font would claim it"


def test_both_rows_keep_their_other_keys_in_either_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    # The swap must touch the Bell play/pause button and nothing else: the Horn row's plain Play
    # triangle is unaffected, since U+25B6 defaults to text presentation.
    for compact in (True, False):
        labels = _build(compact=compact, monkeypatch=monkeypatch)

        assert labels.count(CYCLE_KEY) == 2, f"compact={compact}: one cycle key per row"
        assert PLAY_KEY in labels
        assert labels.count("On") == 1 and labels.count("Off") == 1


def test_the_freight_bell_glyph_avoids_the_emoji_codepoint() -> None:
    # U+1F514 BELL suffers the exact fate documented above for U+23F8: its default presentation is
    # emoji, the Deck's color font claims it, and a U+FE0E selector does not win it back -- so the
    # freight pair's bell must be U+1F56D RINGING BELL, which has no emoji form at all.
    assert len(BELL_KEY) == 1, "a variation selector would be dead weight; the codepoint must stand alone"
    assert ud.name(BELL_KEY) == "RINGING BELL"
    assert "\U0001f514" not in BELL_KEY, "an emoji font would claim it"


def test_the_glyph_is_monochrome_by_construction() -> None:
    # Neither codepoint has an emoji form, so no color emoji font can claim either, and both sit in
    # Geometric Shapes so one font serves the whole label rather than two.
    triangle, bars = PLAY_PAUSE_KEY.split("/")

    assert ud.name(triangle) == "BLACK RIGHT-POINTING TRIANGLE"
    assert set(bars) == {"▮"}
    assert ud.name(bars[0]) == "BLACK VERTICAL RECTANGLE"


def test_the_glyph_is_wide_enough_to_justify_naming_its_size() -> None:
    # Why this one key names a size at all: it is four characters where every other key on either
    # row is one. A keypad cell is a fixed square with pack_propagate(False), so an over-wide label
    # is clipped rather than given room. Shrink the label back to one or two and the override is
    # no longer earned.
    assert len(PLAY_PAUSE_KEY) == 4


def test_every_glyph_label_still_gets_the_large_font() -> None:
    # FONT_SIZE_EXCEPTIONS is matched by value (guizero_base: `label in FONT_SIZE_EXCEPTIONS`), so
    # a new glyph string that is not in the set would silently render at body-text size. The
    # Bell/Horn button overrides it with an explicit size, but any other call site would not.
    for key in (CYCLE_KEY, PLAY_KEY, PLAY_PAUSE_KEY, PAUSE_KEY):
        assert key in FONT_SIZE_EXCEPTIONS, key


def test_the_play_pause_key_names_a_smaller_size_on_both_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    # Four characters against one for every other key on the row. At the s_30 that
    # _build_keypad_button picks for anything in FONT_SIZE_EXCEPTIONS it filled its cell edge to
    # edge, and a cell is a fixed square with pack_propagate off, so there was no margin left.
    # Keyed to the label's width, not to the device, because that is the actual reason.
    for compact in (True, False):
        sizes = dict(_keys(compact, monkeypatch))

        assert sizes[PLAY_PAUSE_KEY] == S_24, f"compact={compact}"


def test_no_other_key_gets_its_size_named_in_either_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    # The whole point of naming one: every other key still resolves its own size from the shared
    # rule, so this stays a single exception rather than the start of a table.
    for compact in (True, False):
        named = [label for label, size in _keys(compact, monkeypatch) if size is not None]

        assert named == [PLAY_PAUSE_KEY], f"compact={compact}: {named}"


def test_the_glyph_is_the_same_on_both_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    # There is no mode split left to drift. Reintroducing one would show up here.
    assert _build(compact=True, monkeypatch=monkeypatch) == _build(compact=False, monkeypatch=monkeypatch)
